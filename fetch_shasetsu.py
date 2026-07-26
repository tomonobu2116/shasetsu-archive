#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社説リンクアーカイブ 取得スクリプト（毎日新聞 / 社説一覧ページ版）

データ源:
  https://mainichi.jp/editorial/   （毎日新聞 社説一覧）
  ※ opinion.rss には社説が載らないため、社説一覧ページのHTMLから取得する

取得するもの:
  - 社説記事へのリンク（URLに /ddm/005/070/ を含むもの）
  - 見出しテキスト（<a>のテキスト。取れなければ空）
  - 公開日（URL内の8桁 YYYYMMDD から生成）
  - 新聞社名
  ※本文・要約・画像は取得・保存しない

使い方:
  python fetch_shasetsu.py           社説を抽出して data/articles.json に追記
  python fetch_shasetsu.py --dump    抽出結果を表示するだけ（保存しない）

依存: 標準ライブラリのみ
"""

import html
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

SOURCES = [
    {
        "name": "毎日新聞",
        "url": "https://mainichi.jp/editorial/",
        "referer": "https://mainichi.jp/",
        # このパターンを含むリンクを社説とみなす
        "path_marker": "/ddm/005/070/",
    },
]
KEEP_DAYS = 7   # 直近この日数だけ保持する

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "articles.json")
JST = timezone(timedelta(hours=9))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# <a href="...">テキスト</a> をゆるく拾う
A_TAG_RE = re.compile(
    r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
# タグ除去用
TAG_RE = re.compile(r"<[^>]+>")
# URL内の日付 YYYYMMDD
DATE_RE = re.compile(r"/articles/(\d{8})/")


def build_headers(referer: str) -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": referer,
    }


def fetch(url: str, referer: str) -> str:
    req = urllib.request.Request(url, headers=build_headers(referer))
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    # 文字コードは utf-8 前提（毎日新聞はutf-8）
    return raw.decode("utf-8", "replace")


def normalize_url(href: str, base: str) -> str:
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://mainichi.jp" + href
    return href


def clean_text(inner: str) -> str:
    # 改行系タグを空白に（塊を1本の文字列にする）
    inner = re.sub(r"<[^>]+>", " ", inner)   # すべてのタグを空白へ
    text = html.unescape(inner)
    # 全角スペースは残す（見出し内の区切りに使われるため一旦保持）
    # 連続する半角空白・改行・タブを1つの半角空白に
    text = re.sub(r"[ \t\r\n]+", " ", text).strip()

    # 見出しの後ろに続く「日付/時刻」「NNN文字」以降を切り捨てる
    # 例: 見出し 2026/7/26 02:01 1688文字 本文...
    cut = re.search(r"\s*\d{4}/\d{1,2}/\d{1,2}", text)   # 日付の直前で切る
    if cut:
        text = text[:cut.start()].strip()
    else:
        cut2 = re.search(r"\s*\d+\s*文字", text)          # 念のため文字数でも切る
        if cut2:
            text = text[:cut2.start()].strip()

    return text.strip()


def date_from_url(url: str) -> str:
    m = DATE_RE.search(url)
    if not m:
        return ""
    try:
        d = datetime.strptime(m.group(1), "%Y%m%d")
        return d.strftime("%Y-%m-%d")
    except Exception:
        return ""


def get_items(src: dict):
    body_referer_pairs = []
    marker = src["path_marker"]

    htmltext = fetch(src["url"], src.get("referer", ""))

    seen_local = set()
    results = []
    for m in A_TAG_RE.finditer(htmltext):
        href, inner = m.group(1), m.group(2)
        url = normalize_url(href, src["url"])
        if marker not in url:
            continue
        # クエリ・フラグメント除去（重複判定を安定させる）
        url = url.split("#")[0].split("?")[0]
        if url in seen_local:
            continue
        seen_local.add(url)

        title = clean_text(inner)
        results.append((title, url, date_from_url(url)))
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
    # 直近 KEEP_DAYS 日以内のものだけ残す
    cutoff = (datetime.now(JST) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    articles = [a for a in articles if a.get("published", "") >= cutoff]
    articles.sort(key=lambda a: (a.get("published", ""), a.get("newspaper", "")),
                  reverse=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)


def cmd_dump() -> int:
    for src in SOURCES:
        print(f"===== {src['name']} 社説一覧ダンプ =====")
        try:
            items = get_items(src)
        except Exception as e:
            print(f"[ERROR] 取得失敗: {e}")
            continue
        print(f"社説候補 = {len(items)} 件\n")
        for i, (title, url, date) in enumerate(items):
            print(f"[{i:2}] {date}  {title or '(見出し取得できず)'}")
            print(f"     {url}")
    return 0


def cmd_run() -> int:
    existing = load_existing()
    seen = {a["url"] for a in existing}
    added = 0
    fetch_failed = 0

    for src in SOURCES:
        try:
            items = get_items(src)
        except Exception as e:
            fetch_failed += 1
            print(f"[ERROR] {src['name']} の取得に失敗: {e}")
            continue

        for title, url, date in items:
            if not url:
                continue
            if url in seen:
                continue
            existing.append({
                "newspaper": src["name"],
                "title": title,
                "url": url,
                "published": date,
            })
            seen.add(url)
            added += 1
            print(f"[ADD] {date} {title}")
        print(f"[INFO] {src['name']}: 社説 {len(items)} 件検出")

    save(existing)
    print(f"\n完了: {added} 件追加 / 合計 {len(existing)} 件")

    if fetch_failed == len(SOURCES):
        print("[FATAL] すべての取得に失敗しました。")
        return 1
    return 0


def main() -> int:
    if "--dump" in sys.argv:
        return cmd_dump()
    return cmd_run()


if __name__ == "__main__":
    raise SystemExit(main())
