# ベースボールマニア — 大学野球情報メディア

大学野球の情報メディア「ベースボールマニア」（運営: PieceTimes）。
東京六大学野球連盟・東都大学野球連盟の公式サイトが公開している試合日程・結果・
順位表（星取表）を取得し、静的サイトを生成する。

- 公開URL: https://tkoba-piecetimes.github.io/baseballmania/
  （独自ドメインは未定。取得次第 `site/CNAME` を追加してカスタムドメインに切り替える）
- 対象:
  - 東京六大学野球連盟（big6.gr.jp）: 6校総当たり1リーグ（部制なし）
  - 東都大学野球連盟（tohto-bbl.com）: 1部〜4部の4リーグ
  - 東京新大学野球連盟（new-tokyo-bbl.com）: 1部〜4部の4リーグ（2026年秋季から）
  - 中国地区大学野球連盟（cubf5589.com）: 1部（中国六大学野球）〜3部の3リーグ
    （2026年秋季から。新人戦（kind=4）は対象外）
  - 阪神大学野球連盟（hanshin-bbl.com）: 1部・2部東・2部西の3リーグ
    （2026年秋季から。日程はPDF配布のみだが、勝敗表（Excel書き出しHTML）に
    節ごとの結果も含まれているためmatches.jsonも取得できる）
  - 東京六大学・東都はいずれも2026年春季・秋季の2シーズン制。データ取得は
    2026年春季から開始（秋季は日程が公開され次第、結果も自動的に埋まっていく）。
    東京新大学・中国地区・阪神の3連盟は2026年秋季から取得開始（シーズン
    パラメータ化してあるので春季・翌年以降の追加もfetch_*.py側の定数変更のみで対応可能）
- 詳細・パース上の注意点は `docs/baseball-sources.md` 参照

## 仕組み

```
big6.gr.jp（東京六大学）/ tohto-bbl.com（東都大学、Shift_JIS）
  / new-tokyo-bbl.com（東京新大学）/ cubf5589.com（中国地区）
  / hanshin-bbl.com（阪神、Shift_JIS/CP932）
  → pipeline/fetch_big6.py / fetch_tohto.py / fetch_shintokyo.py
    / fetch_chugoku.py / fetch_hanshin.py
    ※ pipeline/common.py に共通ヘルパー（fetch/タグ除去/勝率表記統一）を集約
    ※ pipeline/fetch_all.py が連盟ごとにtry/exceptで囲んで順番に実行
      （1連盟の失敗が他連盟を止めない）
  → data/leagues/<code>/  （rikudai-2026-haru, tohto1-2026-haru, ... の全20リーグ）
  → pipeline/generate_site.py
  → site/
```

**順位表は自前集計せず、連盟公式サイトの順位表（星取表）をそのまま取得する。**
大学野球は同一カードで2先勝すると勝ち点1がつく「勝ち点制」という独自ルールのため、
ラグビー/サッカー版のような勝敗からの自動集計（`compute_standings`）は行わない。

## 実行

```
pip install pykakasi
python pipeline/fetch_all.py
python pipeline/generate_site.py
```

（連盟ごとに個別実行したい場合は `pipeline/fetch_big6.py` / `fetch_tohto.py` を
単独で実行できる）

ローカル確認: `python -m http.server 8943 -d site`

## 自動更新

`.github/workflows/update.yml` が毎日6:00 JST（UTC 21:00）に自動実行され、
データ取得→サイト生成→data/siteをコミット→GitHub Pagesへデプロイする。
`main`へのpush時にも同様にデプロイが走る。

## 未実装（今後）

- 独自ドメイン取得・GitHub Pages カスタムドメイン設定
- GA4 / Search Console 連携（`pipeline/generate_site.py`の`GA_MEASUREMENT_ID`/
  `GSC_VERIFICATION`が空文字のため未設定。取得後に値を入れる）
- 読みもの記事・用語辞典（content/articles/, content/glossary.json を追加すれば
  自動で有効化される）
- 協賛メニューの中身入れ（チームページの協賛枠は現状プレースホルダー）
- 2026年秋季の日程・結果の充実（開幕後、自動更新で順次埋まる）
