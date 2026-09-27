# -*- coding: utf-8 -*-
"""中国地区大学野球連盟(cubf5589.com)から試合結果・順位表を取得し、
data/leagues/chugoku<div>-<year>-<season>/ に正規化JSONとして保存する。

データ出典: 中国地区大学野球連盟 (http://www.cubf5589.com/)
1部（伝統的に「中国六大学野球リーグ戦」と呼ばれる）〜3部の3リーグを対象とする
（kind=4の新人戦は対象外）。ページは `league_match_detail.php?kind=<1-3>`。
文字コードはUTF-8、静的HTML。

このサイトは「日程」ページを持たず、試合が行われるたびに1試合ごとの
ボックススコア（先攻/後攻・イニングごとの得点・計）が試合結果ページに
追記されていく方式。よって matches.json には確定済みの結果のみが載る
（未実施の今後の日程はサイト側に掲載がない）。

順位表（勝敗表）は連盟公式の集計（試合数の内訳は掲載されないため
勝敗数から試合数を算出、勝ち点は連盟公式の値をそのまま使用）を取得するが、
「順位」そのものは表内に明記されていない（星取表としてチーム固定順に
並んでいるだけ）ため、このパイプラインで勝ち点→勝率→勝数の順にソートして
順位を付与する（連盟公式の勝敗数・勝ち点はそのまま、並べ替えのみ実施）。
"""
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from common import fetch, to_int, normalize_pct
from team_slugs import slug_for, abbr_for_full

BASE = "http://www.cubf5589.com"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "leagues"

SEASON_YEAR = 2026
SEASONS = [("aki", "秋季")]
# (kindパラメータ, 部)。kind=4は新人戦のため対象外。
DIVISIONS = [("1", "1部"), ("2", "2部"), ("3", "3部")]

STANDINGS_ROW_RE = re.compile(
    r'<tr>\s*<td>\s*([^<]+?)\s*</td>((?:\s*<th[^>]*>.*?</th>)+)\s*</tr>', re.DOTALL)
RECORD_PART_RE = re.compile(r'(\d+)([勝負敗引分])')


def parse_standings(html: str) -> list[dict]:
    idx = html.find(">試合結果<")
    if idx == -1:
        return []
    end = html.find("</table>", idx)
    section = html[idx:end] if end != -1 else html[idx:idx + 40000]
    raw = []
    for name, rest in STANDINGS_ROW_RE.findall(section):
        ths = re.findall(r'<th[^>]*>(.*?)</th>', rest, re.DOTALL)
        ths = [re.sub(r"<[^>]+>", "", x).strip() for x in ths]
        if len(ths) < 2:
            continue
        record_txt, points_txt = ths[-2], ths[-1]
        parts = RECORD_PART_RE.findall(record_txt)
        if not parts:
            continue
        w = l = d = 0
        for num, kind in parts:
            n = to_int(num)
            if kind == "勝":
                w = n
            elif kind in "負敗":
                l = n
            else:  # 引 / 分
                d = n
        points = to_int(points_txt)
        wl_games = w + l
        pct = f"{w / wl_games:.3f}" if wl_games else "-"
        team = abbr_for_full(name.strip())
        raw.append({
            "team": team,
            "slug": slug_for(team),
            "games": w + l + d, "wins": w, "losses": l, "draws": d,
            "points": points,
            "win_pct": normalize_pct(pct),
            "_pct_sort": (w / wl_games) if wl_games else 0.0,
        })
    # 連盟公式サイトには順位（並び順）の明記がなく星取表はチーム固定順のため、
    # 勝ち点→勝率→勝数の順で当サイト側が並べ替えて順位を付与する
    # （勝敗数・勝ち点は連盟公式の値をそのまま使い、順序のみ整理する）。
    raw.sort(key=lambda e: (-e["points"], -e["_pct_sort"], -e["wins"]))
    entries = []
    for i, e in enumerate(raw, 1):
        e = dict(e)
        del e["_pct_sort"]
        e["rank"] = i
        entries.append(e)
    return entries


def parse_matches(html: str) -> list[dict]:
    blocks = re.split(r'(?=<div class="ScoreWrapper">)', html)[1:]
    matches = []
    seen_ids: set[str] = set()
    for b in blocks:
        dm = re.search(r'ScoreDate">令和(\d+)年(\d+)月(\d+)日', b)
        if not dm:
            continue
        reiwa, mo, dd = (int(x) for x in dm.groups())
        year = reiwa + 2018
        tables = re.split(r'<table class="ScoreTable">', b)
        venue_m = re.search(r'<th>([^<]+)</th>', tables[1]) if len(tables) > 1 else None
        venue = venue_m.group(1).strip() if venue_m else "未定"
        box = tables[2] if len(tables) > 2 else ""
        rows = re.findall(
            r'<tr>\s*<th>\s*([^<]+?)\s*</th>((?:\s*<th[^>]*>[^<]*</th>)+)\s*</tr>', box)
        teams = []
        for name, innings in rows:
            vals = re.findall(r'<th[^>]*>([^<]*)</th>', innings)
            total = vals[-1].strip() if vals else ""
            teams.append((abbr_for_full(name.strip()), total))
        if len(teams) != 2:
            continue
        senko = {abbr_for_full(k.strip()): v for k, v in
                 re.findall(r'senko2[^>]*>\s*([^<]+?)\s*[　\s]*【(先攻|後攻)】', b)}
        (t1, s1), (t2, s2) = teams
        # 先攻＝ビジター（アウェイ）、後攻＝ホームの慣例に合わせる。
        # senko2の記載が見つからない場合は掲載順（1試合目=先攻想定）をそのまま使う。
        if senko.get(t1) == "後攻" or senko.get(t2) == "先攻":
            home, home_s, away, away_s = t1, s1, t2, s2
        else:
            home, home_s, away, away_s = t2, s2, t1, s1
        played = bool(re.fullmatch(r"\d+", home_s) and re.fullmatch(r"\d+", away_s))
        try:
            d_iso = date(year, mo, dd).isoformat()
        except ValueError:
            d_iso = None
        base_id = f'{d_iso or "tbd"}-{slug_for(home)}-vs-{slug_for(away)}'
        mid, n = base_id, 2
        while mid in seen_ids:
            mid = f"{base_id}-{n}"
            n += 1
        seen_ids.add(mid)
        matches.append({
            "id": mid,
            "date": d_iso,
            "time": "未定",
            "home": home, "away": away,
            "home_slug": slug_for(home), "away_slug": slug_for(away),
            "venue": venue,
            "status": "played" if played else "scheduled",
            "home_score": int(home_s) if played else None,
            "away_score": int(away_s) if played else None,
            "note": "",
        })
    matches.sort(key=lambda m: (m["date"] or "9999", m["id"]))
    return matches


def build_teams(matches, standings) -> dict:
    teams = {}
    for e in standings:
        teams[e["team"]] = {"team": e["team"], "slug": e["slug"], "block": "総合"}
    for m in matches:
        for team in (m["home"], m["away"]):
            teams.setdefault(team, {"team": team, "slug": slug_for(team), "block": "総合"})
    return teams


def fetch_division(season_label: str, kind: str, div_label: str):
    url = f"{BASE}/league_match_detail.php?kind={kind}"
    try:
        html = fetch(url, encoding="utf-8")
    except Exception as e:
        print(f"[warn] 中国地区{div_label} {season_label}: 取得失敗 ({e})", file=sys.stderr)
        return None
    matches = parse_matches(html)
    standings = parse_standings(html)
    if not matches and not standings:
        print(f"[info] 中国地区{div_label} {season_label}: データなし（未公開）", file=sys.stderr)
        return None
    teams = build_teams(matches, standings)
    return {"matches": matches, "standings": {"総合": standings}, "teams": teams, "url": url}


def main() -> None:
    total = len(SEASONS) * len(DIVISIONS)
    ok = 0
    for season_code, season_label in SEASONS:
        for kind, div_label in DIVISIONS:
            result = fetch_division(season_label, kind, div_label)
            time.sleep(1.5)  # 連盟サイトへの負荷軽減（common.fetchの待機に追加）
            if result is None:
                continue
            code = f"chugoku{kind}-{SEASON_YEAR}-{season_code}"
            out_dir = DATA_DIR / code
            out_dir.mkdir(parents=True, exist_ok=True)
            played = sum(1 for m in result["matches"] if m["status"] == "played")
            meta = {
                "code": code,
                "competition": "中国地区大学野球連盟",
                "division": div_label,
                "season_year": SEASON_YEAR,
                "season_name": season_label,
                "season_code": season_code,
                "league": f"中国地区大学野球 {div_label} {SEASON_YEAR}年{season_label}リーグ戦",
                "source": "中国地区大学野球連盟",
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
    print(f"done: {ok}/{total} divisions (中国地区大学)")


if __name__ == "__main__":
    main()
