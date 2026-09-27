# -*- coding: utf-8 -*-
"""東京新大学野球連盟(new-tokyo-bbl.com)から試合日程・結果・順位表を取得し、
data/leagues/shintokyo<div>-<year>-<season>/ に正規化JSONとして保存する。

データ出典: 東京新大学野球連盟 (https://new-tokyo-bbl.com/)
1部〜4部の4リーグ制。ページは `game/index.html?sid=<年度sid>&category=<1-4>`
（category: 1=1部, 2=2部, 3=3部, 4=4部）。文字コードはUTF-8、静的HTML。

順位表は連盟公式の「順位表」ブロック（<dl class="clearfix">の並び）を
そのまま取得する。同ブロックには順位・チーム名・勝ち点・「W勝L敗D分」の
記録・勝率が含まれる。星取表（勝敗のマス目）は丸写しせず参照しない。

試合一覧は「試合一覧」ブロック（<dl class="clearfix">の並び）から
日付・時間・球場・対戦カード・スコアを取得する。1試合目に記載のチームを
ホーム、2試合目のチームをアウェイとして扱う（連盟サイトに明示的な
ホーム/アウェイの区別はないため、掲載順を踏襲）。
"""
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from common import fetch, strip_tags, to_int, normalize_pct
from team_slugs import slug_for, abbr_for_full

BASE = "https://new-tokyo-bbl.com"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "leagues"

SEASON_YEAR = 2026
# サイト側の年度・シーズンを表す sid。年度が変わったら要更新
# （sidはサイトのトップページ `game/` の「過去の年度」リンクから確認できる）。
SEASON_SID = {
    "aki": "32",   # 2026年度 秋季リーグ戦
}
SEASONS = [("aki", "秋季")]
DIVISIONS = [("1", "1部"), ("2", "2部"), ("3", "3部"), ("4", "4部")]

RANK_BLOCK_RE = re.compile(r'<h3 class="title02">順位表</h3>(.*?)</div><!--rank-->', re.DOTALL)
RANK_DL_RE = re.compile(r'<dl class="clearfix">(.*?)</dl>', re.DOTALL)
SCHEDULE_BLOCK_RE = re.compile(r'<h3 class="title02">試合一覧</h3><div class="schedule">(.*?)</div>',
                                re.DOTALL)
SCHEDULE_DL_RE = re.compile(r'<dl class="clearfix">(.*?)</dl>', re.DOTALL)


def parse_standings(html: str) -> list[dict]:
    m = RANK_BLOCK_RE.search(html)
    if not m:
        return []
    entries = []
    for i, dm in enumerate(RANK_DL_RE.finditer(m.group(1)), 1):
        block = dm.group(1)
        rank_m = re.search(r'<dt>(\d+)位</dt>', block)
        team_m = re.search(r'<span>([^<]+)</span>', block)
        dds = re.findall(r'<dd>(.*?)</dd>', block, re.DOTALL)
        if not team_m or len(dds) < 3:
            continue
        team = abbr_for_full(strip_tags(team_m.group(0)))
        points = to_int(strip_tags(dds[1])) if len(dds) > 1 else 0
        rec_m = re.search(r'(\d+)勝(\d+)敗(\d*)分', strip_tags(dds[2])) if len(dds) > 2 else None
        w, l, d = (to_int(rec_m.group(1)), to_int(rec_m.group(2)), to_int(rec_m.group(3) or "0")) \
            if rec_m else (0, 0, 0)
        pct_m = re.search(r'([.\d]+)', strip_tags(dds[3])) if len(dds) > 3 else None
        entries.append({
            "rank": to_int(rank_m.group(1), default=i) if rank_m else i,
            "team": team,
            "slug": slug_for(team),
            "games": w + l + d, "wins": w, "losses": l, "draws": d,
            "points": points,
            "win_pct": normalize_pct(pct_m.group(1)) if pct_m else "-",
        })
    return entries


def parse_matches(html: str, season_year: int) -> list[dict]:
    m = SCHEDULE_BLOCK_RE.search(html)
    if not m:
        # 末尾が</div>で終わらない構造ゆらぎに備えたフォールバック
        idx = html.find('<h3 class="title02">試合一覧</h3>')
        if idx == -1:
            return []
        body = html[idx:]
    else:
        body = m.group(1)
    matches = []
    seen_ids: set[str] = set()
    for dm in SCHEDULE_DL_RE.finditer(body):
        block = dm.group(1)
        date_m = re.search(r'<dt class="date">(\d{4})/(\d{1,2})/(\d{1,2})</dt>', block)
        time_m = re.search(r'<dd class="time">([^<]*)</dd>', block)
        gid_m = re.search(r'gid=(\d+)', block)
        venue_m = re.search(r'<dd class="stadium">([^<]*)</dd>', block)
        team_m = re.search(
            r'<span class="team1">([^<]*)</span><span class="score">(.*?)</span>'
            r'<span class="team2">([^<]*)', block, re.DOTALL)
        if not date_m or not team_m:
            continue
        y, mo, dd = date_m.groups()
        try:
            d_iso = date(int(y), int(mo), int(dd)).isoformat()
        except ValueError:
            d_iso = None
        home, score_txt, away = team_m.groups()
        home, away = abbr_for_full(home.strip()), abbr_for_full(away.strip())
        if not home or not away:
            continue
        score_m = re.search(r'(\d+)\s*-\s*(\d+)', score_txt)
        played = bool(score_m)
        time_txt = (time_m.group(1).strip() if time_m else "") or "未定"
        venue = (venue_m.group(1).strip() if venue_m else "") or "未定"
        mid = f'gid-{gid_m.group(1)}' if gid_m else f'{d_iso or "tbd"}-{slug_for(home)}-vs-{slug_for(away)}'
        n = 2
        base_id = mid
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
            "home_score": int(score_m.group(1)) if played else None,
            "away_score": int(score_m.group(2)) if played else None,
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


def fetch_division(sid: str, season_label: str, category: str, div_label: str, season_year: int):
    url = f"{BASE}/game/index.html?sid={sid}&category={category}"
    try:
        html = fetch(url, encoding="utf-8")
    except Exception as e:
        print(f"[warn] 東京新大学{div_label} {season_year}{season_label}: 取得失敗 ({e})", file=sys.stderr)
        return None
    matches = parse_matches(html, season_year)
    standings = parse_standings(html)
    if not matches and not standings:
        print(f"[info] 東京新大学{div_label} {season_year}{season_label}: データなし（未公開）", file=sys.stderr)
        return None
    teams = build_teams(matches, standings)
    return {"matches": matches, "standings": {"総合": standings}, "teams": teams, "url": url}


def main() -> None:
    total = len(SEASONS) * len(DIVISIONS)
    ok = 0
    for season_code, season_label in SEASONS:
        sid = SEASON_SID.get(season_code)
        if not sid:
            print(f"[warn] 東京新大学 {season_label}: sid未設定のためスキップ", file=sys.stderr)
            continue
        for category, div_label in DIVISIONS:
            result = fetch_division(sid, season_label, category, div_label, SEASON_YEAR)
            time.sleep(1.5)  # 連盟サイトへの負荷軽減（common.fetchの待機に追加）
            if result is None:
                continue
            code = f"shintokyo{category}-{SEASON_YEAR}-{season_code}"
            out_dir = DATA_DIR / code
            out_dir.mkdir(parents=True, exist_ok=True)
            played = sum(1 for m in result["matches"] if m["status"] == "played")
            meta = {
                "code": code,
                "competition": "東京新大学野球連盟",
                "division": div_label,
                "season_year": SEASON_YEAR,
                "season_name": season_label,
                "season_code": season_code,
                "league": f"東京新大学野球 {div_label} {SEASON_YEAR}年{season_label}リーグ戦",
                "source": "東京新大学野球連盟",
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
    print(f"done: {ok}/{total} divisions (東京新大学)")


if __name__ == "__main__":
    main()
