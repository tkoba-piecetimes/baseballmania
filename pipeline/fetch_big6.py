# -*- coding: utf-8 -*-
"""東京六大学野球連盟(big6.gr.jp)から試合日程・結果・順位表を取得し、
data/leagues/rikudai-<year>-<season>/ に正規化JSONとして保存する。

データ出典: 一般財団法人 東京六大学野球連盟 (https://www.big6.gr.jp/)
六大学は6校総当たり1本のリーグ（部制なし）。春季・秋季それぞれ1シーズンとして扱う。
順位表は連盟公式の勝敗表をそのまま取得する（大学野球は勝ち点制のため自前集計はしない）。

URL: https://www.big6.gr.jp/game/league/<year><s|a>/<year><s|a>_schedule.html
     （sは春季、aは秋季。1ページに日程表と勝敗表の両方が掲載されている）
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from common import fetch, cells_of, normalize_pct, to_int
from team_slugs import slug_for

BASE = "https://www.big6.gr.jp"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "leagues"

SEASON_YEAR = 2026
# (シーズンコード, サイト側の記号, 表示名)
SEASONS = [
    ("haru", "s", "春季"),
    ("aki", "a", "秋季"),
]

VENUE_RE = re.compile(r"会場</span><br>\s*([^<]+)<br>")

DAY_RE = re.compile(
    r'<td class="scd_date" nowrap>(\d{1,2})/(\d{1,2}) \([^)]*\)</td>\s*'
    r'<td class="text14px"[^>]*>[^<]*</td>\s*'
    r'<td class="text13px"[^>]*>([^<]*)</td>\s*'
    r'<td>(.*?)<div style="clear:both;">',
    re.DOTALL)
GAME_RE = re.compile(
    r'<td align="right" class="scd_vs">([^<]*)</td>\s*'
    r'<td class="scd_vs"[^>]*>([^<]*)</td>\s*'
    r'<td align="left" class="scd_vs">([^<]*)</td>',
    re.DOTALL)

STANDINGS_HEADER_RE = re.compile(r"順位</td>.*?</tr>", re.DOTALL)
STANDINGS_ROW_RE = re.compile(
    r'<tr bgcolor="white" valign="middle" align="center">(.*?)</tr>', re.DOTALL)
# チーム名セルは <!--<a ...>--><span class="display_none_on_sp">慶大</span>
# <span class="display_on_sp">慶</span></a> という構造で、コメント混じりのため
# 単純なタグ除去では壊れる。display_none_on_sp（フル表記）だけを直接抜き出す。
TEAM_NAME_RE = re.compile(r'display_none_on_sp">([^<]+)</span>')


def parse_standings(html: str) -> list[dict]:
    hm = STANDINGS_HEADER_RE.search(html)
    if not hm:
        return []
    end = html.find("</table>", hm.end())
    section = html[hm.end():end] if end != -1 else html[hm.end():hm.end() + 20000]
    header_cells = cells_of(hm.group(0))
    # ヘッダー = [空(ロゴ), チーム名xN, 試合,勝利,敗戦,引分,勝ち点,勝率, 空(末尾スペーサ)]
    n_teams = len(header_cells) - 2 - 6
    entries = []
    for i, row_m in enumerate(STANDINGS_ROW_RE.finditer(section), 1):
        row = row_m.group(1)
        cells = cells_of(row)
        # cells = [順位, チームロゴ(空), チーム名(壊れうる), vs x n_teams, 試合,勝利,敗戦,引分,勝ち点,勝率, 末尾スペーサ]
        if len(cells) < 3 + n_teams + 6:
            continue
        rank_txt = cells[0]
        tm = TEAM_NAME_RE.search(row)
        team = tm.group(1) if tm else cells[2]
        stats = cells[3 + n_teams:3 + n_teams + 6]
        games, wins, losses, draws, points, rate = stats
        entries.append({
            "rank": to_int(rank_txt, default=i),
            "team": team,
            "slug": slug_for(team),
            "games": to_int(games), "wins": to_int(wins), "losses": to_int(losses),
            "draws": to_int(draws), "points": to_int(points),
            "win_pct": normalize_pct(rate),
        })
    return entries


def parse_matches(html: str, season_year: int) -> list[dict]:
    venue_m = VENUE_RE.search(html)
    venue = venue_m.group(1).strip() if venue_m else "明治神宮野球場"
    matches = []
    seen_ids: set[str] = set()
    for mo, dd, day_time, day_html in DAY_RE.findall(html):
        try:
            d_iso = date(season_year, int(mo), int(dd)).isoformat()
        except ValueError:
            d_iso = None
        for gi, (home, score_txt, away) in enumerate(GAME_RE.findall(day_html), 1):
            home, away = home.strip(), away.strip()
            if not home or not away:
                continue
            sm = re.match(r"(\d+)\s*-\s*(\d+)", score_txt.strip())
            played = bool(sm)
            base_id = f'{d_iso or "tbd"}-{slug_for(home)}-vs-{slug_for(away)}'
            mid, n = base_id, 2
            while mid in seen_ids:
                mid = f"{base_id}-{n}"
                n += 1
            seen_ids.add(mid)
            matches.append({
                "id": mid,
                "date": d_iso,
                "time": day_time.strip() if gi == 1 else "第1試合終了後",
                "home": home, "away": away,
                "home_slug": slug_for(home), "away_slug": slug_for(away),
                "venue": venue,
                "status": "played" if played else "scheduled",
                "home_score": int(sm.group(1)) if played else None,
                "away_score": int(sm.group(2)) if played else None,
                "note": "",
            })
    return matches


def build_teams(matches, standings) -> dict:
    teams = {}
    for e in standings:
        teams[e["team"]] = {"team": e["team"], "slug": e["slug"], "block": "総合"}
    for m in matches:
        for team in (m["home"], m["away"]):
            teams.setdefault(team, {"team": team, "slug": slug_for(team), "block": "総合"})
    return teams


def fetch_season(season_id: str, season_label: str, season_year: int):
    season_str = f"{season_year}{season_id}"
    url = f"{BASE}/game/league/{season_str}/{season_str}_schedule.html"
    try:
        html = fetch(url)
    except Exception as e:
        print(f"[warn] 東京六大学 {season_year}{season_label}: 取得失敗 ({e})", file=sys.stderr)
        return None
    matches = parse_matches(html, season_year)
    standings = parse_standings(html)
    if not matches and not standings:
        print(f"[info] 東京六大学 {season_year}{season_label}: データなし（未公開）", file=sys.stderr)
        return None
    teams = build_teams(matches, standings)
    return {"matches": matches, "standings": {"総合": standings}, "teams": teams, "url": url}


def main() -> None:
    ok = 0
    for season_code, season_id, season_label in SEASONS:
        result = fetch_season(season_id, season_label, SEASON_YEAR)
        if result is None:
            continue
        code = f"rikudai-{SEASON_YEAR}-{season_code}"
        out_dir = DATA_DIR / code
        out_dir.mkdir(parents=True, exist_ok=True)
        played = sum(1 for m in result["matches"] if m["status"] == "played")
        meta = {
            "code": code,
            "competition": "東京六大学野球連盟",
            "division": "",
            "season_year": SEASON_YEAR,
            "season_name": season_label,
            "season_code": season_code,
            "league": f"東京六大学野球 {SEASON_YEAR}年{season_label}リーグ戦",
            "source": "東京六大学野球連盟",
            "source_url": result["url"],
            "source_updated_at": date.today().isoformat(),
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
        }
        (out_dir / "matches.json").write_text(
            json.dumps(result["matches"], ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / "standings.json").write_text(
            json.dumps(result["standings"], ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / "teams.json").write_text(
            json.dumps(result["teams"], ensure_ascii=False, indent=1), encoding="utf-8")
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{code}: 試合{len(result['matches'])}件(結果{played}) チーム{len(result['teams'])}")
        ok += 1
    print(f"done: {ok}/{len(SEASONS)} seasons (東京六大学)")


if __name__ == "__main__":
    main()
