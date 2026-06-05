#!/usr/bin/env python3
from __future__ import annotations

import argparse
import heapq
import html
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from wechatpub_api import (
    WechatPubError,
    now_iso,
    read_clipboard,
    register_history_source,
)


DEFAULT_SCAN_ROOTS = [
    Path.home() / "Library/Containers/com.tencent.xinWeChat/Data",
    Path.home() / "Library/Containers/5A4RE8SF68.com.tencent.xinWeChat.IPCHelper/Data",
    Path.home() / "Library/Group Containers/5A4RE8SF68.com.tencent.xinWeChat",
    Path.home() / "Library/Caches/com.tencent.xinWeChat",
    Path.home() / "Library/Caches/5A4RE8SF68.com.tencent.xinWeChat",
]
MAX_FILE_BYTES = 25 * 1024 * 1024
URL_PATTERN = re.compile(r"https?://mp\.weixin\.qq\.com/mp/profile_ext[^\s\"'<>\\\x00]+")
ESCAPED_URL_PATTERN = re.compile(r"https?:\\?/\\?/mp\.weixin\.qq\.com\\?/mp\\?/profile_ext[^\s\"'<>\\\x00]+")
ARTICLE_URL_PATTERN = re.compile(r"https://mp\.weixin\.qq\.com/s\?[A-Za-z0-9_.~%&=+\-/:;?,#()]*")
SESSION_COOKIE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_\-])"
    r"(appmsg_token|wxuin|devicetype|version|lang|pass_ticket|wap_sid2|wxtokenkey|rewardsn)"
    r"=([A-Za-z0-9%_+\-./=~]+)"
)
SESSION_COOKIE_KEYS = (
    "appmsg_token",
    "wxtokenkey",
    "wxuin",
    "devicetype",
    "version",
    "lang",
    "pass_ticket",
    "wap_sid2",
    "rewardsn",
)
MACOS_AUTOMATION_PERMISSION_MESSAGE = (
    "macOS 没有允许当前进程控制微信，自动续期无法点击公众号文章。"
    "请到「系统设置 > 隐私与安全性 > 辅助功能」给 Codex/Terminal/Python/osascript 开权限，"
    "或先在电脑微信手动打开该公众号任意一篇文章后重试。"
)
AUTOMATION_DENIED_MARKERS = (
    "不允许发送按键",
    "not allowed to send keystrokes",
    "not authorized to send apple events",
    "not authorized for assistive access",
    "is not allowed assistive access",
    "not allowed to control",
    "不被允许控制",
)


def redact_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    redacted_pairs: list[tuple[str, str]] = []
    for key, values in query.items():
        value = values[-1] if values else ""
        if key.lower() in {"key", "pass_ticket", "appmsg_token", "uin", "wxtoken"}:
            value = "***"
        redacted_pairs.append((key, value))
    redacted_query = "&".join(f"{key}={value}" for key, value in redacted_pairs)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", redacted_query, ""))


def is_macos_automation_denied(stderr: str) -> bool:
    value = (stderr or "").lower()
    return any(marker in value for marker in AUTOMATION_DENIED_MARKERS)


def osascript_payload(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    payload: dict[str, Any] = {
        "ok": result.returncode == 0,
        "stdout": stdout,
        "stderr": stderr,
    }
    if is_macos_automation_denied(stderr):
        payload["permission_denied"] = True
        payload["message"] = MACOS_AUTOMATION_PERMISSION_MESSAGE
    elif result.returncode != 0 and stderr:
        payload["message"] = stderr
    return payload


def denied_automation_action(*actions: dict[str, Any] | None) -> dict[str, Any] | None:
    for action in actions:
        if action and action.get("permission_denied"):
            return action
    return None


def failed_automation_action(*actions: dict[str, Any] | None) -> dict[str, Any] | None:
    for action in actions:
        if action and action.get("ok") is False:
            return action
    return None


def normalize_url(raw: str) -> str:
    value = html.unescape(raw.strip())
    value = value.replace("\\/", "/").replace("\\u0026", "&").replace("\\x26", "&")
    value = value.rstrip(").,;]}\"'")
    parsed = urlparse(value)
    if parsed.netloc != "mp.weixin.qq.com" or parsed.path != "/mp/profile_ext":
        raise WechatPubError("not a mp profile_ext URL")
    query = parse_qs(parsed.query, keep_blank_values=True)
    biz = (query.get("__biz") or [""])[-1].strip()
    if not biz:
        raise WechatPubError("profile_ext URL is missing __biz")
    return value


def extract_profile_ext_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    expanded = html.unescape(text).replace("\\/", "/").replace("\\u0026", "&").replace("\\x26", "&")
    for pattern in (URL_PATTERN, ESCAPED_URL_PATTERN):
        for match in pattern.finditer(expanded):
            try:
                url = normalize_url(match.group(0))
            except WechatPubError:
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def extract_mp_article_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    expanded = html.unescape(text).replace("\\/", "/").replace("\\u0026", "&").replace("\\x26", "&")
    for match in ARTICLE_URL_PATTERN.finditer(expanded):
        value = match.group(0).rstrip(").,;]}\"'")
        query = parse_qs(urlparse(value).query, keep_blank_values=True)
        if not (query.get("__biz") or [""])[-1].strip():
            continue
        if value not in seen:
            seen.add(value)
            urls.append(value)
    return urls


def extract_session_cookies(text: str) -> dict[str, str]:
    expanded = html.unescape(text).replace("\\/", "/").replace("\\u0026", "&").replace("\\x26", "&")
    cookies: dict[str, str] = {}
    for match in SESSION_COOKIE_PATTERN.finditer(expanded):
        cookies[match.group(1)] = match.group(2)
    return cookies


def build_session_history_source(article_url: str, cookies: dict[str, str], *, source: str) -> dict[str, Any] | None:
    query = {key: values[-1] for key, values in parse_qs(urlparse(article_url).query, keep_blank_values=True).items()}
    biz = (query.get("__biz") or "").strip()
    appmsg_token = (query.get("appmsg_token") or cookies.get("appmsg_token") or "").strip()
    key = (query.get("key") or "").strip()
    pass_ticket = (query.get("pass_ticket") or cookies.get("pass_ticket") or "").strip()
    uin = (query.get("uin") or cookies.get("wxuin") or "").strip()
    if not biz or not appmsg_token:
        return None
    history_query = {
        "action": "home",
        "__biz": biz,
        "scene": query.get("scene") or "124",
        "uin": uin,
        "key": key,
        "pass_ticket": pass_ticket,
        "appmsg_token": appmsg_token,
        "wxtoken": cookies.get("wxtokenkey") or query.get("wxtoken") or "",
    }
    history_url = urlunparse(
        (
            "https",
            "mp.weixin.qq.com",
            "/mp/profile_ext",
            "",
            urlencode({key: value for key, value in history_query.items() if value}),
            "wechat_redirect",
        )
    )
    cookie = "; ".join(
        f"{key}={cookies[key]}"
        for key in SESSION_COOKIE_KEYS
        if cookies.get(key)
    )
    return {
        "source": source,
        "source_type": "article_session",
        "url": history_url,
        "cookie": cookie,
        "score": score_url(history_url) + 20 + len(cookies),
        "article_url_redacted": redact_url(article_url),
    }


def extract_session_history_sources(name: str, text: str) -> list[dict[str, Any]]:
    cookies = extract_session_cookies(text)
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for article_url in extract_mp_article_urls(text):
        source = build_session_history_source(article_url, cookies, source=name)
        if not source or source["url"] in seen:
            continue
        seen.add(source["url"])
        matches.append(source)
    return matches


def score_url(url: str) -> int:
    query = parse_qs(urlparse(url).query, keep_blank_values=True)
    score = 0
    for key, weight in {"__biz": 10, "appmsg_token": 6, "key": 5, "pass_ticket": 5, "uin": 2}.items():
        if query.get(key):
            score += weight
    action = (query.get("action") or [""])[-1]
    if action in {"home", "getmsg"}:
        score += 3
    return score


def applescript_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ") + '"'


def candidate_roots(extra_roots: list[str] | None = None) -> list[Path]:
    roots: list[Path] = []
    for raw in extra_roots or []:
        root = Path(raw).expanduser()
        if root.exists() and root not in roots:
            roots.append(root)
    for root in DEFAULT_SCAN_ROOTS:
        if root.exists() and root not in roots:
            roots.append(root)
    return roots


def iter_recent_files(roots: list[Path], *, since_seconds: int, limit: int, deadline: float | None = None) -> list[Path]:
    if limit <= 0:
        return []
    threshold = time.time() - since_seconds if since_seconds > 0 else 0
    files: list[tuple[float, int, Path]] = []
    sequence = 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            if deadline is not None and time.time() > deadline:
                files.sort(reverse=True, key=lambda item: item[0])
                return [path for _, _, path in files]
            dirnames[:] = [name for name in dirnames if name not in {".Trash", "node_modules"}]
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_size <= 0 or stat.st_size > MAX_FILE_BYTES:
                    continue
                if threshold and stat.st_mtime < threshold:
                    continue
                item = (stat.st_mtime, sequence, path)
                sequence += 1
                if len(files) < limit:
                    heapq.heappush(files, item)
                elif item[0] > files[0][0]:
                    heapq.heapreplace(files, item)
    files.sort(reverse=True, key=lambda item: item[0])
    return [path for _, _, path in files]


def scan_text_source(name: str, text: str) -> list[dict[str, Any]]:
    matches = []
    for url in extract_profile_ext_urls(text):
        matches.append({"source": name, "source_type": "profile_ext", "url": url, "score": score_url(url)})
    matches.extend(extract_session_history_sources(name, text))
    return matches


def scan_file(path: Path) -> list[dict[str, Any]]:
    try:
        blob = path.read_bytes()
    except OSError:
        return []
    text = blob.decode("utf-8", errors="ignore")
    matches = scan_text_source(str(path), text)
    if matches:
        return matches
    # Some cache files percent/JSON escape forward slashes; latin-1 keeps bytes
    # visible enough for the relaxed escaped-url regex.
    return scan_text_source(str(path), blob.decode("latin-1", errors="ignore"))


def scan_sources(
    *,
    roots: list[str] | None = None,
    since_seconds: int = 7 * 24 * 3600,
    file_limit: int = 3000,
    deadline: float | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    try:
        clipboard = read_clipboard()
    except WechatPubError:
        clipboard = ""
    if clipboard:
        matches.extend(scan_text_source("clipboard", clipboard))
    for path in iter_recent_files(candidate_roots(roots), since_seconds=since_seconds, limit=file_limit, deadline=deadline):
        matches.extend(scan_file(path))
        if deadline is not None and time.time() > deadline:
            break
    dedup: dict[str, dict[str, Any]] = {}
    for match in matches:
        current = dedup.get(match["url"])
        if current is None or match["score"] > current["score"]:
            dedup[match["url"]] = match
    return sorted(dedup.values(), key=lambda item: item["score"], reverse=True)


def filter_matches_by_biz(matches: list[dict[str, Any]], biz: str | None = None) -> list[dict[str, Any]]:
    if not biz:
        return matches
    filtered: list[dict[str, Any]] = []
    for match in matches:
        query = parse_qs(urlparse(match.get("url") or "").query, keep_blank_values=True)
        if (query.get("__biz") or [""])[-1] == biz:
            filtered.append(match)
    return filtered


def public_match(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": match["source"],
        "source_type": match.get("source_type") or "profile_ext",
        "score": match["score"],
        "has_cookie": bool(match.get("cookie")),
        "url_redacted": redact_url(match["url"]),
    }


def register_best(
    wxid: str,
    matches: list[dict[str, Any]],
    *,
    display_name: str | None = None,
    biz: str | None = None,
) -> dict[str, Any]:
    matches = filter_matches_by_biz(matches, biz)
    if not matches:
        suffix = f"（已按 __biz={biz} 过滤）" if biz else ""
        raise WechatPubError(f"未捕获到包含 __biz 的 profile_ext 链接{suffix}")
    best = matches[0]
    record = register_history_source(wxid, best["url"], display_name=display_name, cookie=best.get("cookie"))
    return {
        "registered": True,
        "captured_from": best["source"],
        "source_type": best.get("source_type") or "profile_ext",
        "score": best["score"],
        "url_redacted": redact_url(best["url"]),
        "has_cookie": bool(best.get("cookie")),
        "record": record,
    }


def open_wechat_search(wxid: str) -> dict[str, Any]:
    script = f'''
set oldClipboard to missing value
try
    set oldClipboard to the clipboard as text
end try
set the clipboard to {applescript_quote(wxid)}
tell application "WeChat"
    activate
end tell
delay 0.8
tell application "System Events"
    keystroke "f" using command down
    delay 0.3
    keystroke "a" using command down
    delay 0.1
    keystroke "v" using command down
end tell
delay 0.2
if oldClipboard is not missing value then
    set the clipboard to oldClipboard
end if
'''
    try:
        subprocess.run(["/usr/bin/open", "-a", "WeChat"], check=False, timeout=10)
        result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "permission_denied": True,
            "message": f"{MACOS_AUTOMATION_PERMISSION_MESSAGE}（osascript 超时）",
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    return osascript_payload(result)


def auto_open_wechat_article(wxid: str) -> dict[str, Any]:
    script = f'''
set oldClipboard to missing value
try
    set oldClipboard to the clipboard as text
end try
set the clipboard to {applescript_quote(wxid)}
tell application "WeChat"
    activate
end tell
delay 0.8
tell application "System Events"
    keystroke "f" using command down
    delay 0.25
    keystroke "a" using command down
    delay 0.1
    keystroke "v" using command down
    delay 0.8
    tell process "WeChat"
        set frontmost to true
        try
            set targetWindow to missing value
            repeat with w in windows
                set s to size of w
                if (item 1 of s) < 420 and (item 2 of s) > 140 then
                    set targetWindow to w
                    exit repeat
                end if
            end repeat
            if targetWindow is not missing value then
                set p to position of targetWindow
                set x0 to item 1 of p
                set y0 to item 2 of p
                click at {{x0 + 130, y0 + 62}}
            else
                set p to position of front window
                set x0 to item 1 of p
                set y0 to item 2 of p
                click at {{x0 + 360, y0 + 310}}
            end if
            delay 0.8
            key code 36
            delay 1.8
            set p2 to position of front window
            set x1 to item 1 of p2
            set y1 to item 2 of p2
            click at {{x1 + 420, y1 + 170}}
            delay 0.2
            click at {{x1 + 420, y1 + 170}}
            delay 0.8
            click at {{x1 + 420, y1 + 230}}
        end try
    end tell
end tell
delay 2.0
if oldClipboard is not missing value then
    set the clipboard to oldClipboard
end if
'''
    try:
        subprocess.run(["/usr/bin/open", "-a", "WeChat"], check=False, timeout=10)
        result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=12)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "permission_denied": True,
            "message": f"{MACOS_AUTOMATION_PERMISSION_MESSAGE}（osascript 超时）",
        }
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    return osascript_payload(result)


def watch_and_register(
    wxid: str,
    *,
    timeout_seconds: int,
    interval_seconds: float,
    roots: list[str] | None = None,
    open_wechat: bool = False,
    display_name: str | None = None,
    biz: str | None = None,
    since_seconds: int = 3600,
    file_limit: int = 500,
) -> dict[str, Any]:
    opened = open_wechat_search(wxid) if open_wechat else None
    deadline = time.time() + timeout_seconds
    last_matches: list[dict[str, Any]] = []
    while time.time() <= deadline:
        last_matches = filter_matches_by_biz(
            scan_sources(roots=roots, since_seconds=since_seconds, file_limit=file_limit, deadline=deadline),
            biz,
        )
        if last_matches:
            data = register_best(wxid, last_matches, display_name=display_name, biz=biz)
            data["opened_wechat"] = opened
            return data
        time.sleep(interval_seconds)
    return {
        "registered": False,
        "message": "监听超时：没有捕获到 profile_ext 历史页链接",
        "opened_wechat": opened,
        "checked_at": now_iso(),
    }


def refresh_and_register(
    wxid: str,
    *,
    timeout_seconds: int,
    interval_seconds: float,
    roots: list[str] | None = None,
    display_name: str | None = None,
    biz: str | None = None,
    since_seconds: int = 4 * 3600,
    file_limit: int = 1500,
    open_wechat: bool = True,
    auto_click: bool = True,
) -> dict[str, Any]:
    first_deadline = time.time() + min(4, max(2, timeout_seconds // 5))
    matches = filter_matches_by_biz(
        scan_sources(roots=roots, since_seconds=since_seconds, file_limit=file_limit, deadline=first_deadline),
        biz,
    )
    if matches:
        data = register_best(wxid, matches, display_name=display_name, biz=biz)
        data["refresh_stage"] = "cache"
        return data

    opened = None
    clicked = None
    if open_wechat:
        clicked = auto_open_wechat_article(wxid) if auto_click else None
        opened = None if auto_click else open_wechat_search(wxid)
        denied_action = denied_automation_action(clicked, opened)
        if denied_action:
            return {
                "registered": False,
                "message": denied_action.get("message") or MACOS_AUTOMATION_PERMISSION_MESSAGE,
                "requires_macos_accessibility": True,
                "opened_wechat": opened,
                "auto_clicked_wechat": clicked,
                "checked_at": now_iso(),
            }
        failed_action = failed_automation_action(clicked, opened)
        if failed_action:
            return {
                "registered": False,
                "message": failed_action.get("message") or "本机微信控制层启动失败，未能自动打开公众号文章。",
                "opened_wechat": opened,
                "auto_clicked_wechat": clicked,
                "checked_at": now_iso(),
            }

    deadline = time.time() + timeout_seconds
    while time.time() <= deadline:
        matches = filter_matches_by_biz(
            scan_sources(roots=roots, since_seconds=max(600, since_seconds), file_limit=file_limit, deadline=deadline),
            biz,
        )
        if matches:
            data = register_best(wxid, matches, display_name=display_name, biz=biz)
            data["refresh_stage"] = "wechat_ui" if open_wechat else "cache_retry"
            data["opened_wechat"] = opened
            data["auto_clicked_wechat"] = clicked
            return data
        time.sleep(interval_seconds)
    return {
        "registered": False,
        "message": "自动续期超时：没有捕获到可用的微信历史源；请确认电脑微信已登录，并让微信打开该公众号任意一篇文章。",
        "opened_wechat": opened,
        "auto_clicked_wechat": clicked,
        "checked_at": now_iso(),
    }


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture WeChat official-account profile_ext history URLs on macOS")
    sub = parser.add_subparsers(dest="cmd", required=True)

    paths = sub.add_parser("paths")
    paths.add_argument("--root", action="append")

    open_cmd = sub.add_parser("open")
    open_cmd.add_argument("wxid")

    scan = sub.add_parser("scan")
    scan.add_argument("wxid")
    scan.add_argument("--register", action="store_true")
    scan.add_argument("--display-name")
    scan.add_argument("--root", action="append")
    scan.add_argument("--biz")
    scan.add_argument("--since-seconds", type=int, default=7 * 24 * 3600)
    scan.add_argument("--file-limit", type=int, default=3000)

    watch = sub.add_parser("watch")
    watch.add_argument("wxid")
    watch.add_argument("--timeout", type=int, default=180)
    watch.add_argument("--interval", type=float, default=1.5)
    watch.add_argument("--open-wechat", action="store_true")
    watch.add_argument("--display-name")
    watch.add_argument("--root", action="append")
    watch.add_argument("--biz")
    watch.add_argument("--since-seconds", type=int, default=3600)
    watch.add_argument("--file-limit", type=int, default=500)

    refresh = sub.add_parser("refresh")
    refresh.add_argument("wxid")
    refresh.add_argument("--timeout", type=int, default=90)
    refresh.add_argument("--interval", type=float, default=1.5)
    refresh.add_argument("--display-name")
    refresh.add_argument("--root", action="append")
    refresh.add_argument("--biz")
    refresh.add_argument("--since-seconds", type=int, default=4 * 3600)
    refresh.add_argument("--file-limit", type=int, default=1500)
    refresh.add_argument("--no-open-wechat", action="store_true")
    refresh.add_argument("--no-auto-click", action="store_true")

    clip = sub.add_parser("register-clipboard")
    clip.add_argument("wxid")
    clip.add_argument("--display-name")

    args = parser.parse_args(argv)
    if args.cmd == "paths":
        print_json([str(path) for path in candidate_roots(args.root)])
        return 0
    if args.cmd == "open":
        print_json(open_wechat_search(args.wxid))
        return 0
    if args.cmd == "scan":
        matches = filter_matches_by_biz(
            scan_sources(roots=args.root, since_seconds=args.since_seconds, file_limit=args.file_limit),
            args.biz,
        )
        if args.register:
            print_json(register_best(args.wxid, matches, display_name=args.display_name, biz=args.biz))
        else:
            print_json(
                {
                    "count": len(matches),
                    "matches": [public_match(item) for item in matches[:20]],
                }
            )
        return 0
    if args.cmd == "watch":
        print_json(
            watch_and_register(
                args.wxid,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
                roots=args.root,
                open_wechat=args.open_wechat,
                display_name=args.display_name,
                biz=args.biz,
                since_seconds=args.since_seconds,
                file_limit=args.file_limit,
            )
        )
        return 0
    if args.cmd == "refresh":
        print_json(
            refresh_and_register(
                args.wxid,
                timeout_seconds=args.timeout,
                interval_seconds=args.interval,
                roots=args.root,
                display_name=args.display_name,
                biz=args.biz,
                since_seconds=args.since_seconds,
                file_limit=args.file_limit,
                open_wechat=not args.no_open_wechat,
                auto_click=not args.no_auto_click,
            )
        )
        return 0
    if args.cmd == "register-clipboard":
        record = register_history_source(args.wxid, read_clipboard(), display_name=args.display_name)
        print_json({"registered": True, "record": record})
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
