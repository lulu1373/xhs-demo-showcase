#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import hashlib
import html as html_lib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from lxml import html


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}
SOGOU_BASE = "https://weixin.sogou.com"
WECHAT_MP_BASE = "https://mp.weixin.qq.com"
DEFAULT_OUT = Path("/Users/lulu/AIWork/wechat-archive")
TENCENT_DOCS_ENV = Path("/Users/lulu/.config/carrie-secrets/tencent-docs.env")
WECHATPUB_SOURCES_PATH = Path("/Users/lulu/.config/carrie-secrets/wechatpub-sources.json")
WECHATPUB_ENV = Path("/Users/lulu/.config/carrie-secrets/wechatpub-api.env")
XHS_ENV = Path("/Users/lulu/.config/carrie-secrets/xiaohongshu-api.env")
WECHAT_HISTORY_CAPTURE = Path(__file__).with_name("wechat-history-capture")
XHS_SIGNED_HELPER = Path(__file__).with_name("xhs_signed_request.py")
XHS_BROWSER_CAPTURE_HELPER = Path(__file__).with_name("xhs_browser_search_capture.py")
XHS_SIGNED_PYTHON = Path(os.environ.get("XHS_SIGNED_PYTHON", str(Path(__file__).with_name(".venv-xhs") / "bin" / "python")))
XHS_BROWSER_PYTHON = Path(os.environ.get("XHS_BROWSER_PYTHON", sys.executable))
XHS_BROWSER_PROFILE = Path(os.environ.get("XHS_BROWSER_PROFILE", "/Users/lulu/.config/carrie-secrets/xhs-browser-profile"))
XHS_CHROME_PATH = Path(os.environ.get("XHS_CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
XHS_HOT_TRENDS_CACHE = Path(os.environ.get("XHS_HOT_TRENDS_CACHE", "/Users/lulu/AIWork/run/xhs-hot-trends-cache.json"))
XHS_HOT_TRENDS_CACHE_TTL_SECONDS = int(os.environ.get("XHS_HOT_TRENDS_CACHE_TTL_SECONDS", "600"))
XHS_HOT_SEARCH_CACHE = Path(os.environ.get("XHS_HOT_SEARCH_CACHE", "/Users/lulu/AIWork/run/xhs-hot-search-cache.json"))
XHS_HOT_SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("XHS_HOT_SEARCH_CACHE_TTL_SECONDS", "3600"))
XHS_GLOBAL_HOT_CACHE = Path(os.environ.get("XHS_GLOBAL_HOT_CACHE", "/Users/lulu/AIWork/run/xhs-global-hot-keywords-cache.json"))
XHS_GLOBAL_HOT_HAR_INBOX = Path(os.environ.get("XHS_GLOBAL_HOT_HAR_INBOX", "/Users/lulu/AIWork/xhs-hot-har-inbox"))
HISTORY_REFRESH_TIMEOUT_SECONDS = int(os.environ.get("WECHAT_HISTORY_REFRESH_TIMEOUT_SECONDS", "45"))
HISTORY_REFRESH_SINCE_SECONDS = int(os.environ.get("WECHAT_HISTORY_REFRESH_SINCE_SECONDS", "300"))
JUSTONE_API_BASE = os.environ.get("JUSTONE_API_BASE", "https://api.justoneapi.com").rstrip("/")
XHS_HOT_SEARCH_PATH = "/api/xiaohongshu/hot-search/v1"
XHS_WEB_BASE = "https://www.xiaohongshu.com"
XHS_EXPLORE_URL = f"{XHS_WEB_BASE}/explore"
XHS_SEARCH_NOTES_PATH = "/api/sns/web/v1/search/notes"
XHS_QUERYTRENDING_PATHS = {
    "/api/sns/web/v1/search/trending/query",
    "/api/sns/web/v1/search/querytrending",
}
XHS_ORDER_BY_FIELDS = {
    "premium_imp_num": "readNum",
    "premium_good_read_rate": "readRate",
    "premium_read_num": "readNum",
    "premium_engage_num": "engageNum",
    "premium_engage_rate": "engageRate",
    "premium_like_num": "likeNum",
    "premium_fav_num": "favNum",
    "premium_cmt_num": "cmtNum",
}
XHS_TIME_RANGES = {"DAY_3", "DAY_7", "DAY_14", "DAY_30"}


class WechatPubError(RuntimeError):
    pass


class TencentDocsError(RuntimeError):
    pass


class XiaohongshuError(RuntimeError):
    pass


def api_response(data: Any = None, *, code: int = 0, message: str = "success", status_code: int = 200) -> JSONResponse:
    return JSONResponse({"code": code, "message": message, "data": data}, status_code=status_code)


def api_error(exc: Exception, *, code: int = 301, status_code: int = 502) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": str(exc)})


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html_lib.unescape(value)).strip()


def js_unescape(value: str) -> str:
    value = value.replace("\\/", "/")
    value = value.replace("\\x26", "&")
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except Exception:
        return value


def safe_slug(value: str, fallback: str = "untitled") -> str:
    value = clean_text(value)
    value = re.sub(r"[\\/:*?\"<>|#%&{}$!'@+`=]", "_", value)
    value = re.sub(r"\s+", "_", value).strip("._ ")
    return value[:90] or fallback


def normalize_query(value: str) -> str:
    value = clean_text(value)
    value = re.sub(r"[「」\"'“”]", "", value)
    value = re.sub(r"(收集|抓取|获取|公众号|最近|最新|近\s*\d+\s*篇|前\s*\d+\s*篇|\d+\s*篇|文章|推文)", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def fetch_text(url: str, *, referer: str | None = None, timeout: int = 30) -> tuple[str, str]:
    s = session()
    if referer:
        s.headers["Referer"] = referer
    response = s.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text, response.url


def parse_history_cookie(raw_cookie: str | None = None) -> dict[str, str]:
    raw_cookie = raw_cookie or os.environ.get("WECHAT_HISTORY_COOKIE", "")
    cookies: dict[str, str] = {}
    for item in raw_cookie.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def build_getmsg_url(history_url: str, *, offset: int, count: int = 10) -> str:
    parsed = urlparse(history_url)
    query = {key: values[-1] for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
    if "__biz" not in query:
        raise WechatPubError("historyUrl must include __biz")
    query.update(
        {
            "action": "getmsg",
            "f": "json",
            "offset": str(offset),
            "count": str(count),
            "is_ok": query.get("is_ok", "1"),
            "scene": query.get("scene", "124"),
            "x5": query.get("x5", "0"),
        }
    )
    return urlunparse(("https", "mp.weixin.qq.com", "/mp/profile_ext", "", urlencode(query), ""))


def flatten_history_message(item: dict[str, Any]) -> list[dict[str, Any]]:
    comm = item.get("comm_msg_info") or {}
    ext = item.get("app_msg_ext_info") or {}
    publish_time = ""
    if str(comm.get("datetime") or "").isdigit():
        publish_time = dt.datetime.fromtimestamp(int(comm["datetime"])).astimezone().isoformat(timespec="seconds")

    def convert(article: dict[str, Any], idx: int) -> dict[str, Any]:
        url = html_lib.unescape(article.get("content_url") or "")
        if url.startswith("/"):
            url = urljoin(WECHAT_MP_BASE, url)
        return {
            "title": clean_text(article.get("title")),
            "url": url,
            "source_name": clean_text(article.get("source_name")),
            "summary": clean_text(article.get("digest")),
            "publish_time": publish_time,
            "cover": html_lib.unescape(article.get("cover") or ""),
            "author": clean_text(article.get("author")),
            "msg_id": comm.get("id"),
            "datetime": comm.get("datetime"),
            "idx": idx,
            "source": "wechat_profile_history",
            "resolve_error": "",
            "collected_at": now_iso(),
        }

    articles = []
    if ext.get("title") or ext.get("content_url"):
        articles.append(convert(ext, 1))
    for idx, sub_item in enumerate(ext.get("multi_app_msg_item_list") or [], start=2):
        if sub_item.get("title") or sub_item.get("content_url"):
            articles.append(convert(sub_item, idx))
    return articles


def parse_history_response(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    base_resp = payload.get("base_resp") or {}
    ret = payload.get("ret", base_resp.get("ret", 0))
    if ret not in (0, "0", None):
        message = payload.get("errmsg") or base_resp.get("errmsg") or f"ret={ret}"
        raise WechatPubError(f"WeChat history source rejected request: {message}")
    raw_list = payload.get("general_msg_list")
    if isinstance(raw_list, str):
        parsed = json.loads(raw_list or "{}")
    elif isinstance(raw_list, dict):
        parsed = raw_list
    else:
        parsed = {}
    posts: list[dict[str, Any]] = []
    for item in parsed.get("list") or []:
        posts.extend(flatten_history_message(item))
    can_msg_continue = bool(payload.get("can_msg_continue"))
    return posts, can_msg_continue


def history_error_needs_refresh(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(
        marker in text
        for marker in (
            "no session",
            "session",
            "cookie",
            "expired",
            "ret=-3",
            "rejected request",
            "请在微信客户端打开",
            "登录",
        )
    )


def fetch_wechat_history_articles(
    history_url: str,
    *,
    limit: int = 30,
    cookie: str | None = None,
    delay: float = 0.8,
) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    s = session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36 NetType/WIFI "
                "MicroMessenger/8.0 WindowsWechat"
            ),
            "X-Requested-With": "XMLHttpRequest",
            "Referer": history_url,
        }
    )
    for key, value in parse_history_cookie(cookie).items():
        s.cookies.set(key, value, domain=".weixin.qq.com")
    posts: list[dict[str, Any]] = []
    seen: set[str] = set()
    offset = 0
    while len(posts) < limit:
        url = build_getmsg_url(history_url, offset=offset, count=min(10, limit - len(posts)))
        response = s.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        batch, can_continue = parse_history_response(payload)
        for post in batch:
            key = post.get("url") or f"{post.get('msg_id')}:{post.get('idx')}"
            if key in seen:
                continue
            seen.add(key)
            post["rank"] = len(posts) + 1
            posts.append(post)
            if len(posts) >= limit:
                break
        if not can_continue or not batch:
            break
        offset += 10
        if delay:
            time.sleep(delay)
    return posts


def resolve_sogou_link(href: str, client: requests.Session | None = None) -> str:
    url = urljoin(SOGOU_BASE, href)
    if client is None:
        text, final_url = fetch_text(url, referer=SOGOU_BASE, timeout=20)
    else:
        client.headers["Referer"] = SOGOU_BASE
        response = client.get(url, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        text, final_url = response.text, response.url
    if "antispider" in final_url or "请输入验证码" in text or "verify_page" in text:
        raise WechatPubError("Sogou anti-spider challenge encountered while resolving link")
    if "mp.weixin.qq.com" in final_url:
        return final_url
    parts = re.findall(r"url\s*\+=\s*'([^']*)'", text)
    if parts:
        return "".join(parts).replace("@", "")
    match = re.search(r"window\.location\.replace\(['\"]([^'\"]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"https://mp\.weixin\.qq\.com/[^'\"<>\\]+", text)
    if match:
        return html_lib.unescape(match.group(0))
    raise WechatPubError("Could not resolve Sogou redirect link")


def parse_js_var(text: str, name: str) -> str:
    patterns = [
        rf"var\s+{re.escape(name)}\s*=\s*'((?:\\'|[^'])*)'",
        rf'var\s+{re.escape(name)}\s*=\s*"((?:\\"|[^"])*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(js_unescape(match.group(1)))
    return ""


def html_fragment_to_markdown(fragment: str) -> str:
    if not fragment:
        return ""
    doc = html.fragment_fromstring(fragment, create_parent="div")
    lines: list[str] = []

    def walk(node: Any) -> None:
        tag = getattr(node, "tag", "")
        if tag in {"script", "style", "svg"}:
            return
        if tag == "img":
            src = node.get("data-src") or node.get("src") or ""
            alt = clean_text(node.get("alt"))
            if src:
                lines.append(f"![{alt}]({src})")
            return
        text = clean_text(node.text)
        if text:
            lines.append(text)
        for child in node:
            walk(child)
            tail = clean_text(child.tail)
            if tail:
                lines.append(tail)

    walk(doc)
    compact: list[str] = []
    previous = ""
    for line in lines:
        if line != previous:
            compact.append(line)
        previous = line
    return "\n\n".join(compact)


def extract_article_detail(article_url: str) -> dict[str, Any]:
    text, final_url = fetch_text(article_url, timeout=45)
    doc = html.fromstring(text)
    title = (
        clean_text(doc.xpath("string(//h1[@id='activity-name'])"))
        or clean_text(doc.xpath("string(//h1)"))
        or parse_js_var(text, "msg_title")
    )
    account_name = (
        clean_text(doc.xpath("string(//*[@id='js_name'])"))
        or parse_js_var(text, "nickname")
    )
    author = clean_text(doc.xpath("string(//*[@id='js_author_name'])")) or parse_js_var(text, "author")
    desc = parse_js_var(text, "msg_desc")
    cover = parse_js_var(text, "msg_cdn_url") or parse_js_var(text, "cdn_url")
    ct = parse_js_var(text, "ct")
    publish_time = ""
    if ct.isdigit():
        publish_time = dt.datetime.fromtimestamp(int(ct)).astimezone().isoformat(timespec="seconds")
    content_nodes = doc.xpath("//*[@id='js_content']")
    content_html = ""
    content_text = ""
    markdown = ""
    if content_nodes:
        content_node = content_nodes[0]
        for noisy_node in content_node.xpath(".//script|.//style|.//svg"):
            noisy_node.drop_tree()
        content_html = html.tostring(content_node, encoding="unicode", method="html")
        content_text = clean_text(content_node.text_content())
        markdown = html_fragment_to_markdown(content_html)
    if not title and not content_text:
        raise WechatPubError("Article page did not expose readable content")
    return {
        "url": article_url,
        "final_url": final_url,
        "title": title,
        "account_name": account_name,
        "author": author,
        "description": desc,
        "cover": cover,
        "publish_time": publish_time,
        "content_text": content_text,
        "content_html": content_html,
        "markdown": markdown,
        "collected_at": now_iso(),
    }


def parse_sogou_time(li: Any) -> str:
    scripts = " ".join(li.xpath(".//script/text()"))
    match = re.search(r"timeConvert\('([0-9]+)'\)", scripts)
    if match:
        return dt.datetime.fromtimestamp(int(match.group(1))).astimezone().isoformat(timespec="seconds")
    return ""


def search_sogou_articles(
    query: str,
    *,
    limit: int = 30,
    pages: int | None = None,
    exact_account: str | None = None,
    resolve: bool = True,
    delay: float = 0.8,
) -> list[dict[str, Any]]:
    if limit < 1:
        return []
    pages = pages or min(10, max(1, (limit + 9) // 10))
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    s = session()
    for page in range(1, pages + 1):
        url = f"{SOGOU_BASE}/weixin?type=2&query={quote(query)}&ie=utf8&page={page}"
        response = s.get(url, timeout=30)
        response.raise_for_status()
        doc = html.fromstring(response.text)
        lis = doc.xpath("//li[contains(@id,'sogou_vr_11002601_box_')]")
        if not lis and ("antispider" in response.url or "验证码" in response.text):
            raise WechatPubError("Sogou anti-spider challenge encountered")
        for li in lis:
            title = clean_text(li.xpath("string(.//h3/a)"))
            hrefs = li.xpath(".//h3/a/@href")
            if not title or not hrefs:
                continue
            summary = clean_text(li.xpath("string(.//p[contains(@class,'txt-info')])"))
            source = clean_text(li.xpath("string(.//div[contains(@class,'s-p')]/span[1])"))
            if exact_account and exact_account not in source:
                continue
            href = hrefs[0]
            article_url = urljoin(SOGOU_BASE, href)
            if resolve:
                try:
                    article_url = resolve_sogou_link(href, s)
                except Exception as exc:
                    article_url = urljoin(SOGOU_BASE, href)
                    error = str(exc)
                else:
                    error = ""
            else:
                error = ""
            key = article_url
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "title": title,
                    "url": article_url,
                    "source_name": source,
                    "summary": summary,
                    "publish_time": parse_sogou_time(li),
                    "rank": len(items) + 1,
                    "source": "sogou_weixin_search",
                    "resolve_error": error,
                    "collected_at": now_iso(),
                }
            )
            if len(items) >= limit:
                return items
            if resolve and delay:
                time.sleep(delay)
        if delay:
            time.sleep(delay)
    return items


def get_article_posts(
    query: str,
    *,
    limit: int,
    exact_account: str | None = None,
    source: str = "search",
    history_url: str | None = None,
    strict_recent: bool = False,
    auto_refresh: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = source or "search"
    history_cookie: str | None = None
    history_record: dict[str, Any] | None = None
    if source == "auto":
        history_record = find_history_source(query)
        if history_record and history_record.get("history_url"):
            history_url = str(history_record["history_url"])
            history_cookie = str(history_record.get("cookie") or "") or None
            source = "history"
        else:
            source = "search"
    if source == "history" or history_url:
        if not history_url:
            raise WechatPubError("history source requires historyUrl")
        if history_cookie is None:
            history_record = history_record or find_history_source(query)
            if history_record and history_record.get("history_url") == history_url:
                history_cookie = str(history_record.get("cookie") or "") or None
        posts, refresh_result = fetch_wechat_history_articles_with_refresh(
            query,
            history_url,
            limit=limit,
            cookie=history_cookie,
            record=history_record,
            auto_refresh=auto_refresh and bool(history_record),
        )
        meta = {
            "source_mode": "wechat_profile_history",
            "is_chronological_timeline": True,
            "coverage_note": "微信公众号历史消息页返回的时间线；依赖 historyUrl 中的短期登录态。",
        }
        if refresh_result:
            meta["auto_refreshed_history_source"] = True
            meta["history_refresh_stage"] = refresh_result.get("refresh_stage") or ""
        return posts, meta
    if strict_recent:
        registered = find_history_source(query)
        if registered and not registered.get("history_url"):
            suffix = "已找到账号记录，但缺少可用 historyUrl。"
        else:
            suffix = "尚未注册该公众号的历史源。"
        raise WechatPubError(
            "当前请求要求真实最近文章，但没有提供微信公众号历史页 historyUrl。"
            f"{suffix}请先调用 /api/weixin/register-source/v1 注册 profile_ext 链接。"
        )
    normalized_query = normalize_query(query)
    posts = search_sogou_articles(normalized_query, limit=limit, exact_account=exact_account, resolve=True)
    return posts, {
        "source_mode": "sogou_weixin_search",
        "is_chronological_timeline": False,
        "coverage_note": "公开搜狗微信搜索结果，按搜索引擎返回排序；不是公众号后台时间线，不能保证为最近文章。",
    }


def write_article(out_dir: Path, index: int, article: dict[str, Any]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = safe_slug(article.get("title") or f"article_{index:03d}")
    stem = f"{index:03d}_{slug}"
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        f"# {article.get('title') or 'Untitled'}",
        "",
        f"- 公众号: {article.get('account_name') or ''}",
        f"- 作者: {article.get('author') or ''}",
        f"- 发布时间: {article.get('publish_time') or ''}",
        f"- 原文: {article.get('final_url') or article.get('url') or ''}",
        "",
        article.get("markdown") or article.get("content_text") or "",
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = shlex.split(raw_value)[0] if raw_value.strip() else ""
        values[key] = value
    return values


def local_api_token() -> str:
    file_values = load_env_file(WECHATPUB_ENV)
    return os.environ.get("WECHATPUB_API_TOKEN") or file_values.get("WECHATPUB_API_TOKEN", "")


def validate_token(token: str | None = None) -> None:
    expected = local_api_token()
    if expected and token != expected:
        raise WechatPubError("Token 无效或已失效")


def xhs_justone_token(explicit_token: str | None = None) -> str:
    if explicit_token:
        return explicit_token
    file_values = load_env_file(XHS_ENV)
    return (
        os.environ.get("XHS_JUSTONE_TOKEN")
        or os.environ.get("JUSTONE_API_TOKEN")
        or file_values.get("XHS_JUSTONE_TOKEN", "")
        or file_values.get("JUSTONE_API_TOKEN", "")
    )


def xhs_cookie(explicit_cookie: str | None = None) -> str:
    if explicit_cookie:
        return explicit_cookie.strip()
    file_values = load_env_file(XHS_ENV)
    return (
        os.environ.get("XHS_COOKIE")
        or os.environ.get("XHS_WEB_COOKIE")
        or file_values.get("XHS_COOKIE", "")
        or file_values.get("XHS_WEB_COOKIE", "")
    ).strip()


def xhs_cookie_status(cookie: str | None = None) -> dict[str, Any]:
    raw_cookie = xhs_cookie(cookie)
    names = set()
    for part in raw_cookie.split(";"):
        if "=" in part:
            names.add(part.split("=", 1)[0].strip())
    return {
        "configured": bool(raw_cookie),
        "has_a1": "a1" in names,
        "has_web_session": "web_session" in names,
        "cookie_names": sorted(name for name in names if name in {"a1", "web_session", "webId", "gid", "abRequestId"}),
    }


def save_xhs_cookie(cookie: str) -> None:
    XHS_ENV.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if XHS_ENV.exists():
        lines = XHS_ENV.read_text(encoding="utf-8").splitlines()
    output = []
    replaced = False
    for line in lines:
        if line.strip().startswith("XHS_COOKIE=") or line.strip().startswith("XHS_WEB_COOKIE="):
            if not replaced:
                output.append("XHS_COOKIE=" + shlex.quote(cookie))
                replaced = True
            continue
        output.append(line)
    if not replaced:
        output.append("XHS_COOKIE=" + shlex.quote(cookie))
    tmp_path = XHS_ENV.with_suffix(".env.tmp")
    tmp_path.write_text("\n".join(output).strip() + "\n", encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    tmp_path.replace(XHS_ENV)
    os.chmod(XHS_ENV, 0o600)


def capture_xhs_cookie_from_browser(
    *,
    timeout_seconds: int = 180,
    user_data_dir: str = "/Users/lulu/.config/carrie-secrets/xhs-browser-profile",
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise XiaohongshuError(f"Playwright not available: {exc}") from exc

    browser_path = os.environ.get("XHS_CHROME_PATH", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if not Path(browser_path).exists():
        raise XiaohongshuError(f"Chrome not found: {browser_path}")
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_seconds
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            executable_path=browser_path,
            args=["--disable-blink-features=AutomationControlled"],
            locale="zh-CN",
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(XHS_EXPLORE_URL, wait_until="domcontentloaded", timeout=60000)
            last_status: dict[str, Any] = {}
            while time.time() < deadline:
                cookies = context.cookies([XHS_WEB_BASE, "https://edith.xiaohongshu.com"])
                cookie = "; ".join(f"{item['name']}={item['value']}" for item in cookies if item.get("name") and item.get("value"))
                last_status = xhs_cookie_status(cookie)
                if last_status["has_a1"] and last_status["has_web_session"]:
                    save_xhs_cookie(cookie)
                    return {
                        "saved": True,
                        "path": str(XHS_ENV),
                        "cookie": last_status,
                    }
                page.wait_for_timeout(2000)
            return {
                "saved": False,
                "path": str(XHS_ENV),
                "cookie": last_status,
                "message": "未在超时时间内检测到 a1 + web_session；请在打开的浏览器里完成小红书登录后重试。",
            }
        finally:
            context.close()


def validate_xhs_hot_search_params(order_by: str, nd: str) -> None:
    if order_by not in XHS_ORDER_BY_FIELDS:
        raise XiaohongshuError(f"Unsupported orderBy: {order_by}")
    if nd not in XHS_TIME_RANGES:
        raise XiaohongshuError(f"Unsupported nd: {nd}")


def parse_human_count(value: Any) -> int:
    text = clean_text(str(value or ""))
    if not text:
        return 0
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100000000
        text = text[:-1]
    text = text.replace(",", "")
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def xhs_engage_metrics(note_info: dict[str, Any]) -> dict[str, float]:
    read_num = int(note_info.get("readNum") or 0)
    like_num = int(note_info.get("likeNum") or 0)
    fav_num = int(note_info.get("favNum") or 0)
    cmt_num = int(note_info.get("cmtNum") or 0)
    engage_num = like_num + fav_num + cmt_num
    return {
        "readNum": float(read_num),
        "likeNum": float(like_num),
        "favNum": float(fav_num),
        "cmtNum": float(cmt_num),
        "engageNum": float(engage_num),
        "engageRate": float(engage_num / read_num) if read_num else 0.0,
        "readRate": float(note_info.get("readRate") or 0),
    }


def first_present(mapping: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return default


def normalize_xhs_note_item(item: dict[str, Any]) -> dict[str, Any]:
    note_info = dict(item.get("noteInfo") or {})
    user_info = dict(item.get("userInfo") or {})
    metrics = xhs_engage_metrics(note_info)
    note_info.setdefault("engageNum", int(metrics["engageNum"]))
    note_info.setdefault("engageRate", metrics["engageRate"])
    normalized = dict(item)
    normalized["noteInfo"] = note_info
    normalized["userInfo"] = user_info
    return normalized


def shape_xhs_hot_search_data(
    data: dict[str, Any],
    *,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
    source_mode: str,
    warning: str | None = None,
    already_paged: bool = False,
    filter_keyword: bool = True,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_xhs_hot_search_params(order_by, nd)
    shaped = dict(data or {})
    note_list = [normalize_xhs_note_item(item) for item in shaped.get("noteList") or [] if isinstance(item, dict)]
    keyword = clean_text(search_word).lower()
    if keyword and filter_keyword:
        note_list = [
            item
            for item in note_list
            if keyword in clean_text((item.get("noteInfo") or {}).get("title")).lower()
            or keyword in clean_text((item.get("userInfo") or {}).get("nickName")).lower()
        ]
    metric_field = XHS_ORDER_BY_FIELDS[order_by]
    note_list = sorted(
        note_list,
        key=lambda item: xhs_engage_metrics(item.get("noteInfo") or {}).get(metric_field, 0),
        reverse=True,
    )
    page_info = dict(shaped.get("pageInfoDto") or {})
    page_size = int(page_info.get("pageSize") or 10)
    page_num = max(1, int(page_num or 1))
    total = int(page_info.get("total") or len(note_list)) if already_paged else len(note_list)
    if already_paged:
        shaped["noteList"] = note_list
    else:
        start = (page_num - 1) * page_size
        shaped["noteList"] = note_list[start: start + page_size]
    shaped["total"] = total
    shaped["pageInfoDto"] = {
        **page_info,
        "pageNum": page_num,
        "pageSize": page_size,
        "total": total,
        "totalPage": (total + page_size - 1) // page_size if page_size else 0,
    }
    shaped["localMeta"] = {
        "source_mode": source_mode,
        "searchWord": search_word,
        "orderBy": order_by,
        "nd": nd,
    }
    if extra_meta:
        shaped["localMeta"].update(extra_meta)
    if warning:
        shaped["localMeta"]["warning"] = warning
    return shaped


def fetch_justone_status_example(api_path: str = XHS_HOT_SEARCH_PATH, *, timeout: int = 30) -> dict[str, Any]:
    response = requests.get(
        f"{JUSTONE_API_BASE}/status/api-example/detail",
        params={"api": api_path},
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise XiaohongshuError(payload.get("message") or "Just One status example unavailable")
    detail = payload.get("data") or {}
    example = detail.get("example")
    if not isinstance(example, dict):
        raise XiaohongshuError("Just One status example missing response example")
    return {
        "example": example,
        "checked_at": detail.get("checkedAt"),
    }


def xhs_hot_search_cache_key(*, search_word: str, order_by: str, nd: str) -> str:
    return json.dumps(
        {
            "searchWord": clean_text(search_word),
            "orderBy": order_by,
            "nd": nd,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def save_xhs_hot_search_cache(payload: dict[str, Any]) -> None:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
    key = xhs_hot_search_cache_key(
        search_word=str(local_meta.get("searchWord") or ""),
        order_by=str(local_meta.get("orderBy") or "premium_imp_num"),
        nd=str(local_meta.get("nd") or "DAY_7"),
    )
    try:
        cache = json.loads(XHS_HOT_SEARCH_CACHE.read_text(encoding="utf-8")) if XHS_HOT_SEARCH_CACHE.exists() else {}
    except Exception:
        cache = {}
    entries = cache.get("entries") if isinstance(cache.get("entries"), dict) else {}
    entry_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    entry_payload["cacheSavedAtEpoch"] = time.time()
    entry_payload["cacheSavedAt"] = now_iso()
    entries[key] = entry_payload
    XHS_HOT_SEARCH_CACHE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = XHS_HOT_SEARCH_CACHE.with_suffix(f"{XHS_HOT_SEARCH_CACHE.suffix}.tmp")
    tmp_path.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(XHS_HOT_SEARCH_CACHE)


def load_xhs_hot_search_cache(
    *,
    search_word: str,
    order_by: str,
    nd: str,
    max_age_seconds: int | None = None,
) -> dict[str, Any] | None:
    if not XHS_HOT_SEARCH_CACHE.exists():
        return None
    try:
        cache = json.loads(XHS_HOT_SEARCH_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    entries = cache.get("entries") if isinstance(cache.get("entries"), dict) else {}
    payload = entries.get(xhs_hot_search_cache_key(search_word=search_word, order_by=order_by, nd=nd))
    if not isinstance(payload, dict):
        return None
    saved_at_epoch = payload.get("cacheSavedAtEpoch")
    age_seconds: int | None = None
    if isinstance(saved_at_epoch, (int, float)):
        age_seconds = max(0, int(time.time() - saved_at_epoch))
        if max_age_seconds is not None and age_seconds > max_age_seconds:
            return None
    response_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"cacheSavedAtEpoch", "cacheSavedAt"}
    }
    data = response_payload.get("data") if isinstance(response_payload.get("data"), dict) else {}
    local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
    response_payload["data"] = {
        **data,
        "localMeta": {
            **local_meta,
            "cache": True,
            "cachePath": str(XHS_HOT_SEARCH_CACHE),
            "cacheSavedAt": payload.get("cacheSavedAt") or "",
            "cacheAgeSeconds": age_seconds,
        },
    }
    return response_payload


def fetch_xhs_web_html(url: str = XHS_EXPLORE_URL, *, timeout: int = 30) -> str:
    headers = {
        **DEFAULT_HEADERS,
        "Referer": XHS_WEB_BASE,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_xhs_initial_state(text: str) -> dict[str, Any]:
    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(.*?)</script>", text, re.S)
    if not match:
        raise XiaohongshuError("小红书网页没有暴露 __INITIAL_STATE__")
    raw = match.group(1).strip().rstrip(";")
    raw = raw.replace(":undefined", ":null")
    raw = raw.replace("[undefined", "[null")
    raw = raw.replace(",undefined", ",null")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise XiaohongshuError(f"小红书网页状态解析失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise XiaohongshuError("小红书网页状态格式异常")
    return payload


def xhs_record_time_from_state(state: dict[str, Any]) -> str:
    server_time = (state.get("global") or {}).get("serverTime")
    if isinstance(server_time, (int, float)) and server_time > 0:
        timestamp = server_time / 1000 if server_time > 100000000000 else server_time
        return dt.datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")
    return now_iso()


def normalize_xhs_web_feed_item(item: dict[str, Any], *, rank: int) -> dict[str, Any] | None:
    note_card = item.get("noteCard") or {}
    if not isinstance(note_card, dict):
        return None
    note_id = clean_text(str(item.get("id") or item.get("trackId") or ""))
    title = clean_text(note_card.get("displayTitle") or note_card.get("title"))
    if not note_id and not title:
        return None
    interact_info = note_card.get("interactInfo") or {}
    user = note_card.get("user") or {}
    cover = note_card.get("cover") or {}
    cover_url = cover.get("urlDefault") or cover.get("urlPre") or cover.get("url") or ""
    liked_count = parse_human_count(interact_info.get("likedCount"))
    # Public SSR only exposes like counts. Keep derived fields explicit so callers
    # do not mistake them for Xiaohongshu's private premium metrics.
    estimated_read_num = liked_count * 120 if liked_count else 0
    note_info = {
        "noteId": note_id,
        "title": title,
        "url": f"{XHS_WEB_BASE}/explore/{note_id}" if note_id else "",
        "cover": cover_url,
        "type": note_card.get("type") or item.get("modelType") or "",
        "rank": rank,
        "readNum": estimated_read_num,
        "likeNum": liked_count,
        "favNum": 0,
        "cmtNum": 0,
        "readRate": 0,
        "metricsEstimated": True,
        "likedCountText": clean_text(str(interact_info.get("likedCount") or "")),
    }
    user_info = {
        "userId": clean_text(str(user.get("userId") or "")),
        "nickName": clean_text(user.get("nickName") or user.get("nickname")),
        "avatar": user.get("avatar") or "",
        "xsecToken": user.get("xsecToken") or "",
    }
    return {
        "noteInfo": note_info,
        "userInfo": user_info,
        "xsecToken": item.get("xsecToken") or "",
        "source": "xiaohongshu_web_explore",
    }


def extract_xhs_web_explore_notes(state: dict[str, Any]) -> list[dict[str, Any]]:
    feeds = ((state.get("feed") or {}).get("feeds")) or []
    if not isinstance(feeds, list):
        return []
    notes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in feeds:
        if not isinstance(item, dict):
            continue
        normalized = normalize_xhs_web_feed_item(item, rank=len(notes) + 1)
        if not normalized:
            continue
        note_info = normalized.get("noteInfo") or {}
        note_key = note_info.get("noteId") or note_info.get("title")
        if note_key in seen:
            continue
        seen.add(str(note_key))
        notes.append(normalized)
    return notes


def xhs_note_url(note_id: str, *, xsec_token: str = "", xsec_source: str = "") -> str:
    if not note_id:
        return ""
    params = {
        key: value
        for key, value in {
            "xsec_token": xsec_token,
            "xsec_source": xsec_source,
        }.items()
        if value
    }
    suffix = f"?{urlencode(params)}" if params else ""
    return f"{XHS_WEB_BASE}/explore/{note_id}{suffix}"


def normalize_xhs_web_search_note_item(item: dict[str, Any], *, rank: int) -> dict[str, Any] | None:
    model_type = clean_text(str(first_present(item, "model_type", "modelType")))
    if model_type in {"rec_query", "hot_query"}:
        return None
    note_card = first_present(item, "note_card", "noteCard", default={})
    note_card = note_card if isinstance(note_card, dict) else {}
    note_id = clean_text(str(first_present(item, "id", "note_id", "noteId", "trackId")))
    title = clean_text(first_present(note_card, "display_title", "displayTitle", "title", "desc"))
    if not note_id and not title:
        return None

    interact_info = first_present(note_card, "interact_info", "interactInfo", default={})
    interact_info = interact_info if isinstance(interact_info, dict) else {}
    user = first_present(note_card, "user", "user_info", "userInfo", default={})
    user = user if isinstance(user, dict) else {}
    cover = first_present(note_card, "cover", "image", default={})
    cover = cover if isinstance(cover, dict) else {}

    liked_count = parse_human_count(first_present(interact_info, "liked_count", "likedCount"))
    fav_count = parse_human_count(first_present(interact_info, "collected_count", "collectedCount", "fav_count", "favCount"))
    cmt_count = parse_human_count(first_present(interact_info, "comment_count", "commentCount", "cmt_count", "cmtCount"))
    share_count = parse_human_count(first_present(interact_info, "share_count", "shareCount"))
    estimated_read_num = liked_count * 120 if liked_count else 0
    xsec_token = clean_text(str(first_present(item, "xsec_token", "xsecToken")))
    xsec_source = clean_text(str(first_present(item, "xsec_source", "xsecSource", default="pc_search")))
    note_info = {
        "noteId": note_id,
        "title": title,
        "url": xhs_note_url(note_id, xsec_token=xsec_token, xsec_source=xsec_source),
        "cover": first_present(cover, "url_default", "urlDefault", "url_pre", "urlPre", "url"),
        "type": first_present(note_card, "type", "note_type", "noteType", default=model_type),
        "rank": rank,
        "readNum": estimated_read_num,
        "likeNum": liked_count,
        "favNum": fav_count,
        "cmtNum": cmt_count,
        "shareNum": share_count,
        "readRate": 0,
        "metricsEstimated": True,
        "likedCountText": clean_text(str(first_present(interact_info, "liked_count", "likedCount"))),
    }
    user_info = {
        "userId": clean_text(str(first_present(user, "user_id", "userId"))),
        "nickName": clean_text(first_present(user, "nickname", "nickName")),
        "avatar": first_present(user, "avatar", "image"),
        "xsecToken": clean_text(str(first_present(user, "xsec_token", "xsecToken"))),
    }
    return {
        "noteInfo": note_info,
        "userInfo": user_info,
        "xsecToken": xsec_token,
        "xsecSource": xsec_source,
        "source": "xiaohongshu_web_search",
    }


def extract_xhs_web_search_notes(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = data.get("items") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []
    notes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_xhs_web_search_note_item(item, rank=len(notes) + 1)
        if not normalized:
            continue
        note_info = normalized.get("noteInfo") or {}
        note_key = note_info.get("noteId") or note_info.get("title")
        if note_key in seen:
            continue
        seen.add(str(note_key))
        notes.append(normalized)
    return notes


def fetch_self_xhs_explore_hot_search(
    *,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
) -> dict[str, Any]:
    validate_xhs_hot_search_params(order_by, nd)
    html_text = fetch_xhs_web_html()
    state = parse_xhs_initial_state(html_text)
    notes = extract_xhs_web_explore_notes(state)
    if not notes:
        raise XiaohongshuError("小红书网页端 Explore feed 没有返回可读笔记")
    warning = (
        "自有源来自小红书网页端公开 Explore SSR；公开数据不含阅读/收藏/评论等 premium 指标，"
        "readNum 为基于点赞数的估算，favNum/cmtNum 暂为 0。"
    )
    response_payload = {
        "code": 0,
        "message": "success",
        "data": shape_xhs_hot_search_data(
            {
                "noteList": notes,
                "pageInfoDto": {"pageNum": page_num, "pageSize": 10, "total": len(notes)},
                "sourceUrl": XHS_EXPLORE_URL,
            },
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
            source_mode="self_web_explore",
            warning=warning,
            extra_meta={"usesJustOne": False, "endpoint": "__INITIAL_STATE__.feed.feeds"},
        ),
        "recordTime": xhs_record_time_from_state(state),
    }
    return response_payload


def fetch_self_xhs_hot_search(
    *,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
) -> dict[str, Any]:
    return fetch_self_xhs_explore_hot_search(
        search_word=search_word,
        page_num=page_num,
        order_by=order_by,
        nd=nd,
    )


def run_xhs_signed_helper(op: str, *, cookie: str, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    if not XHS_SIGNED_PYTHON.exists():
        raise XiaohongshuError(f"XHS signed Python runtime not found: {XHS_SIGNED_PYTHON}")
    if not XHS_SIGNED_HELPER.exists():
        raise XiaohongshuError(f"XHS signed helper not found: {XHS_SIGNED_HELPER}")
    if not cookie:
        raise XiaohongshuError(f"Missing XHS_COOKIE/XHS_WEB_COOKIE in {XHS_ENV}")
    request = {
        "op": op,
        "cookie": cookie,
        "params": params or {},
        "timeout": timeout,
    }
    result = subprocess.run(
        [str(XHS_SIGNED_PYTHON), str(XHS_SIGNED_HELPER)],
        input=json.dumps(request, ensure_ascii=False),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout + 10,
    )
    output = (result.stdout or "").strip()
    try:
        payload = json.loads(output or "{}")
    except json.JSONDecodeError as exc:
        raise XiaohongshuError(f"XHS signed helper returned invalid JSON: {output[:300]}") from exc
    if result.returncode != 0 or not payload.get("ok"):
        raise XiaohongshuError(payload.get("error") or result.stderr.strip() or "XHS signed helper failed")
    return payload


def xhs_search_sort_for_order_by(order_by: str) -> str:
    validate_xhs_hot_search_params(order_by, "DAY_7")
    if order_by in {
        "premium_imp_num",
        "premium_read_num",
        "premium_engage_num",
        "premium_engage_rate",
        "premium_like_num",
        "premium_fav_num",
        "premium_cmt_num",
    }:
        return "popularity_descending"
    return "general"


def fetch_signed_xhs_hot_search(
    *,
    cookie: str | None = None,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
) -> dict[str, Any]:
    validate_xhs_hot_search_params(order_by, nd)
    keyword = clean_text(search_word)
    if not keyword:
        raise XiaohongshuError("web_search source requires searchWord")
    page_num = max(1, int(page_num or 1))
    page_size = 10
    effective_cookie = xhs_cookie(cookie)
    helper_payload = run_xhs_signed_helper(
        "searchnotes",
        cookie=effective_cookie,
        params={
            "keyword": keyword,
            "page": page_num,
            "page_size": page_size,
            "sort": xhs_search_sort_for_order_by(order_by),
            "note_type": 0,
        },
    )
    payload = helper_payload.get("payload") or {}
    if str(payload.get("code")) not in {"0", "None"} and not payload.get("success"):
        raise XiaohongshuError(payload.get("msg") or payload.get("message") or f"XHS search notes returned code={payload.get('code')}")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    notes = extract_xhs_web_search_notes(data)
    if not notes:
        raise XiaohongshuError("小红书 Web 搜索没有返回可读笔记")
    warning = (
        "自有源来自小红书 Web 搜索接口；无需 JustOne/Proxyman。公开搜索结果不直接暴露阅读数，"
        "readNum 仍按点赞数估算。"
    )
    total = int(data.get("total") or data.get("total_count") or len(notes))
    response_payload = {
        "code": 0,
        "message": "success",
        "data": shape_xhs_hot_search_data(
            {
                "noteList": notes,
                "pageInfoDto": {
                    "pageNum": page_num,
                    "pageSize": page_size,
                    "total": total,
                    "hasMore": bool(data.get("has_more")),
                },
                "sourceUrl": f"{XHS_WEB_BASE}/search_result?keyword={quote(keyword)}",
            },
            search_word=keyword,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
            source_mode="self_web_search",
            warning=warning,
            already_paged=True,
            filter_keyword=False,
            extra_meta={
                "usesJustOne": False,
                "endpoint": XHS_SEARCH_NOTES_PATH,
                "login": xhs_cookie_status(effective_cookie),
            },
        ),
        "recordTime": now_iso(),
    }
    save_xhs_hot_search_cache(response_payload)
    return response_payload


def shape_xhs_search_notes_payload(
    payload: dict[str, Any],
    *,
    search_word: str,
    page_num: int,
    order_by: str,
    nd: str,
    source_mode: str,
    warning: str,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    notes = extract_xhs_web_search_notes(data)
    if not notes:
        raise XiaohongshuError("小红书 Web 搜索没有返回可读笔记")
    page_size = int(data.get("page_size") or data.get("pageSize") or len(notes) or 10)
    total = int(data.get("total") or data.get("total_count") or len(notes))
    return shape_xhs_hot_search_data(
        {
            "noteList": notes,
            "pageInfoDto": {
                "pageNum": page_num,
                "pageSize": page_size,
                "total": total,
                "hasMore": bool(data.get("has_more")),
            },
            "sourceUrl": f"{XHS_WEB_BASE}/search_result?keyword={quote(search_word)}",
        },
        search_word=search_word,
        page_num=page_num,
        order_by=order_by,
        nd=nd,
        source_mode=source_mode,
        warning=warning,
        already_paged=True,
        filter_keyword=False,
        extra_meta={
            "usesJustOne": False,
            "endpoint": XHS_SEARCH_NOTES_PATH,
            **(extra_meta or {}),
        },
    )


def fetch_browser_xhs_search_payload(keyword: str, *, timeout_seconds: int = 60) -> dict[str, Any]:
    if not XHS_BROWSER_CAPTURE_HELPER.exists():
        raise XiaohongshuError(f"XHS browser capture helper not found: {XHS_BROWSER_CAPTURE_HELPER}")
    if not XHS_BROWSER_PYTHON.exists():
        raise XiaohongshuError(f"XHS browser Python not found: {XHS_BROWSER_PYTHON}")
    if not XHS_CHROME_PATH.exists():
        raise XiaohongshuError(f"Chrome not found: {XHS_CHROME_PATH}")
    keyword = clean_text(keyword)
    if not keyword:
        raise XiaohongshuError("browser_search source requires searchWord")
    request = {
        "keyword": keyword,
        "timeout_seconds": int(timeout_seconds),
        "chrome_path": str(XHS_CHROME_PATH),
        "profile_path": str(XHS_BROWSER_PROFILE),
        "search_notes_path": XHS_SEARCH_NOTES_PATH,
        "web_base": XHS_WEB_BASE,
    }
    try:
        result = subprocess.run(
            [str(XHS_BROWSER_PYTHON), str(XHS_BROWSER_CAPTURE_HELPER)],
            input=json.dumps(request, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
            timeout=max(15, int(timeout_seconds) + 15),
        )
    except subprocess.TimeoutExpired as exc:
        raise XiaohongshuError(f"浏览器搜索捕获超时: {timeout_seconds}s") from exc
    output = (result.stdout or "").strip()
    try:
        helper_payload = json.loads(output or "{}")
    except json.JSONDecodeError as exc:
        raise XiaohongshuError(f"浏览器搜索 helper 返回非 JSON: {output[:300]}") from exc
    if result.returncode != 0 or not helper_payload.get("ok"):
        raise XiaohongshuError(helper_payload.get("error") or result.stderr.strip() or "浏览器搜索 helper 失败")
    payload = helper_payload.get("payload")
    if not isinstance(payload, dict):
        raise XiaohongshuError("浏览器搜索 helper 没有返回 payload")
    return payload


def fetch_browser_xhs_hot_search(
    *,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    validate_xhs_hot_search_params(order_by, nd)
    keyword = clean_text(search_word)
    payload = fetch_browser_xhs_search_payload(keyword, timeout_seconds=timeout_seconds)
    if str(payload.get("code")) not in {"0", "None"} and not payload.get("success"):
        raise XiaohongshuError(payload.get("msg") or payload.get("message") or f"XHS browser search returned code={payload.get('code')}")
    warning = (
        "自有源来自浏览器内小红书 Web 搜索响应；无需 JustOne/Proxyman。公开搜索结果不直接暴露阅读数，"
        "readNum 仍按点赞数估算。"
    )
    response_payload = {
        "code": 0,
        "message": "success",
        "data": shape_xhs_search_notes_payload(
            payload,
            search_word=keyword,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
            source_mode="self_browser_search",
            warning=warning,
            extra_meta={"login": xhs_cookie_status(xhs_cookie())},
        ),
        "recordTime": now_iso(),
    }
    save_xhs_hot_search_cache(response_payload)
    return response_payload


def fetch_free_xhs_web_search(
    *,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
) -> dict[str, Any]:
    signed_error = ""
    try:
        return fetch_signed_xhs_hot_search(
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
        )
    except Exception as exc:
        signed_error = str(exc)
    payload = fetch_browser_xhs_hot_search(
        search_word=search_word,
        page_num=page_num,
        order_by=order_by,
        nd=nd,
    )
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
    payload["data"] = {
        **data,
        "localMeta": {
            **local_meta,
            "signed_search_error": signed_error,
        },
    }
    return payload


def normalize_xhs_trend_item(item: dict[str, Any], rank: int) -> dict[str, Any]:
    title = clean_text(
        item.get("title")
        or item.get("text")
        or item.get("query")
        or item.get("keyword")
        or item.get("word")
        or item.get("search_word")
    )
    score = item.get("score")
    if score is None:
        score = item.get("heat") or item.get("hotValue") or item.get("viewNum") or item.get("count") or ""
    return {
        "rank": rank,
        "title": title,
        "score": score,
        "searchWord": item.get("search_word") or title,
        "description": item.get("desc") or "",
        "icon": item.get("icon") or item.get("iconUrl") or "",
        "type": item.get("type") or item.get("wordType") or "",
        "id": item.get("id") or item.get("queryId") or item.get("wordRequestId") or "",
        "raw": item,
    }


def shape_xhs_hot_trends_data(payload: dict[str, Any], *, source_mode: str, cookie: str | None = None) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload, dict) else {}
    data = data if isinstance(data, dict) else {}
    candidates = (
        data.get("queries")
        or data.get("searchHotSpots")
        or data.get("searchCardHotSpots")
        or data.get("hotSpots")
        or data.get("items")
        or []
    )
    if not isinstance(candidates, list):
        candidates = []
    trend_list = [
        normalize_xhs_trend_item(item, rank)
        for rank, item in enumerate(candidates, start=1)
        if isinstance(item, dict)
    ]
    return {
        "trendList": trend_list,
        "total": len(trend_list),
        "hintWord": data.get("hintWord") or {},
        "wordRequestId": data.get("wordRequestId") or "",
        "searchCplId": data.get("searchCplId") or "",
        "localMeta": {
            "source_mode": source_mode,
            "result_type": "search_suggestions",
            "isGlobalHotSearch": False,
            "warning": "This is Xiaohongshu search-box suggestion data, not a platform-wide hot-search ranking.",
            "endpoint": "/api/sns/web/v1/search/trending/query",
            "login": xhs_cookie_status(cookie),
        },
    }


def save_xhs_hot_trends_cache(payload: dict[str, Any]) -> None:
    XHS_HOT_TRENDS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    cache_payload["cacheSavedAtEpoch"] = time.time()
    cache_payload["cacheSavedAt"] = now_iso()
    tmp_path = XHS_HOT_TRENDS_CACHE.with_suffix(f"{XHS_HOT_TRENDS_CACHE.suffix}.tmp")
    tmp_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(XHS_HOT_TRENDS_CACHE)


def load_xhs_hot_trends_cache(*, max_age_seconds: int | None = None) -> dict[str, Any] | None:
    if not XHS_HOT_TRENDS_CACHE.exists():
        return None
    try:
        payload = json.loads(XHS_HOT_TRENDS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    saved_at_epoch = payload.get("cacheSavedAtEpoch")
    age_seconds: int | None = None
    if isinstance(saved_at_epoch, (int, float)):
        age_seconds = max(0, int(time.time() - saved_at_epoch))
        if max_age_seconds is not None and age_seconds > max_age_seconds:
            return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
    response_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"cacheSavedAtEpoch", "cacheSavedAt"}
    }
    response_payload["data"] = {
        **data,
        "localMeta": {
            **local_meta,
            "cache": True,
            "cachePath": str(XHS_HOT_TRENDS_CACHE),
            "cacheSavedAt": payload.get("cacheSavedAt") or "",
            "cacheAgeSeconds": age_seconds,
        },
    }
    return response_payload


def fetch_signed_xhs_hot_trends(*, cookie: str | None = None, source: str = "Explore") -> dict[str, Any]:
    effective_cookie = xhs_cookie(cookie)
    helper_payload = run_xhs_signed_helper(
        "querytrending",
        cookie=effective_cookie,
        params={
            "source": source,
            "search_type": "trend",
            "last_query": "",
            "last_query_time": 0,
            "word_request_situation": "FIRST_ENTER",
            "hint_word": "",
            "hint_word_type": "",
            "hint_word_request_id": "",
        },
    )
    payload = helper_payload.get("payload") or {}
    if str(payload.get("code")) not in {"0", "None"} and not payload.get("success"):
        raise XiaohongshuError(payload.get("msg") or payload.get("message") or f"XHS querytrending returned code={payload.get('code')}")
    response_payload = {
        "code": 0,
        "message": "success",
        "data": shape_xhs_hot_trends_data(payload, source_mode="xhs_signed_querytrending", cookie=effective_cookie),
        "recordTime": now_iso(),
    }
    save_xhs_hot_trends_cache(response_payload)
    return response_payload


def fetch_browser_xhs_hot_trends(*, timeout_seconds: int = 60) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise XiaohongshuError(f"Playwright not available: {exc}") from exc
    if not XHS_CHROME_PATH.exists():
        raise XiaohongshuError(f"Chrome not found: {XHS_CHROME_PATH}")
    XHS_BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
    captured: dict[str, Any] = {}

    def is_trending_response(url: str) -> bool:
        return "xiaohongshu.com/api/sns/web/v1/search/trending/query" in url

    with sync_playwright() as playwright:
        launch_timeout_ms = int(max(10, min(timeout_seconds, 45)) * 1000)
        context = playwright.chromium.launch_persistent_context(
            str(XHS_BROWSER_PROFILE),
            headless=False,
            executable_path=str(XHS_CHROME_PATH),
            args=["--disable-blink-features=AutomationControlled"],
            locale="zh-CN",
            timeout=launch_timeout_ms,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()

            def on_response(response: Any) -> None:
                if captured or not is_trending_response(response.url):
                    return
                try:
                    payload = response.json()
                except Exception:
                    return
                captured["payload"] = payload
                captured["url"] = response.url

            page.on("response", on_response)
            page.goto(XHS_EXPLORE_URL, wait_until="domcontentloaded", timeout=60000)
            deadline = time.time() + timeout_seconds
            while time.time() < deadline and not captured:
                for selector in ("input.search-input", "input[placeholder*=搜索]", "input", ".input-box", ".search-input"):
                    try:
                        locator = page.locator(selector).first
                        if locator.count():
                            locator.click(timeout=3000)
                            break
                    except Exception:
                        continue
                page.wait_for_timeout(2000)
            if not captured:
                raise XiaohongshuError("浏览器登录态源未捕获到 search/trending/query 响应")
            payload = captured.get("payload") or {}
            if str(payload.get("code")) not in {"0", "1000"} and not payload.get("success"):
                raise XiaohongshuError(payload.get("msg") or payload.get("message") or f"XHS browser trending returned code={payload.get('code')}")
            data = shape_xhs_hot_trends_data(payload, source_mode="xhs_browser_signed_querytrending", cookie=xhs_cookie())
            data["localMeta"]["endpoint"] = "/api/sns/web/v1/search/trending/query"
            data["localMeta"]["requestUrl"] = captured.get("url")
            response_payload = {
                "code": 0,
                "message": "success",
                "data": data,
                "recordTime": now_iso(),
            }
            save_xhs_hot_trends_cache(response_payload)
            return response_payload
        finally:
            context.close()


def get_xhs_hot_trends(*, source: str = "auto") -> dict[str, Any]:
    if source not in {"auto", "browser", "signed", "cache"}:
        raise XiaohongshuError("source must be auto, browser, signed, or cache")
    if source == "cache":
        cached_payload = load_xhs_hot_trends_cache()
        if cached_payload:
            return cached_payload
        raise XiaohongshuError("XHS hot trends cache is empty")
    if source == "auto":
        fresh_cached_payload = load_xhs_hot_trends_cache(max_age_seconds=XHS_HOT_TRENDS_CACHE_TTL_SECONDS)
        if fresh_cached_payload:
            return fresh_cached_payload
    browser_error = ""
    if source in {"auto", "browser"}:
        try:
            return fetch_browser_xhs_hot_trends()
        except Exception as exc:
            if source == "browser":
                raise
            browser_error = str(exc)
    signed_error = ""
    try:
        payload = fetch_signed_xhs_hot_trends()
        if browser_error:
            payload.setdefault("data", {}).setdefault("localMeta", {})["browser_error"] = browser_error
        return payload
    except Exception as exc:
        signed_error = str(exc)
        cached_payload = load_xhs_hot_trends_cache()
        if cached_payload and source == "auto":
            cached_payload.setdefault("data", {}).setdefault("localMeta", {})["browser_error"] = browser_error
            cached_payload.setdefault("data", {}).setdefault("localMeta", {})["signed_error"] = signed_error
            return cached_payload
        if browser_error:
            raise XiaohongshuError(f"browser source failed: {browser_error}; signed helper failed: {signed_error}") from exc
        raise


def decode_har_response_content(content: dict[str, Any]) -> str:
    text = content.get("text", "")
    if not text:
        return ""
    if content.get("encoding") != "base64":
        return text
    raw = base64.b64decode(text)
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    return raw.decode("utf-8", "ignore")


def normalize_xhs_global_hot_keyword_item(item: dict[str, Any], rank: int) -> dict[str, Any]:
    title = clean_text(
        item.get("title")
        or item.get("text")
        or item.get("query")
        or item.get("keyword")
        or item.get("word")
        or item.get("name")
        or item.get("search_word")
        or item.get("hot_word")
    )
    score = (
        item.get("score")
        if item.get("score") is not None
        else item.get("heat")
        or item.get("hotValue")
        or item.get("hot_value")
        or item.get("viewNum")
        or item.get("count")
        or item.get("impNum")
        or item.get("readNum")
        or ""
    )
    return {
        "rank": rank,
        "title": title,
        "score": score,
        "searchWord": item.get("search_word") or item.get("keyword") or item.get("word") or title,
        "description": item.get("desc") or item.get("description") or "",
        "icon": item.get("icon") or item.get("iconUrl") or item.get("icon_url") or "",
        "type": item.get("type") or item.get("wordType") or item.get("label") or "",
        "id": item.get("id") or item.get("queryId") or item.get("wordRequestId") or "",
        "raw": item,
    }


def xhs_global_hot_list_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    containers: list[Any] = [payload]
    data = payload.get("data")
    if isinstance(data, (dict, list)):
        containers.append(data)

    list_keys = (
        "trendList",
        "trendingList",
        "hotSearchList",
        "hotWordList",
        "hotWords",
        "hotList",
        "hotlist",
        "hotQueries",
        "hot_query",
        "searchHotSpots",
        "searchCardHotSpots",
        "items",
        "list",
    )
    candidates: list[Any] = []
    for container in containers:
        if isinstance(container, list):
            candidates = container
            break
        if not isinstance(container, dict):
            continue
        for key in list_keys:
            value = container.get(key)
            if isinstance(value, list) and value:
                candidates = value
                break
        if candidates:
            break
    if not candidates:
        return []

    normalized = [
        normalize_xhs_global_hot_keyword_item(item, rank)
        for rank, item in enumerate(candidates, start=1)
        if isinstance(item, dict)
    ]
    return [item for item in normalized if item.get("title")]


def is_xhs_search_suggestion_path(path: str) -> bool:
    return path in XHS_QUERYTRENDING_PATHS or path.endswith("/search/trending/query") or path.endswith("/search/querytrending")


def is_xhs_global_hot_candidate_path(path: str) -> bool:
    lowered = path.lower()
    if is_xhs_search_suggestion_path(path):
        return False
    return any(marker in lowered for marker in ("hot", "trend", "rank", "billboard", "keyword"))


def shape_xhs_global_hot_keywords_data(
    keywords: list[dict[str, Any]],
    *,
    source_mode: str,
    endpoint: str,
    host: str = "",
    har_path: str = "",
) -> dict[str, Any]:
    return {
        "trendList": keywords,
        "total": len(keywords),
        "localMeta": {
            "source_mode": source_mode,
            "result_type": "global_hot_keywords",
            "isGlobalHotSearch": True,
            "endpoint": endpoint,
            "host": host,
            "harPath": har_path,
            "warning": "Parsed from a local Xiaohongshu App/Web_V3 HAR capture; no cookies or request headers are returned.",
        },
    }


def save_xhs_global_hot_keywords_cache(payload: dict[str, Any]) -> None:
    XHS_GLOBAL_HOT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    cache_payload["cacheSavedAtEpoch"] = time.time()
    cache_payload["cacheSavedAt"] = now_iso()
    tmp_path = XHS_GLOBAL_HOT_CACHE.with_suffix(f"{XHS_GLOBAL_HOT_CACHE.suffix}.tmp")
    tmp_path.write_text(json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(XHS_GLOBAL_HOT_CACHE)


def load_xhs_global_hot_keywords_cache() -> dict[str, Any] | None:
    if not XHS_GLOBAL_HOT_CACHE.exists():
        return None
    try:
        payload = json.loads(XHS_GLOBAL_HOT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None
    saved_at_epoch = payload.get("cacheSavedAtEpoch")
    age_seconds: int | None = None
    if isinstance(saved_at_epoch, (int, float)):
        age_seconds = max(0, int(time.time() - saved_at_epoch))
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
    response_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"cacheSavedAtEpoch", "cacheSavedAt"}
    }
    response_payload["data"] = {
        **data,
        "localMeta": {
            **local_meta,
            "cache": True,
            "cachePath": str(XHS_GLOBAL_HOT_CACHE),
            "cacheSavedAt": payload.get("cacheSavedAt") or "",
            "cacheAgeSeconds": age_seconds,
        },
    }
    return response_payload


def resolve_xhs_global_hot_har_path(har_file: str | None = None) -> Path:
    inbox = XHS_GLOBAL_HOT_HAR_INBOX.resolve()
    inbox.mkdir(parents=True, exist_ok=True)
    if not har_file:
        candidates = sorted(inbox.glob("*.har"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            raise XiaohongshuError(
                f"尚未接入真实全站热搜源：请把小红书 App/Web_V3 热搜页 HAR 放到 {XHS_GLOBAL_HOT_HAR_INBOX}"
            )
        return candidates[0]
    path = Path(har_file)
    if not path.is_absolute():
        path = inbox / path
    resolved = path.resolve()
    try:
        resolved.relative_to(inbox)
    except ValueError as exc:
        raise XiaohongshuError(f"HAR file must be inside {XHS_GLOBAL_HOT_HAR_INBOX}") from exc
    if resolved.suffix.lower() != ".har":
        raise XiaohongshuError("HAR file must end with .har")
    if not resolved.exists():
        raise XiaohongshuError(f"HAR file not found: {resolved}")
    return resolved


def fetch_har_xhs_global_hot_keywords(*, har_file: str | None = None) -> dict[str, Any]:
    har_path = resolve_xhs_global_hot_har_path(har_file)
    try:
        har = json.loads(har_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise XiaohongshuError(f"HAR JSON parse failed: {exc}") from exc
    entries = ((har.get("log") or {}).get("entries") or [])
    best: dict[str, Any] | None = None
    seen_xhs_paths: set[str] = set()
    skipped_suggestion_paths: set[str] = set()
    for entry in entries:
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        parsed = urlparse(request.get("url") or "")
        if "xiaohongshu.com" not in parsed.netloc:
            continue
        seen_xhs_paths.add(parsed.path)
        if is_xhs_search_suggestion_path(parsed.path):
            skipped_suggestion_paths.add(parsed.path)
            continue
        if not is_xhs_global_hot_candidate_path(parsed.path):
            continue
        content = decode_har_response_content(response.get("content") or {})
        if not content:
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        keywords = xhs_global_hot_list_from_payload(payload)
        if len(keywords) < 3:
            continue
        candidate = {
            "keywords": keywords,
            "host": parsed.netloc,
            "endpoint": parsed.path,
        }
        if best is None or len(keywords) > len(best["keywords"]):
            best = candidate
    if not best:
        seen = ", ".join(sorted(seen_xhs_paths)[:12])
        skipped = ", ".join(sorted(skipped_suggestion_paths))
        suffix = f"；已排除搜索建议路径: {skipped}" if skipped else ""
        raise XiaohongshuError(f"HAR 中没有找到可确认的全站热搜关键词列表；看到的小红书路径: {seen or '无'}{suffix}")
    response_payload = {
        "code": 0,
        "message": "success",
        "data": shape_xhs_global_hot_keywords_data(
            best["keywords"],
            source_mode="xhs_har_global_hot_keywords",
            endpoint=best["endpoint"],
            host=best["host"],
            har_path=str(har_path),
        ),
        "recordTime": now_iso(),
    }
    save_xhs_global_hot_keywords_cache(response_payload)
    return response_payload


def get_xhs_global_hot_keywords(*, source: str = "auto", har_file: str | None = None) -> dict[str, Any]:
    if source not in {"auto", "har", "cache"}:
        raise XiaohongshuError("source must be auto, har, or cache")
    if source == "cache":
        cached_payload = load_xhs_global_hot_keywords_cache()
        if cached_payload:
            return cached_payload
        raise XiaohongshuError("XHS global hot keywords cache is empty")
    har_error = ""
    if source in {"auto", "har"}:
        try:
            return fetch_har_xhs_global_hot_keywords(har_file=har_file)
        except Exception as exc:
            if source == "har":
                raise
            har_error = str(exc)
    cached_payload = load_xhs_global_hot_keywords_cache()
    if cached_payload:
        cached_payload.setdefault("data", {}).setdefault("localMeta", {})["har_error"] = har_error
        return cached_payload
    raise XiaohongshuError(har_error or "尚未接入真实全站热搜源")


def fetch_justone_xhs_hot_search(
    *,
    token: str,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
    timeout: int = 60,
) -> dict[str, Any]:
    validate_xhs_hot_search_params(order_by, nd)
    response = requests.get(
        f"{JUSTONE_API_BASE}{XHS_HOT_SEARCH_PATH}",
        params={
            "token": token,
            "searchWord": search_word,
            "pageNum": page_num,
            "orderBy": order_by,
            "nd": nd,
        },
        headers={"Accept": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if str(payload.get("code")) != "0":
        raise XiaohongshuError(payload.get("message") or f"Just One API returned code={payload.get('code')}")
    return payload


def get_xhs_hot_search(
    *,
    token: str | None = None,
    search_word: str = "",
    page_num: int = 1,
    order_by: str = "premium_imp_num",
    nd: str = "DAY_7",
    source: str = "auto",
) -> dict[str, Any]:
    validate_xhs_hot_search_params(order_by, nd)
    effective_token = xhs_justone_token(token)
    if source not in {"auto", "self", "web_search", "browser_search", "signed_search", "explore", "cache", "justone", "example"}:
        raise XiaohongshuError("source must be auto, self, web_search, browser_search, signed_search, explore, cache, justone, or example")
    self_error = ""
    if source == "cache":
        cached = load_xhs_hot_search_cache(
            search_word=search_word,
            order_by=order_by,
            nd=nd,
            max_age_seconds=None,
        )
        if not cached:
            raise XiaohongshuError("No cached XHS hot-search result for the requested searchWord/orderBy/nd")
        return cached
    if source == "web_search":
        cached = load_xhs_hot_search_cache(
            search_word=search_word,
            order_by=order_by,
            nd=nd,
            max_age_seconds=XHS_HOT_SEARCH_CACHE_TTL_SECONDS,
        )
        if cached:
            return cached
        try:
            return fetch_free_xhs_web_search(
                search_word=search_word,
                page_num=page_num,
                order_by=order_by,
                nd=nd,
            )
        except Exception as exc:
            cached = load_xhs_hot_search_cache(
                search_word=search_word,
                order_by=order_by,
                nd=nd,
                max_age_seconds=XHS_HOT_SEARCH_CACHE_TTL_SECONDS,
            )
            if cached:
                data = cached.get("data") if isinstance(cached.get("data"), dict) else {}
                local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
                cached["data"] = {
                    **data,
                    "localMeta": {
                        **local_meta,
                        "web_search_error": str(exc),
                    },
                }
                return cached
            raise
    if source == "browser_search":
        return fetch_browser_xhs_hot_search(
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
        )
    if source == "signed_search":
        return fetch_signed_xhs_hot_search(
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
        )
    if source == "explore":
        return fetch_self_xhs_explore_hot_search(
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
        )
    if source == "auto" and clean_text(search_word):
        cached = load_xhs_hot_search_cache(
            search_word=search_word,
            order_by=order_by,
            nd=nd,
            max_age_seconds=XHS_HOT_SEARCH_CACHE_TTL_SECONDS,
        )
        if cached:
            return cached
        try:
            return fetch_free_xhs_web_search(
                search_word=search_word,
                page_num=page_num,
                order_by=order_by,
                nd=nd,
            )
        except Exception as exc:
            self_error = str(exc)
            cached = load_xhs_hot_search_cache(
                search_word=search_word,
                order_by=order_by,
                nd=nd,
                max_age_seconds=XHS_HOT_SEARCH_CACHE_TTL_SECONDS,
            )
            if cached:
                data = cached.get("data") if isinstance(cached.get("data"), dict) else {}
                local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
                cached["data"] = {
                    **data,
                    "localMeta": {
                        **local_meta,
                        "web_search_error": self_error,
                    },
                }
                return cached
    if source in {"auto", "self"}:
        try:
            payload = fetch_self_xhs_hot_search(
                search_word=search_word,
                page_num=page_num,
                order_by=order_by,
                nd=nd,
            )
            if self_error:
                data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
                local_meta = data.get("localMeta") if isinstance(data.get("localMeta"), dict) else {}
                payload["data"] = {
                    **data,
                    "localMeta": {
                        **local_meta,
                        "web_search_error": self_error,
                    },
                }
            return payload
        except Exception as exc:
            if source == "self":
                raise
            self_error = str(exc)
    if source in {"auto", "justone"} and effective_token:
        payload = fetch_justone_xhs_hot_search(
            token=effective_token,
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
        )
        payload["data"] = shape_xhs_hot_search_data(
            payload.get("data") or {},
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
            source_mode="justone_live",
        )
        return payload
    if source == "justone":
        raise XiaohongshuError("Missing XHS_JUSTONE_TOKEN/JUSTONE_API_TOKEN")
    status = fetch_justone_status_example()
    example = status["example"]
    warning = "未配置 XHS_JUSTONE_TOKEN/JUSTONE_API_TOKEN，当前返回 Just One 公开健康检查成功样例并做本地过滤/排序。"
    if self_error:
        warning = f"自有源暂不可用，已回退到 Just One 公开健康检查成功样例；自有源错误: {self_error}"
    return {
        "code": 0,
        "message": example.get("message") or "success",
        "data": shape_xhs_hot_search_data(
            example.get("data") or {},
            search_word=search_word,
            page_num=page_num,
            order_by=order_by,
            nd=nd,
            source_mode="justone_status_example",
            warning=warning,
        ),
        "recordTime": example.get("recordTime") or status.get("checked_at") or now_iso(),
    }


def load_history_sources() -> dict[str, Any]:
    if not WECHATPUB_SOURCES_PATH.exists():
        return {"accounts": {}}
    try:
        data = json.loads(WECHATPUB_SOURCES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WechatPubError(f"History source registry is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise WechatPubError("History source registry must be a JSON object")
    accounts = data.setdefault("accounts", {})
    if not isinstance(accounts, dict):
        raise WechatPubError("History source registry accounts must be a JSON object")
    return data


def save_history_sources(data: dict[str, Any]) -> None:
    WECHATPUB_SOURCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = WECHATPUB_SOURCES_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    tmp_path.replace(WECHATPUB_SOURCES_PATH)
    os.chmod(WECHATPUB_SOURCES_PATH, 0o600)


def source_key(value: str) -> str:
    return normalize_query(value).lower()


def extract_biz_from_history_url(history_url: str) -> str:
    query = parse_qs(urlparse(history_url).query, keep_blank_values=True)
    values = query.get("__biz") or []
    return values[-1] if values else ""


def register_history_source(
    wxid: str,
    history_url: str,
    *,
    display_name: str | None = None,
    cookie: str | None = None,
) -> dict[str, Any]:
    if not history_url or "mp.weixin.qq.com/mp/profile_ext" not in history_url:
        raise WechatPubError("historyUrl must be a mp.weixin.qq.com/mp/profile_ext URL")
    biz = extract_biz_from_history_url(history_url)
    if not biz:
        raise WechatPubError("historyUrl must include __biz")
    data = load_history_sources()
    key = source_key(wxid)
    if not key:
        raise WechatPubError("wxid is required")
    record = {
        "wxid": wxid,
        "display_name": display_name or wxid,
        "__biz": biz,
        "history_url": history_url,
        "updated_at": now_iso(),
    }
    if cookie:
        record["cookie"] = cookie.strip()
    data["accounts"][key] = record
    if display_name:
        data["accounts"][source_key(display_name)] = record
    save_history_sources(data)
    return {
        key: value
        for key, value in record.items()
        if key not in {"history_url", "cookie"}
    } | {"has_history_url": True, "has_cookie": bool(record.get("cookie"))}


def find_history_source(wxid: str) -> dict[str, Any] | None:
    data = load_history_sources()
    accounts = data.get("accounts") or {}
    candidates = [wxid, normalize_query(wxid)]
    for candidate in candidates:
        record = accounts.get(source_key(candidate))
        if isinstance(record, dict):
            return record
    return None


def refresh_history_source(
    wxid: str,
    *,
    record: dict[str, Any] | None = None,
    timeout_seconds: int = HISTORY_REFRESH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if not WECHAT_HISTORY_CAPTURE.exists():
        raise WechatPubError(f"WeChat history capture helper not found: {WECHAT_HISTORY_CAPTURE}")
    command = [
        str(WECHAT_HISTORY_CAPTURE),
        "refresh",
        wxid,
        "--timeout",
        str(timeout_seconds),
        "--since-seconds",
        str(HISTORY_REFRESH_SINCE_SECONDS),
        "--file-limit",
        "1500",
    ]
    display_name = str((record or {}).get("display_name") or wxid)
    if display_name:
        command.extend(["--display-name", display_name])
    biz = str((record or {}).get("__biz") or "")
    if biz:
        command.extend(["--biz", biz])
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 20,
        )
    except subprocess.TimeoutExpired as exc:
        raise WechatPubError("微信历史源自动续期超时；请确认电脑微信已登录，并打开该公众号任意一篇文章。") from exc
    except Exception as exc:
        raise WechatPubError(f"微信历史源自动续期失败：{exc}") from exc
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if result.returncode != 0:
        message = stdout or stderr or f"exit={result.returncode}"
        raise WechatPubError(f"微信历史源自动续期失败：{message}")
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError as exc:
        raise WechatPubError("微信历史源自动续期输出不是有效 JSON") from exc
    if not payload.get("registered"):
        raise WechatPubError(payload.get("message") or "微信历史源自动续期未捕获到可用历史源")
    return payload


def fetch_wechat_history_articles_with_refresh(
    wxid: str,
    history_url: str,
    *,
    limit: int,
    cookie: str | None = None,
    record: dict[str, Any] | None = None,
    auto_refresh: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        return fetch_wechat_history_articles(history_url, limit=limit, cookie=cookie), None
    except Exception as exc:
        if not auto_refresh or not history_error_needs_refresh(exc):
            raise
        refresh_result = refresh_history_source(wxid, record=record)
        refreshed_record = find_history_source(wxid)
        if not refreshed_record or not refreshed_record.get("history_url"):
            raise WechatPubError("微信历史源已自动续期，但源库没有写入新的 historyUrl") from exc
        posts = fetch_wechat_history_articles(
            str(refreshed_record["history_url"]),
            limit=limit,
            cookie=str(refreshed_record.get("cookie") or "") or None,
        )
        return posts, refresh_result


def redacted_source_record(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {"registered": False}
    return {
        "registered": True,
        "wxid": record.get("wxid") or "",
        "display_name": record.get("display_name") or "",
        "__biz": record.get("__biz") or "",
        "updated_at": record.get("updated_at") or "",
        "has_history_url": bool(record.get("history_url")),
        "has_cookie": bool(record.get("cookie")),
    }


def read_clipboard() -> str:
    try:
        result = subprocess.run(["/usr/bin/pbpaste"], check=True, capture_output=True, text=True, timeout=5)
    except Exception as exc:
        raise WechatPubError(f"Could not read macOS clipboard: {exc}") from exc
    return result.stdout.strip()


def tencent_docs_credentials() -> dict[str, str]:
    file_values = load_env_file(TENCENT_DOCS_ENV)
    credentials = {
        "client_id": os.environ.get("TENCENT_DOCS_CLIENT_ID") or file_values.get("TENCENT_DOCS_CLIENT_ID", ""),
        "access_token": os.environ.get("TENCENT_DOCS_ACCESS_TOKEN") or file_values.get("TENCENT_DOCS_ACCESS_TOKEN", ""),
        "open_id": os.environ.get("TENCENT_DOCS_OPEN_ID") or file_values.get("TENCENT_DOCS_OPEN_ID", ""),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise TencentDocsError(f"Missing Tencent Docs credentials: {', '.join(missing)}")
    return credentials


def tencent_docs_headers(content_type: str | None = None) -> dict[str, str]:
    credentials = tencent_docs_credentials()
    headers = {
        "Access-Token": credentials["access_token"],
        "Client-Id": credentials["client_id"],
        "Open-Id": credentials["open_id"],
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def render_summary_text(manifest: dict[str, Any], *, full_content: bool = True) -> str:
    source_mode = manifest.get("source_mode") or "sogou_weixin_search"
    coverage_note = manifest.get("coverage_note") or "当前文章发现来源为公开搜狗微信搜索，不保证等同于单一公众号后台的严格时间线。"
    lines = [
        f"{manifest.get('query') or '公众号文章'}文章采集汇总",
        "",
        f"采集时间: {manifest.get('collected_at') or ''}",
        f"请求数量: {manifest.get('limit') or ''}",
        f"返回数量: {manifest.get('count') or 0}",
        f"本地目录: {manifest.get('out') or ''}",
        f"来源模式: {source_mode}",
        "",
        f"重要说明: {coverage_note}",
        "",
    ]
    for idx, item in enumerate(manifest.get("articles", []), start=1):
        post = item.get("post") or {}
        detail = item.get("detail") or {}
        title = detail.get("title") or post.get("title") or f"文章 {idx}"
        url = detail.get("final_url") or detail.get("url") or post.get("url") or ""
        account = detail.get("account_name") or post.get("source_name") or ""
        publish_time = detail.get("publish_time") or post.get("publish_time") or ""
        summary = detail.get("description") or post.get("summary") or ""
        content = (detail.get("markdown") or clean_text(detail.get("content_text") or "")).strip()
        body = content if full_content else content[:1200] + ("..." if len(content) > 1200 else "")
        lines.extend(
            [
                f"{idx}. {title}",
                f"公众号: {account}",
                f"发布时间: {publish_time}",
                f"原文: {url}",
                f"摘要: {summary}",
                "",
            ]
        )
        if body:
            lines.extend(["正文全文:" if full_content else "正文摘录:", body, ""])
        if not item.get("ok", False):
            lines.extend([f"采集状态: 失败，原因: {item.get('error') or ''}", ""])
    return "\n".join(lines).strip() + "\n"


def write_summary(out_dir: Path, manifest: dict[str, Any], *, full_content: bool = True) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_text = render_summary_text(manifest, full_content=full_content)
    summary_path = out_dir / "公众号文章采集汇总.txt"
    summary_path.write_text(summary_text, encoding="utf-8")
    return {"summary_txt": str(summary_path)}


def import_file_to_tencent_doc(file_path: Path, *, title: str | None = None, parentfolder_id: str | None = None) -> dict[str, Any]:
    if not file_path.exists():
        raise TencentDocsError(f"File not found: {file_path}")
    blob = file_path.read_bytes()
    file_md5 = hashlib.md5(blob).hexdigest()
    file_name = file_path.name
    headers = tencent_docs_headers("application/x-www-form-urlencoded")
    pre = requests.post(
        "https://docs.qq.com/openapi/drive/v2/files/upload",
        headers=headers,
        data={"fileMD5": file_md5, "fileName": file_name, "fileSize": str(len(blob))},
        timeout=30,
    )
    pre.raise_for_status()
    pre_data = pre.json()
    if pre_data.get("ret") != 0:
        raise TencentDocsError(f"Tencent Docs pre-import failed: {pre_data.get('msg') or pre_data}")
    cos = pre_data.get("data") or {}
    put = requests.put(cos["COSPutURL"], data=blob, headers=cos.get("CustomHeader") or {}, timeout=60)
    put.raise_for_status()
    import_payload = {"fileMD5": file_md5, "fileName": file_name, "COSFileKey": cos["COSFileKey"]}
    if parentfolder_id:
        import_payload["parentfolderID"] = parentfolder_id
    imported = requests.post(
        "https://docs.qq.com/openapi/drive/v2/files/async-import",
        headers=headers,
        data=import_payload,
        timeout=30,
    )
    imported.raise_for_status()
    import_data = imported.json()
    if import_data.get("ret") != 0:
        raise TencentDocsError(f"Tencent Docs async import failed: {import_data.get('msg') or import_data}")
    query_id = (import_data.get("data") or {}).get("progressQueryID")
    if not query_id:
        raise TencentDocsError("Tencent Docs async import did not return progressQueryID")
    poll_headers = tencent_docs_headers()
    final: dict[str, Any] = {}
    for _ in range(30):
        time.sleep(2)
        progress = requests.get(
            "https://docs.qq.com/openapi/drive/v2/files/import-progress",
            headers=poll_headers,
            params={"progressQueryID": query_id},
            timeout=30,
        )
        progress.raise_for_status()
        final = progress.json()
        data = final.get("data") or {}
        if data.get("progress") == 100 or data.get("url"):
            break
    if final.get("ret") != 0:
        raise TencentDocsError(f"Tencent Docs import progress failed: {final.get('msg') or final}")
    data = final.get("data") or {}
    if not data.get("url"):
        raise TencentDocsError("Tencent Docs import did not finish before timeout")
    result = {
        "id": data.get("ID"),
        "title": title or data.get("title"),
        "type": data.get("type"),
        "url": data.get("url"),
        "progress": data.get("progress"),
        "imported_at": now_iso(),
    }
    return result


def collect(
    query: str,
    out: Path,
    limit: int,
    exact_account: str | None = None,
    *,
    strict_recent: bool = True,
    source: str = "search",
    history_url: str | None = None,
    auto_refresh: bool = True,
) -> dict[str, Any]:
    normalized_query = normalize_query(query)
    posts, source_meta = get_article_posts(
        normalized_query,
        limit=limit,
        exact_account=exact_account,
        source=source,
        history_url=history_url,
        strict_recent=strict_recent,
        auto_refresh=auto_refresh,
    )
    out.mkdir(parents=True, exist_ok=True)
    articles = []
    for idx, post in enumerate(posts, start=1):
        try:
            detail = extract_article_detail(post["url"])
            detail["search"] = post
            paths = write_article(out, idx, detail)
            articles.append({"post": post, "detail": detail, "paths": paths, "ok": True})
        except Exception as exc:
            articles.append({"post": post, "ok": False, "error": str(exc)})
    manifest = {
        "query": normalized_query,
        "raw_query": query,
        "exact_account": exact_account,
        "limit": limit,
        "count": len(articles),
        "out": str(out),
        **source_meta,
        "collected_at": now_iso(),
        "articles": articles,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def collect_to_tencent_doc(
    query: str,
    out: Path,
    limit: int,
    exact_account: str | None = None,
    parentfolder_id: str | None = None,
    strict_recent: bool = True,
    source: str = "search",
    history_url: str | None = None,
    auto_refresh: bool = True,
) -> dict[str, Any]:
    manifest = collect(
        query,
        out,
        limit,
        exact_account,
        strict_recent=strict_recent,
        source=source,
        history_url=history_url,
        auto_refresh=auto_refresh,
    )
    summary_paths = write_summary(out, manifest, full_content=True)
    title = f"{manifest.get('query') or query} 公众号文章采集汇总 {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    doc = import_file_to_tencent_doc(Path(summary_paths["summary_txt"]), title=title, parentfolder_id=parentfolder_id)
    manifest["summary_paths"] = summary_paths
    manifest["tencent_doc"] = doc
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


app = FastAPI(title="WechatPub API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "wechatpub-api", "time": now_iso()}


@app.get("/api/xiaohongshu/hot-search/v1")
def api_xhs_hot_search(
    token: Optional[str] = Query(None, description="Just One token; only used with source=justone or auto fallback"),
    searchWord: str = Query("", description="搜索关键词"),
    pageNum: int = Query(1, ge=1),
    orderBy: str = Query("premium_imp_num", description="排序指标"),
    nd: str = Query("DAY_7", description="时间范围：DAY_3/DAY_7/DAY_14/DAY_30"),
    source: str = Query("auto", description="auto, web_search, browser_search, signed_search, self/explore, cache, justone, or example"),
) -> JSONResponse:
    try:
        payload = get_xhs_hot_search(
            token=token,
            search_word=searchWord,
            page_num=pageNum,
            order_by=orderBy,
            nd=nd,
            source=source,
        )
        return JSONResponse(payload)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/xiaohongshu/hot-trends/v1")
def api_xhs_hot_trends(
    token: Optional[str] = Query(None, description="Optional local API token"),
    source: str = Query("auto", description="auto, browser, signed, or cache"),
) -> JSONResponse:
    try:
        validate_token(token)
        payload = get_xhs_hot_trends(source=source)
        return JSONResponse(payload)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/xiaohongshu/global-hot-keywords/v1")
def api_xhs_global_hot_keywords(
    token: Optional[str] = Query(None, description="Optional local API token"),
    source: str = Query("auto", description="auto, har, or cache"),
    harFile: Optional[str] = Query(None, description="HAR filename inside the configured XHS hot HAR inbox"),
) -> JSONResponse:
    try:
        validate_token(token)
        payload = get_xhs_global_hot_keywords(source=source, har_file=harFile)
        return JSONResponse(payload)
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/xiaohongshu/source-status/v1")
def api_xhs_source_status(
    token: Optional[str] = Query(None, description="Optional local API token"),
) -> JSONResponse:
    try:
        validate_token(token)
        XHS_GLOBAL_HOT_HAR_INBOX.mkdir(parents=True, exist_ok=True)
        har_files = sorted(XHS_GLOBAL_HOT_HAR_INBOX.glob("*.har"), key=lambda path: path.stat().st_mtime, reverse=True)
        return api_response(
            {
                "signed_helper": XHS_SIGNED_HELPER.exists(),
                "signed_python": XHS_SIGNED_PYTHON.exists(),
                "cookie": xhs_cookie_status(),
                "global_hot_keywords": {
                    "cache_exists": XHS_GLOBAL_HOT_CACHE.exists(),
                    "cache_path": str(XHS_GLOBAL_HOT_CACHE),
                    "har_inbox": str(XHS_GLOBAL_HOT_HAR_INBOX),
                    "har_count": len(har_files),
                    "latest_har": str(har_files[0]) if har_files else "",
                },
            }
        )
    except Exception as exc:
        raise api_error(exc)


@app.get("/api/weixin/get-user-post/v1")
def api_get_user_post(
    wxid: str = Query(..., description="Public account id/name or search query"),
    token: Optional[str] = Query(None, description="Optional local API token"),
    limit: int = Query(30, ge=1, le=100),
    exactAccount: Optional[str] = Query(None, description="Optional exact/contains account display-name filter"),
    historyUrl: Optional[str] = Query(None, description="WeChat profile_ext history URL with login/session query"),
    source: str = Query("auto", description="auto or history. Search is only available at /api/weixin/search/v1"),
    autoRefresh: bool = Query(True, description="Auto-refresh expired WeChat client session source once"),
) -> JSONResponse:
    try:
        validate_token(token)
        if source == "search":
            raise WechatPubError("get-user-post 是精确公众号历史列表接口，不允许 source=search；公开搜索请调用 /api/weixin/search/v1。")
        record = find_history_source(wxid)
        resolved_history_url = historyUrl or (str(record["history_url"]) if record and record.get("history_url") else "")
        if not resolved_history_url:
            raise WechatPubError("精确公众号历史列表必须先注册 historyUrl；公开搜索请调用 /api/weixin/search/v1。")
        history_cookie = str(record.get("cookie") or "") if record else None
        data, _refresh = fetch_wechat_history_articles_with_refresh(
            wxid,
            resolved_history_url,
            limit=limit,
            cookie=history_cookie,
            record=record,
            auto_refresh=autoRefresh and bool(record),
        )
        return api_response(data)
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc)


@app.get("/api/weixin/search/v1")
def api_search(
    keyword: str = Query(..., description="Search keyword"),
    token: Optional[str] = Query(None, description="Optional local API token"),
    offset: int = Query(0, ge=0),
    searchType: str = Query("_0"),
    sortType: str = Query("_0"),
    limit: int = Query(20, ge=1, le=100),
) -> JSONResponse:
    try:
        validate_token(token)
        results = search_sogou_articles(
            keyword,
            limit=limit + offset,
            resolve=True,
        )
        data = results[offset: offset + limit] if offset else results
        return api_response(
            {
                "items": data,
                "offset": offset,
                "searchType": searchType,
                "sortType": sortType,
                "source_mode": "sogou_weixin_search",
                "is_chronological_timeline": False,
            }
        )
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc)


@app.get("/api/weixin/register-source/v1")
def api_register_source(
    wxid: str = Query(...),
    historyUrl: str = Query(...),
    token: Optional[str] = Query(None),
    displayName: Optional[str] = Query(None),
) -> JSONResponse:
    try:
        validate_token(token)
        return api_response(register_history_source(wxid, historyUrl, display_name=displayName))
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc, code=400, status_code=400)


@app.get("/api/weixin/register-source-from-clipboard/v1")
def api_register_source_from_clipboard(
    wxid: str = Query(...),
    token: Optional[str] = Query(None),
    displayName: Optional[str] = Query(None),
) -> JSONResponse:
    try:
        validate_token(token)
        return api_response(register_history_source(wxid, read_clipboard(), display_name=displayName))
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc, code=400, status_code=400)


@app.get("/api/weixin/source-status/v1")
def api_source_status(
    wxid: str = Query(...),
    token: Optional[str] = Query(None),
) -> JSONResponse:
    try:
        validate_token(token)
        return api_response(redacted_source_record(find_history_source(wxid)))
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc)


@app.get("/api/weixin/get-article-detail/v1")
def api_get_article_detail(articleUrl: str = Query(...), token: Optional[str] = Query(None)) -> JSONResponse:
    try:
        validate_token(token)
        return api_response(extract_article_detail(articleUrl))
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc)


@app.get("/api/weixin/collect/v1")
def api_collect(
    wxid: str = Query(...),
    token: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    exactAccount: Optional[str] = None,
    out: Optional[str] = None,
    strictRecent: bool = Query(True, description="Fail instead of using search results when true recent timeline is required"),
    source: str = Query("auto", description="auto, search, or history"),
    historyUrl: Optional[str] = Query(None, description="WeChat profile_ext history URL with login/session query"),
    autoRefresh: bool = Query(True, description="Auto-refresh expired WeChat client session source once"),
) -> JSONResponse:
    target = Path(out) if out else DEFAULT_OUT / safe_slug(wxid) / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        validate_token(token)
        data = collect(
            wxid,
            target,
            limit,
            exactAccount,
            strict_recent=strictRecent,
            source=source,
            history_url=historyUrl,
            auto_refresh=autoRefresh,
        )
        return api_response(data)
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc)


@app.get("/api/weixin/collect-to-tencent-doc/v1")
def api_collect_to_tencent_doc(
    wxid: str = Query(...),
    token: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    exactAccount: Optional[str] = None,
    out: Optional[str] = None,
    parentfolderID: Optional[str] = None,
    strictRecent: bool = Query(True, description="Fail instead of publishing search results when true recent timeline is required"),
    source: str = Query("auto", description="auto, search, or history"),
    historyUrl: Optional[str] = Query(None, description="WeChat profile_ext history URL with login/session query"),
    autoRefresh: bool = Query(True, description="Auto-refresh expired WeChat client session source once"),
) -> JSONResponse:
    target = Path(out) if out else DEFAULT_OUT / safe_slug(wxid) / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        validate_token(token)
        data = collect_to_tencent_doc(
            wxid,
            target,
            limit,
            exactAccount,
            parentfolderID,
            strict_recent=strictRecent,
            source=source,
            history_url=historyUrl,
            auto_refresh=autoRefresh,
        )
        return api_response(data)
    except Exception as exc:
        if "Token 无效" in str(exc):
            raise api_error(exc, code=100, status_code=401)
        raise api_error(exc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Self-hosted WeChat public-account article collector")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18831)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=30)
    search.add_argument("--exact-account")
    search.add_argument("--no-resolve", action="store_true")
    search.add_argument("--source", choices=["search", "history"], default="search")
    search.add_argument("--history-url")
    search.add_argument("--no-auto-refresh", action="store_true")

    register_source = sub.add_parser("register-source")
    register_source.add_argument("wxid")
    register_source.add_argument("--history-url")
    register_source.add_argument("--from-clipboard", action="store_true")
    register_source.add_argument("--display-name")

    source_status = sub.add_parser("source-status")
    source_status.add_argument("wxid")

    xhs_hot = sub.add_parser("xhs-hot-search")
    xhs_hot.add_argument("--token")
    xhs_hot.add_argument("--search-word", default="")
    xhs_hot.add_argument("--page-num", type=int, default=1)
    xhs_hot.add_argument("--order-by", default="premium_imp_num", choices=sorted(XHS_ORDER_BY_FIELDS))
    xhs_hot.add_argument("--nd", default="DAY_7", choices=sorted(XHS_TIME_RANGES))
    xhs_hot.add_argument(
        "--source",
        default="auto",
        choices=["auto", "web_search", "browser_search", "signed_search", "self", "explore", "cache", "justone", "example"],
    )

    xhs_trends = sub.add_parser("xhs-hot-trends")
    xhs_trends.add_argument("--source", default="auto", choices=["auto", "browser", "signed", "cache"])

    xhs_global_hot = sub.add_parser("xhs-global-hot-keywords")
    xhs_global_hot.add_argument("--source", default="auto", choices=["auto", "har", "cache"])
    xhs_global_hot.add_argument("--har-file", help="HAR filename inside /Users/lulu/AIWork/xhs-hot-har-inbox")

    xhs_status = sub.add_parser("xhs-source-status")

    xhs_login = sub.add_parser("xhs-login-capture")
    xhs_login.add_argument("--timeout", type=int, default=180)
    xhs_login.add_argument("--user-data-dir", default="/Users/lulu/.config/carrie-secrets/xhs-browser-profile")

    detail = sub.add_parser("detail")
    detail.add_argument("url")
    detail.add_argument("--out")

    collect_cmd = sub.add_parser("collect")
    collect_cmd.add_argument("query")
    collect_cmd.add_argument("--limit", type=int, default=30)
    collect_cmd.add_argument("--exact-account")
    collect_cmd.add_argument("--out")
    collect_cmd.add_argument("--strict-recent", action="store_true")
    collect_cmd.add_argument("--allow-search", action="store_true", help="Allow Sogou search results for non-recent discovery")
    collect_cmd.add_argument("--source", choices=["auto", "search", "history"], default="auto")
    collect_cmd.add_argument("--history-url")
    collect_cmd.add_argument("--no-auto-refresh", action="store_true")

    collect_doc_cmd = sub.add_parser("collect-doc")
    collect_doc_cmd.add_argument("query")
    collect_doc_cmd.add_argument("--limit", type=int, default=30)
    collect_doc_cmd.add_argument("--exact-account")
    collect_doc_cmd.add_argument("--out")
    collect_doc_cmd.add_argument("--parentfolder-id")
    collect_doc_cmd.add_argument("--strict-recent", action="store_true")
    collect_doc_cmd.add_argument("--allow-search", action="store_true", help="Allow Sogou search results for non-recent discovery")
    collect_doc_cmd.add_argument("--source", choices=["auto", "search", "history"], default="auto")
    collect_doc_cmd.add_argument("--history-url")
    collect_doc_cmd.add_argument("--no-auto-refresh", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "serve":
        import uvicorn

        uvicorn.run("wechatpub_api:app", host=args.host, port=args.port, reload=False)
        return 0
    if args.cmd == "search":
        if args.source == "history" or args.history_url:
            record = find_history_source(args.query)
            history_url = args.history_url or (str(record["history_url"]) if record and record.get("history_url") else args.query)
            cookie = str(record.get("cookie") or "") if record else None
            data, _refresh = fetch_wechat_history_articles_with_refresh(
                args.query,
                history_url,
                limit=args.limit,
                cookie=cookie,
                record=record,
                auto_refresh=not args.no_auto_refresh and bool(record),
            )
            print(json.dumps({"code": 0, "data": data}, ensure_ascii=False, indent=2))
            return 0
        print(
            json.dumps(
                {
                    "code": 0,
                    "data": search_sogou_articles(
                        args.query,
                        limit=args.limit,
                        exact_account=args.exact_account,
                        resolve=not args.no_resolve,
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.cmd == "detail":
        article = extract_article_detail(args.url)
        if args.out:
            paths = write_article(Path(args.out), 1, article)
            article["paths"] = paths
        print(json.dumps({"code": 0, "data": article}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "register-source":
        history_url = read_clipboard() if args.from_clipboard else args.history_url
        if not history_url:
            raise WechatPubError("register-source requires --history-url or --from-clipboard")
        data = register_history_source(args.wxid, history_url, display_name=args.display_name)
        print(json.dumps({"code": 0, "message": "success", "data": data}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "source-status":
        data = redacted_source_record(find_history_source(args.wxid))
        print(json.dumps({"code": 0, "message": "success", "data": data}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "xhs-hot-search":
        data = get_xhs_hot_search(
            token=args.token,
            search_word=args.search_word,
            page_num=args.page_num,
            order_by=args.order_by,
            nd=args.nd,
            source=args.source,
        )
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "xhs-hot-trends":
        data = get_xhs_hot_trends(source=args.source)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "xhs-global-hot-keywords":
        try:
            data = get_xhs_global_hot_keywords(source=args.source, har_file=args.har_file)
        except Exception as exc:
            print(json.dumps({"code": 301, "message": str(exc), "data": None}, ensure_ascii=False, indent=2))
            return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "xhs-source-status":
        XHS_GLOBAL_HOT_HAR_INBOX.mkdir(parents=True, exist_ok=True)
        har_files = sorted(XHS_GLOBAL_HOT_HAR_INBOX.glob("*.har"), key=lambda path: path.stat().st_mtime, reverse=True)
        print(
            json.dumps(
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "signed_helper": XHS_SIGNED_HELPER.exists(),
                        "signed_python": XHS_SIGNED_PYTHON.exists(),
                        "cookie": xhs_cookie_status(),
                        "global_hot_keywords": {
                            "cache_exists": XHS_GLOBAL_HOT_CACHE.exists(),
                            "cache_path": str(XHS_GLOBAL_HOT_CACHE),
                            "har_inbox": str(XHS_GLOBAL_HOT_HAR_INBOX),
                            "har_count": len(har_files),
                            "latest_har": str(har_files[0]) if har_files else "",
                        },
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.cmd == "xhs-login-capture":
        data = capture_xhs_cookie_from_browser(timeout_seconds=args.timeout, user_data_dir=args.user_data_dir)
        print(json.dumps({"code": 0, "message": "success", "data": data}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "collect":
        target = Path(args.out) if args.out else DEFAULT_OUT / safe_slug(args.query) / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        data = collect(
            args.query,
            target,
            args.limit,
            args.exact_account,
            strict_recent=args.strict_recent or not args.allow_search,
            source=args.source,
            history_url=args.history_url,
            auto_refresh=not args.no_auto_refresh,
        )
        print(json.dumps({"code": 0, "data": data}, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "collect-doc":
        target = Path(args.out) if args.out else DEFAULT_OUT / safe_slug(args.query) / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        data = collect_to_tencent_doc(
            args.query,
            target,
            args.limit,
            args.exact_account,
            args.parentfolder_id,
            strict_recent=args.strict_recent or not args.allow_search,
            source=args.source,
            history_url=args.history_url,
            auto_refresh=not args.no_auto_refresh,
        )
        print(json.dumps({"code": 0, "data": data}, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
