from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from lxml import html


MODULE_PATH = Path("/Users/lulu/AIWork/tools/wechatpub-api/wechatpub_api.py")
CAPTURE_PATH = Path("/Users/lulu/AIWork/tools/wechatpub-api/wechat_history_capture.py")
XHS_SIGNED_PATH = Path("/Users/lulu/AIWork/tools/wechatpub-api/xhs_signed_request.py")


def load_module():
    spec = importlib.util.spec_from_file_location("wechatpub_api", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_capture_module():
    sys.path.insert(0, str(MODULE_PATH.parent))
    try:
        spec = importlib.util.spec_from_file_location("wechat_history_capture", CAPTURE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        if sys.path[0] == str(MODULE_PATH.parent):
            sys.path.pop(0)


def load_xhs_signed_module():
    fake_xhshow = types.ModuleType("xhshow")
    fake_core = types.ModuleType("xhshow.core")
    fake_crypto = types.ModuleType("xhshow.core.crypto")

    class FakeXhshow:
        pass

    class FakeCryptoProcessor:
        def build_payload_array(self, *args, **kwargs):
            return [0] * 160

    fake_xhshow.Xhshow = FakeXhshow
    fake_crypto.CryptoProcessor = FakeCryptoProcessor
    previous_modules = {key: sys.modules.get(key) for key in ("xhshow", "xhshow.core", "xhshow.core.crypto")}
    sys.modules["xhshow"] = fake_xhshow
    sys.modules["xhshow.core"] = fake_core
    sys.modules["xhshow.core.crypto"] = fake_crypto
    spec = importlib.util.spec_from_file_location("xhs_signed_request", XHS_SIGNED_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        for key, value in previous_modules.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


class WechatPubApiTest(unittest.TestCase):
    def test_safe_slug_removes_filename_unsafe_chars(self):
        api = load_module()

        self.assertEqual(api.safe_slug(' A/B:C*D?E"F<G>H| #x '), "A_B_C_D_E_F_G_H___x")

    def test_resolve_sogou_link_reassembles_js_redirect(self):
        api = load_module()
        test_case = self

        class Response:
            text = "var url = ''; url += 'https://mp.weixin.qq.com/s/abc'; url += '@@x';"
            url = "https://weixin.sogou.com/link?url=test"
            encoding = "utf-8"
            apparent_encoding = "utf-8"

            def raise_for_status(self):
                return None

        class Client:
            headers = {}

            def get(self, url, timeout):
                test_case.assertIn("weixin.sogou.com/link", url)
                test_case.assertEqual(timeout, 20)
                return Response()

        self.assertEqual(api.resolve_sogou_link("/link?url=test", Client()), "https://mp.weixin.qq.com/s/abcx")

    def test_parse_sogou_time_from_script(self):
        api = load_module()
        li = html.fromstring("<li><script>timeConvert('1700000000')</script></li>")

        self.assertTrue(api.parse_sogou_time(li))

    def test_html_fragment_to_markdown_keeps_text_and_images(self):
        api = load_module()

        markdown = api.html_fragment_to_markdown(
            '<div id="js_content"><p>第一段</p><script>var noisy = true;</script>'
            '<img data-src="https://example.com/a.jpg" alt="封面"><p>第二段</p></div>'
        )

        self.assertIn("第一段", markdown)
        self.assertIn("![封面](https://example.com/a.jpg)", markdown)
        self.assertIn("第二段", markdown)
        self.assertNotIn("noisy", markdown)

    def test_write_article_creates_json_and_markdown(self):
        api = load_module()
        article = {
            "title": "测试文章",
            "account_name": "测试号",
            "author": "作者",
            "publish_time": "2026-05-29T10:00:00+08:00",
            "final_url": "https://mp.weixin.qq.com/s/test",
            "markdown": "正文",
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = api.write_article(Path(tmp_dir), 1, article)
            json_path = Path(paths["json"])
            md_path = Path(paths["markdown"])

            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["title"], "测试文章")
            self.assertIn("# 测试文章", md_path.read_text(encoding="utf-8"))

    def test_render_summary_text_contains_doc_ready_fields(self):
        api = load_module()
        manifest = {
            "query": "测试号",
            "limit": 1,
            "count": 1,
            "out": "/tmp/out",
            "collected_at": "2026-05-29T10:00:00+08:00",
            "articles": [
                {
                    "ok": True,
                    "post": {"summary": "搜索摘要"},
                    "detail": {
                        "title": "文章标题",
                        "account_name": "测试号",
                        "publish_time": "2026-05-29",
                        "final_url": "https://mp.weixin.qq.com/s/test",
                        "content_text": "正文" * 10,
                    },
                }
            ],
        }

        text = api.render_summary_text(manifest)

        self.assertIn("测试号文章采集汇总", text)
        self.assertIn("文章标题", text)
        self.assertIn("https://mp.weixin.qq.com/s/test", text)

    def test_build_getmsg_url_preserves_login_query_and_sets_offset(self):
        api = load_module()

        url = api.build_getmsg_url(
            "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=abc%3D%3D&scene=124&uin=u&key=k&pass_ticket=p&appmsg_token=t#wechat_redirect",
            offset=20,
            count=10,
        )

        self.assertIn("action=getmsg", url)
        self.assertIn("__biz=abc%3D%3D", url)
        self.assertIn("offset=20", url)
        self.assertIn("appmsg_token=t", url)

    def test_parse_history_response_flattens_multi_article_messages(self):
        api = load_module()
        payload = {
            "ret": 0,
            "can_msg_continue": 1,
            "general_msg_list": json.dumps(
                {
                    "list": [
                        {
                            "comm_msg_info": {"id": 123, "datetime": 1700000000},
                            "app_msg_ext_info": {
                                "title": "头条",
                                "content_url": "/s?__biz=abc&mid=1&idx=1&sn=x&amp;chksm=y",
                                "digest": "摘要",
                                "author": "作者",
                                "cover": "https://example.com/a.jpg",
                                "multi_app_msg_item_list": [
                                    {
                                        "title": "次条",
                                        "content_url": "https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=2&sn=z",
                                    }
                                ],
                            },
                        }
                    ]
                },
                ensure_ascii=False,
            ),
        }

        posts, can_continue = api.parse_history_response(payload)

        self.assertTrue(can_continue)
        self.assertEqual([post["title"] for post in posts], ["头条", "次条"])
        self.assertEqual(posts[0]["source"], "wechat_profile_history")
        self.assertIn("&chksm=y", posts[0]["url"])

    def test_collect_defaults_reject_search_results(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(api.WechatPubError):
                api.collect("游戏葡萄", Path(tmp_dir), 1)

            with self.assertRaises(api.WechatPubError):
                api.collect_to_tencent_doc("游戏葡萄", Path(tmp_dir), 1)

    def test_api_defaults_do_not_fall_back_to_sogou(self):
        api = load_module()

        get_posts_sig = inspect.signature(api.api_get_user_post)
        collect_sig = inspect.signature(api.api_collect)
        collect_doc_sig = inspect.signature(api.api_collect_to_tencent_doc)

        self.assertEqual(get_posts_sig.parameters["source"].default.default, "auto")
        self.assertTrue(collect_sig.parameters["strictRecent"].default.default)
        self.assertTrue(collect_doc_sig.parameters["strictRecent"].default.default)

    def test_get_user_post_rejects_search_source(self):
        api = load_module()

        with self.assertRaises(Exception) as caught:
            api.api_get_user_post(wxid="游戏葡萄", limit=1, source="search")

        self.assertEqual(caught.exception.status_code, 502)
        self.assertIn("不允许 source=search", caught.exception.detail["message"])

    def test_xhs_hot_search_uses_status_example_when_requested(self):
        api = load_module()
        example = {
            "code": 0,
            "message": None,
            "data": {
                "noteList": [
                    {
                        "noteInfo": {
                            "title": "低互动",
                            "readNum": 100,
                            "likeNum": 1,
                            "favNum": 1,
                            "cmtNum": 1,
                        },
                        "userInfo": {"nickName": "甲"},
                    },
                    {
                        "noteInfo": {
                            "title": "高互动",
                            "readNum": 100,
                            "likeNum": 10,
                            "favNum": 5,
                            "cmtNum": 2,
                        },
                        "userInfo": {"nickName": "乙"},
                    },
                ],
                "pageInfoDto": {"pageNum": 1, "pageSize": 10, "total": 2},
            },
            "recordTime": None,
        }

        api.fetch_justone_status_example = lambda: {"example": example, "checked_at": "2026-06-01T11:00:00"}
        api.xhs_justone_token = lambda explicit_token=None: ""

        payload = api.get_xhs_hot_search(order_by="premium_engage_num", source="example")

        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["recordTime"], "2026-06-01T11:00:00")
        self.assertEqual(payload["data"]["noteList"][0]["noteInfo"]["title"], "高互动")
        self.assertEqual(payload["data"]["noteList"][0]["noteInfo"]["engageNum"], 17)
        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "justone_status_example")

    def test_xhs_hot_search_self_source_reads_web_initial_state(self):
        api = load_module()
        state = {
            "global": {"serverTime": 1780288150007},
            "feed": {
                "feeds": [
                    {
                        "noteCard": {
                            "interactInfo": {"likedCount": "1.1万"},
                            "cover": {"urlDefault": "https://example.com/a.webp"},
                            "type": "normal",
                            "displayTitle": "世界杯城市笔记",
                            "user": {"nickName": "甲", "avatar": "https://example.com/u.jpg", "userId": "u1"},
                        },
                        "id": "note1",
                        "trackId": "note1",
                        "modelType": "note",
                    },
                    {
                        "noteCard": {
                            "interactInfo": {"likedCount": "20"},
                            "displayTitle": "普通笔记",
                            "user": {"nickname": "乙", "userId": "u2"},
                        },
                        "id": "note2",
                    },
                ]
            },
        }
        raw_state = json.dumps(state, ensure_ascii=False)[:-1] + ',"pwaAddDesktopPrompt":undefined}'
        api.fetch_xhs_web_html = lambda: f"<script>window.__INITIAL_STATE__={raw_state}</script>"

        payload = api.get_xhs_hot_search(search_word="世界杯", source="self")

        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "self_web_explore")
        self.assertEqual(payload["data"]["pageInfoDto"]["total"], 1)
        note_info = payload["data"]["noteList"][0]["noteInfo"]
        self.assertEqual(note_info["title"], "世界杯城市笔记")
        self.assertEqual(note_info["likeNum"], 11000)
        self.assertEqual(note_info["readNum"], 1320000)
        self.assertTrue(note_info["metricsEstimated"])

    def test_xhs_hot_search_proxies_justone_token_and_params(self):
        api = load_module()

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "code": 0,
                    "message": "success",
                    "data": {"noteList": [], "pageInfoDto": {"pageSize": 10}},
                    "recordTime": "2026-06-01T11:00:00",
                }

        calls = []

        def fake_get(url, *, params=None, headers=None, timeout=None):
            calls.append((url, params, headers, timeout))
            return Response()

        api.requests.get = fake_get

        payload = api.get_xhs_hot_search(
            token="tok",
            search_word="世界杯",
            page_num=2,
            order_by="premium_like_num",
            nd="DAY_30",
            source="justone",
        )

        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "justone_live")
        self.assertEqual(calls[0][0], "https://api.justoneapi.com/api/xiaohongshu/hot-search/v1")
        self.assertEqual(calls[0][1]["token"], "tok")
        self.assertEqual(calls[0][1]["searchWord"], "世界杯")
        self.assertEqual(calls[0][1]["pageNum"], 2)
        self.assertEqual(calls[0][1]["orderBy"], "premium_like_num")
        self.assertEqual(calls[0][1]["nd"], "DAY_30")

    def test_xhs_hot_search_web_search_source_uses_signed_helper(self):
        api = load_module()
        api.xhs_cookie = lambda explicit_cookie=None: "a1=a; web_session=s"

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_SEARCH_CACHE = Path(tmp_dir) / "empty-cache.json"

            def fake_helper(op, *, cookie, params=None, timeout=30):
                self.assertEqual(op, "searchnotes")
                self.assertEqual(cookie, "a1=a; web_session=s")
                self.assertEqual(params["keyword"], "世界杯")
                self.assertEqual(params["page"], 2)
                self.assertEqual(params["page_size"], 10)
                return {
                    "ok": True,
                    "payload": {
                        "code": 0,
                        "success": True,
                        "data": {
                            "has_more": False,
                            "items": [
                                {
                                    "id": "note1",
                                    "xsec_token": "xsec1",
                                    "xsec_source": "pc_search",
                                    "note_card": {
                                        "display_title": "世界杯城市笔记",
                                        "type": "normal",
                                        "cover": {"url_default": "https://example.com/cover.webp"},
                                        "interact_info": {
                                            "liked_count": "1.2万",
                                            "collected_count": "300",
                                            "comment_count": "45",
                                            "share_count": "9",
                                        },
                                        "user": {
                                            "user_id": "u1",
                                            "nickname": "甲",
                                            "avatar": "https://example.com/u.jpg",
                                        },
                                    },
                                }
                            ],
                        },
                    },
                }

            api.run_xhs_signed_helper = fake_helper

            payload = api.get_xhs_hot_search(
                search_word="世界杯",
                page_num=2,
                order_by="premium_like_num",
                source="web_search",
            )

        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "self_web_search")
        self.assertEqual(payload["data"]["localMeta"]["endpoint"], "/api/sns/web/v1/search/notes")
        self.assertFalse(payload["data"]["localMeta"]["usesJustOne"])
        self.assertEqual(payload["data"]["pageInfoDto"]["pageNum"], 2)
        note_info = payload["data"]["noteList"][0]["noteInfo"]
        self.assertEqual(note_info["title"], "世界杯城市笔记")
        self.assertEqual(note_info["likeNum"], 12000)
        self.assertEqual(note_info["favNum"], 300)
        self.assertEqual(note_info["cmtNum"], 45)
        self.assertEqual(note_info["engageNum"], 12345)
        self.assertEqual(note_info["url"], "https://www.xiaohongshu.com/explore/note1?xsec_token=xsec1&xsec_source=pc_search")
        self.assertTrue(note_info["metricsEstimated"])

    def test_xhs_hot_search_auto_falls_back_to_explore_when_web_search_unavailable(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_SEARCH_CACHE = Path(tmp_dir) / "empty-cache.json"
            api.fetch_signed_xhs_hot_search = lambda **kwargs: (_ for _ in ()).throw(api.XiaohongshuError("cookie missing"))
            api.fetch_browser_xhs_hot_search = lambda **kwargs: (_ for _ in ()).throw(api.XiaohongshuError("browser missing"))
            api.fetch_self_xhs_explore_hot_search = lambda **kwargs: {
                "code": 0,
                "message": "success",
                "data": {"noteList": [], "pageInfoDto": {}, "localMeta": {"source_mode": "self_web_explore"}},
                "recordTime": "2026-06-02T12:00:00+08:00",
            }

            payload = api.get_xhs_hot_search(search_word="世界杯", source="auto")

        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "self_web_explore")
        self.assertIn("web_search_error", payload["data"]["localMeta"])

    def test_xhs_hot_search_browser_source_shapes_captured_search_notes(self):
        api = load_module()
        api.xhs_cookie = lambda explicit_cookie=None: "a1=a; web_session=s"
        api.fetch_browser_xhs_search_payload = lambda keyword, timeout_seconds=60: {
            "code": 0,
            "success": True,
            "data": {
                "has_more": True,
                "items": [
                    {
                        "id": "note1",
                        "xsec_token": "xsec1",
                        "xsec_source": "pc_search",
                        "note_card": {
                            "display_title": "世界杯直播指南",
                            "interact_info": {
                                "liked_count": "6773",
                                "collected_count": "2244",
                                "comment_count": "734",
                            },
                            "user": {"nickname": "薯队长", "user_id": "u1"},
                        },
                    }
                ],
            },
        }

        payload = api.get_xhs_hot_search(search_word="世界杯", source="browser_search")

        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "self_browser_search")
        self.assertEqual(payload["data"]["localMeta"]["endpoint"], "/api/sns/web/v1/search/notes")
        self.assertEqual(payload["data"]["noteList"][0]["noteInfo"]["title"], "世界杯直播指南")
        self.assertEqual(payload["data"]["noteList"][0]["noteInfo"]["likeNum"], 6773)

    def test_xhs_hot_search_web_search_prefers_fresh_cache(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_SEARCH_CACHE = Path(tmp_dir) / "hot-search-cache.json"
            api.save_xhs_hot_search_cache(
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "noteList": [{"noteInfo": {"title": "缓存世界杯", "likeNum": 1}, "userInfo": {}}],
                        "pageInfoDto": {"pageNum": 1, "pageSize": 1, "total": 1},
                        "localMeta": {
                            "source_mode": "self_browser_search",
                            "searchWord": "世界杯",
                            "orderBy": "premium_like_num",
                            "nd": "DAY_7",
                        },
                    },
                    "recordTime": "2026-06-02T12:00:00+08:00",
                }
            )
            api.fetch_signed_xhs_hot_search = lambda **kwargs: (_ for _ in ()).throw(api.XiaohongshuError("signed blocked"))
            api.fetch_browser_xhs_hot_search = lambda **kwargs: (_ for _ in ()).throw(api.XiaohongshuError("browser timeout"))

            payload = api.get_xhs_hot_search(
                search_word="世界杯",
                order_by="premium_like_num",
                nd="DAY_7",
                source="web_search",
            )

        self.assertEqual(payload["data"]["noteList"][0]["noteInfo"]["title"], "缓存世界杯")
        self.assertTrue(payload["data"]["localMeta"]["cache"])
        self.assertNotIn("web_search_error", payload["data"]["localMeta"])

    def test_xhs_signed_helper_supports_search_notes_post(self):
        helper = load_xhs_signed_module()
        calls = []

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"code": 0, "success": True, "data": {"items": []}}

        def fake_post(url, *, data=None, headers=None, timeout=None):
            calls.append((url, data, headers, timeout))
            return Response()

        helper.requests.post = fake_post
        helper.sign_headers = lambda uri, params, cookie, method="GET": {
            "Cookie": cookie,
            "X-S": f"{method}:{uri}",
        }

        result = helper.request_search_notes(
            "a1=a; web_session=s",
            {"keyword": "世界杯", "page": 2, "page_size": 10, "search_id": "sid"},
            timeout=9,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["uri"], "/api/sns/web/v1/search/notes")
        self.assertEqual(calls[0][0], "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes")
        self.assertEqual(json.loads(calls[0][1])["keyword"], "世界杯")
        self.assertEqual(calls[0][2]["X-S"], "POST:/api/sns/web/v1/search/notes")
        self.assertEqual(calls[0][3], 9)

    def test_xhs_hot_trends_uses_signed_helper(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_TRENDS_CACHE = Path(tmp_dir) / "hot-trends.json"
            api.xhs_cookie = lambda explicit_cookie=None: "a1=a; web_session=s"

            def fake_helper(op, *, cookie, params=None, timeout=30):
                self.assertEqual(op, "querytrending")
                self.assertEqual(cookie, "a1=a; web_session=s")
                self.assertEqual(params["word_request_situation"], "FIRST_ENTER")
                return {
                    "ok": True,
                    "payload": {
                        "code": 0,
                        "success": True,
                        "data": {
                            "queries": [
                                {"title": "春节旅行", "score": "热"},
                                {"query": "世界杯", "heat": 100},
                            ],
                            "hintWord": {"title": "搜索小红书"},
                            "wordRequestId": "wr1",
                        },
                    },
                }

            api.run_xhs_signed_helper = fake_helper

            payload = api.fetch_signed_xhs_hot_trends()

        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["localMeta"]["source_mode"], "xhs_signed_querytrending")
        self.assertFalse(payload["data"]["localMeta"]["isGlobalHotSearch"])
        self.assertEqual(payload["data"]["localMeta"]["result_type"], "search_suggestions")
        self.assertEqual(payload["data"]["trendList"][0]["title"], "春节旅行")
        self.assertEqual(payload["data"]["trendList"][1]["title"], "世界杯")
        self.assertEqual(payload["data"]["total"], 2)

    def test_xhs_hot_trends_auto_prefers_browser_source(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_TRENDS_CACHE = Path(tmp_dir) / "missing-cache.json"
            api.fetch_browser_xhs_hot_trends = lambda: {"code": 0, "data": {"localMeta": {"source_mode": "browser"}}}

            payload = api.get_xhs_hot_trends()

            self.assertEqual(payload["data"]["localMeta"]["source_mode"], "browser")

    def test_xhs_hot_trends_cache_roundtrip(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_TRENDS_CACHE = Path(tmp_dir) / "hot-trends.json"
            api.save_xhs_hot_trends_cache(
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "trendList": [{"title": "小红书热搜"}],
                        "localMeta": {"source_mode": "xhs_browser_signed_querytrending"},
                    },
                    "recordTime": "2026-06-01T15:00:00+08:00",
                }
            )

            payload = api.get_xhs_hot_trends(source="cache")

            self.assertEqual(payload["code"], 0)
            self.assertTrue(payload["data"]["localMeta"]["cache"])
            self.assertEqual(payload["data"]["trendList"][0]["title"], "小红书热搜")
            self.assertNotIn("cacheSavedAtEpoch", payload)

    def test_xhs_hot_trends_auto_falls_back_to_cache(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_TRENDS_CACHE = Path(tmp_dir) / "hot-trends.json"
            api.XHS_HOT_TRENDS_CACHE_TTL_SECONDS = -1
            api.save_xhs_hot_trends_cache(
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "trendList": [{"title": "缓存热搜"}],
                        "localMeta": {"source_mode": "xhs_browser_signed_querytrending"},
                    },
                    "recordTime": "2026-06-01T15:00:00+08:00",
                }
            )
            api.fetch_browser_xhs_hot_trends = lambda: (_ for _ in ()).throw(api.XiaohongshuError("browser down"))
            api.fetch_signed_xhs_hot_trends = lambda: (_ for _ in ()).throw(api.XiaohongshuError("signed down"))

            payload = api.get_xhs_hot_trends(source="auto")

            self.assertEqual(payload["data"]["trendList"][0]["title"], "缓存热搜")
            self.assertTrue(payload["data"]["localMeta"]["cache"])
            self.assertIn("browser down", payload["data"]["localMeta"]["browser_error"])
            self.assertIn("signed down", payload["data"]["localMeta"]["signed_error"])

    def test_xhs_hot_trends_auto_uses_fresh_cache_first(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_HOT_TRENDS_CACHE = Path(tmp_dir) / "hot-trends.json"
            api.XHS_HOT_TRENDS_CACHE_TTL_SECONDS = 600
            api.save_xhs_hot_trends_cache(
                {
                    "code": 0,
                    "message": "success",
                    "data": {
                        "trendList": [{"title": "新鲜缓存"}],
                        "localMeta": {"source_mode": "xhs_browser_signed_querytrending"},
                    },
                    "recordTime": "2026-06-01T15:00:00+08:00",
                }
            )
            api.fetch_browser_xhs_hot_trends = lambda: (_ for _ in ()).throw(AssertionError("should not refresh"))

            payload = api.get_xhs_hot_trends(source="auto")

            self.assertEqual(payload["data"]["trendList"][0]["title"], "新鲜缓存")
            self.assertTrue(payload["data"]["localMeta"]["cache"])

    def test_xhs_global_hot_keywords_parses_har_and_marks_global(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_GLOBAL_HOT_HAR_INBOX = Path(tmp_dir) / "inbox"
            api.XHS_GLOBAL_HOT_CACHE = Path(tmp_dir) / "global-hot-cache.json"
            api.XHS_GLOBAL_HOT_HAR_INBOX.mkdir()
            har_path = api.XHS_GLOBAL_HOT_HAR_INBOX / "xhs-hot.har"
            payload = {
                "code": 0,
                "success": True,
                "data": {
                    "hotWordList": [
                        {"keyword": "春节旅行", "heat": 1000},
                        {"word": "世界杯", "hotValue": 900},
                        {"title": "开学穿搭", "score": 800},
                    ]
                },
            }
            har_path.write_text(
                json.dumps(
                    {
                        "log": {
                            "entries": [
                                {
                                    "request": {"url": "https://edith.xiaohongshu.com/api/sns/v2/search/hot_list"},
                                    "response": {"content": {"text": json.dumps(payload, ensure_ascii=False)}},
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = api.get_xhs_global_hot_keywords(source="har", har_file="xhs-hot.har")

            self.assertEqual(result["code"], 0)
            self.assertTrue(result["data"]["localMeta"]["isGlobalHotSearch"])
            self.assertEqual(result["data"]["localMeta"]["result_type"], "global_hot_keywords")
            self.assertEqual(result["data"]["localMeta"]["endpoint"], "/api/sns/v2/search/hot_list")
            self.assertEqual(result["data"]["trendList"][0]["title"], "春节旅行")
            self.assertEqual(result["data"]["total"], 3)
            self.assertTrue(api.XHS_GLOBAL_HOT_CACHE.exists())

    def test_xhs_global_hot_keywords_rejects_search_suggestions_har(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_GLOBAL_HOT_HAR_INBOX = Path(tmp_dir) / "inbox"
            api.XHS_GLOBAL_HOT_CACHE = Path(tmp_dir) / "global-hot-cache.json"
            api.XHS_GLOBAL_HOT_HAR_INBOX.mkdir()
            har_path = api.XHS_GLOBAL_HOT_HAR_INBOX / "suggestions.har"
            payload = {
                "code": 0,
                "success": True,
                "data": {
                    "queries": [
                        {"title": "这是猜你想搜"},
                        {"title": "不是全站热搜"},
                        {"title": "不能混进榜单"},
                    ]
                },
            }
            har_path.write_text(
                json.dumps(
                    {
                        "log": {
                            "entries": [
                                {
                                    "request": {
                                        "url": "https://www.xiaohongshu.com/api/sns/web/v1/search/trending/query"
                                    },
                                    "response": {"content": {"text": json.dumps(payload, ensure_ascii=False)}},
                                }
                            ]
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(api.XiaohongshuError) as caught:
                api.get_xhs_global_hot_keywords(source="har", har_file="suggestions.har")

            self.assertIn("没有找到可确认的全站热搜关键词列表", str(caught.exception))
            self.assertIn("已排除搜索建议路径", str(caught.exception))

    def test_save_xhs_cookie_updates_secret_file(self):
        api = load_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.XHS_ENV = Path(tmp_dir) / "xiaohongshu-api.env"
            api.XHS_ENV.write_text("OTHER=1\nXHS_COOKIE=old\n", encoding="utf-8")

            api.save_xhs_cookie("a1=a; web_session=s")

            content = api.XHS_ENV.read_text(encoding="utf-8")
            self.assertIn("OTHER=1", content)
            self.assertIn("XHS_COOKIE='a1=a; web_session=s'", content)
            self.assertTrue(api.XHS_ENV.stat().st_mode & 0o600)

    def test_register_history_source_redacts_secret_url_and_supports_lookup(self):
        api = load_module()
        history_url = "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=abc%3D%3D&appmsg_token=t&key=k"

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.WECHATPUB_SOURCES_PATH = Path(tmp_dir) / "sources.json"

            public_record = api.register_history_source("游戏葡萄", history_url, display_name="游戏葡萄")
            stored_record = api.find_history_source("游戏葡萄")
            status = api.redacted_source_record(stored_record)

            self.assertTrue(public_record["has_history_url"])
            self.assertFalse(public_record["has_cookie"])
            self.assertNotIn("history_url", public_record)
            self.assertEqual(stored_record["history_url"], history_url)
            self.assertEqual(status["__biz"], "abc==")
            self.assertNotIn("history_url", status)
            self.assertNotIn("cookie", status)

    def test_get_article_posts_auto_uses_registered_history_source(self):
        api = load_module()
        history_url = "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=abc%3D%3D&appmsg_token=t&key=k"

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.WECHATPUB_SOURCES_PATH = Path(tmp_dir) / "sources.json"
            api.register_history_source("游戏葡萄", history_url, cookie="appmsg_token=t; wxuin=123")

            calls = []

            def fake_fetch(url, *, limit=30, cookie=None, delay=0.8):
                calls.append((url, limit, cookie))
                return [{"title": "新文章", "url": "https://mp.weixin.qq.com/s/new"}]

            api.fetch_wechat_history_articles = fake_fetch
            posts, meta = api.get_article_posts("游戏葡萄", limit=1, source="auto", strict_recent=True)

            self.assertEqual(posts[0]["title"], "新文章")
            self.assertEqual(calls, [(history_url, 1, "appmsg_token=t; wxuin=123")])
            self.assertEqual(meta["source_mode"], "wechat_profile_history")

    def test_get_article_posts_auto_refreshes_expired_history_source(self):
        api = load_module()
        stale_url = "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=abc%3D%3D&appmsg_token=old&key=old"
        fresh_url = "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=abc%3D%3D&appmsg_token=new&key=new"

        with tempfile.TemporaryDirectory() as tmp_dir:
            api.WECHATPUB_SOURCES_PATH = Path(tmp_dir) / "sources.json"
            api.register_history_source("游戏葡萄", stale_url, cookie="appmsg_token=old")

            calls = []

            def fake_fetch(url, *, limit=30, cookie=None, delay=0.8):
                calls.append((url, limit, cookie))
                if len(calls) == 1:
                    raise api.WechatPubError("WeChat history source rejected request: no session")
                return [{"title": "续期后文章", "url": "https://mp.weixin.qq.com/s/fresh"}]

            def fake_refresh(wxid, *, record=None, timeout_seconds=90):
                api.register_history_source(wxid, fresh_url, cookie="appmsg_token=new")
                return {"registered": True, "refresh_stage": "cache"}

            api.fetch_wechat_history_articles = fake_fetch
            api.refresh_history_source = fake_refresh
            posts, meta = api.get_article_posts("游戏葡萄", limit=1, source="auto", strict_recent=True)

            self.assertEqual(posts[0]["title"], "续期后文章")
            self.assertEqual(
                calls,
                [
                    (stale_url, 1, "appmsg_token=old"),
                    (fresh_url, 1, "appmsg_token=new"),
                ],
            )
            self.assertTrue(meta["auto_refreshed_history_source"])
            self.assertEqual(meta["history_refresh_stage"], "cache")

    def test_capture_extracts_and_redacts_profile_ext_url(self):
        capture = load_capture_module()
        text = (
            'url = "https:\\/\\/mp.weixin.qq.com\\/mp\\/profile_ext?action=home'
            '&amp;__biz=abc%3D%3D&amp;appmsg_token=t&amp;key=k&amp;pass_ticket=p"'
        )

        urls = capture.extract_profile_ext_urls(text)
        redacted = capture.redact_url(urls[0])

        self.assertEqual(len(urls), 1)
        self.assertIn("__biz=abc%3D%3D", urls[0])
        self.assertIn("appmsg_token=***", redacted)
        self.assertIn("key=***", redacted)

    def test_capture_scan_file_finds_profile_ext_url(self):
        capture = load_capture_module()
        text = "prefix https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=abc%3D%3D&appmsg_token=t suffix"

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cache.txt"
            path.write_text(text, encoding="utf-8")

            matches = capture.scan_file(path)

        self.assertEqual(matches[0]["score"], 19)
        self.assertEqual(matches[0]["source"], str(path))

    def test_capture_builds_session_source_from_article_cache(self):
        capture = load_capture_module()
        text = (
            "GET https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=1&idx=1"
            "&scene=231&uin=u123&key=k123&pass_ticket=p123 HTTP/1.1\n"
            "Set-Cookie: appmsg_token=t123; Path=/;\n"
            "Set-Cookie: wxuin=2056108862; Path=/;\n"
            "Set-Cookie: wxtokenkey=777; Path=/;\n"
            "Set-Cookie: wap_sid2=sid123==; Path=/;\n"
        )

        matches = capture.scan_text_source("cache", text)
        match = matches[0]

        self.assertEqual(match["source_type"], "article_session")
        self.assertTrue(match["cookie"].startswith("appmsg_token=t123"))
        self.assertIn("/mp/profile_ext?", match["url"])
        self.assertIn("__biz=abc%3D%3D", match["url"])
        self.assertIn("appmsg_token=t123", match["url"])
        self.assertTrue(match["score"] > 30)

    def test_capture_refresh_registers_matching_biz_from_cache(self):
        capture = load_capture_module()
        text = (
            "GET https://mp.weixin.qq.com/s?__biz=abc%3D%3D&mid=1&idx=1"
            "&scene=231&uin=u123&key=k123&pass_ticket=p123 HTTP/1.1\n"
            "Set-Cookie: appmsg_token=t123; Path=/;\n"
            "Set-Cookie: wxuin=2056108862; Path=/;\n"
        )
        registered = []

        def fake_register(wxid, history_url, *, display_name=None, cookie=None):
            registered.append((wxid, history_url, display_name, cookie))
            return {"wxid": wxid, "__biz": "abc==", "has_history_url": True, "has_cookie": bool(cookie)}

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "cache.txt"
            path.write_text(text, encoding="utf-8")
            os.utime(path, (2000000000, 2000000000))
            capture.register_history_source = fake_register
            capture.read_clipboard = lambda: ""

            result = capture.refresh_and_register(
                "游戏葡萄",
                timeout_seconds=1,
                interval_seconds=0.1,
                roots=[tmp_dir],
                display_name="游戏葡萄",
                biz="abc==",
                since_seconds=0,
                file_limit=10,
                open_wechat=False,
            )

        self.assertTrue(result["registered"])
        self.assertEqual(result["refresh_stage"], "cache")
        self.assertEqual(registered[0][0], "游戏葡萄")
        self.assertIn("__biz=abc%3D%3D", registered[0][1])
        self.assertIn("appmsg_token=t123", registered[0][3])

    def test_capture_refresh_reports_macos_accessibility_denial(self):
        capture = load_capture_module()

        def fake_scan_sources(*, roots=None, since_seconds=3600, file_limit=500, deadline=None):
            return []

        capture.scan_sources = fake_scan_sources
        capture.auto_open_wechat_article = lambda wxid: {
            "ok": False,
            "permission_denied": True,
            "message": "macOS accessibility denied",
        }

        result = capture.refresh_and_register(
            "游戏葡萄",
            timeout_seconds=30,
            interval_seconds=0.1,
            roots=[],
            display_name="游戏葡萄",
            biz="abc==",
            since_seconds=0,
            file_limit=10,
            open_wechat=True,
            auto_click=True,
        )

        self.assertFalse(result["registered"])
        self.assertTrue(result["requires_macos_accessibility"])
        self.assertEqual(result["message"], "macOS accessibility denied")

    def test_capture_ignores_empty_biz_template_url(self):
        capture = load_capture_module()

        urls = capture.extract_profile_ext_urls("https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=")

        self.assertEqual(urls, [])

    def test_capture_applescript_quote_keeps_chinese_text(self):
        capture = load_capture_module()

        quoted = capture.applescript_quote('游戏葡萄 "A"')

        self.assertIn("游戏葡萄", quoted)
        self.assertNotIn("\\u", quoted)
        self.assertIn('\\"A\\"', quoted)

    def test_capture_recent_file_iterator_respects_limit_and_deadline(self):
        capture = load_capture_module()

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            older = root / "older.txt"
            newer = root / "newer.txt"
            newest = root / "newest.txt"
            for index, path in enumerate([older, newer, newest]):
                path.write_text("x", encoding="utf-8")
                os.utime(path, (1700000000 + index, 1700000000 + index))

            files = capture.iter_recent_files([root], since_seconds=0, limit=2)
            timed_out = capture.iter_recent_files([root], since_seconds=0, limit=2, deadline=0.0)

        self.assertEqual([path.name for path in files], ["newest.txt", "newer.txt"])
        self.assertEqual(timed_out, [])

if __name__ == "__main__":
    unittest.main()
