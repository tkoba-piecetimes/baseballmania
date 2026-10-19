# 図解（assets/diagrams/*.svg）の確認元

読者の知識レベル配慮（仕様 reader-level-spec.md v1.0）で描いたSVG図が、何を根拠にしているかの記録。
確認日: 2026-10-19。新しい図を足すときも、ここに1行ずつ追記する。

| slug | 内容 | 確認元（公式情報） | 備考 |
| --- | --- | --- | --- |
| baseball-field-positions | 守備位置と番号1〜9、DHの位置づけ | NPB式スコアブックの記入方法（守備位置の数字）https://npb.jp/scoring/scoring_howto.pdf ／ DH: 日本高野連「指名打者について【公認野球規則5.11】」https://www.jhbf.or.jp/memberschool/regulation/dh/ | 配置は一般的な守備位置の概略図（寸法は描いていない） |
| baseball-diamond-bases | 内野・外野・ファウルライン・ファウルゾーン、走る向き（本塁→一塁→二塁→三塁→本塁） | NPB式スコアブックの記入方法（本塁・各塁・守備位置）https://npb.jp/scoring/scoring_howto.pdf ／ 走者の進塁・触れ直し・逆走の規定: 日本高野連の審判員向け資料（走者に関する規則）https://www.jhbf.or.jp/memberschool/umpire/07.pdf ／ NPB 2013年度規則改正（フェア地域・ファウル地域の用語。一塁・三塁を基準にした判断）https://npb.jp/npb/2013rules.html | 寸法（塁間・投手板までの距離）は図に書いていない。ファウルラインの定義条文そのものは未確認のため、一般的な区画名のみ記載 |
| baseball-strike-zone | ストライクゾーンの上限・下限 | 日本高野連 審判員講習資料「打者に関する規則」（定義72・73）https://www.jhbf.or.jp/memberschool/umpire/06.pdf ：上限=打者の肩の上部とユニフォームのズボンの上部との中間点の水平ライン、下限=ひざ頭の下部のライン、本塁上の空間 | 判定は審判員が行う旨も同資料の「宣告」に基づく |
| baseball-winpoint-system | 勝ち点制（先に2勝で勝ち点1、順位の決め方、優勝決定戦、開催日） | 東京六大学野球連盟「対戦方式・規定等」http://www.big6.gr.jp/game/league/league_regulation.html（勝率の計算に引き分けを含めない旨も同ページ） | 東都大学野球連盟も2戦先勝の勝ち点制（東都の入替戦ページの試合結果表示と、記事 daigaku-yakyu-irekaesen-guide の記述）。図は東京六大学の規定として記載 |
| baseball-tohto-bu-system | 東都の1部〜4部と入れ替え戦（上の部の最下位×下の部の優勝）、昇格・降格 | 東都大学野球連盟 令和8年度春季入替戦 http://www.tohto-bbl.com/gameinfo/2026/change_s.shtml（「1部6位×2部1位」の対戦と残留・昇格表示。3試合まで行われる結果表）／ 連盟ガイド（四部制）http://www.tohto-bbl.com/tohto/ | 各部の加盟校数は年度で変わるため図には書かない。「2戦先勝」は記事 daigaku-yakyu-irekaesen-guide の記述と入替戦ページの試合数表示に基づく |
| baseball-league-compare | 東京六大学（6校固定・総当たり・部なし）と東都（1〜4部・入れ替え戦あり）の違い | 東京六大学野球連盟 対戦方式・規定等（6校総当たり）http://www.big6.gr.jp/game/league/league_regulation.html ／ 東都大学野球連盟 連盟ガイド（四部制・入替戦）http://www.tohto-bbl.com/tohto/ | 6校の頭文字は早稲田・慶應義塾・明治・法政・立教・東京（大学名のみ。ロゴ・ユニフォームは使っていない） |
| baseball-nyubu-routes | 入部の3ルート（スポーツ推薦・セレクション・一般入部）の時期・主体・特徴 | 文部科学省「令和3年度入学者選抜について」（総合型選抜・学校推薦型選抜の区分）https://www.mext.go.jp/a_menu/koutou/senbatsu/1412102_00003.htm ／ 青山学院大学硬式野球部「入部希望の方へ」（練習参加・入部の流れの一例）https://www.agubbc.com/ ／ 早稲田大学野球部「入部を希望される方へ」https://www.wasedabbc.org/join/ ／ 内容の整理は記事 koko-yakyu-daigaku-shingaku-guide の表と出典に準拠 | 大学ごとに制度が違うため、図にも「大学ごとに違う」と明記。特定大学の制度として描いていない |
| baseball-student-staff-roles | 学生スタッフ4種（主務・マネージャー／学生コーチ／アナリスト／学生トレーナー）の主な役割 | 東京大学野球部（主務・マネージャー）https://tokyo6s.com/blog/tokyo/2025/05/03/syumu/ ／ 東京大学運動会硬式野球部 入部案内（アナリスト・学生コーチ）https://tokyo-bbc.net/nyuubu/nyuubu_analyst.html ／ 早稲田大学野球部（学生トレーナー・データ班）https://www.wasedabbc.org/join/ ／ 立教大学・早稲田大学の学生コーチ紹介（記事 daigaku-yakyubu-gakusei-coach-yakuwari-guide の出典） | 呼び名・募集の有無は大学で違う（例: 東京大学では学生コーチを「アナリスト」と呼ぶ）。図にも明記 |

## 描くのを見送った図
- タイブレークの走者配置（無死一・二塁など）: 東都・六大学のリーグ戦の現行規定を連盟公式ページで確認できず、大会ごとに方式が違う（2026年から変わったという報道もあり、連盟発表では未確認）ため描かない。用語辞典の説明も「走者を塁に置いて始める方式。形は大会ごとに違う」までに留めた。
- 塁間・投手板までの距離の寸法入りグラウンド図: 公認野球規則の本文（競技場の章）をNPB/日本高野連の公開資料から直接確認できなかったため描かない。

## 用語辞典（data/glossary.json）の主な確認元
- 記録・成績の用語（打率・出塁率・防御率・自責点・投球回・盗塁・犠打・犠飛・併殺・四球・死球・暴投・捕逸・残塁・失策・セーブ・故意四球・先発/救援）: NPB「公認野球規則 9.00 記録に関する規則」https://npb.jp/scoring/officialrule_900.pdf と「記録の計算方法」https://npb.jp/scoring/calculation.html
- リーグの仕組み（勝ち点・総当たり・優勝決定戦・ベンチ入り）: 東京六大学野球連盟 対戦方式・規定等。部制・入れ替え戦・昇格降格: 東都大学野球連盟
- プロ志望届・特待生・学生野球憲章: 全日本大学野球連盟「日本学生野球憲章 付属規定」https://www.jubf.net/material/doc/charter_accompanyingrule.pdf
- 準硬式: 早稲田大学競技スポーツセンター準硬式野球部ページ https://www.waseda.jp/inst/athletic/club/junko-baseball/
- ドラフト会議・NPB: NPB「2026年新人選手選択会議 開催と特別協賛社決定のお知らせ」https://npb.jp/news/detail/20260819_01.html ／ 社会人野球: 日本野球連盟 https://www.jaba.or.jp/
