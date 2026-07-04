"""青空文庫(Aozora Bunko)から作品を礼儀正しく取得するスクレイパー。

サイト全体は17,771作品にのぼるため、厳選した代表作(src/corpus/curated_list.py)
のみを対象とする。各リクエストの後に必ず待機し、独自のUser-Agentを名乗ることで、
ボランティア運営の小規模サーバーへの負荷を抑える(robots.txtにDisallowは無いが、
大手クローラー以外への配慮として自主的にポライトネスを設定している)。
"""
from __future__ import annotations

import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup
from bs4.dammit import UnicodeDammit

USER_AGENT = "shisui-literary-corpus-bot/1.0 (personal local research assistant; local use only)"
REQUEST_TIMEOUT = 15
POLITE_DELAY_SECONDS = 2.0
BASE_URL = "https://www.aozora.gr.jp"


def _polite_fetch(url: str) -> bytes:
    """礼儀正しくURLを取得する(独自UA・タイムアウト・リクエスト後に必ず待機)。"""
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.content
    finally:
        time.sleep(POLITE_DELAY_SECONDS)


def _decode_html(content: bytes) -> str:
    """meta charset宣言 → bs4の自動判定、の順でHTMLバイト列をデコードする。"""
    head = content[:2000].decode("latin1", errors="ignore")
    match = re.search(r'charset=["\']?([\w-]+)', head, re.IGNORECASE)
    if match:
        try:
            return content.decode(match.group(1), errors="strict")
        except (LookupError, UnicodeDecodeError):
            pass
    dammit = UnicodeDammit(content)
    if dammit.unicode_markup is not None:
        return dammit.unicode_markup
    return content.decode("utf-8", errors="replace")


def _parse_author_index(html: str) -> list[tuple[str, str]]:
    """著者別作品リストのHTMLから (タイトル, 図書カードURL) のリストを抽出する。"""
    soup = BeautifulSoup(html, features="html.parser")
    results = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if re.search(r"/cards/\d+/card\d+\.html$", href):
            title = link.get_text(strip=True)
            if title:
                results.append((title, urllib.parse.urljoin(BASE_URL, href)))
    return results


def _parse_all_authors(html: str) -> list[tuple[str, str]]:
    """全作家一覧ページのHTMLから (person_id, 作家名) のリストを抽出する。"""
    soup = BeautifulSoup(html, features="html.parser")
    results = []
    seen_ids: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r"person(\d+)\.html", href)
        if not match:
            continue
        person_id = match.group(1)
        if person_id in seen_ids:
            continue
        author = link.get_text(strip=True)
        if not author:
            continue
        seen_ids.add(person_id)
        results.append((person_id, author))
    return results


def fetch_all_authors() -> list[tuple[str, str]]:
    """青空文庫の全作家一覧ページを取得し、(person_id, 作家名) のリストを返す。

    2000名を超える全作家が対象(厳選作家のcurated_list.pyとは別の、
    青空文庫全体を少しずつ読み進める機能で使う)。
    """
    url = f"{BASE_URL}/index_pages/person_all.html"
    html = _decode_html(_polite_fetch(url))
    return _parse_all_authors(html)


def fetch_author_index(person_id: str) -> list[tuple[str, str]]:
    """著者ページを取得し、(タイトル, 図書カードURL) のリストを返す。"""
    url = f"{BASE_URL}/index_pages/person{person_id}.html"
    html = _decode_html(_polite_fetch(url))
    return _parse_author_index(html)


def _parse_text_url(card_html: str, card_url: str) -> str | None:
    """図書カードHTMLから、本文(XHTML版優先)へのURLを解決する。候補が無ければNone。"""
    soup = BeautifulSoup(card_html, features="html.parser")
    candidates: list[tuple[str, bool]] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if re.search(r"files/.*\.html$", href):
            container = link.find_parent("tr") or link.find_parent("td") or link
            label_text = container.get_text()
            candidates.append((href, "XHTML" in label_text))

    if not candidates:
        return None

    for href, is_xhtml in candidates:
        if is_xhtml:
            return urllib.parse.urljoin(card_url, href)
    return urllib.parse.urljoin(card_url, candidates[0][0])


def resolve_text_url(card_url: str) -> str | None:
    """図書カードページを取得し、本文ページのURLを返す(見つからなければNone)。"""
    html = _decode_html(_polite_fetch(card_url))
    return _parse_text_url(html, card_url)


_RUBY_WITH_BASE = re.compile(r"｜(.+?)《.*?》")
_RUBY_TRAILING = re.compile(r"(?<=[一-龠々ヶ])《.*?》")
_RUBY_CATCHALL = re.compile(r"《.*?》")
_ANNOTATION = re.compile(r"※?［＃.*?］")
_NOTATION_LEGEND_BLOCK = re.compile(r"-{10,}[\s\S]*?-{10,}")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def _clean_body_text(text: str) -> str:
    """ルビ記法・編集注記・書誌ボイラープレートを取り除き、読みやすい本文のみ残す。"""
    text = _NOTATION_LEGEND_BLOCK.sub("", text)
    text = _RUBY_WITH_BASE.sub(r"\1", text)
    text = _RUBY_TRAILING.sub("", text)
    text = _RUBY_CATCHALL.sub("", text)
    text = _ANNOTATION.sub("", text)

    footer_index = text.find("底本：")
    if footer_index != -1:
        text = text[:footer_index]

    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def _parse_work_text(html: str) -> str:
    """本文ページのHTMLから、ルビ・注記・ボイラープレートを除いた本文テキストを返す。"""
    soup = BeautifulSoup(html, features="html.parser")

    for tag in soup.find_all(["rt", "rp"]):
        tag.decompose()

    main_text = soup.find("div", class_="main_text")
    body = main_text if main_text is not None else soup

    return _clean_body_text(body.get_text())


def fetch_work_text(text_url: str) -> str:
    """本文ページを取得し、クリーニング済みの本文テキストを返す。"""
    html = _decode_html(_polite_fetch(text_url))
    return _parse_work_text(html)
