# -*- coding: utf-8 -*-
"""阪神大学野球連盟(hanshin-bbl.com)から試合結果・順位表を取得し、
data/leagues/hanshin<div>-<year>-<season>/ に正規化JSONとして保存する。

データ出典: 阪神大学野球連盟 (https://hanshin-bbl.com/)
1部・2部東・2部西の3リーグを対象とする。日程はPDF配布だが、勝敗表・
順位表はExcel書き出しのHTML（Shift_JIS/CP932）で公開されており、
同じページ内に「節」ごとの試合結果（対戦カード・スコア）も含まれているため、
matches.jsonも取得できる（PDFはパースしない）。

URL: `https://hanshin-bbl.com/<season>-league-standings.htm` が
フレームセットになっており、実データは
`<season>-league-standings.files/sheet00N.htm` に入っている
（N: 1=1部, 2=2部東, 3=2部西）。年度・シーズンが変わるとファイル名も
変わるため、まずトップページ(https://hanshin-bbl.com/)から該当シーズンの
「○○年秋季リーグ順位表」的なリンクを探して起点URLを決める。

ルビ（ふりがな）は `<ruby>漢字<span style='display:none'><rt>よみ</rt>
</span></ruby>` の形で埋め込まれており、単純なタグ除去だと読み仮名が
本文に混ざる（例:「天理テンリ大学ダイガク」）ため、`display:none`の
spanごと先に除去してからタグを剥がす。

順位表は「試合数・勝・負・分・ポイント」の列が連盟公式の集計値。
「順位」列は表内に数値が入らず（画像アイコン想定）、チームは常に
固定順（登録順）で並んでいるため、このパイプライン側で
ポイント→勝率→勝数の順に並べ替えて順位を付与する
（値そのものは連盟公式の集計をそのまま使用）。
"""
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

from common import fetch, to_int, normalize_pct
from team_slugs import slug_for

BASE = "https://hanshin-bbl.com"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "leagues"

SEASON_YEAR = 2026
SEASONS = [("aki", "秋季", "autumn")]
# (シート番号, 部)
DIVISIONS = [("001", "1部"), ("002", "2部東"), ("003", "2部西")]
SHEET_TO_CODE = {"001": "1", "002": "2e", "003": "2w"}

# ルビの読み仮名は<rt>...</rt>（display:noneのspanで包まれる）に入っている。
# spanの属性値の空白の入り方（改行含む）が揺れるため、spanごとではなく
# <rt>...</rt>そのものを読み仮名テキストごと除去する方が確実。
RUBY_RT_RE = re.compile(r"(?s)<rt>.*?</rt>")
TAG_RE = re.compile(r"<[^>]+>")
STANDINGS_ROW_RE = re.compile(r"(?s)<tr[^>]*>(.*?)</tr>")
RECORD_RE = re.compile(r"(\d+)勝(?:(\d+)[負敗])?(?:(\d+)[引分])?")


def _clean(html_fragment: str) -> str:
    return TAG_RE.sub("", html_fragment).replace("&nbsp;", "").strip()


def fetch_cp932(url: str) -> str:
    return fetch(url, encoding="cp932")


def find_sheet_base_url(season_key: str) -> str | None:
    """トップページから該当シーズンの順位表フレームセットURLを探し、
    sheet001.htm系のベースURL（末尾なし、拡張子.files/を除いた部分）を返す。"""
    try:
        top = fetch_cp932(f"{BASE}/")
    except Exception as e:
        print(f"[warn] 阪神 トップページ取得失敗 ({e})", file=sys.stderr)
        return None
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', top)
    year_prefix = str(SEASON_YEAR)
    candidates = [h for h in hrefs
                  if season_key in h and "standings" in h and h.endswith(".htm")
                  and year_prefix in h]
    if not candidates:
        return None
    # 最初に見つかったもの（トップページ最新のお知らせ欄にあるリンク）を採用
    href = candidates[0]
    if not href.startswith("http"):
        href = f"{BASE}/{href.lstrip('/')}"
    return href


def parse_sheet(html: str, div_label: str):
    html = RUBY_RT_RE.sub("", html)
    rows = STANDINGS_ROW_RE.findall(html)

    abbr_order: list[str] = []
    raw_standings = []
    matches_rows = []
    for row in rows:
        cells = re.findall(r"(?s)<td([^>]*)>(.*?)</td>", row)
        texts = [_clean(c) for _attrs, c in cells]
        # 行末に空の<td>（Excel書き出し特有の余剰セル）が付くことがあるため、
        # 末尾5列＝集計列を正しく拾えるよう末尾の空セルを落としておく。
        while texts and texts[-1] == "":
            texts.pop()
        texts_nonempty = [t for t in texts if t]
        if "大学名" in texts_nonempty and not abbr_order:
            # ヘッダー行:「大学名」列見出しの直後〜「試合数」列見出しの直前が
            # 対戦相手ごとの略称（対戦カード欄と同じ表記）。これをチームの
            # 登録順（＝順位表の行が並ぶ順）の対応表として使う。
            i0 = texts_nonempty.index("大学名")
            i1 = texts_nonempty.index("試合数") if "試合数" in texts_nonempty else len(texts_nonempty)
            abbr_order = texts_nonempty[i0 + 1:i1]
            continue
        # 順位表の1チーム分の行: 「◯◯大学」を含み、末尾5セルが全て数字
        # （試合数,勝,負,分,ポイント）のもの。
        team_candidates = [t for t in texts_nonempty if t.endswith("大学")]
        if team_candidates and len(texts) >= 5 and all(re.fullmatch(r"\d+", x) for x in texts[-5:]):
            team_full = team_candidates[0]
            g, w, l, d, pts = (to_int(x) for x in texts[-5:])
            raw_standings.append({"full": team_full, "games": g, "wins": w, "losses": l,
                                   "draws": d, "points": pts})
        if re.search(r"\d{1,2}月\d{1,2}日", row):
            matches_rows.append(row)

    # チーム名（略称）を登録順で対応付け
    entries = []
    for i, rec in enumerate(raw_standings):
        abbr = abbr_order[i] if i < len(abbr_order) else rec["full"]
        wl = rec["wins"] + rec["losses"]
        pct = (rec["wins"] / wl) if wl else 0.0
        entries.append({
            "team": abbr,
            "slug": slug_for(abbr),
            "games": rec["games"], "wins": rec["wins"], "losses": rec["losses"],
            "draws": rec["draws"], "points": rec["points"],
            "win_pct": normalize_pct(f"{pct:.3f}") if wl else "-",
            "_pct_sort": pct,
        })
    entries.sort(key=lambda e: (-e["points"], -e["_pct_sort"], -e["wins"]))
    for i, e in enumerate(entries, 1):
        del e["_pct_sort"]
        e["rank"] = i

    matches = []
    seen_ids: set[str] = set()
    for row in matches_rows:
        cells = re.findall(r"(?s)<td([^>]*)>(.*?)</td>", row)
        texts = [_clean(c) for _attrs, c in cells]
        date_idx = next((i for i, t in enumerate(texts) if re.fullmatch(r"\d{1,2}月\d{1,2}日", t)),
                         None)
        if date_idx is None:
            continue
        mdm = re.match(r"(\d{1,2})月(\d{1,2})日", texts[date_idx])
        mo, dd = int(mdm.group(1)), int(mdm.group(2))
        # date_idx+1 = 曜日, date_idx+2 = 球場, それ以降が試合の並び
        rest = texts[date_idx + 3:] if len(texts) > date_idx + 2 else []
        venue = texts[date_idx + 2] if len(texts) > date_idx + 2 else "未定"
        for gi in range(0, len(rest) - 4, 5):
            t1, s1, dash, s2, t2 = rest[gi:gi + 5]
            if dash != "ー" and dash != "-":
                continue
            if not t1 or not t2:
                continue
            s1n, s2n = s1.rstrip("xX"), s2.rstrip("xX")
            played = bool(re.fullmatch(r"\d+", s1n) and re.fullmatch(r"\d+", s2n))
            try:
                d_iso = date(SEASON_YEAR, mo, dd).isoformat()
            except ValueError:
                d_iso = None
            base_id = f'{d_iso or "tbd"}-{slug_for(t1)}-vs-{slug_for(t2)}'
            mid, n = base_id, 2
            while mid in seen_ids:
                mid = f"{base_id}-{n}"
                n += 1
            seen_ids.add(mid)
            matches.append({
                "id": mid,
                "date": d_iso,
                "time": "未定",
                "home": t1, "away": t2,
                "home_slug": slug_for(t1), "away_slug": slug_for(t2),
                "venue": venue or "未定",
                "status": "played" if played else "scheduled",
                "home_score": int(s1n) if played else None,
                "away_score": int(s2n) if played else None,
                "note": "",
            })
    return entries, matches


def build_teams(matches, standings) -> dict:
    teams = {}
    for e in standings:
        teams[e["team"]] = {"team": e["team"], "slug": e["slug"], "block": "総合"}
    for m in matches:
        for team in (m["home"], m["away"]):
            teams.setdefault(team, {"team": team, "slug": slug_for(team), "block": "総合"})
    return teams


def fetch_division(season_label: str, season_key: str, sheet_no: str, div_label: str,
                    base_href: str | None):
    if not base_href:
        return None
    files_base = base_href[:-4] + ".files" if base_href.endswith(".htm") else base_href
    url = f"{files_base}/sheet{sheet_no}.htm"
    try:
        html = fetch_cp932(url)
    except Exception as e:
        print(f"[warn] 阪神{div_label} {season_label}: 取得失敗 ({e})", file=sys.stderr)
        return None
    standings, matches = parse_sheet(html, div_label)
    if not matches and not standings:
        print(f"[info] 阪神{div_label} {season_label}: データなし（未公開）", file=sys.stderr)
        return None
    teams = build_teams(matches, standings)
    return {"matches": matches, "standings": {"総合": standings}, "teams": teams, "url": url}


def main() -> None:
    total = len(SEASONS) * len(DIVISIONS)
    ok = 0
    for season_code, season_label, season_key in SEASONS:
        base_href = find_sheet_base_url(season_key)
        time.sleep(1.5)
        if not base_href:
            print(f"[warn] 阪神 {season_label}: 順位表フレームセットURLが見つからず全部スキップ",
                  file=sys.stderr)
            continue
        for sheet_no, div_label in DIVISIONS:
            div_code = SHEET_TO_CODE[sheet_no]
            code = f"hanshin{div_code}-{SEASON_YEAR}-{season_code}"
            result = fetch_division(season_label, season_key, sheet_no, div_label, base_href)
            time.sleep(1.5)  # 連盟サイトへの負荷軽減（common.fetchの待機に追加）
            if result is None:
                continue
            out_dir = DATA_DIR / code
            out_dir.mkdir(parents=True, exist_ok=True)
            played = sum(1 for m in result["matches"] if m["status"] == "played")
            meta = {
                "code": code,
                "competition": "阪神大学野球連盟",
                "division": div_label,
                "season_year": SEASON_YEAR,
                "season_name": season_label,
                "season_code": season_code,
                "league": f"阪神大学野球 {div_label} {SEASON_YEAR}年{season_label}リーグ戦",
                "source": "阪神大学野球連盟",
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
    print(f"done: {ok}/{total} divisions (阪神大学)")


if __name__ == "__main__":
    main()
