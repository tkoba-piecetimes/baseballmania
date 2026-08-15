# -*- coding: utf-8 -*-
"""試合データから「節レビュー記事」（Type A: 週末の結果まとめ）を自動生成する。

data/leagues/<league>/matches.json・standings.json・meta.json を読み、
リーグ×「結果が入った試合日クラスタ」（連続する試合日の間隔が
CLUSTER_GAP_DAYS日以内なら同じ週末・同じ節とみなしてまとめる。六大学・東都
3部/4部の週末開催（金土日月）はもちろん、東都1部/2部の平日開催（火水木）
のような中1日空きの連戦もひとまとまりになる）ごとに1記事を
content/articles/ に生成する。slugは決定的（review-<リーグcode>-<週末代表日>）
なので、同slugのファイルが既にあれば再生成しない（冪等）。

1回の実行で生成するのは最大MAX_PER_RUN件。全リーグを横断して代表日が
古い週から順に処理するため、過去分は毎日の自動実行（update.yml）で
少しずつ消化され、いずれ最新の節に追いつく。

生成する記事はLLMを使わず、試合データからテンプレートで機械的に組み立てる
（見出し・結果テーブル・順位表テーブル・チームページへのリンク・出典）。
frontmatterは generate_site.py の load_articles() が読める平文形式。
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONTENT = ROOT / "content" / "articles"

LEAGUE_ORDER = [
    "rikudai-2026-haru", "rikudai-2026-aki",
    "tohto1-2026-haru", "tohto1-2026-aki",
    "tohto2-2026-haru", "tohto2-2026-aki",
    "tohto3-2026-haru", "tohto3-2026-aki",
    "tohto4-2026-haru", "tohto4-2026-aki",
]

MAX_PER_RUN = 2          # 1回の実行で生成する記事数の上限（過去分消化のペース制御）
CLUSTER_GAP_DAYS = 2      # この日数以内の間隔で連続する試合日は同じ「節」クラスタとみなす
WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]


# ---------------------------------------------------------------- data loading

def load_league(code):
    d = DATA / "leagues" / code
    if not (d / "matches.json").exists():
        return None
    return {
        "code": code,
        "matches": json.loads((d / "matches.json").read_text(encoding="utf-8")),
        "standings": json.loads((d / "standings.json").read_text(encoding="utf-8")),
        "meta": json.loads((d / "meta.json").read_text(encoding="utf-8")),
    }


def load_leagues():
    out = []
    for code in LEAGUE_ORDER:
        lg = load_league(code)
        if lg:
            out.append(lg)
    return out


# ---------------------------------------------------------------- text helpers

def date_jp(iso):
    d = date.fromisoformat(iso)
    return f"{d.month}月{d.day}日（{WEEKDAYS_JP[d.weekday()]}）"


def date_range_jp(dates):
    if dates[0] == dates[-1]:
        return date_jp(dates[0].isoformat())
    return f"{date_jp(dates[0].isoformat())}から{date_jp(dates[-1].isoformat())}にかけて"


def score_diff(m):
    return abs(m["home_score"] - m["away_score"])


def notable_sentence(matches):
    """その節で最も注目すべきスコア（接戦 or 最大点差）に触れる1文を作る。"""
    draws = [m for m in matches if m["home_score"] == m["away_score"]]
    if draws:
        m = draws[0]
        return (f'{m["home"]}と{m["away"]}の一戦は{m["home_score"]}-{m["away_score"]}の'
                f'引き分けとなった。')
    closest = min(matches, key=score_diff)
    if score_diff(closest) <= 1:
        m = closest
        winner = m["home"] if m["home_score"] > m["away_score"] else m["away"]
        loser = m["away"] if winner == m["home"] else m["home"]
        hs, as_ = max(m["home_score"], m["away_score"]), min(m["home_score"], m["away_score"])
        return f'{winner}が{loser}を{hs}-{as_}の1点差で振り切る接戦もあった。'
    m = max(matches, key=score_diff)
    winner = m["home"] if m["home_score"] > m["away_score"] else m["away"]
    loser = m["away"] if winner == m["home"] else m["home"]
    hs, as_ = max(m["home_score"], m["away_score"]), min(m["home_score"], m["away_score"])
    return f'{winner}が{loser}に{hs - as_}点差（{hs}-{as_}）をつける快勝を収めた。'


def leader_sentence(standings):
    entries = standings.get("総合") or []
    leaders = [e for e in entries if e.get("rank") == 1]
    if not leaders:
        return ""
    if len(leaders) == 1:
        e = leaders[0]
        return f'現在の首位は{e["team"]}（勝ち点{e["points"]}）です。'
    names = "・".join(e["team"] for e in leaders)
    return f'現在は{names}が勝ち点{leaders[0]["points"]}で首位に並んでいます。'


# ---------------------------------------------------------------- clustering

def cluster_dates(dates):
    """昇順のdateリストを、間隔がCLUSTER_GAP_DAYS以内なら同じ節とみなしてクラスタ化する。"""
    clusters = []
    cur = [dates[0]]
    for d in dates[1:]:
        if (d - cur[-1]).days <= CLUSTER_GAP_DAYS:
            cur.append(d)
        else:
            clusters.append(cur)
            cur = [d]
    clusters.append(cur)
    return clusters


def find_pending(leagues):
    """(代表日, リーグ, 節内の試合)のリストを代表日昇順で返す。"""
    pending = []
    for lg in leagues:
        played = [m for m in lg["matches"] if m["status"] == "played" and m["date"]]
        if not played:
            continue
        distinct_dates = sorted({date.fromisoformat(m["date"]) for m in played})
        for cluster in cluster_dates(distinct_dates):
            iso_set = {d.isoformat() for d in cluster}
            cluster_matches = [m for m in played if m["date"] in iso_set]
            cluster_matches.sort(key=lambda m: (m["date"], m["time"]))
            rep = cluster[0]
            slug = f'review-{lg["code"]}-{rep.strftime("%Y%m%d")}'
            pending.append({
                "rep": rep,
                "slug": slug,
                "league": lg,
                "dates": cluster,
                "matches": cluster_matches,
            })
    pending.sort(key=lambda p: (p["rep"], p["league"]["code"]))
    return pending


# ---------------------------------------------------------------- article body

def build_body(item):
    lg = item["league"]
    meta = lg["meta"]
    code = lg["code"]
    matches = item["matches"]

    lead = (f'{meta["league"]}では、{date_range_jp(item["dates"])}{len(matches)}試合が'
            f'行われました。')
    leader = leader_sentence(lg["standings"])
    if leader:
        lead += leader
    lead += notable_sentence(matches)

    result_rows = ["| 日付 | 対戦 | スコア |", "| --- | --- | --- |"]
    for m in matches:
        matchup = f'[{m["home"]} vs {m["away"]}](../../{code}/matches/{m["id"]}/index.html)'
        result_rows.append(
            f'| {date_jp(m["date"])} | {matchup} | {m["home_score"]} - {m["away_score"]} |')
    results_table = "\n".join(result_rows)

    standings_rows = ["| 順位 | チーム | 勝敗 | 勝点 |", "| --- | --- | --- | --- |"]
    for e in lg["standings"].get("総合", []):
        team_link = f'[{e["team"]}](../../{code}/clubs/{e["slug"]}/index.html)'
        wl = f'{e["wins"]}勝{e["losses"]}敗{e["draws"]}分'
        standings_rows.append(f'| {e["rank"]} | {team_link} | {wl} | {e["points"]} |')
    standings_table = "\n".join(standings_rows)

    seen, teams = set(), []
    for m in matches:
        for team, slug in ((m["home"], m["home_slug"]), (m["away"], m["away_slug"])):
            if slug not in seen:
                seen.add(slug)
                teams.append((team, slug))
    teams.sort(key=lambda t: t[0])
    team_links = "\n".join(
        f'- [{t}のページ](../../{code}/clubs/{s}/index.html)' for t, s in teams)

    source = f'- [{meta["source"]}]({meta["source_url"]})'

    return f"""{lead}

## 今節の結果

{results_table}

## 現在の順位表

{standings_table}

## 対戦カードのチームページ

{team_links}

## 出典

{source}
"""


def build_article(item):
    lg = item["league"]
    meta = lg["meta"]
    rep = item["rep"]
    n = len(item["matches"])
    title = f'【{meta["league"]}】{rep.month}月{rep.day}日週の結果まとめ'
    description = f'{rep.month}月{rep.day}日週は{n}試合が行われた。' + notable_sentence(item["matches"])
    body = build_body(item)
    frontmatter = (
        "---\n"
        f"title: {title}\n"
        f"description: {description}\n"
        f"date: {rep.isoformat()}\n"
        "category: 週末レビュー\n"
        "cta: sponsor\n"
        "---\n"
    )
    return frontmatter + body


# ---------------------------------------------------------------- main

def main():
    CONTENT.mkdir(parents=True, exist_ok=True)
    leagues = load_leagues()
    if not leagues:
        raise SystemExit("リーグデータがありません（pipeline/fetch_all.pyを先に実行）")

    pending = find_pending(leagues)
    existing = {f.stem for f in CONTENT.glob("*.md")}
    todo = [p for p in pending if p["slug"] not in existing]

    created = []
    for item in todo[:MAX_PER_RUN]:
        text = build_article(item)
        (CONTENT / f'{item["slug"]}.md').write_text(text, encoding="utf-8")
        created.append(item["slug"])

    remaining = len(todo) - len(created)
    print(f'OK: generated {len(created)} article(s): {", ".join(created) if created else "(none)"}')
    print(f'Pending (not yet generated): {remaining}')


if __name__ == "__main__":
    main()
