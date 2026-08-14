# -*- coding: utf-8 -*-
"""東京六大学野球連盟・東都大学野球連盟の取得スクリプトで共有するヘルパー。

大学野球は「勝ち点制」（同一カードで2先勝した方が勝ち点1）という独自ルールのため、
順位表は自前集計せず、各連盟公式サイトが計算済みの順位表をそのまま取得する
（ラグビー版のcompute_standingsに相当するロジックはここには存在しない）。
"""
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; BaseballManiaBot/1.0)"

TAG_RE = re.compile(r"<[^>]+>")
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL)


def fetch(url: str, retries: int = 2, encoding: str = "utf-8") -> str:
    """礼儀正しく取得する: 失敗時は1回だけリトライし、成功・失敗に関わらず
    呼び出しごとに1秒あける（連盟サイトへの負荷軽減）。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                raw = res.read()
            return raw.decode(encoding, errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt == retries - 1:
                break
            print(f"[warn] fetch failed ({e}), retrying in 5s... ({url})", file=sys.stderr)
            time.sleep(5)
        finally:
            time.sleep(1)
    raise last_err


def strip_tags(s: str) -> str:
    return TAG_RE.sub("", s).replace("&nbsp;", "").replace("　", "").strip()


def cells_of(row_html: str) -> list[str]:
    """<tr>...</tr> の中身から入れ子のないシンプルな<td>セルをテキストとして
    順番に取り出す（星取表のように<td>の中に<table>が無い行専用。
    日程表のように<td>の中に<table>が入れ子になっている行には使えない）。"""
    return [strip_tags(c) for c in TD_RE.findall(row_html)]


def normalize_pct(s: str) -> str:
    """勝率表記を「.714」形式に揃える（連盟によって"0.714"/".714"/"-"が混在）。"""
    s = s.strip()
    if not s or s == "-":
        return "-"
    if s.startswith("0."):
        return s[1:]
    return s


def to_int(s: str, default: int = 0) -> int:
    s = s.strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else default
