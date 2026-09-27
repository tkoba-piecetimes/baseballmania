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

    # ---- 東京新大学野球連盟 1部 ----
    "杏林大": ("kyorin", "杏林大学"),
    "創価大": ("soka", "創価大学"),
    "東京国際大": ("tokyo-kokusai", "東京国際大学"),
    "流経大": ("ryutsu-keizai", "流通経済大学"),
    "共栄大": ("kyoei", "共栄大学"),
    "駿河台大": ("surugadai", "駿河台大学"),

    # ---- 東京新大学野球連盟 2部 ----
    "学芸大": ("gakugei", "東京学芸大学"),
    "日本ウェルネス大": ("nihon-wellness", "日本ウェルネススポーツ大学東京"),
    "東洋学園大": ("toyogakuen", "東洋学園大学"),
    "高千穂大": ("takachiho", "高千穂大学"),
    "工学院大": ("kogakuin", "工学院大学"),
    "都立大": ("toritsu", "都立大学"),

    # ---- 東京新大学野球連盟 3部 ----
    "淑徳大": ("shukutoku", "淑徳大学埼玉キャンパス"),
    "日本工大": ("nihon-kogyo", "日本工業大学"),
    "東京理科大": ("tokyo-rika", "東京理科大学"),
    "国際基督教大": ("icu", "国際基督教大学"),
    "文京学院大": ("bunkyogakuin", "文京学院大学"),
    "日大生物資源": ("nihon-seibutsushigen", "日本大学生物資源科学部"),

    # ---- 東京新大学野球連盟 4部 ----
    "東京外語大": ("tokyo-gaigo", "東京外国語大学"),
    "東京電機大": ("tokyo-denki", "東京電機大学"),
    "電気通信大": ("denki-tsushin", "電気通信大学"),
    "東京農工大": ("tokyo-noko", "東京農工大学"),
    "東京工科大": ("tokyo-koka", "東京工科大学"),
    "東京海洋大": ("tokyo-kaiyo", "東京海洋大学"),

    # ---- 中国地区大学野球連盟 1部 ----
    "周南公立大": ("shunan-kritsu", "周南公立大学"),
    "広島文化学園大": ("hiroshima-bunka", "広島文化学園大学"),
    "東亜大": ("toa", "東亜大学"),
    "吉備国際大": ("kibi-kokusai", "吉備国際大学"),
    "環太平洋大": ("kantaiheiyo", "環太平洋大学"),
    "岡山商科大": ("okayama-shoka", "岡山商科大学"),

    # ---- 中国地区大学野球連盟 2部 ----
    "岡山理科大": ("okayama-rika", "岡山理科大学"),
    "至誠館大": ("shiseikan", "至誠館大学"),
    "福山大": ("fukuyama", "福山大学"),
    "岡山大": ("okayama", "岡山大学"),
    "川崎医療福祉大": ("kawasaki-iryo-fukushi", "川崎医療福祉大学"),
    "島根大": ("shimane", "島根大学"),

    # ---- 中国地区大学野球連盟 3部 ----
    "岡山県立大": ("okayama-kenritsu", "岡山県立大学"),
    "鳥取大": ("tottori", "鳥取大学"),
    "山口大": ("yamaguchi", "山口大学"),
    "島根県立大": ("shimane-kenritsu", "島根県立大学"),
    "尾道市立大": ("onomichi-shiritsu", "尾道市立大学"),
    "倉敷芸術科学大": ("kurashiki-geijutsu", "倉敷芸術科学大学"),
    "比治山大": ("hijiyama", "比治山大学"),
    "くらしき作陽大": ("kurashiki-sakuyo", "くらしき作陽大学"),

    # ---- 阪神大学野球連盟 1部 ----
    "天理大": ("tenri", "天理大学"),
    "大体大": ("osaka-taiiku", "大阪体育大学"),
    "関国大": ("kansai-kokusai", "関西国際大学"),
    "大産大": ("osaka-sangyo", "大阪産業大学"),
    "甲南大": ("konan", "甲南大学"),
    "関外大": ("kansai-gaikokugo", "関西外国語大学"),

    # ---- 阪神大学野球連盟 2部東 ----
    # 略称は連盟サイトの表記（勝敗表ヘッダー・対戦カード）にそのまま合わせる
    "電通大": ("osaka-dentsu", "大阪電気通信大学"),
    "桃山大": ("momoyama", "桃山学院大学"),
    "追門大": ("otemon", "追手門学院大学"),
    "摂南大": ("setsunan", "摂南大学"),
    "経法大": ("keiho", "大阪経済法科大学"),
    "帝塚大": ("tezukayama", "帝塚山大学"),

    # ---- 阪神大学野球連盟 2部西 ----
    "流科大": ("ryutsu-kagaku", "流通科学大学"),
    "獨協大": ("himeji-dokkyo", "姫路獨協大学"),
    "神国大": ("kobe-kokusai", "神戸国際大学"),
    "宝医大": ("takarazuka-iryo", "宝塚医療大学"),
    "兵庫大": ("hyogo", "兵庫大学"),
    "関福大": ("kansai-fukushi", "関西福祉大学"),
}

_FULL_TO_ABBR: dict[str, str] | None = None


def abbr_for_full(full_name: str) -> str:
    """フル表記（「杏林大学」等）からTEAM_INFOの略称キー（「杏林大」等）を逆引きする。
    東京新大学野球連盟のように、連盟サイト側がフル表記でチーム名を掲載する場合に、
    既存の東都・六大学と同じ「略称をteamフィールドに使う」慣習に揃えるためのヘルパー。
    対応表に無ければフル表記をそのまま返す（pykakasiでロ―マ字化される）。"""
    global _FULL_TO_ABBR
    if _FULL_TO_ABBR is None:
        _FULL_TO_ABBR = {full: abbr for abbr, (_slug, full) in TEAM_INFO.items()}
    return _FULL_TO_ABBR.get(full_name, full_name)


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
