# 社説リンクアーカイブ（PoC / 毎日新聞のみ）

各紙の社説へのリンクを日付ごとにまとめて公開する静的サイトの試作です。
**保存するのは「新聞社名・公開日・見出し・元記事URL」のみ**で、本文・要約・画像は扱いません。

現在の対象は **毎日新聞のみ**（公式RSSを利用）。
朝日・日経は利用条件の確認後に追加できる構造にしています。

## 構成

```
shasetsu-archive/
├─ index.html                     … 表示ページ（data/articles.json を読み込む）
├─ data/
│   └─ articles.json              … 蓄積データ（Actionsが更新）
├─ scripts/
│   └─ fetch_shasetsu.py          … RSS取得スクリプト（標準ライブラリのみ）
├─ .github/workflows/
│   └─ update.yml                 … 毎日 JST 06:00 に自動更新
└─ README.md
```

## 仕組み

```
GitHub Actions（毎朝）
   └─ python scripts/fetch_shasetsu.py
        ├─ 毎日新聞RSSを取得
        ├─ タイトルが「社説」で始まる項目だけ抽出
        ├─ タイトル / URL / 公開日 / 新聞社名 を取得
        └─ data/articles.json に追記（URLで重複排除）
   └─ 変更があれば自動commit＆push
GitHub Pages が index.html を公開
```

## セットアップ手順

1. GitHub で新しいリポジトリを作成し、このフォルダ一式をpush
2. リポジトリの **Settings → Pages** で
   - Source: `Deploy from a branch`
   - Branch: `main` / `/ (root)`
3. **Settings → Actions → General → Workflow permissions** を
   `Read and write permissions` に設定（Actionsがpushできるように）
4. **Actions** タブから `Update shasetsu archive` を一度手動実行（Run workflow）
   - `data/articles.json` が更新される
5. 公開URL（`https://<ユーザー名>.github.io/<リポジトリ名>/`）で表示を確認

## ローカルでの試し方

```bash
# データ取得（毎日新聞RSSにアクセスします）
python scripts/fetch_shasetsu.py

# 表示確認（簡易サーバ）
python -m http.server 8000
# → ブラウザで http://localhost:8000/ を開く
```

## 新聞社を追加する場合

`scripts/fetch_shasetsu.py` の `SOURCES` に追記します。

```python
SOURCES = [
    {"name": "毎日新聞", "rss": "https://mainichi.jp/rss/etc/opinion.rss", "title_prefix": "社説"},
    # {"name": "朝日新聞", "rss": "<社説RSSのURL>", "title_prefix": "（社説）"},
]
```

※追加前に、その新聞社のRSS提供の有無・利用条件（自動取得の可否、リンク条件）を必ず確認してください。

## 注意

- 各記事の著作権は各新聞社に帰属します。
- 本サイトは本文を保存・表示しません。リンク先で各社サイトを閲覧する形です。
- RSSやページ構成は予告なく変更されることがあります（リンク切れの可能性あり）。
