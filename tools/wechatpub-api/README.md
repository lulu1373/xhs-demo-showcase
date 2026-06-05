# wechatpub-api

Self-hosted WeChat public-account article collector, plus a small local
Xiaohongshu/Rednote API surface.

This is a local replacement for the parts of paid APIs that collect public WeChat
official-account articles:

- `GET /api/weixin/get-user-post/v1?wxid=...`
- `GET /api/weixin/search/v1?keyword=...`
- `GET /api/weixin/get-article-detail/v1?articleUrl=...`
- `GET /api/weixin/collect/v1?wxid=...&limit=30`
- `GET /api/weixin/collect-to-tencent-doc/v1?wxid=...&limit=30`
- `GET /api/weixin/register-source/v1?wxid=...&historyUrl=...`
- `GET /api/weixin/source-status/v1?wxid=...`
- `GET /api/xiaohongshu/hot-search/v1?searchWord=...&pageNum=1`
- `GET /api/xiaohongshu/hot-trends/v1`
- `GET /api/xiaohongshu/global-hot-keywords/v1`
- `GET /api/xiaohongshu/source-status/v1`

For precise latest/history lists, it uses WeChat official-account history
`profile_ext` URLs copied from a logged-in WeChat client. Public Sogou Weixin
search remains available only as an explicit discovery fallback; Sogou results
are search results, not an official-account chronological timeline. It does not
read private WeChat chats, decrypt local WeChat databases, or bypass account
permissions.

## Run

```bash
cd /Users/lulu/AIWork/tools/wechatpub-api
python3 wechatpub_api.py serve --port 18831
```

Health check:

```bash
curl http://127.0.0.1:18831/health
```

## Install as a local service

```bash
cd /Users/lulu/AIWork/tools/wechatpub-api
python3 -m pip install -r requirements.txt
chmod +x wechatpub deploy/install-launchd.sh
./deploy/install-launchd.sh
```

The service listens on `http://127.0.0.1:18831` and writes logs to:

- `/Users/lulu/Library/Logs/wechatpub-api.log`
- `/Users/lulu/Library/Logs/wechatpub-api.err.log`

## CLI

Search public-account articles:

```bash
./wechatpub search "人民日报" --limit 5
```

Fetch one article:

```bash
./wechatpub detail "https://mp.weixin.qq.com/s/..."
```

Fetch Xiaohongshu hot-search data:

```bash
./wechatpub xhs-hot-search --search-word 世界杯 --order-by premium_imp_num --nd DAY_7
```

This is a Just-One-like hot-note/content ranking shape. It accepts
`searchWord`, `orderBy`, and `nd`, so do not present it as the platform-wide
keyword hot-search list.

By default, `source=auto` is free/self-hosted. When `searchWord` is present it
first tries Xiaohongshu's signed web search API and marks
`data.localMeta.source_mode` as `self_web_search`. If the signed request is
blocked by account permissions, it opens the local Chrome profile and captures
the browser's own search response as `self_browser_search`. Both paths use the
local Xiaohongshu web login cookie, not Just One and not Proxyman. If both search
sources are unavailable, it falls back to the public Explore SSR source and
records the error under `data.localMeta.web_search_error`.

Successful `web_search` or `browser_search` results are cached at
`/Users/lulu/AIWork/run/xhs-hot-search-cache.json`. Use `source=cache` to return
the latest matching `searchWord/orderBy/nd` result without opening Chrome:

```bash
./wechatpub xhs-hot-search --source cache --search-word 世界杯 --order-by premium_like_num
```

The Explore fallback reads the public SSR state from
`https://www.xiaohongshu.com/explore` and converts it into a Just-One-like
response shape. Xiaohongshu's public web/search state does not expose premium
read metrics, so `readNum` is estimated from likes and items are marked with
`noteInfo.metricsEstimated=true`.

To force the self-hosted source:

```bash
./wechatpub xhs-hot-search --source web_search --search-word 世界杯 --order-by premium_like_num
```

To skip the direct signed attempt and force Chrome browser capture:

```bash
./wechatpub xhs-hot-search --source browser_search --search-word 世界杯
```

To force the public Explore fallback:

```bash
./wechatpub xhs-hot-search --source self --order-by premium_like_num
```

To explicitly proxy Just One, put a token in
`/Users/lulu/.config/carrie-secrets/xiaohongshu-api.env`:

```text
XHS_JUSTONE_TOKEN=...
```

Then call:

```bash
./wechatpub xhs-hot-search --source justone --search-word 世界杯
```

`source=example` keeps the old Just One public health-check sample path for
schema/debugging only.

Fetch Xiaohongshu signed search-box suggestion words:

```bash
./wechatpub xhs-hot-trends
curl 'http://127.0.0.1:18831/api/xiaohongshu/hot-trends/v1?source=auto'
```

By default this opens/reuses the dedicated local Chrome profile and captures the
browser-signed response from Xiaohongshu's query-trending endpoint:

```text
/api/sns/web/v1/search/trending/query
```

The browser source lets Xiaohongshu's own frontend JS generate the current
request signatures. A pure helper source also exists as `--source signed`, but
Xiaohongshu may reject it when the web signature rules move faster than the local
algorithm.

Important: this endpoint returns search-box suggestion data (`猜你想搜`), not a
platform-wide Xiaohongshu hot-search ranking. The response metadata includes
`isGlobalHotSearch: false` so callers do not present it as a total hot list.

Successful browser or signed captures are cached at
`/Users/lulu/AIWork/run/xhs-hot-trends-cache.json`. Use `--source cache` or
`source=cache` to return the latest real capture immediately. `source=auto`
returns a cache younger than 10 minutes first, then tries a live browser capture,
then falls back to the cache if launchd cannot open the GUI browser profile.
Use `--source browser` when you explicitly want to refresh the cache.

The signed helper source requires a logged-in Xiaohongshu web cookie with at
least `a1` and `web_session`. Store it in:

```text
/Users/lulu/.config/carrie-secrets/xiaohongshu-api.env
```

as:

```text
XHS_COOKIE='a1=...; web_session=...; webId=...'
```

Do not send this cookie in a URL. The local API reads it from the secret file and
uses the isolated Python 3.10+ helper at
`/Users/lulu/AIWork/tools/wechatpub-api/xhs_signed_request.py` to generate the
`X-S`, `X-T`, `x-S-Common`, and `X-B3-Traceid` headers.

Check whether the signed source is ready:

```bash
./wechatpub xhs-source-status
curl 'http://127.0.0.1:18831/api/xiaohongshu/source-status/v1'
```

To capture the login cookie without pasting it manually:

```bash
./wechatpub xhs-login-capture --timeout 180
```

It opens a local Chrome profile at
`/Users/lulu/.config/carrie-secrets/xhs-browser-profile`; scan/login in that
window once. When `a1` and `web_session` appear, the command writes `XHS_COOKIE`
to the secret file and exits.

Fetch true platform-wide hot keyword list from a local App/Web_V3 HAR capture:

```bash
mkdir -p /Users/lulu/AIWork/xhs-hot-har-inbox
./wechatpub xhs-global-hot-keywords --source har --har-file xhs-hot.har
curl 'http://127.0.0.1:18831/api/xiaohongshu/global-hot-keywords/v1?source=har&harFile=xhs-hot.har'
```

Put the HAR file under `/Users/lulu/AIWork/xhs-hot-har-inbox/`. The parser
intentionally rejects the PC-web query-trending paths
`/api/sns/web/v1/search/trending/query` and
`/api/sns/web/v1/search/querytrending`, because those are search-box suggestion
words, not the global hot-search list. Successful HAR parses are cached at
`/Users/lulu/AIWork/run/xhs-global-hot-keywords-cache.json`; use
`--source cache` or `source=cache` to return the latest parsed list.

Collect and archive articles:

```bash
./wechatpub collect "人民日报" --source history --limit 30 \
  --history-url 'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=...' \
  --out /Users/lulu/AIWork/wechat-archive/人民日报/latest
```

Collect, archive, and publish a summary into Tencent Docs:

```bash
./wechatpub collect-doc "人民日报" --source history --limit 30 \
  --history-url 'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=...' \
  --out /Users/lulu/AIWork/wechat-archive/人民日报/latest
```

Collect from a true WeChat official-account history timeline:

```bash
./wechatpub collect-doc "游戏葡萄" --source history --limit 30 \
  --history-url 'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=...&appmsg_token=...&uin=...&key=...&pass_ticket=...'
```

Register a history source once, then use Just-One-like `wxid` calls:

```bash
./wechatpub register-source "游戏葡萄" \
  --history-url 'https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=...&appmsg_token=...&uin=...&key=...&pass_ticket=...'

./wechatpub source-status "游戏葡萄"
./wechatpub collect-doc "游戏葡萄" --limit 30
```

Capture/register a history source from the macOS WeChat client:

```bash
./wechat-history-capture watch "游戏葡萄" --open-wechat --timeout 180
```

The helper focuses WeChat, types the account name into search, then watches the
clipboard and recent WeChat cache files for a valid `profile_ext` URL. Open the
official account's `全部消息/历史消息` page during the watch window; once captured,
the helper registers the source in the local registry.

Collect/publish commands are strict by default. They fail instead of publishing
search results as if they were recent unless a history source is supplied:

```bash
./wechatpub collect-doc "人民日报" --limit 30
```

For explicit public-search discovery, opt in with `--allow-search`:

```bash
./wechatpub collect-doc "人民日报" --source search --allow-search --limit 30
```

Tencent Docs credentials are read from:

```text
/Users/lulu/.config/carrie-secrets/tencent-docs.env
```

The file must define `TENCENT_DOCS_CLIENT_ID`, `TENCENT_DOCS_ACCESS_TOKEN`, and
`TENCENT_DOCS_OPEN_ID`. Keep it chmod `600`.

Optional local API token:

```text
/Users/lulu/.config/carrie-secrets/wechatpub-api.env
```

If it defines `WECHATPUB_API_TOKEN`, compatible HTTP calls must pass
`token=...`, matching Just One API's query-token style.

Registered account history sources are stored locally in:

```text
/Users/lulu/.config/carrie-secrets/wechatpub-sources.json
```

The file contains short-lived WeChat history URLs and is written chmod `600`.

## API examples for 小猫咪 / OpenClaw

Register a precise WeChat history source:

```bash
curl --get 'http://127.0.0.1:18831/api/weixin/register-source/v1' \
  --data-urlencode 'wxid=游戏葡萄' \
  --data-urlencode 'historyUrl=https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=...'
```

Collect and return a Tencent Docs URL from the registered source:

```bash
curl --get 'http://127.0.0.1:18831/api/weixin/collect-to-tencent-doc/v1' \
  --data-urlencode 'wxid=人民日报' \
  --data-urlencode 'limit=30'
```

Without `historyUrl`, collect/publish calls default to strict mode and fail
rather than returning search results with misleading dates.

Collect searchable articles for a public account keyword:

```bash
curl --get 'http://127.0.0.1:18831/api/weixin/collect/v1' \
  --data-urlencode 'wxid=人民日报' \
  --data-urlencode 'limit=30' \
  --data-urlencode 'source=search' \
  --data-urlencode 'strictRecent=false'
```

Get article links only:

```bash
curl --get 'http://127.0.0.1:18831/api/weixin/get-user-post/v1' \
  --data-urlencode 'wxid=人民日报' \
  --data-urlencode 'limit=30'
```

`get-user-post` is strict and never falls back to search. It will reject
`source=search`; use the dedicated search endpoint below for discovery.

Keyword search is explicit discovery, not a recent timeline:

```bash
curl --get 'http://127.0.0.1:18831/api/weixin/search/v1' \
  --data-urlencode 'keyword=游戏葡萄' \
  --data-urlencode 'sortType=_2'
```

Get one article's readable content:

```bash
curl --get 'http://127.0.0.1:18831/api/weixin/get-article-detail/v1' \
  --data-urlencode 'articleUrl=https://mp.weixin.qq.com/s/...'
```

So 小猫咪 can execute a task like:

```text
先调用 source-status 检查公众号是否已注册历史源；未注册时要求完整 profile_ext 链接并调用 register-source；已注册后调用 collect-to-tencent-doc，参数 wxid=公众号名，limit=30；
把返回的 data.tencent_doc.url 发给我。没有注册历史源时不要走搜索结果，直接告诉我需要公众号历史页链接。
```

## Notes

- Collect/publish defaults are strict. Sogou results require explicit
  `source=search&strictRecent=false` or CLI `--allow-search`.
- Use `--exact-account "公众号显示名"` to filter by source account name when the
  search result source names are stable.
- For Just-One-API-like latest posts, use the `source=history` adapter with a
  WeChat `profile_ext` history URL. The URL contains short-lived login/session
  query values from WeChat; do not paste it in public chats.
