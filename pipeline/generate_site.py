# -*- coding: utf-8 -*-
"""data/leagues/ の正規化JSONから静的サイト「ベースボールマニア」（site/）を生成する。

URL構造:
  site/index.html                     ポータルトップ（連盟・シーズン一覧・最新結果）
  site/<league>/index.html            リーグトップ（最新結果・日程・順位）
  site/<league>/schedule/ 等          リーグ別の日程・順位表・チーム一覧
  site/<league>/clubs/<slug>/         チームページ
  site/<league>/matches/<id>/         試合ページ
  site/articles/ glossary/ videos/    全リーグ共通コンテンツ（現状は空でも動作する）

大学野球は「勝ち点制」（同一カード2先勝制）という独自ルールのため、順位表は
連盟公式サイトが計算済みの値をそのまま使う（自前集計はしない）。
"""
import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

from team_slugs import full_name_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
ASSETS = ROOT / "assets"
CONTENT = ROOT / "content" / "articles"

SITE_BASE = "https://baseballmania.jp/"
GA_MEASUREMENT_ID = "G-162E02Q55F"  # GA4「ツナカレ部活メディア」共有プロパティ（tkoba-piecetimes.github.io配下で共有）
GSC_VERIFICATION = "0X77J6-cDQak8VJkyt1PGegqMjZwEI2HWAYjkwl3OF0"  # Search Console所有権確認トークン（アカウント共通）
SPONSOR_CTA_URL = "https://tunakare.jp/?utm_source=baseballmania&utm_medium=referral&utm_campaign=sponsor"

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]
SEASON_YEAR = 2026
LEAGUE_ORDER = [
    "rikudai-2026-haru", "rikudai-2026-aki",
    "tohto1-2026-haru", "tohto1-2026-aki",
    "tohto2-2026-haru", "tohto2-2026-aki",
    "tohto3-2026-haru", "tohto3-2026-aki",
    "tohto4-2026-haru", "tohto4-2026-aki",
]
COMPETITION_ORDER = ["東京六大学野球連盟", "東都大学野球連盟"]
SEASON_ORDER = ["春季", "秋季"]

_sitemap_paths: list[str] = []


# ---------------------------------------------------------------- data loading

def load_leagues():
    leagues = []
    for code in LEAGUE_ORDER:
        d = DATA / "leagues" / code
        if not (d / "matches.json").exists():
            continue
        lg = {
            "code": code,
            "matches": json.loads((d / "matches.json").read_text(encoding="utf-8")),
            "standings": json.loads((d / "standings.json").read_text(encoding="utf-8")),
            "teams": json.loads((d / "teams.json").read_text(encoding="utf-8")),
            "meta": json.loads((d / "meta.json").read_text(encoding="utf-8")),
        }
        lg["label"] = lg["meta"]["league"]
        leagues.append(lg)
    # 同じ大会・部の「もう一方のシーズン」を探せるように索引を作る
    by_key: dict[tuple, dict] = {}
    for lg in leagues:
        key = (lg["meta"]["competition"], lg["meta"]["division"])
        by_key.setdefault(key, {})[lg["meta"]["season_code"]] = lg
    for lg in leagues:
        key = (lg["meta"]["competition"], lg["meta"]["division"])
        lg["siblings"] = by_key.get(key, {})
    return leagues


def load_articles():
    if not CONTENT.exists():
        return []
    arts = []
    for f in sorted(CONTENT.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        _, fm, body = raw.split("---", 2)
        a = {"slug": f.stem, "body": body.strip()}
        for line in fm.strip().splitlines():
            k, _, v = line.partition(":")
            a[k.strip()] = v.strip()
        arts.append(a)
    arts.sort(key=lambda a: (a.get("date", ""), a["slug"]), reverse=True)
    return arts


# ---------------------------------------------------------------- text helpers

def date_jp(iso, with_year=False):
    d = date.fromisoformat(iso)
    wd = WEEKDAYS_JP[d.weekday()]
    return (f"{d.year}年" if with_year else "") + f"{d.month}月{d.day}日（{wd}）"


def score_str(m):
    return f'{m["home_score"]} - {m["away_score"]}' if m["status"] == "played" else "—"


def club_label(team):
    return f"{full_name_for(team)}硬式野球部"


def match_headline(m):
    if m["status"] != "played":
        d = f'（{date_jp(m["date"])}）' if m["date"] else ""
        return f'{m["home"]} vs {m["away"]}{d}'
    hs, as_ = m["home_score"], m["away_score"]
    if hs == as_:
        return f'{m["home"]} {hs}-{as_} {m["away"]} 引き分け'
    winner = m["home"] if hs > as_ else m["away"]
    return f'{winner}が勝利　{m["home"]} {hs}-{as_} {m["away"]}'


def match_report(m, standings, league_name):
    d = date_jp(m["date"], with_year=True) if m["date"] else "日程未定"
    if m["status"] != "played":
        if m["time"] not in ("未定", "第1試合終了後"):
            return (f'{d}、{m["venue"]}にて{league_name}の'
                    f'{m["home"]}対{m["away"]}が{m["time"]}に行われる予定です。')
        return (f'{d}、{m["venue"]}にて{league_name}の'
                f'{m["home"]}対{m["away"]}が行われる予定です。')
    hs, as_ = m["home_score"], m["away_score"]
    base = (f'{d}、{m["venue"]}にて{league_name}の'
            f'{m["home"]}対{m["away"]}が行われました。')
    if hs == as_:
        result = f'試合は{hs}-{as_}で引き分けとなりました。'
    else:
        winner = m["home"] if hs > as_ else m["away"]
        loser = m["away"] if hs > as_ else m["home"]
        result = f'試合は{winner}が{max(hs, as_)}-{min(hs, as_)}で{loser}を下しました。'
    ctx = ""
    for e in standings.get("総合", []):
        if hs != as_ and e["team"] == (m["home"] if hs > as_ else m["away"]):
            ctx = f'この結果、{e["team"]}は{league_name}で{e["rank"]}位（勝ち点{e["points"]}）につけています。'
    return base + result + ctx


def h2h_list(a, b, matches):
    out = [m for m in matches
           if m["status"] == "played" and {m["home"], m["away"]} == {a, b}]
    out.sort(key=lambda m: m["date"] or "", reverse=True)
    return out


def recent_results(team, matches, n=3):
    ms = [m for m in matches
          if m["status"] == "played" and team in (m["home"], m["away"])]
    return list(reversed(ms))[:n]


def result_mark(m, team):
    gf = m["home_score"] if m["home"] == team else m["away_score"]
    ga = m["away_score"] if m["home"] == team else m["home_score"]
    return "○" if gf > ga else ("△" if gf == ga else "●")


def badge(mark):
    cls = {"○": "w", "△": "d", "●": "l"}[mark]
    return f'<span class="mk mk-{cls}">{mark}</span>'


def jsonld_sports_event(m, league_name):
    data = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": f'{league_name} {m["home"]} vs {m["away"]}',
        "startDate": m["date"],
        "location": {"@type": "Place", "name": m["venue"]},
        "homeTeam": {"@type": "SportsTeam", "name": club_label(m["home"])},
        "awayTeam": {"@type": "SportsTeam", "name": club_label(m["away"])},
        "sport": "Baseball",
    }
    return ('<script type="application/ld+json">'
            + json.dumps(data, ensure_ascii=False) + "</script>")


# ---------------------------------------------------------------- markdown

def md_inline(s):
    s = escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return s


def md_to_html(md):
    out, para = [], []
    in_ul = in_ol = in_table = False

    def close_blocks():
        nonlocal in_ul, in_ol, in_table
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False
        if in_table:
            out.append("</tbody></table></div>")
            in_table = False

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para = []

    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            flush_para()
            if in_ul or in_ol:
                close_blocks()
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r"[-: ]+", c) for c in cells):
                continue
            if not in_table:
                out.append('<div class="tbl"><table><thead><tr>'
                           + "".join(f"<th>{md_inline(c)}</th>" for c in cells)
                           + "</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</tbody></table></div>")
            in_table = False
        if not s:
            flush_para()
            close_blocks()
        elif s.startswith("### "):
            flush_para(); close_blocks()
            out.append(f"<h3>{md_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            flush_para(); close_blocks()
            out.append(f"<h2>{md_inline(s[3:])}</h2>")
        elif s.startswith("- "):
            flush_para()
            if not in_ul:
                close_blocks()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{md_inline(s[2:])}</li>")
        elif re.match(r"^\d+\.\s", s):
            flush_para()
            if not in_ol:
                close_blocks()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{md_inline(re.sub(r'^\\d+\\.\\s', '', s))}</li>")
        else:
            para.append(s)
    flush_para()
    close_blocks()
    return "\n".join(out)


# ---------------------------------------------------------------- page shell

NAV_ITEMS = [
    ("index.html", "トップ"),
]


def league_subnav(lg, L):
    items = [("index.html", "リーグトップ"), ("schedule/index.html", "日程・結果"),
             ("standings/index.html", "順位表"), ("teams/index.html", "チーム")]
    links = "".join(f'<a href="{L}{href}">{label}</a>' for href, label in items)
    season_html = ""
    sib = lg.get("siblings") or {}
    if len(sib) > 1:
        parts = []
        for code in ("haru", "aki"):
            other = sib.get(code)
            if not other:
                continue
            label = other["meta"]["season_name"]
            if other["code"] == lg["code"]:
                parts.append(f'<span class="season-current">{escape(label)}</span>')
            else:
                # L は現リーグ配下からリーグルート（code/）への相対パス。
                # そこからさらに1段上がるとサイトルートに出る。
                parts.append(f'<a href="{L}../{other["code"]}/index.html">{escape(label)}</a>')
        if len(parts) > 1:
            season_html = f'<span class="season-switch">シーズン: {" / ".join(parts)}</span>'
    return ('<div class="league-nav"><div class="league-nav-inner">'
            f'<span class="league-name">{escape(lg["label"])}</span>{links}{season_html}</div></div>')


def page(rel, title, body, meta, *, path="", desc="", extra_head="", og_type="website",
         subnav="", sitemap=True):
    if sitemap:
        _sitemap_paths.append(path)
    else:
        extra_head = '<meta name="robots" content="noindex, nofollow">\n' + extra_head
    desc = desc or "東京六大学野球・東都大学野球の試合結果・日程・順位表を毎日更新する大学野球情報メディア。"
    url = SITE_BASE + path
    og_image = ""
    if (ASSETS / "ogp.png").exists():
        og_image = (f'<meta property="og:image" content="{SITE_BASE}assets/ogp.png">\n'
                    '<meta name="twitter:card" content="summary_large_image">\n')
    ga = ""
    if GA_MEASUREMENT_ID:
        ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>'
              '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
              f"gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>")
    gsc = (f'<meta name="google-site-verification" content="{GSC_VERIFICATION}">\n'
           if GSC_VERIFICATION else "")
    nav = "".join(f'<a href="{rel}{href}">{label}</a>' for href, label in NAV_ITEMS)
    if "sources" in meta:
        src_html = " / ".join(
            f'<a href="{escape(s["url"])}">{escape(s["label"])}</a>' for s in meta["sources"])
    else:
        src_html = f'<a href="{escape(meta["source_url"])}">{escape(meta["source"])}</a>'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{gsc}<title>{escape(title)}</title>
<meta name="description" content="{escape(desc)}">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:type" content="{og_type}">
<meta property="og:url" content="{escape(url)}">
<meta property="og:site_name" content="ベースボールマニア">
{og_image}<link rel="icon" href="{rel}assets/favicon.svg" type="image/svg+xml">
<link rel="canonical" href="{escape(url)}">
{extra_head}{ga}
<link rel="stylesheet" href="{rel}style.css">
</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="{rel}index.html"><span class="brand-tick"></span>ベースボールマニア<span class="brand-sub">JAPAN COLLEGE BASEBALL</span></a>
    <nav class="global-nav">{nav}</nav>
  </div>
</header>
{subnav}
<main>
{body}
</main>
<footer class="site-footer">
  <div class="footer-inner">
    <p class="footer-brand">ベースボールマニア</p>
    <nav class="footer-nav">{nav}</nav>
    <p>試合データ出典: {src_html}
    （情報更新日: {escape(meta['fetched_at'][:10])}）</p>
    <p>ベースボールマニアは大学野球の情報メディアです。掲載の日程・結果・順位表は各連盟公式サイトの発表に基づいています。最新の確定情報は各連盟公式サイトをご確認ください。</p>
  </div>
</footer>
</body>
</html>"""


def write_page(path, html):
    out = SITE / path / "index.html" if path else SITE / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- components

def match_row(m, L, league_label=None, league_code=None):
    link = f'{L}matches/{m["id"]}/index.html' if league_code is None else f'{league_code}/matches/{m["id"]}/index.html'
    lg_cell = f'<td><span class="cat">{escape(league_label)}</span></td>' if league_label else ""
    d = date_jp(m["date"]) if m["date"] else "未定"
    return (f'<tr><td>{d}</td>{lg_cell}<td>{escape(m["time"])}</td>'
            f'<td><a href="{link}">{escape(m["home"])} vs {escape(m["away"])}</a></td>'
            f'<td class="score">{score_str(m)}</td>'
            f'<td class="venue">{escape(m["venue"])}</td></tr>')


def match_table(rows, with_league=False):
    lg_th = "<th>リーグ</th>" if with_league else ""
    return (f'<div class="tbl"><table><thead><tr><th>日付</th>{lg_th}<th>時間</th>'
            '<th>対戦</th><th>スコア</th><th>球場</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def standings_table(entries, L):
    rows = "".join(
        f'<tr><td class="rank">{e["rank"]}</td>'
        f'<td><a href="{L}clubs/{e["slug"]}/index.html">{escape(e["team"])}</a></td>'
        f'<td>{e["games"]}</td><td>{e["wins"]}</td><td>{e["losses"]}</td><td>{e["draws"]}</td>'
        f'<td><strong>{e["points"]}</strong></td><td>{escape(e["win_pct"])}</td></tr>'
        for e in entries)
    return ('<div class="tbl"><table><thead><tr><th>順位</th><th>チーム</th><th>試合</th>'
            '<th>勝</th><th>敗</th><th>分</th><th>勝点</th><th>勝率</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def article_card(a, rel):
    return (f'<div class="digest-card"><p class="cat-line"><span class="cat">{escape(a["category"])}</span>'
            f' <span class="note">{escape(a["date"])}</span></p>'
            f'<h3><a href="{rel}articles/{a["slug"]}/index.html">{escape(a["title"])}</a></h3>'
            f'<p class="note">{escape(a["description"])}</p></div>')


def h2h_section(m, matches):
    pair = [x for x in h2h_list(m["home"], m["away"], matches) if x["id"] != m["id"]]
    if not pair:
        return ""
    a = m["home"]
    wins = sum(1 for x in pair if result_mark(x, a) == "○")
    draws = sum(1 for x in pair if result_mark(x, a) == "△")
    losses = len(pair) - wins - draws
    rows = "".join(
        f'<tr><td>{date_jp(x["date"]) if x["date"] else "—"}</td>'
        f'<td>{escape(x["home"])} {x["home_score"]} - {x["away_score"]} {escape(x["away"])}</td>'
        f'<td>{badge(result_mark(x, a))}</td></tr>'
        for x in pair[:6])
    return ('<section><h2>今季のこれまでの対戦</h2>'
            f'<p>今季のここまでの対戦成績は{escape(a)}から見て'
            f'<strong>{wins}勝{draws}分{losses}敗</strong>（{len(pair)}試合）。</p>'
            '<div class="tbl"><table><thead><tr><th>日付</th><th>結果</th>'
            f'<th>{escape(a)}</th></tr></thead><tbody>{rows}</tbody></table></div></section>')


def preview_sections(m, matches, standings):
    body = ""
    rows = ""
    for t in (m["home"], m["away"]):
        e = next((x for x in standings.get("総合", []) if x["team"] == t), None)
        if e:
            rows += (f'<tr><td>{escape(t)}</td><td>{e["rank"]}位</td>'
                     f'<td>{e["wins"]}-{e["losses"]}-{e["draws"]}</td>'
                     f'<td>{e["points"]}</td><td>{escape(e["win_pct"])}</td></tr>')
    if rows:
        body += ('<section><h2>両チームの今季成績</h2>'
                 '<div class="tbl"><table><thead><tr><th>チーム</th><th>順位</th>'
                 '<th>勝-敗-分</th><th>勝点</th><th>勝率</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div></section>')
    for t in (m["home"], m["away"]):
        rec = recent_results(t, matches)
        if not rec:
            continue
        rows = "".join(
            f'<tr><td>{date_jp(x["date"])}</td><td>{badge(result_mark(x, t))}</td>'
            f'<td>{escape(x["home"])} {x["home_score"]} - {x["away_score"]} {escape(x["away"])}</td></tr>'
            for x in rec)
        body += (f'<section><h2>{escape(t)}の直近の試合</h2>'
                 '<div class="tbl"><table><thead><tr><th>日付</th><th>勝敗</th><th>結果</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table></div></section>')
    return body


# ---------------------------------------------------------------- portal

def build_portal(leagues, articles, meta):
    rel = ""
    total_teams = sum(len(lg["teams"]) for lg in leagues)
    comps_present = [c for c in COMPETITION_ORDER if any(lg["meta"]["competition"] == c for lg in leagues)]
    kicker = "・".join(c.replace("野球連盟", "") for c in comps_present)
    body = ('<div class="hero"><div class="hero-inner">'
            f'<p class="hero-kicker">{escape(kicker)}</p>'
            '<h1>大学野球の試合結果・日程・順位を毎日更新</h1>'
            f'<p class="hero-sub">全{len(leagues)}リーグ・{total_teams}チームの結果・順位を掲載　|　最終更新 {escape(meta["fetched_at"][:10])}</p>'
            '</div></div>')
    for comp in COMPETITION_ORDER:
        comp_leagues = [lg for lg in leagues if lg["meta"]["competition"] == comp]
        if not comp_leagues:
            continue
        body += f'<section><h2>{escape(comp)}</h2>'
        for season in SEASON_ORDER:
            cards = ""
            for lg in comp_leagues:
                if lg["meta"]["season_name"] != season:
                    continue
                played = sum(1 for m in lg["matches"] if m["status"] == "played")
                cards += (f'<div class="digest-card"><h3><a href="{lg["code"]}/index.html">'
                          f'{escape(lg["label"])}</a></h3>'
                          f'<p class="cat-line"><span class="cat">チーム {len(lg["teams"])}</span> '
                          f'<span class="cat">消化 {played}/{len(lg["matches"])}試合</span></p></div>')
            if cards:
                body += f'<h3>{SEASON_YEAR}年{escape(season)}</h3>'
                body += f'<div class="digest">{cards}</div>'
        body += '</section>'
    recent = []
    for lg in leagues:
        for m in lg["matches"]:
            if m["status"] == "played" and m["date"]:
                recent.append((m["date"], lg, m))
    recent.sort(key=lambda x: x[0], reverse=True)
    rows = "".join(match_row(m, "", league_label=lg["label"], league_code=lg["code"])
                   for _, lg, m in recent[:10])
    if rows:
        body += ('<section><h2>最新結果</h2>' + match_table(rows, with_league=True)
                 + '</section>')
    if articles:
        body += ('<section><h2>読みもの</h2><div class="digest">'
                 + "".join(article_card(a, rel) for a in articles[:3])
                 + f'</div><p class="more"><a class="cta" href="articles/index.html">読みもの一覧へ →</a></p></section>')
    write_page("", page(rel, "ベースボールマニア | 大学野球の試合結果・順位・データ", body, meta,
                        path="",
                        desc=f"{kicker}の試合結果・日程・順位表を毎日更新する大学野球情報メディア。"))


# ---------------------------------------------------------------- league pages

def build_league(lg, articles):
    code = lg["code"]
    meta, matches, standings = lg["meta"], lg["matches"], lg["standings"]
    league_name = meta["league"]
    today = date.today().isoformat()

    # ---- league top
    R, L = "../", ""
    sub = league_subnav(lg, L)
    played = [m for m in matches if m["status"] == "played"]
    scheduled = [m for m in matches if m["status"] == "scheduled"]
    upcoming = [m for m in scheduled if m["date"] and m["date"] >= today][:8]
    awaiting = [m for m in scheduled if m["date"] and m["date"] < today]
    recent = list(reversed([m for m in played if m["date"]]))[:8]

    body = f'<h1>{escape(league_name)}</h1>'
    body += f'<p class="lead">試合結果・日程・順位表を毎日更新。チーム{len(lg["teams"])}・全{len(matches)}試合。</p>'
    if recent:
        body += ('<section><h2>最新の試合結果</h2>'
                 + match_table("".join(match_row(m, L) for m in recent))
                 + f'<p class="more"><a class="cta" href="{L}schedule/index.html">全試合の日程・結果 →</a></p></section>')
    if upcoming:
        body += ('<section><h2>今後の試合</h2>'
                 + match_table("".join(match_row(m, L) for m in upcoming)) + '</section>')
    if awaiting:
        body += ('<section><h2>結果反映待ちの試合</h2>'
                 '<p class="note">連盟の公表データにまだスコアが入っていない日程（延期・中止の可能性あり）。</p>'
                 + match_table("".join(match_row(m, L) for m in awaiting)) + '</section>')
    for block, entries in standings.items():
        if entries:
            body += '<section><h2>順位表</h2>' + standings_table(entries, L) + '</section>'
    write_page(code, page(R, f'{league_name} 試合結果・日程・順位表 | ベースボールマニア', body, meta,
                          path=f"{code}/",
                          desc=f'{league_name}の試合結果・日程・順位表・チーム戦績を毎日更新。',
                          subnav=sub))

    # ---- schedule / standings / teams
    R, L = "../../", "../"
    sub = league_subnav(lg, L)
    body = f'<h1>試合日程・結果</h1><p class="lead">{escape(league_name)}</p>'
    upcoming_all = [m for m in scheduled if m["date"] and m["date"] >= today]
    if upcoming_all:
        body += ('<section><h2>今後の試合</h2>'
                 + match_table("".join(match_row(m, L) for m in upcoming_all)) + "</section>")
    if played:
        body += ('<section><h2>試合結果</h2>'
                 + match_table("".join(match_row(m, L) for m in reversed(played))) + "</section>")
    if awaiting:
        body += ('<section><h2>結果反映待ちの試合</h2>'
                 + match_table("".join(match_row(m, L) for m in awaiting)) + "</section>")
    write_page(f"{code}/schedule",
               page(R, f'試合日程・結果 | {league_name} | ベースボールマニア', body, meta,
                    path=f"{code}/schedule/", desc=f'{league_name}の全試合日程と結果の一覧。',
                    subnav=sub))

    body = f'<h1>順位表</h1><p class="lead">{escape(league_name)}</p>'
    for block, entries in standings.items():
        if entries:
            body += standings_table(entries, L)
    body += '<p class="note">※順位表は連盟公式サイトの発表をそのまま掲載しています（大学野球は同一カード2先勝で勝ち点1がつく勝ち点制のため）。</p>'
    write_page(f"{code}/standings",
               page(R, f'順位表 | {league_name} | ベースボールマニア', body, meta,
                    path=f"{code}/standings/", desc=f'{league_name}の順位表。勝点・勝率を毎日更新。',
                    subnav=sub))

    body = f'<h1>チーム一覧</h1><p class="lead">{escape(league_name)}</p>'
    links = "".join(
        f'<li><a href="{L}clubs/{t["slug"]}/index.html">{escape(full_name_for(t["team"]))}</a></li>'
        for t in sorted(lg["teams"].values(), key=lambda x: x["team"]))
    body += f'<ul class="team-list">{links}</ul>'
    write_page(f"{code}/teams",
               page(R, f'チーム一覧 | {league_name} | ベースボールマニア', body, meta,
                    path=f"{code}/teams/", desc=f'{league_name}参加全チームの一覧。',
                    subnav=sub))

    # ---- club pages
    R, L = "../../../", "../../"
    sub = league_subnav(lg, L)
    for team, info in lg["teams"].items():
        slug = info["slug"]
        name = club_label(team)
        my_matches = [m for m in matches if team in (m["home"], m["away"])]
        my_played = [m for m in my_matches if m["status"] == "played"]
        my_upcoming = [m for m in my_matches if m["status"] == "scheduled"]
        entry = next((e for e in standings.get("総合", []) if e["team"] == team), None)

        body = (f'<p class="breadcrumb"><a href="{R}index.html">トップ</a> › '
                f'<a href="{L}index.html">{escape(lg["label"])}</a> › {escape(name)}</p>')
        body += f'<h1>{escape(name)}</h1>'
        body += f'<p class="lead">{escape(league_name)} 所属。</p>'
        if entry:
            body += ('<section><h2>現在の戦績</h2><div class="stat-row">'
                     f'<div class="stat"><span class="num">{entry["rank"]}</span>位</div>'
                     f'<div class="stat"><span class="num">{entry["wins"]}-{entry["losses"]}-{entry["draws"]}</span>勝-敗-分</div>'
                     f'<div class="stat"><span class="num">{entry["points"]}</span>勝ち点</div>'
                     f'<div class="stat"><span class="num">{escape(entry["win_pct"])}</span>勝率</div>'
                     '</div></section>')
        if my_played:
            body += ('<section><h2>試合結果</h2>'
                     + match_table("".join(match_row(m, L) for m in reversed(my_played)))
                     + "</section>")
        if my_upcoming:
            body += ('<section><h2>今後の日程</h2>'
                     + match_table("".join(match_row(m, L) for m in my_upcoming))
                     + "</section>")
        if articles:
            art_links = "".join(
                f'<li><a href="{R}articles/{a["slug"]}/index.html">{escape(a["title"])}</a></li>'
                for a in articles[:3])
            body += (f'<section><h2>読みもの</h2><ul>{art_links}</ul>'
                     f'<p class="more"><a href="{R}articles/index.html">読みもの一覧へ →</a></p></section>')
        body += ('<section class="sponsor"><h2>この部活を応援する企業</h2>'
                 '<p class="todo">（協賛メニュー連携枠：スポンサー企業ロゴ・リンクをここに配置）</p>'
                 f'<p><a class="cta" href="{SPONSOR_CTA_URL}" target="_blank" rel="noopener" '
                 'onclick="window.gtag&&gtag(\'event\',\'cv_sponsor_click\')">協賛について問い合わせる →</a></p></section>')
        write_page(f"{code}/clubs/{slug}",
                   page(R, f'{name} 試合結果・日程・戦績 | ベースボールマニア', body, meta,
                        path=f"{code}/clubs/{slug}/",
                        desc=f'{name}の試合結果・今後の日程・戦績。{league_name}所属。',
                        subnav=sub))

    # ---- match pages
    for m in matches:
        report = match_report(m, standings, league_name)
        body = (f'<p class="breadcrumb"><a href="{R}index.html">トップ</a> › '
                f'<a href="{L}index.html">{escape(lg["label"])}</a> › '
                f'<a href="{L}schedule/index.html">日程・結果</a></p>')
        body += f'<h1>{escape(match_headline(m))}</h1>'
        body += f'<p class="report">{escape(report)}</p>'
        if m["status"] == "scheduled":
            body += preview_sections(m, matches, standings)
        body += h2h_section(m, matches)
        d = date_jp(m["date"], with_year=True) if m["date"] else "未定"
        body += ('<div class="tbl"><table class="detail"><tbody>'
                 f'<tr><th>日付</th><td>{d}</td></tr>'
                 f'<tr><th>時間</th><td>{escape(m["time"])}</td></tr>'
                 f'<tr><th>球場</th><td>{escape(m["venue"])}</td></tr>'
                 f'<tr><th>スコア</th><td>{score_str(m)}</td></tr>'
                 '</tbody></table></div>')
        body += ('<p class="links">'
                 f'<a href="{L}clubs/{m["home_slug"]}/index.html">{escape(m["home"])}のページ</a> / '
                 f'<a href="{L}clubs/{m["away_slug"]}/index.html">{escape(m["away"])}のページ</a></p>')
        write_page(f"{code}/matches/{m['id']}",
                   page(R, match_headline(m) + f' | {lg["label"]} | ベースボールマニア', body, meta,
                        path=f"{code}/matches/{m['id']}/", desc=report[:120], og_type="article",
                        extra_head=jsonld_sports_event(m, league_name),
                        subnav=sub))


# ---------------------------------------------------------------- global pages

def build_articles(articles, meta):
    if not articles:
        return
    rel = "../"
    cards = "".join(article_card(a, rel) for a in articles)
    body = ('<h1>読みもの</h1>'
            '<p class="lead">戦術・練習・チーム運営・分析 ― 大学野球の現場で使える知見をまとめています。</p>'
            f'<div class="digest">{cards}</div>')
    write_page("articles",
               page(rel, "読みもの（戦術・練習・チーム運営・分析） | ベースボールマニア", body, meta,
                    path="articles/",
                    desc="大学野球の戦術・練習メニュー・チーム運営・映像分析の実践的なノウハウ記事。"))
    rel = "../../"
    for a in articles:
        others = [x for x in articles if x["slug"] != a["slug"]][:3]
        related = "".join(
            f'<li><a href="../{x["slug"]}/index.html">{escape(x["title"])}</a></li>'
            for x in others)
        body = (f'<p class="breadcrumb"><a href="{rel}index.html">トップ</a> › '
                f'<a href="{rel}articles/index.html">読みもの</a> › {escape(a["category"])}</p>')
        body += (f'<p class="cat-line"><span class="cat">{escape(a["category"])}</span>'
                 f' <span class="note">{escape(a["date"])}</span></p>')
        body += f'<h1>{escape(a["title"])}</h1>'
        body += f'<div class="article">{md_to_html(a["body"])}</div>'
        body += f'<section><h2>あわせて読む</h2><ul>{related}</ul></section>'
        write_page(f"articles/{a['slug']}",
                   page(rel, f'{a["title"]} | ベースボールマニア', body, meta,
                        path=f'articles/{a["slug"]}/', desc=a["description"], og_type="article"))


def build_glossary(meta):
    gfile = ROOT / "content" / "glossary.json"
    if not gfile.exists():
        return
    rel = "../"
    terms = json.loads(gfile.read_text(encoding="utf-8"))
    cats: dict[str, list] = {}
    for t in terms:
        cats.setdefault(t["category"], []).append(t)
    body = ('<h1>野球用語辞典</h1>'
            f'<p class="lead">試合観戦や部活動で使われる野球用語{len(terms)}語を分野別にまとめました。</p>')
    for cat, items in cats.items():
        rows = "".join(
            f'<tr><th>{escape(t["term"])}</th><td>{escape(t["def"])}</td></tr>'
            for t in items)
        body += (f'<section><h2>{escape(cat)}</h2>'
                 f'<div class="tbl"><table class="detail"><tbody>{rows}</tbody></table></div></section>')
    write_page("glossary",
               page(rel, "野球用語辞典（ルール・ポジション・技術用語） | ベースボールマニア", body, meta,
                    path="glossary/",
                    desc="大学野球の用語を分野別に解説。観戦・新入生・保護者向けの用語集。"))


def build_videos(meta):
    vfile = DATA / "videos.json"
    if not vfile.exists():
        return
    rel = "../"
    vids = json.loads(vfile.read_text(encoding="utf-8"))
    if not vids:
        return
    cats: dict[str, list] = {}
    for v in vids:
        cats.setdefault(v["category"], []).append(v)
    body = ('<h1>動画インデックス</h1>'
            '<p class="lead">大学野球の試合映像・配信を公式ソースから探せるリンク集です。</p>')
    for cat, items in cats.items():
        cards = "".join(
            f'<div class="digest-card"><h3><a href="{escape(v["url"])}">{escape(v["title"])}</a></h3>'
            f'<p class="note">{escape(v["note"])}</p>'
            f'<p class="cat-line"><span class="cat">{escape(v["source"])}</span></p></div>'
            for v in items)
        body += f'<h2>{escape(cat)}</h2><div class="digest">{cards}</div>'
    write_page("videos",
               page(rel, "動画インデックス（試合映像・ライブ配信） | ベースボールマニア", body, meta,
                    path="videos/",
                    desc="大学野球の試合映像・ライブ配信を公式ソースから探せるリンク集。"))


DASHBOARD_PATH = "dash-bm-ops"  # 非公開運用ダッシュボード（noindex・sitemap非掲載）


def build_dashboard(leagues, articles, meta):
    from datetime import datetime, timedelta
    rel = "../"
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    total_teams = sum(len(lg["teams"]) for lg in leagues)
    total_matches = sum(len(lg["matches"]) for lg in leagues)
    total_played = sum(1 for lg in leagues for m in lg["matches"] if m["status"] == "played")
    recent_results = sum(1 for lg in leagues for m in lg["matches"]
                         if m["status"] == "played" and m["date"] and m["date"] >= week_ago)

    body = ('<h1>運営ダッシュボード</h1>'
            f'<p class="lead">ベースボールマニアの定点観測。毎朝の自動更新で最新化されます。'
            f'ビルド: {today.isoformat()} / データ取得: {escape(meta["fetched_at"][:16].replace("T", " "))}</p>')

    body += ('<section><h2>サイト全体</h2><div class="stat-row">'
             f'<div class="stat"><span class="num">{len(_sitemap_paths)}</span>公開ページ</div>'
             f'<div class="stat"><span class="num">{len(leagues)}</span>リーグ</div>'
             f'<div class="stat"><span class="num">{total_teams}</span>チーム</div>'
             f'<div class="stat"><span class="num">{total_played}/{total_matches}</span>消化試合</div>'
             f'<div class="stat"><span class="num">{recent_results}</span>直近7日の結果</div>'
             '</div></section>')

    mfile = DATA / "metrics.json"
    if mfile.exists():
        mx = json.loads(mfile.read_text(encoding="utf-8"))
        ga = mx.get("ga", {})
        gsc = mx.get("gsc", {})
        body += (f'<section><h2>リリース後の実績（{escape(mx.get("release_date", ""))}〜）</h2>'
                 '<div class="stat-row">'
                 f'<div class="stat"><span class="num">{ga.get("total_users", "—")}</span>ユーザー</div>'
                 f'<div class="stat"><span class="num">{ga.get("total_pageviews", "—")}</span>ページビュー</div>'
                 f'<div class="stat"><span class="num">{gsc.get("total_clicks", "—")}</span>検索クリック</div>'
                 '</div>'
                 f'<p class="note">最終取得: {escape(mx.get("updated_at", ""))}</p></section>')
    else:
        body += ('<section><h2>リリース後の実績</h2>'
                 '<p class="note">GA4/Search Console 未連携。連携が完了すると数値が表示されます。</p></section>')

    rows = ""
    for lg in leagues:
        played = sum(1 for m in lg["matches"] if m["status"] == "played")
        total = len(lg["matches"])
        pct = round(played / total * 100) if total else 0
        upd = lg["meta"]["source_updated_at"] or "—"
        rows += (f'<tr><td><a href="{rel}{lg["code"]}/index.html">{escape(lg["label"])}</a></td>'
                 f'<td>{len(lg["teams"])}</td><td>{played}/{total}（{pct}%）</td>'
                 f'<td>{escape(upd)}</td></tr>')
    body += ('<section><h2>リーグ別の状況</h2>'
             '<div class="tbl"><table><thead><tr><th>リーグ</th><th>チーム</th>'
             '<th>消化試合</th><th>取得日</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div></section>')

    body += ('<section><h2>外部ツール（クリックで開く）</h2><ul>'
             '<li><a href="https://search.google.com/search-console">Search Console</a></li>'
             '<li><a href="https://analytics.google.com/">GA4</a></li>'
             '</ul></section>')

    write_page(DASHBOARD_PATH,
               page(rel, "運営ダッシュボード | ベースボールマニア", body, meta,
                    path=f"{DASHBOARD_PATH}/", desc="運営用の内部ダッシュボード。",
                    sitemap=False))


# ---------------------------------------------------------------- misc output

def write_sitemap_and_robots():
    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{SITE_BASE}{p}</loc><lastmod>{today}</lastmod></url>"
        for p in _sitemap_paths)
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + urls + "</urlset>", encoding="utf-8")
    (SITE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_BASE}sitemap.xml\n", encoding="utf-8")


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="#14213d"/>
<rect x="10" y="40" width="44" height="8" rx="4" fill="#c8102e"/>
<text x="32" y="36" font-family="Arial, sans-serif" font-size="26" font-weight="bold"
 fill="#ffffff" text-anchor="middle">BM</text>
</svg>
"""

STYLE = """
:root {
  --ink:#1a2028; --sub:#5b6472; --line:#dde2e8; --bg:#f5f7fa; --surface:#fff;
  --navy:#14213d; --navy-2:#1b2f57; --accent:#c8102e; --accent-dark:#96001f;
  --win:#15803d; --draw:#b45309; --loss:#b91c1c;
}
* { box-sizing:border-box; }
body { margin:0; font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,sans-serif;
  color:var(--ink); background:var(--bg); line-height:1.7; }
a { color:var(--navy-2); }
a:hover { color:var(--accent-dark); }

.site-header { background:var(--navy); }
.header-inner { max-width:960px; margin:0 auto; padding:.7rem 1rem .5rem;
  display:flex; flex-wrap:wrap; align-items:center; gap:.3rem 1.5rem; }
.brand { display:flex; align-items:baseline; gap:.5rem; font-weight:800;
  color:#fff; text-decoration:none; font-size:1.25rem; letter-spacing:.02em; }
.brand-tick { width:.55em; height:.55em; background:var(--accent);
  border-radius:2px; align-self:center; }
.brand-sub { font-size:.6rem; color:#a9b8d4; font-weight:600; letter-spacing:.18em; }
.global-nav { display:flex; gap:.2rem; overflow-x:auto; margin-left:auto; }
.global-nav a { color:#d7e0ee; text-decoration:none; font-size:.85rem; font-weight:600;
  padding:.35em .7em; border-radius:6px; white-space:nowrap; }
.global-nav a:hover { background:var(--navy-2); color:#fff; }

.league-nav { background:var(--navy-2); }
.league-nav-inner { max-width:960px; margin:0 auto; padding:.3rem 1rem;
  display:flex; gap:.15rem; align-items:center; overflow-x:auto; flex-wrap:wrap; }
.league-nav .league-name { color:#fff; font-weight:700; font-size:.85rem;
  margin-right:.6rem; white-space:nowrap; }
.league-nav a { color:#d7e0ee; text-decoration:none; font-size:.8rem;
  padding:.3em .6em; border-radius:6px; white-space:nowrap; }
.league-nav a:hover { background:var(--navy); color:#fff; }
.season-switch { margin-left:auto; font-size:.78rem; color:#a9b8d4; white-space:nowrap; }
.season-switch a { color:#d7e0ee; }
.season-current { color:#fff; font-weight:700; }

.hero { background:linear-gradient(120deg, var(--navy) 0%, var(--navy-2) 70%, #2c4a6e 100%);
  color:#fff; margin:0 -1rem; }
.hero-inner { max-width:960px; margin:0 auto; padding:2.2rem 1rem 2.4rem; }
.hero-kicker { color:var(--accent); font-weight:700; font-size:.85rem; margin:0 0 .4rem; }
.hero h1 { font-size:1.5rem; line-height:1.45; margin:0 0 .6rem; }
.hero-sub { color:#c9d4e6; font-size:.85rem; margin:0; }

main { max-width:960px; margin:0 auto; padding:0 1rem 3rem; }
h1 { font-size:1.35rem; line-height:1.45; }
h2 { font-size:1.08rem; border-left:4px solid var(--accent); padding-left:.55em;
  margin-top:2.4em; }
h3 { font-size:.95rem; margin-top:1.6em; }

.tbl { overflow-x:auto; background:var(--surface); border:1px solid var(--line);
  border-radius:10px; }
table { width:100%; border-collapse:collapse; font-size:.85rem; }
th, td { border-bottom:1px solid var(--line); padding:.5em .7em; text-align:left;
  white-space:nowrap; }
tbody tr:last-child td { border-bottom:none; }
thead th { background:var(--navy); color:#fff; font-weight:600; font-size:.78rem; }
tbody tr:nth-child(even) { background:#f4f6fa; }
td.score { font-weight:700; }
td.venue { color:var(--sub); font-size:.78rem; max-width:16em; overflow:hidden;
  text-overflow:ellipsis; }
td.rank { font-weight:700; text-align:center; }
.cat { background:#e8ecf4; color:var(--navy-2); font-size:.72rem; font-weight:700;
  padding:.15em .5em; border-radius:999px; }
table.detail th { background:#eef1f7; color:var(--ink); width:9em; white-space:normal; }
table.detail td { white-space:normal; }

.mk { font-weight:700; }
.mk-w { color:var(--win); }
.mk-d { color:var(--draw); }
.mk-l { color:var(--loss); }

.breadcrumb { font-size:.8rem; color:var(--sub); margin-top:1rem; }
.breadcrumb a { color:var(--sub); }
.lead { color:var(--sub); }
.note { color:var(--sub); font-size:.8rem; }
.more { margin:.9rem 0 0; }
.cta { display:inline-block; background:var(--accent); color:#fff; font-weight:700;
  font-size:.85rem; text-decoration:none; padding:.5em 1.1em; border-radius:8px; }
.cta:hover { background:var(--accent-dark); color:#fff; }

.stat-row { display:flex; gap:.8rem; flex-wrap:wrap; }
.stat { background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:.7rem 1.1rem; font-size:.75rem; color:var(--sub); min-width:100px;
  text-align:center; }
.stat .num { display:block; font-size:1.35rem; font-weight:800; color:var(--navy); }

.report { background:var(--surface); border:1px solid var(--line);
  border-left:4px solid var(--accent); border-radius:10px; padding:1rem 1.2rem; }

.digest { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr));
  gap:1rem; }
.digest-card { background:var(--surface); border:1px solid var(--line);
  border-radius:10px; padding:.9rem 1rem 1rem; }
.digest-card h3 { margin:.1em 0 .6em; }
.digest-card h3 a { text-decoration:none; color:var(--navy); }
.digest-card h3 a:hover { color:var(--accent-dark); }
.digest-card .tbl { border:none; }
.team-list { list-style:none; margin:0; padding:0; columns:2; font-size:.9rem; }
.team-list li { margin:.25em 0; break-inside:avoid; }

.sponsor .todo { color:var(--sub); background:var(--surface);
  border:1px dashed var(--line); border-radius:10px; padding:.8rem; font-size:.85rem; }

.cat-line { font-size:.8rem; margin:.4rem 0; }
.article { background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:1.4rem 1.6rem 1.6rem; }
.article h2 { margin-top:1.8em; }
.article h2:first-child { margin-top:.4em; }
.article li { margin:.3em 0; }

.site-footer { background:var(--navy); color:#a9b8d4; font-size:.75rem;
  margin-top:3rem; }
.footer-inner { max-width:960px; margin:0 auto; padding:1.4rem 1rem 2rem; }
.footer-brand { color:#fff; font-weight:800; font-size:.95rem; margin:0 0 .3rem; }
.footer-nav { display:flex; gap:1rem; margin:.2rem 0 .8rem; }
.footer-nav a { color:#c9d4e6; text-decoration:none; }
.site-footer a { color:#c9d4e6; }
"""


def main():
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    _sitemap_paths.clear()

    leagues = load_leagues()
    articles = load_articles()
    if not leagues:
        raise SystemExit("リーグデータがありません（pipeline/fetch_all.pyを先に実行）")
    global_meta = dict(leagues[0]["meta"])
    global_meta["fetched_at"] = max(lg["meta"]["fetched_at"] for lg in leagues)
    global_meta["source_updated_at"] = max(lg["meta"]["source_updated_at"] for lg in leagues)
    seen_sources: dict[str, str] = {}
    for lg in leagues:
        seen_sources.setdefault(lg["meta"]["source"], lg["meta"]["source_url"])
    global_meta["sources"] = [{"label": k, "url": v} for k, v in seen_sources.items()]

    (SITE / "style.css").write_text(STYLE, encoding="utf-8")
    (SITE / "assets").mkdir()
    (SITE / "assets" / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    if ASSETS.exists():
        for f in ASSETS.iterdir():
            shutil.copy(f, SITE / "assets" / f.name)

    build_portal(leagues, articles, global_meta)
    for lg in leagues:
        build_league(lg, articles)
    build_articles(articles, global_meta)
    build_videos(global_meta)
    build_glossary(global_meta)
    build_dashboard(leagues, articles, global_meta)
    write_sitemap_and_robots()

    print(f"OK: {len(_sitemap_paths)} pages ({len(leagues)} leagues) in {SITE}")


if __name__ == "__main__":
    main()
