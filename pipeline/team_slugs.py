# -*- coding: utf-8 -*-
"""チーム名（連盟表記の略称） → URLスラッグ・正式名称の対応表（大学野球版）。

東京六大学野球連盟(big6.gr.jp)・東都大学野球連盟(tohto-bbl.com)ともに
「早大」「國學院大」のような略称でチームを表記するため、この略称をキーにする。
解決順: 1) 手動登録の対応表  2) pykakasiによるローマ字化  3) ハッシュフォールバック
"""
import re
import sys

# 略称 -> (スラッグ, 正式名称)
TEAM_INFO = {
    # ---- 東京六大学野球連盟 ----
    "早大": ("waseda", "早稲田大学"),
    "慶大": ("keio", "慶應義塾大学"),
    "明大": ("meiji", "明治大学"),
    "法大": ("hosei", "法政大学"),
    "立大": ("rikkyo", "立教大学"),
    "東大": ("todai", "東京大学"),

    # ---- 東都大学野球連盟 1部 ----
    "國學院大": ("kokugakuin", "國學院大學"),
    "青学大": ("aoyamagakuin", "青山学院大学"),
    "亜細亜大": ("asia", "亜細亜大学"),
    "中央大": ("chuo", "中央大学"),
    "立正大": ("rissho", "立正大学"),
    "東洋大": ("toyo", "東洋大学"),

    # ---- 東都大学野球連盟 2部 ----
    "専修大": ("senshu", "専修大学"),
    "駒澤大": ("komazawa", "駒澤大学"),
    "日本大": ("nihon", "日本大学"),
    "拓殖大": ("takushoku", "拓殖大学"),
    "東農大": ("tokyo-nodai", "東京農業大学"),
    "帝平大": ("teikyo-heisei", "帝京平成大学"),

    # ---- 東都大学野球連盟 3部 ----
    "国士大": ("kokushikan", "国士舘大学"),
    "大正大": ("taisho", "大正大学"),
    "上智大": ("sophia", "上智大学"),
    "成蹊大": ("seikei", "成蹊大学"),
    "学習大": ("gakushuin", "学習院大学"),
    "一橋大": ("hitotsubashi", "一橋大学"),

    # ---- 東都大学野球連盟 4部 ----
    "順大": ("juntendo", "順天堂大学"),
    "芝工大": ("shibaura", "芝浦工業大学"),
    "都市大": ("tokyo-city", "東京都市大学"),
    "科学大": ("science-tokyo", "東京科学大学"),
}

_kks = None


def _romaji(name: str) -> str | None:
    global _kks
    try:
        if _kks is None:
            import pykakasi
            _kks = pykakasi.kakasi()
        base = re.sub(r"(大学院|大学|大)$", "", name.strip())
        s = "".join(x["hepburn"] for x in _kks.convert(base))
        s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
        return s or None
    except Exception:
        return None


def slug_for(team: str) -> str:
    if team in TEAM_INFO:
        return TEAM_INFO[team][0]
    r = _romaji(team)
    if r:
        TEAM_INFO[team] = (r, team)
        return r
    print(f"[warn] スラッグ生成不可のチーム名: {team}", file=sys.stderr)
    return f"team-{abs(hash(team)) % 10**8}"


def full_name_for(team: str) -> str:
    if team in TEAM_INFO:
        return TEAM_INFO[team][1]
    return team
