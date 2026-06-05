#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from typing import Any
from urllib.parse import quote

import requests
from xhshow import Xhshow
from xhshow.core.crypto import CryptoProcessor


XHS_API_BASE = "https://edith.xiaohongshu.com"
QUERY_TRENDING_URI = "/api/sns/web/v1/search/trending/query"
SEARCH_NOTES_URI = "/api/sns/web/v1/search/notes"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def patch_xhshow_get_sign() -> None:
    original_build = CryptoProcessor.build_payload_array

    def patched_build(
        self,
        hex_parameter,
        a1_value,
        app_identifier="xhs-pc-web",
        string_param="",
        timestamp=None,
        sign_state=None,
    ):
        payload = original_build(self, hex_parameter, a1_value, app_identifier, string_param, timestamp, sign_state)
        if "{" not in string_param:
            correct_md5_hex = hashlib.md5(string_param.encode("utf-8")).hexdigest()
            correct_md5_bytes = [int(correct_md5_hex[i:i + 2], 16) for i in range(0, 32, 2)]
            seed_byte = payload[4]
            ts_bytes = payload[8:16]
            correct_a3_hash = self._custom_hash_v2(list(ts_bytes) + correct_md5_bytes)
            for i in range(16):
                payload[128 + i] = correct_a3_hash[i] ^ seed_byte
        return payload

    CryptoProcessor.build_payload_array = patched_build


patch_xhshow_get_sign()


def cookie_dict(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in cookie.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def build_query(params: dict[str, Any]) -> str:
    return "&".join(f"{key}={quote(str(value), safe=',')}" for key, value in params.items())


def base36encode(number: int, alphabet: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") -> str:
    if not isinstance(number, int):
        raise TypeError("number must be an integer")
    if number == 0:
        return "0"
    sign = "-" if number < 0 else ""
    number = abs(number)
    digits = ""
    while number:
        number, index = divmod(number, len(alphabet))
        digits = alphabet[index] + digits
    return sign + digits


def get_search_id() -> str:
    timestamp_part = int(time.time() * 1000) << 64
    random_part = int(random.uniform(0, 2147483646))
    return base36encode(timestamp_part + random_part)


def default_query_trending_params(params: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {
        "source": "Explore",
        "search_type": "trend",
        "last_query": "",
        "last_query_time": 0,
        "word_request_situation": "FIRST_ENTER",
        "hint_word": "",
        "hint_word_type": "",
        "hint_word_request_id": "",
    }
    merged.update(params or {})
    return merged


def default_search_notes_payload(params: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {
        "keyword": "",
        "page": 1,
        "page_size": 10,
        "search_id": get_search_id(),
        "sort": "popularity_descending",
        "note_type": 0,
    }
    merged.update(params or {})
    if not str(merged.get("keyword") or "").strip():
        raise ValueError("search notes requires keyword")
    return merged


def sign_headers(uri: str, params: dict[str, Any], cookie: str, *, method: str = "GET") -> dict[str, str]:
    parsed_cookie = cookie_dict(cookie)
    if not parsed_cookie.get("a1"):
        raise ValueError("XHS cookie missing a1")
    if not parsed_cookie.get("web_session"):
        raise ValueError("XHS cookie missing web_session")
    client = Xhshow()
    if method.upper() == "POST":
        signed = client.sign_headers_post(uri=uri, cookies=cookie, payload=params)
    else:
        signed = client.sign_headers_get(uri=uri, cookies=parsed_cookie, params=params)
    return {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.xiaohongshu.com/",
        "Origin": "https://www.xiaohongshu.com",
        "Content-Type": "application/json;charset=UTF-8",
        "Cookie": cookie,
        "X-S": signed.get("x-s") or signed.get("X-S") or "",
        "X-T": str(signed.get("x-t") or signed.get("X-T") or ""),
        "x-S-Common": signed.get("x-s-common") or signed.get("x-S-Common") or "",
        "X-B3-Traceid": signed.get("x-b3-traceid") or signed.get("X-B3-Traceid") or "",
    }


def request_query_trending(cookie: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    request_params = default_query_trending_params(params)
    headers = sign_headers(QUERY_TRENDING_URI, request_params, cookie)
    url = f"{XHS_API_BASE}{QUERY_TRENDING_URI}?{build_query(request_params)}"
    started = time.time()
    response = requests.get(url, headers=headers, timeout=timeout)
    elapsed_ms = int((time.time() - started) * 1000)
    response.raise_for_status()
    return {
        "ok": True,
        "uri": QUERY_TRENDING_URI,
        "elapsedMs": elapsed_ms,
        "payload": response.json(),
    }


def request_search_notes(cookie: str, params: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    payload = default_search_notes_payload(params)
    headers = sign_headers(SEARCH_NOTES_URI, payload, cookie, method="POST")
    started = time.time()
    response = requests.post(
        f"{XHS_API_BASE}{SEARCH_NOTES_URI}",
        data=json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        headers=headers,
        timeout=timeout,
    )
    elapsed_ms = int((time.time() - started) * 1000)
    response.raise_for_status()
    return {
        "ok": True,
        "uri": SEARCH_NOTES_URI,
        "elapsedMs": elapsed_ms,
        "payload": response.json(),
    }


def main() -> int:
    try:
        request = json.loads(sys.stdin.read() or "{}")
        op = request.get("op") or "querytrending"
        if op == "querytrending":
            result = request_query_trending(
                cookie=str(request.get("cookie") or ""),
                params=request.get("params") or {},
                timeout=int(request.get("timeout") or 20),
            )
        elif op == "searchnotes":
            result = request_search_notes(
                cookie=str(request.get("cookie") or ""),
                params=request.get("params") or {},
                timeout=int(request.get("timeout") or 20),
            )
        else:
            raise ValueError(f"Unsupported op: {op}")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
