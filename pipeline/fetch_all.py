# -*- coding: utf-8 -*-
"""東京六大学野球連盟・東都大学野球連盟の2連盟を順番に取得する。"""
import fetch_big6
import fetch_big6_players
import fetch_tohto


def main() -> None:
    print("=== 東京六大学野球連盟（big6.gr.jp）===")
    fetch_big6.main()
    print("=== 東京六大学野球連盟 個人成績（big6.gr.jp）===")
    fetch_big6_players.main()
    print("=== 東都大学野球連盟（tohto-bbl.com）===")
    fetch_tohto.main()


if __name__ == "__main__":
    main()
