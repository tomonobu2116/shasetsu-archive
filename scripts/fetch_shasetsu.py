#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社説リンクアーカイブ 取得スクリプト（毎日新聞のみ / 診断強化版）"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

SOURCES = [
    {
        "name": "毎日新聞",
        "rss": "https://mainichi.jp/rss/etc/opinion.rss",
        # タイトルに「社説」を含む項目だけ採用（含まれない項目は除外）
        "title_keyword": "社説",
    },
]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "articles.json")
JST = timezone(timedelta(hours=9))
NS = {"dc": "http://purl.org/dc/elements/1.1/"}

# 一部ニュースサイトはブラウザ以外のUAを弾くため、ブラウザ風UAを指定
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_pubdate(item: ET.Element) -> str:
    pub = item.findtext("pubDate")
    if pub:
        try:
            dt = parsedate_to_datetime(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(JST).strftime("%Y-%m-%d")
        except Exception:
            pass
    dc_date = item.findtext("dc:date", namespaces=NS)
    if dc_date:
        try:
            dt = datetime.fromisoformat(dc_date.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(JST).strftime("%Y-%m-%d")
        except Exception:
            pass
    return ""


def collect_from_source(src: dict) -> list:
    raw = fetch(src["rss"])
    root = ET.fromstring(raw)
    items = root.findall(".//item")
    print(f"[INFO] {src['name']}: RSS項目数 = {len(items)}")

    # 診断用：最初の3項目のタイトルを出力
    for i, item in enumerate(items[:3]):
        t = (item.findtext("title") or "(タイトル空)").strip()
        print(f"[DEBUG] title[{i}] = {t!r}")

    keyword = src.get("title_keyword")
    results = []
    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        if keyword and keyword not in title.replace("　", "").replace(" ", ""):
            continue
        results.append({
            "newspaper": src["name"],
            "title": title,
            "url": link,
            "published": parse_pubdate(item),
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

    # 全ソース取得失敗なら赤く止めて気づけるようにする
    if fetch_failed == len(SOURCES):
        print("[FATAL] すべてのRSS取得に失敗しました。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
