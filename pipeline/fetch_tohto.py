# -*- coding: utf-8 -*-
"""東都大学野球連盟(tohto-bbl.com)から試合日程・結果・星取表（順位表）を取得し、
data/leagues/tohto<div>-<year>-<season>/ に正規化JSONとして保存する。

データ出典: 一般財団法人 東都大学野球連盟 (http://www.tohto-bbl.com/)
1部〜4部の4リーグ制。春季・秋季それぞれ1シーズンとして扱う。
文字コードはShift_JIS。日程表は「週」「試合日」セルがrowspanで複数行に
またがるため、直前の値を引き継ぎながら1行=1試合に展開する。
順位表（星取表）は連盟公式の集計をそのまま取得する（大学野球は勝ち点制のため
自前集計はしない）。
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from common import fetch, cells_of, normalize_pct, to_int, strip_tags
from team_slugs import slug_for

BASE = "http://www.tohto-bbl.com"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "leagues"

SEASON_YEAR = 2026
# (シーズンコード, サイト側SEASONID, 表示名)
SEASONS = [
    ("haru", "01", "春季"),
    ("aki", "02", "秋季"),
]
# (リーグID, 部, コード用の数字)
DIVISIONS = [("01", "1部", "1"), ("02", "2部", "2"), ("03", "3部", "3"), ("04", "4部", "4")]

STANDINGS_HEADER_RE = re.compile(r"順位</td>.*?</tr>", re.DOTALL)
STANDINGS_ROW_RE = re.compile(r'<tr align="center">(.*?)</tr>', re.DOTALL)

ROW_RE = re.compile(r'<tr align="center" valign="middle">(.*?)</tr>\s*<!--end-->', re.DOTALL)
WEEK_RE = re.compile(r"第(\d+)週")
DATE_RE = re.compile(r'class="f10navy">(\d{1,2})/(\d{1,2})[（(][^<]*</td>')
GAME_RE = re.compile(
    r'<td width="20" class="f10navy">[^<]*</td>\s*'
    r'<td width="50"[^>]*class="f10navy">([^<]*)</td>\s*'
    r'<td width="30" class="f10navy">([^<]*)</td>\s*'
    r'<td width="20" class="f10navy">-</td>\s*'
    r'<td width="30" class="f10navy">([^<]*)</td>\s*'
    r'<td width="50" class="f10navy">([^<]*)</td>',
    re.DOTALL)
TIME_RE = re.compile(r'class="f10navy">(\d{1,2}:\d{2})</td>')
VENUE_LINK_RE = re.compile(r'\.\./studium/[^"\']*class="tb">([^<]+)</a>')
VENUE_CELL_RE = re.compile(r'<td width="(?:129|98)"[^>]*class="f10navy">(.*?)</td>', re.DOTALL)


COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def parse_standings(html: str) -> list[dict]:
    hm = STANDINGS_HEADER_RE.search(html)
    if not hm:
        return []
    end = html.find("</table>", hm.end())
    section = html[hm.end():end] if end != -1 else html[hm.end():hm.end() + 20000]
    # 同順位のチームはコメントアウトされた重複<td>（連番の順位）が残っており、
    # 単純なタグ抽出だとセル数がずれるため、行を見る前にコメントを除去する。
    section = COMMENT_RE.sub("", section)
    header_cells = cells_of(hm.group(0))
    # ヘッダー = [空, チーム名xN, 勝数,負数,分数,勝率,勝点]
    n_teams = len(header_cells) - 1 - 5
    entries = []
    for i, row_m in enumerate(STANDINGS_ROW_RE.finditer(section), 1):
        cells = cells_of(row_m.group(1))
        if len(cells) < 2 + n_teams + 5:
            continue
        rank_txt, team = cells[0], cells[1]
        wins, losses, draws, rate, points = cells[2 + n_teams:2 + n_teams + 5]
        w, l, d = to_int(wins), to_int(losses), to_int(draws)
        entries.append({
            "rank": to_int(rank_txt, default=i),
            "team": team,
            "slug": slug_for(team),
            "games": w + l + d, "wins": w, "losses": l,
            "draws": d, "points": to_int(points),
            "win_pct": normalize_pct(rate),
        })
    return entries


def parse_matches(html: str, season_year: int) -> list[dict]:
    matches = []
    seen_ids: set[str] = set()
    cur_mo = cur_dd = None
    for row in ROW_RE.findall(html):
        # 表示切り替え用にコメントアウトされた重複セル（同じ日付/球場の別レイアウト版）
        # が残っているため、先に取り除いてから解析する。
        row = COMMENT_RE.sub("", row)
        wm = WEEK_RE.search(row)
        dm = DATE_RE.search(row)
        if dm:
            cur_mo, cur_dd = int(dm.group(1)), int(dm.group(2))
        gm = GAME_RE.search(row)
        if not gm:
            continue
        home, s1, s2, away = (g.strip() for g in gm.groups())
        if not home or not away:
            continue
        tm = TIME_RE.search(row)
        time_txt = tm.group(1) if tm else "未定"
        vm = VENUE_LINK_RE.search(row)
        if vm:
            venue = vm.group(1).strip()
        else:
            vc = VENUE_CELL_RE.search(row)
            venue = strip_tags(vc.group(1)) if vc else "未定"
        venue = venue or "未定"

        d_iso = None
        if cur_mo and cur_dd:
            try:
                d_iso = date(season_year, cur_mo, cur_dd).isoformat()
            except ValueError:
                d_iso = None
        played = bool(re.fullmatch(r"\d+", s1) and re.fullmatch(r"\d+", s2))
        base_id = f'{d_iso or "tbd"}-{slug_for(home)}-vs-{slug_for(away)}'
        mid, n = base_id, 2
        while mid in seen_ids:
            mid = f"{base_id}-{n}"
            n += 1
        seen_ids.add(mid)
        matches.append({
            "id": mid,
            "date": d_iso,
            "time": time_txt,
            "home": home, "away": away,
            "home_slug": slug_for(home), "away_slug": slug_for(away),
            "venue": venue,
            "status": "played" if played else "scheduled",
            "home_score": int(s1) if played else None,
            "away_score": int(s2) if played else None,
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


def fetch_division(season_id: str, season_label: str, league_id: str, div_label: str,
                    season_year: int):
    url = f"{BASE}/gameinfo/schedule.php?YEAR={season_year}&SEASONID={season_id}&LEAGUEID={league_id}"
    try:
        html = fetch(url, encoding="cp932")
    except Exception as e:
        print(f"[warn] 東都{div_label} {season_year}{season_label}: 取得失敗 ({e})", file=sys.stderr)
        return None
    matches = parse_matches(html, season_year)
    standings = parse_standings(html)
    if not matches and not standings:
        print(f"[info] 東都{div_label} {season_year}{season_label}: データなし（未公開）", file=sys.stderr)
        return None
    teams = build_teams(matches, standings)
    return {"matches": matches, "standings": {"総合": standings}, "teams": teams, "url": url}


def main() -> None:
    total = len(SEASONS) * len(DIVISIONS)
    ok = 0
    for season_code, season_id, season_label in SEASONS:
        for league_id, div_label, div_num in DIVISIONS:
            result = fetch_division(season_id, season_label, league_id, div_label, SEASON_YEAR)
            if result is None:
                continue
            code = f"tohto{div_num}-{SEASON_YEAR}-{season_code}"
            out_dir = DATA_DIR / code
            out_dir.mkdir(parents=True, exist_ok=True)
            played = sum(1 for m in result["matches"] if m["status"] == "played")
            meta = {
                "code": code,
                "competition": "東都大学野球連盟",
                "division": div_label,
                "season_year": SEASON_YEAR,
                "season_name": season_label,
                "season_code": season_code,
                "league": f"東都大学野球{div_label} {SEASON_YEAR}年{season_label}リーグ戦",
                "source": "東都大学野球連盟",
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
            print(f"{code}: 試合{len(result['matches'])}件(結果{played}) "
                  f"チーム{len(result['teams'])}")
            ok += 1
    print(f"done: {ok}/{total} divisions (東都大学)")


if __name__ == "__main__":
    main()
