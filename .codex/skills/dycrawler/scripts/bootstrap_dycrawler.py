#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path


MEDIA_REPO_URL = "https://github.com/NanmiCoder/MediaCrawler.git"
LOCAL_FALLBACK_REPO = Path("/Users/lulu/AIWork/MediaCrawler")
DEFAULT_PORT = 9222


PATCHED_GET_AWEME_ALL_COMMENTS = '''    async def get_aweme_all_comments(
        self,
        aweme_id: str,
        crawl_interval: float = 1.0,
        is_fetch_sub_comments=False,
        callback: Optional[Callable] = None,
        max_count: int = 10,
    ):
        """
        获取帖子的所有评论，包括子评论
        :param aweme_id: 帖子ID
        :param crawl_interval: 抓取间隔
        :param is_fetch_sub_comments: 是否抓取子评论
        :param callback: 回调函数，用于处理抓取到的评论
        :param max_count: 一次帖子爬取的最大评论数量
        :return: 评论列表
        """
        result = []
        comments_has_more = 1
        comments_cursor = 0
        top_level_count = 0
        sub_comment_count = 0
        while comments_has_more and len(result) < max_count:
            current_cursor = comments_cursor
            comments_res = await self.get_aweme_comments(aweme_id, comments_cursor)
            comments_has_more = comments_res.get("has_more", 0)
            comments_cursor = comments_res.get("cursor", 0)
            comments = comments_res.get("comments", [])
            if not comments:
                utils.logger.warning(
                    f"[DouYinClient.get_aweme_all_comments] aweme_id:{aweme_id} "
                    f"empty top-level comments page, cursor:{current_cursor}, "
                    f"next_cursor:{comments_cursor}, has_more:{comments_has_more}"
                )
                break
            if len(result) + len(comments) > max_count:
                comments = comments[:max_count - len(result)]
            result.extend(comments)
            top_level_count += len(comments)
            utils.logger.info(
                f"[DouYinClient.get_aweme_all_comments] aweme_id:{aweme_id} "
                f"top-level page count:{len(comments)}, total_top:{top_level_count}, "
                f"cursor:{current_cursor}, next_cursor:{comments_cursor}, "
                f"has_more:{comments_has_more}"
            )
            if callback:  # If there is a callback function, execute the callback function
                await callback(aweme_id, comments)

            await asyncio.sleep(crawl_interval)
            if not is_fetch_sub_comments:
                continue
            # Get secondary reviews
            for comment in comments:
                reply_comment_total = comment.get("reply_comment_total")

                if reply_comment_total > 0:
                    comment_id = comment.get("cid")
                    sub_comments_has_more = 1
                    sub_comments_cursor = 0

                    while sub_comments_has_more:
                        current_sub_cursor = sub_comments_cursor
                        sub_comments_res = await self.get_sub_comments(aweme_id, comment_id, sub_comments_cursor)
                        sub_comments_has_more = sub_comments_res.get("has_more", 0)
                        sub_comments_cursor = sub_comments_res.get("cursor", 0)
                        sub_comments = sub_comments_res.get("comments", [])

                        if not sub_comments:
                            utils.logger.warning(
                                f"[DouYinClient.get_aweme_all_comments] aweme_id:{aweme_id} "
                                f"empty sub-comments page, comment_id:{comment_id}, "
                                f"cursor:{current_sub_cursor}, next_cursor:{sub_comments_cursor}, "
                                f"has_more:{sub_comments_has_more}"
                            )
                            break
                        result.extend(sub_comments)
                        sub_comment_count += len(sub_comments)
                        utils.logger.info(
                            f"[DouYinClient.get_aweme_all_comments] aweme_id:{aweme_id} "
                            f"sub-comments page count:{len(sub_comments)}, total_sub:{sub_comment_count}, "
                            f"comment_id:{comment_id}, cursor:{current_sub_cursor}, "
                            f"next_cursor:{sub_comments_cursor}, has_more:{sub_comments_has_more}"
                        )
                        if callback:  # If there is a callback function, execute the callback function
                            await callback(aweme_id, sub_comments)
                        await asyncio.sleep(crawl_interval)
        utils.logger.info(
            f"[DouYinClient.get_aweme_all_comments] aweme_id:{aweme_id} finished, "
            f"top_level_count:{top_level_count}, sub_comment_count:{sub_comment_count}, "
            f"total:{len(result)}, has_more:{comments_has_more}, cursor:{comments_cursor}"
        )
        return result
'''


def is_mediacrawler_repo(path: Path) -> bool:
    return (path / "main.py").exists() and (path / "pyproject.toml").exists()


def discover_mediacrawler_dir(cli_value: str, install_dir: Path) -> Path:
    if cli_value:
        return Path(cli_value).expanduser().resolve()

    env_value = os.environ.get("MEDIACRAWLER_DIR", "")
    if env_value:
        return Path(env_value).expanduser().resolve()

    candidates = [
        Path.cwd(),
        Path.cwd() / "MediaCrawler",
        install_dir / "MediaCrawler",
        Path(__file__).resolve().parents[3] / "MediaCrawler",
        LOCAL_FALLBACK_REPO,
    ]
    for candidate in candidates:
        if is_mediacrawler_repo(candidate):
            return candidate.resolve()

    return (install_dir / "MediaCrawler").resolve()


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def status(label: str, ok: bool, detail: str = "") -> bool:
    marker = "OK" if ok else "MISSING"
    suffix = f" - {detail}" if detail else ""
    print(f"[{marker}] {label}{suffix}")
    return ok


def uv_install_instructions() -> str:
    return "\n".join(
        [
            "Install uv first:",
            "  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh",
            '  Windows PowerShell: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"',
            "Then restart the terminal and run this bootstrap again.",
        ]
    )


def chrome_launch_commands(port: int) -> str:
    system = platform.system()
    user_data = "$HOME/.dycrawler-chrome-profile"
    if system == "Darwin":
        return (
            'macOS:\n'
            f'  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" '
            f'--remote-debugging-port={port} --user-data-dir="{user_data}"'
        )
    if system == "Windows":
        return (
            "Windows PowerShell:\n"
            f'  Start-Process "$Env:ProgramFiles\\Google\\Chrome\\Application\\chrome.exe" '
            f'-ArgumentList "--remote-debugging-port={port} --user-data-dir=$Env:USERPROFILE\\.dycrawler-chrome-profile"'
        )
    return (
        "Linux:\n"
        f'  google-chrome --remote-debugging-port={port} --user-data-dir="{user_data}"'
    )


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def cdp_version(port: int) -> str:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2) as response:
            return response.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        return ""


def patch_present(repo: Path) -> bool:
    core = repo / "media_platform/douyin/core.py"
    client = repo / "media_platform/douyin/client.py"
    if not core.exists() or not client.exists():
        return False
    core_text = core.read_text(encoding="utf-8")
    client_text = client.read_text(encoding="utf-8")
    return all(
        [
            "await asyncio.gather(*task_list)" in core_text,
            "unexpected comment crawl error" in core_text,
            "top_level_count" in client_text,
            "sub_comment_count" in client_text,
            "empty top-level comments page" in client_text,
            "finished, " in client_text and "top_level_count" in client_text,
        ]
    )


def write_backup(path: Path, original: str) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".dycrawler.bak.{timestamp}")
    backup.write_text(original, encoding="utf-8")
    print(f"[OK] backup written: {backup}")


def patch_core(repo: Path) -> bool:
    path = repo / "media_platform/douyin/core.py"
    original = path.read_text(encoding="utf-8")
    text = original
    text = text.replace("await asyncio.wait(task_list)", "await asyncio.gather(*task_list)")

    if "unexpected comment crawl error" not in text:
        old = (
            '            except DataFetchError as e:\n'
            '                utils.logger.error(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} get comments failed, error: {e}")\n'
        )
        new = (
            '            except DataFetchError as e:\n'
            '                utils.logger.error(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} get comments failed, error: {e}")\n'
            '                raise\n'
            '            except Exception as e:\n'
            '                utils.logger.error(f"[DouYinCrawler.get_comments] aweme_id: {aweme_id} unexpected comment crawl error: {e}")\n'
            '                raise\n'
        )
        if old not in text:
            raise RuntimeError(f"Could not patch DataFetchError block in {path}")
        text = text.replace(old, new)

    if text == original:
        return False
    write_backup(path, original)
    path.write_text(text, encoding="utf-8")
    return True


def patch_client(repo: Path) -> bool:
    path = repo / "media_platform/douyin/client.py"
    original = path.read_text(encoding="utf-8")
    if "finished, top_level_count" in original and "empty top-level comments page" in original:
        return False

    start = original.find("    async def get_aweme_all_comments(")
    end = original.find("\n    async def get_user_info", start)
    if start < 0 or end < 0:
        raise RuntimeError(f"Could not locate get_aweme_all_comments in {path}")

    text = original[:start] + PATCHED_GET_AWEME_ALL_COMMENTS + original[end:]
    write_backup(path, original)
    path.write_text(text, encoding="utf-8")
    return True


def apply_patch(repo: Path) -> None:
    if not is_mediacrawler_repo(repo):
        raise SystemExit(f"MediaCrawler repo not found: {repo}")
    changed_core = patch_core(repo)
    changed_client = patch_client(repo)
    if changed_core or changed_client:
        print("[OK] Douyin reliability patch applied.")
    else:
        print("[OK] Douyin reliability patch already present.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap dycrawler dependencies for MediaCrawler Douyin comment crawling.")
    parser.add_argument("--install-dir", default=str(Path.home() / "AIWork"), help="Parent directory used when cloning MediaCrawler.")
    parser.add_argument("--mediacrawler-dir", default="", help="Existing or target MediaCrawler directory.")
    parser.add_argument("--clone", action="store_true", help="Clone MediaCrawler if it is missing.")
    parser.add_argument("--sync", action="store_true", help="Run uv sync in MediaCrawler.")
    parser.add_argument("--apply-patch", action="store_true", help="Apply dycrawler's Douyin comment reliability patch.")
    parser.add_argument("--all", action="store_true", help="Equivalent to --clone --sync --apply-patch.")
    parser.add_argument("--cdp-port", type=int, default=DEFAULT_PORT, help="Chrome DevTools Protocol port.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.all:
        args.clone = True
        args.sync = True
        args.apply_patch = True

    install_dir = Path(args.install_dir).expanduser().resolve()
    repo = discover_mediacrawler_dir(args.mediacrawler_dir, install_dir)

    print("dycrawler bootstrap")
    print(f"MediaCrawler target: {repo}")

    git_ok = status("git", command_exists("git"))
    uv_ok = status("uv", command_exists("uv"))
    status("python", True, sys.executable)

    if not uv_ok:
        print(uv_install_instructions())

    if not is_mediacrawler_repo(repo):
        status("MediaCrawler repo", False, str(repo))
        if args.clone:
            if not git_ok:
                raise SystemExit("git is required to clone MediaCrawler.")
            repo.parent.mkdir(parents=True, exist_ok=True)
            run(["git", "clone", MEDIA_REPO_URL, str(repo)])
        else:
            print(f"To clone: git clone {MEDIA_REPO_URL} {repo}")
    else:
        status("MediaCrawler repo", True, str(repo))

    if is_mediacrawler_repo(repo) and args.sync:
        if not uv_ok:
            raise SystemExit("uv is required before running uv sync.")
        run(["uv", "sync"], cwd=repo)

    if is_mediacrawler_repo(repo):
        has_patch = patch_present(repo)
        if args.apply_patch and not has_patch:
            apply_patch(repo)
            has_patch = patch_present(repo)
        status("Douyin reliability patch", has_patch)
        if not has_patch:
            print("To patch: python3 scripts/bootstrap_dycrawler.py --apply-patch --mediacrawler-dir " + str(repo))

    port_open = is_port_open("127.0.0.1", args.cdp_port)
    status(f"Chrome CDP 127.0.0.1:{args.cdp_port}", port_open)
    if port_open:
        version = cdp_version(args.cdp_port)
        if version:
            print("[OK] CDP /json/version responded.")
    else:
        print(chrome_launch_commands(args.cdp_port))

    print("Manual step: open Douyin in that Chrome profile, finish login/verification, then run the crawl script.")


if __name__ == "__main__":
    main()
