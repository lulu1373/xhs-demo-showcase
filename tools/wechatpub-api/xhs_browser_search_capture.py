#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote


def capture_search_notes(request: dict[str, Any]) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    keyword = str(request.get("keyword") or "").strip()
    if not keyword:
        raise ValueError("keyword is required")
    timeout_seconds = int(request.get("timeout_seconds") or 60)
    chrome_path = Path(str(request.get("chrome_path") or ""))
    profile_path = Path(str(request.get("profile_path") or ""))
    search_notes_path = str(request.get("search_notes_path") or "/api/sns/web/v1/search/notes")
    web_base = str(request.get("web_base") or "https://www.xiaohongshu.com").rstrip("/")
    if not chrome_path.exists():
        raise ValueError(f"Chrome not found: {chrome_path}")
    profile_path.mkdir(parents=True, exist_ok=True)

    captured: dict[str, Any] = {}
    with sync_playwright() as playwright:
        launch_timeout_ms = int(max(10, min(timeout_seconds, 45)) * 1000)
        context = playwright.chromium.launch_persistent_context(
            str(profile_path),
            executable_path=str(chrome_path),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
            timeout=launch_timeout_ms,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()

            def on_response(response: Any) -> None:
                if captured or search_notes_path not in response.url:
                    return
                try:
                    captured["payload"] = response.json()
                except Exception as exc:
                    captured["error"] = str(exc)

            page.on("response", on_response)
            page.goto(
                f"{web_base}/search_result?keyword={quote(keyword)}",
                wait_until="domcontentloaded",
                timeout=launch_timeout_ms,
            )
            deadline = time.time() + max(5, min(timeout_seconds, 45))
            while time.time() < deadline and not captured:
                page.wait_for_timeout(500)
        finally:
            context.close()
    if captured.get("payload"):
        return captured["payload"]
    raise RuntimeError(captured.get("error") or "browser did not capture search notes response")


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
        payload = capture_search_notes(request)
        print(json.dumps({"ok": True, "payload": payload}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
