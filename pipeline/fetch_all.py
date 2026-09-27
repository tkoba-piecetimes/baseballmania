# -*- coding: utf-8 -*-
"""対象連盟を順番に取得する（東京六大学・東都大学・東京新大学・中国地区・阪神）。

連盟ごとに独立してtry/exceptで囲み、1連盟の取得が失敗しても他の連盟の
取得を止めない（失敗した連盟は前回取得済みのdata/leagues/配下をそのまま
残し、エラー内容を出力するだけに留める）。"""
import sys

import fetch_big6
import fetch_big6_players
import fetch_tohto
import fetch_shintokyo
import fetch_chugoku
import fetch_hanshin


def run(label: str, fn) -> None:
    print(f"=== {label} ===")
    try:
        fn()
    except Exception as e:  # 1連盟の失敗が他連盟の取得を止めないようにする
        print(f"[error] {label}: 取得処理が失敗しました ({e})", file=sys.stderr)


def main() -> None:
    run("東京六大学野球連盟（big6.gr.jp）", fetch_big6.main)
    run("東京六大学野球連盟 個人成績（big6.gr.jp）", fetch_big6_players.main)
    run("東都大学野球連盟（tohto-bbl.com）", fetch_tohto.main)
    run("東京新大学野球連盟（new-tokyo-bbl.com）", fetch_shintokyo.main)
    run("中国地区大学野球連盟（cubf5589.com）", fetch_chugoku.main)
    run("阪神大学野球連盟（hanshin-bbl.com）", fetch_hanshin.main)


if __name__ == "__main__":
    main()
