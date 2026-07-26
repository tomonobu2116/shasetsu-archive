#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社説リンクアーカイブ 取得スクリプト（毎日新聞のみ / PoC版）

やること:
  1. 毎日新聞「社説・解説・コラム」RSS を取得
  2. タイトルが「社説」で始まる項目だけ抽出（＝社説のみに絞る）
  3. タイトル / URL / 公開日 / 新聞社名 を data/articles.json に追記
  4. URL で重複排除（既存データは保持 = アーカイブ）

保存する情報は「タイトル・URL・公開日・新聞社名」のみ。
本文・要約・画像は一切取得・保存しない。

実行: python scripts/fetch_shasetsu.py
依存: 標準ライブラリのみ（追加インストール不要）
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

# ---- 設定 -------------------------------------------------------------

# 取得対象。今は毎日新聞のみ。将来ここに追加できる構造にしてある。
SOURCES = [
    {
        "name": "毎日新聞",
        "rss": "https://mainichi.jp/rss/etc/opinion.rss",
        # タイトルがこの接頭辞で始まる項目だけを社説として採用する。
        # 毎日新聞の社説は概ね「社説：…」形式のため。
        "title_prefix": "社説",
    },
]

# 出力先
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "articles.json")

JST = timezone(timedelta(hours=9))

# RSS の名前空間（dc:date 用）
NS = {
    "dc": "http://purl.org/dc/elements/1.1/",
}

USER_AGENT = "ShasetsuArchive/0.1 (personal, RSS reader; title+link only)"


# ---- ユーティリティ ---------------------------------------------------

def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_pubdate(item: ET.Element) -> str:
    """公開日を YYYY-MM-DD (JST) で返す。取れなければ空文字。"""
    # 1) RSS 標準の pubDate
    pub = item.findtext("pubDate")
    if pub:
        try:
            dt = parsedate_to_datetime(pub)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(JST).strftime("%Y-%m-%d")
        except Exception:
            pass
    # 2) dc:date (ISO8601)
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
    results = []
    prefix = src.get("title_prefix")

    for item in items:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue

        # 社説のみに絞り込み
        if prefix:
            # 「社説：」「社説 」などの表記ゆれを吸収するため接頭一致で判定
            normalized = title.replace("　", "").replace(" ", "")
            if not normalized.startswith(prefix):
                continue

        results.append({
            "newspaper": src["name"],
            "title": title,
            "url": link,
            "published": parse_pubdate(item),
        })

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
    # 公開日の新しい順 → 同日は新聞社名で安定ソート
    articles.sort(key=lambda a: (a.get("published", ""), a.get("newspaper", "")),
                  reverse=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def main() -> int:
    existing = load_existing()
    seen = {a["url"] for a in existing}

    added = 0
    for src in SOURCES:
        try:
            fetched = collect_from_source(src)
        except Exception as e:
            print(f"[WARN] {src['name']} の取得に失敗: {e}", file=sys.stderr)
            continue

        for art in fetched:
            if art["url"] in seen:
                continue
            existing.append(art)
            seen.add(art["url"])
            added += 1
            print(f"[ADD] {art['published']} {art['newspaper']} {art['title']}")

    save(existing)
    print(f"\n完了: {added} 件追加 / 合計 {len(existing)} 件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
