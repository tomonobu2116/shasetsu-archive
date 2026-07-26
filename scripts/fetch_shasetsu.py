#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社説リンクアーカイブ 取得スクリプト（毎日新聞のみ / 案B: RSSプロキシ経由版）"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

SOURCES = [
    {
        "name": "毎日新聞",
        "rss": "https://mainichi.jp/rss/etc/opinion.rss",
        "title_keyword": "社説",
    },
]

# RSS→JSON 変換プロキシ（APIキー不要枠）
PROXY_TMPL = "https://api.rss2json.com/v1/api.json?rss_url={rss}"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "articles.json")
JST = timezone(timedelta(hours=9))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def fetch_json(url: str, retries: int = 3, wait: float = 3.0) -> dict:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            print(f"[WARN] 試行{attempt}/{retries} HTTP {e.code}", file=sys.stderr)
        except Exception as e:
            last_err = e
            print(f"[WARN] 試行{attempt}/{retries} {e}", file=sys.stderr)
        if attempt < retries:
            time.sleep(wait)
    raise last_err


def to_date(s: str) -> str:
    """rss2jsonのpubDate 'YYYY-MM-DD HH:MM:SS' を JST日付へ。"""
    if not s:
        return ""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                # rss2jsonはUTC表記で返すことが多い
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(JST).strftime("%Y-%m-%d")
        except Exception:
            continue
    return s[:10]  # 最低限 先頭10文字


def collect_from_source(src: dict) -> list:
    url = PROXY_TMPL.format(rss=urllib.parse.quote(src["rss"], safe=""))
    data = fetch_json(url)

    status = data.get("status")
    items = data.get("items", []) or []
    print(f"[INFO] {src['name']}: proxy status={status}, 項目数={len(items)}")
    for i, it in enumerate(items[:3]):
        print(f"[DEBUG] title[{i}] = {it.get('title','')!r}")

    if status != "ok":
        raise RuntimeError(f"proxy status != ok: {status} / {data.get('message','')}")

    keyword = src.get("title_keyword")
    results = []
    for it in items:
        title = (it.get("title") or "").strip()
        link = (it.get("link") or "").strip()
        if not title or not link:
            continue
        if keyword and keyword not in title.replace("　", "").replace(" ", ""):
            continue
        results.append({
            "newspaper": src["name"],
            "title": title,
            "url": link,
            "published": to_date(it.get("pubDate", "")),
        })
    print(f"[INFO] {src['name']}: 社説として一致 = {len(results)} 件")
    return results


def load_existing() -> list:
    if not os.path.exists(DATA_PATH):
        return []
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save(articles: list) -> None:
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    articles.sort(key=lambda a: (a.get("published", ""), a.get("newspaper", "")),
                  reverse=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def main() -> int:
    existing = load_existing()
    seen = {a["url"] for a in existing}
    added = 0
    fetch_failed = 0

    for src in SOURCES:
        try:
            fetched = collect_from_source(src)
        except Exception as e:
            fetch_failed += 1
            print(f"[ERROR] {src['name']} の取得に失敗: {e}", file=sys.stderr)
            continue
        for art in fetched:
            if art["url"] in seen:
                continue
            existing.append(art)
            seen.add(art["url"])
            added += 1
            print(f"[ADD] {art['published']} {art['title']}")

    save(existing)
    print(f"\n完了: {added} 件追加 / 合計 {len(existing)} 件")

    if fetch_failed == len(SOURCES):
        print("[FATAL] すべてのRSS取得に失敗しました。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
