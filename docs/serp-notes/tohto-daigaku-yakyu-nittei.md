# SERP分析メモ: 東都大学野球 日程

- 実施日: 2026-09-17
- レーン/番号: H6（上位クエリ）
- 想定slug: `tohto-daigaku-yakyu-nittei-guide`

## KW選定の経緯

当初ターゲットは H1「大学野球 強豪」だったが、`content/articles/daigaku-yakyu-kyogo-guide.md`
（2026-09-11公開・title「大学野球の強豪はどこか｜2026年の順位表で見る六大学・東都の勢力図」）が
同一検索意図を既にカバーしているため見送り。keyword-inventory.md の H群から未カバーの
H6「東都大学野球 日程」に変更した。

既存記事との重複チェック結果:
- `daigaku-yakyu-chukei-haishin-guide`（配信・中継）: 視聴手段が主題。日程は末尾で軽く触れるのみ → 重複なし
- `jingu-kyujo-daigaku-yakyu-kansen-guide`（神宮球場観戦）: 六大学・神宮に限定。東都の2〜4部会場は未カバー → 重複なし
- `daigaku-yakyu-league-shikumi-guide`（仕組み解説）: 勝ち点制・部制度の制度解説。日程表の読み方や会場情報は未カバー → 重複なし
- `daigaku-yakyu-kyogo-guide`（強豪）: 順位表が主題 → 重複なし

## SERP上位の顔ぶれ（WebSearch・4クエリで確認）

1. 一球速報.com（baseball.omyutech.com） — 速報系データベース。1〜4部の試合情報あり
2. 球歴.com（kyureki.com） — 日程・結果のデータベース
3. スポカレ（spocale.com） — 日程一覧
4. 明治神宮野球場公式（jingu-stadium.com/event/2026/tohto_a_index.html） — 神宮開催分の月間スケジュール
5. univbbl.com（大学野球総合サイト） — 令和8年度秋季1部リーグの日程ページ
6. 東都大学野球連盟 公式（tohto-bbl.com/gameinfo/schedule.php） — 一次情報。部ごとにURLが分岐・Shift_JIS
7. イープラス（eplus.jp） — チケット販売
8. 日本大学スポーツ公式（nihon-u.ac.jp） — 大学単位の観戦イベント告知
9. 個人運営の日程まとめサイト（xn--8wv97xz6xo7h.online） — 1〜4部の日程・結果まとめ
10. スポーツナビ（baseball.yahoo.co.jp） — 東都2部の日程・結果
（ノイズ: 東都大学準硬式野球連盟 tohtojunko.com、東京新大学野球連盟 new-tokyo-bbl.com）

## 共通点と差別化点（3行）

- 共通点: 上位はほぼ「試合日程データベース」か「1部（神宮開催分）だけの日程ページ」で、日程の羅列が中心。2部〜4部を横断して会場・開催曜日の違いまで解説した記事は見当たらない。
- 共通点2: 一次情報である連盟公式は部ごとにURLが分かれShift_JISで閲覧性が低く、「どの部がどこでやるのか」を1ページで把握できる導線がない。
- 差別化点: ①2026年秋季の実データで1部〜4部の会場を横断整理（1部=神宮／2部=等々力・大田／3部=大学グラウンド等7会場を転戦／4部=芝浦工大・一橋大）、②勝ち点制ゆえに日程が流動的で会場が「調整中」のまま残る構造を、当サイトの取得データ（2026-09-16時点で1部の10/13以降が「調整中」）を根拠に説明、③各部の `schedule` / `standings` ページへ直接導線。

## 必須の内部リンク（実在パス確認済み・2026-09-17）

- https://baseballmania.jp/tohto1-2026-aki/schedule/ （`site/tohto1-2026-aki/schedule` 存在）
- https://baseballmania.jp/tohto2-2026-aki/schedule/
- https://baseballmania.jp/tohto3-2026-aki/schedule/
- https://baseballmania.jp/tohto4-2026-aki/schedule/
- https://baseballmania.jp/tohto1-2026-aki/standings/
- https://baseballmania.jp/tohto1-2026-aki/clubs/asia/ （clubs配下: aoyamagakuin/asia/chuo/kokugakuin/rissho/toyo）
- https://baseballmania.jp/rikudai-2026-aki/schedule/

## 一次情報の確認状況

- 東都大学野球連盟公式（tohto-bbl.com）は 2026-09-17 時点で HTTPS 証明書エラーのため WebFetch 不可。
  代わりに当サイトが連盟公式日程表から取得済みの `data/leagues/tohto{1,2,3,4}-2026-aki/`
  （`meta.json` の `source_updated_at`: 2026-09-16、`source_url`: tohto-bbl.com の各部日程表）を根拠に使用する。
- 入場料・チケット価格は一次情報で確定できなかったため**記事に金額を書かない**。
- 第57回明治神宮野球大会（2026年）の日程は主催者公式（student-baseball.or.jp）で確認できなかったため**日程を書かない**。
- 秋季入替戦の日程も一次確認できず**書かない**。
