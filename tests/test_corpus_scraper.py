"""青空文庫スクレイパー(src/corpus/aozora_scraper.py)のパース・クリーニング関数の単体テスト。

実際のネットワークには接続せず、Aozora Bunko風のfixture HTML文字列を直接
パース関数に渡してロジックのみを検証する。
"""
from src.corpus.aozora_scraper import (
    _clean_body_text,
    _decode_html,
    _parse_author_index,
    _parse_text_url,
    _parse_work_text,
)

AUTHOR_INDEX_HTML = """
<html><body>
<ol>
<li><a href="../cards/000148/card789.html">吾輩は猫である</a></li>
<li><a href="../cards/000148/card752.html">坊っちゃん</a></li>
<li><a href="./person148.html">作家情報</a></li>
</ol>
</body></html>
"""

CARD_PAGE_HTML = """
<html><body>
<table>
<tr><td>テキストファイル</td><td><a href="./files/789.html">789.html</a></td></tr>
<tr><td>XHTML版</td><td><a href="./files/789_14547.html">789_14547.html</a></td></tr>
</table>
</body></html>
"""

CARD_PAGE_HTML_NO_LINKS = "<html><body><p>本文なし</p></body></html>"

WORK_TEXT_HTML = """
<html><body>
<div class="main_text">
-------------------------------------------------------
【テキスト中に現れる記号について】
-------------------------------------------------------
<p>
<ruby><rb>吾輩</rb><rp>(</rp><rt>わがはい</rt><rp>)</rp></ruby>は猫である。
名前はまだ｜無い《ない》。
どこで生れたかとんと見当《けんとう》がつかぬ。［＃改ページ］
</p>
</div>
<div class="bibliographical_information">
底本：「吾輩は猫である」新潮文庫
</div>
</body></html>
"""


def test_parse_author_index_extracts_title_and_url():
    results = _parse_author_index(AUTHOR_INDEX_HTML)
    titles = [title for title, _ in results]
    assert "吾輩は猫である" in titles
    assert "坊っちゃん" in titles
    urls = dict(results)
    assert urls["吾輩は猫である"].endswith("/cards/000148/card789.html")


def test_parse_text_url_prefers_xhtml_labeled_link():
    url = _parse_text_url(CARD_PAGE_HTML, "https://www.aozora.gr.jp/cards/000148/card789.html")
    assert url is not None
    assert url.endswith("789_14547.html")


def test_parse_text_url_returns_none_when_no_candidates():
    assert _parse_text_url(CARD_PAGE_HTML_NO_LINKS, "https://example.com/card1.html") is None


def test_parse_work_text_strips_ruby_and_boilerplate():
    text = _parse_work_text(WORK_TEXT_HTML)

    assert "わがはい" not in text  # <rt>のふりがなは除去される
    assert "吾輩は猫である" in text
    assert "無い" in text and "ない" not in text.replace("無い", "")  # ｜...《...》のルビは除去
    assert "けんとう" not in text  # 送り仮名なしルビの除去
    assert "［＃" not in text  # 編集注記の除去
    assert "底本" not in text  # 書誌ボイラープレートの除去
    assert "-----" not in text  # 注記凡例ブロックの除去


def test_clean_body_text_removes_legend_block_and_annotations():
    dashes = "-" * 20
    raw = f"{dashes}\n注記\n{dashes}\n本文｜漢字《かんじ》です。［＃ここまで］\n底本：テスト"
    cleaned = _clean_body_text(raw)
    assert "-----" not in cleaned
    assert "漢字" in cleaned
    assert "かんじ" not in cleaned
    assert "［＃" not in cleaned
    assert "底本" not in cleaned


def test_decode_html_respects_meta_charset_shift_jis():
    html = '<html><head><meta charset="Shift_JIS"></head><body>日本語テスト</body></html>'
    content = html.encode("shift_jis")
    decoded = _decode_html(content)
    assert "日本語テスト" in decoded


def test_decode_html_falls_back_for_utf8_without_meta():
    html = "<html><body>日本語テスト</body></html>"
    content = html.encode("utf-8")
    decoded = _decode_html(content)
    assert "日本語テスト" in decoded
