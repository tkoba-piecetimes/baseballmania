# -*- coding: utf-8 -*-
"""東京六大学野球連盟(big6.gr.jp)の個人成績ランキング（打撃・投手）を取得し、
data/leagues/rikudai-<year>-<season>/players.json に保存する。

データ出典: 一般財団法人 東京六大学野球連盟 (https://www.big6.gr.jp/)
連盟公式が「規定打席」「規定投球回」を満たした選手のみを対象に集計・掲載している
公式ランキングをそのまま取得する（自前集計はしない）。本サイトでは上位10人のみを掲載。

URL: https://www.big6.gr.jp/system/prog/kojinseiseki_season.php?m=pc&gs=ranking&k=<batting|pitching>&s=<year><s|a>
      （kojinseiseki = 個人成績。sは春季、aは秋季）

東都大学野球連盟(tohto-bbl.com)は個人成績ページの調査結果、現行シーズンの成績
ランキングに相当するページが存在しない（「選手名鑑」は氏名・学年・出身校等の
プロフィールのみで成績を含まない。「過去の記録」は歴代記録保持者一覧のみで、
かつHTMLタグの閉じ忘れが多数あり構造が不安定）と判断し、個人成績機能は
東京六大学のみで提供する（docs/baseball-sources.md に調査記録あり）。
"""
import json
import re
import sys
from pathlib import Path

from common import fetch, cells_of, to_int
from team_slugs import slug_for

BASE = "https://www.big6.gr.jp"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "leagues"

SEASON_YEAR = 2026
SEASONS = [
    ("haru", "s", "春季"),
    ("aki", "a", "秋季"),
]
TOP_N = 10

# ランキング表のチーム識別画像ファイル名 -> 連盟表記の略称（team_slugs.TEAM_INFOのキーと
# 一致させる。画像ファイル名は "rikkio"/"tokyo" 表記で、既存スラッグ "rikkyo"/"todai" とは
# 異なるため、略称経由でslug_for()に渡してスラッグを揃える）
IMG_SLUG_TO_TEAM = {
    "waseda": "早大", "keio": "慶大", "meiji": "明大",
    "hosei": "法大", "rikkio": "立大", "tokyo": "東大",
}

ROW_RE = re.compile(r'<tr bgcolor="ffffff" align="center" height="23">(.*?)</tr>', re.DOTALL)
TEAM_IMG_RE = re.compile(r'image/([a-z]+)\.gif" class="display_none_on_sp"')


def parse_ranking(html: str, kind: str) -> list[dict]:
    """打撃(batting)・投手(pitching)ランキング表を解析する。
    表は<tr bgcolor="ffffff" align="center" height="23">の行が並ぶだけの単純な構造で、
    セルの入れ子もないため、既存のcells_of()がそのまま使える（東都のような
    表示切り替え用コメントの混入は無い）。チームは氏名セルの前にある画像セルの
    ファイル名から判定する（テキストが無いため）。"""
    entries = []
    for row in ROW_RE.findall(html):
        cells = cells_of(row)
        tm = TEAM_IMG_RE.search(row)
        img_slug = tm.group(1) if tm else None
        team = IMG_SLUG_TO_TEAM.get(img_slug)
        if not team:
            print(f"[warn] 個人成績: 未知のチーム画像 ({img_slug})", file=sys.stderr)
            continue
        name = cells[2] if len(cells) > 2 else ""
        if not name:
            continue
        rank = to_int(cells[0], default=len(entries) + 1)
        entry = {"rank": rank, "team": team, "slug": slug_for(team), "name": name}
        if kind == "batting":
            if len(cells) < 19:
                continue
            # cells: [順位,(空),氏名,試合,打席,打数,得点,安打,二塁打,三塁打,
            #         本塁打,塁打,打点,盗塁,犠打,四死球,三振,失策,打率]
            entry.update({
                "games": to_int(cells[3]), "at_bats": to_int(cells[5]),
                "hits": to_int(cells[7]), "home_runs": to_int(cells[10]),
                "rbi": to_int(cells[12]), "avg": cells[18],
            })
        elif kind == "pitching":
            if len(cells) < 22:
                continue
            # cells: [順位,(空),氏名,試合,完投,完了,当初,無点勝,無四球,勝利,敗戦,
            #         引分,打者,投球回,安打,本塁打,四死球,三振,失点,自責点,防御率,球数]
            entry.update({
                "games": to_int(cells[3]), "wins": to_int(cells[9]),
                "losses": to_int(cells[10]), "innings": cells[13],
                "strikeouts": to_int(cells[17]), "era": cells[20],
            })
        else:
            continue
        entries.append(entry)
    entries.sort(key=lambda e: e["rank"])
    return entries[:TOP_N]


def fetch_ranking(season_id: str, season_label: str, kind: str, season_year: int) -> list[dict]:
    season_str = f"{season_year}{season_id}"
    url = f"{BASE}/system/prog/kojinseiseki_season.php?m=pc&gs=ranking&k={kind}&s={season_str}"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"[warn] 東京六大学 個人成績({kind}) {season_year}{season_label}: 取得失敗 ({e})",
              file=sys.stderr)
        return []
    return parse_ranking(html, kind)


def main() -> None:
    ok = 0
    for season_code, season_id, season_label in SEASONS:
        batting = fetch_ranking(season_id, season_label, "batting", SEASON_YEAR)
        pitching = fetch_ranking(season_id, season_label, "pitching", SEASON_YEAR)
        code = f"rikudai-{SEASON_YEAR}-{season_code}"
        out_dir = DATA_DIR / code
        if not batting and not pitching:
            print(f"[info] {code}: 個人成績データなし（未公開、規定打席・投球回未到達など）",
                  file=sys.stderr)
            continue
        if not out_dir.exists():
            print(f"[warn] {code}: リーグデータ未取得のためスキップ（先にfetch_big6.pyを実行）",
                  file=sys.stderr)
            continue
        (out_dir / "players.json").write_text(
            json.dumps({"batting": batting, "pitching": pitching}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print(f"{code}: 個人成績 打撃{len(batting)}件 投手{len(pitching)}件")
        ok += 1
    print(f"done: {ok}/{len(SEASONS)} seasons (東京六大学 個人成績)")


if __name__ == "__main__":
    main()
