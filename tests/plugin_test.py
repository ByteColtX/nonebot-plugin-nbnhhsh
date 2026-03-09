"""
tests/test_plugin.py
~~~~~~~~~~~~~~~~~~~~
nonebot-plugin-nbnhhsh 单元测试
"""

from __future__ import annotations

import pytest

from nonebot_plugin_nbnhhsh.parser import (
    Tag, Translation,
    extract_abbrs, has_abbr, parse_tags,
)
from nonebot_plugin_nbnhhsh.core import format_result


# ── extract_abbrs ────────────────────────────────────────────────────────────

class TestExtractAbbrs:
    def test_basic(self):
        assert extract_abbrs("yyds nb！") == "yyds,nb"

    def test_mixed_text(self):
        assert extract_abbrs("今天 yyds，tfboys 真的 nb！") == "yyds,tfboys,nb"

    def test_single_char_ignored(self):
        assert extract_abbrs("a b c dd") == "dd"

    def test_numbers(self):
        assert extract_abbrs("b4 666 test") == "b4,666,test"

    def test_no_abbr(self):
        assert extract_abbrs("你好世界") == ""


# ── has_abbr ─────────────────────────────────────────────────────────────────

class TestHasAbbr:
    def test_true(self):
        assert has_abbr("yyds！") is True

    def test_false(self):
        assert has_abbr("你好世界！") is False

    def test_single_char(self):
        assert has_abbr("a") is False


# ── parse_tags ───────────────────────────────────────────────────────────────

class TestParseTags:
    def test_with_trans(self):
        """有 trans 字段且有值 → has_translation"""
        tags = parse_tags([{"name": "yyds", "trans": ["永远的神（网络流行语）", "永远滴神"]}])
        tag = tags[0]
        assert tag.name == "yyds"
        assert tag.has_translation
        assert tag.translations is not None
        assert tag.translations[0].text == "永远的神"
        assert tag.translations[0].note == "网络流行语"
        assert tag.translations[1].text == "永远滴神"
        assert tag.translations[1].note is None

    def test_no_trans_with_inputting(self):
        """无 trans 字段，有 inputting → 暂未录入"""
        tags = parse_tags([{"name": "hsdf", "inputting": ["还是地方"]}])
        tag = tags[0]
        assert not tag.has_translation
        assert tag.inputting == ["还是地方"]

    def test_empty_trans_with_inputting(self):
        """trans 为空列表，有 inputting → 暂未录入"""
        tags = parse_tags([{"name": "nb", "trans": [], "inputting": ["牛逼", "宁波"]}])
        tag = tags[0]
        assert not tag.has_translation
        assert tag.inputting == ["牛逼", "宁波"]

    def test_empty_inputting(self):
        """无 trans，inputting 为空 → 完全没信息"""
        tags = parse_tags([{"name": "hjjl", "inputting": []}])
        tag = tags[0]
        assert not tag.has_translation
        assert not tag.inputting

    def test_no_trans_no_inputting(self):
        """无 trans，无 inputting 字段 → 完全没信息"""
        tags = parse_tags([{"name": "xyz"}])
        tag = tags[0]
        assert not tag.has_translation
        assert not tag.inputting


# ── Tag.format ───────────────────────────────────────────────────────────────

class TestTagFormat:
    def test_with_translation(self):
        tag = Tag(
            name="yyds",
            translations=[Translation("永远的神", "网络流行语"), Translation("永远滴神")],
        )
        assert tag.format() == "[yyds] 永远的神（网络流行语）、 永远滴神"

    def test_inputting_with_hint(self):
        tag = Tag(name="nb", translations=[], inputting=["牛逼", "宁波"])
        result = tag.format()
        assert "暂未录入" in result
        assert "牛逼" in result
        assert "宁波" in result

    def test_inputting_empty(self):
        tag = Tag(name="hjjl", translations=[], inputting=[])
        assert tag.format().strip() == "[hjjl] 暂未录入"


# ── format_result ─────────────────────────────────────────────────────────────

class TestFormatResult:
    def test_with_translations(self):
        tags = parse_tags([{"name": "yyds", "trans": ["永远的神"]}])
        assert format_result(tags) == "[yyds] 永远的神"

    def test_filters_empty_tags(self):
        """无 trans 且 inputting 为空的词条应被过滤"""
        tags = parse_tags([{"name": "hjjl", "inputting": []}])
        assert format_result(tags) == "未找到翻译结果。"

    def test_shows_inputting(self):
        """有 inputting 的词条应显示"""
        tags = parse_tags([{"name": "hsdf", "inputting": ["还是地方"]}])
        assert "还是地方" in format_result(tags)

    def test_multiple_tags(self):
        tags = parse_tags([
            {"name": "yyds", "trans": ["永远的神"]},
            {"name": "nb",   "trans": ["牛逼"]},
        ])
        result = format_result(tags)
        assert "[yyds] 永远的神" in result
        assert "[nb] 牛逼" in result

    def test_empty(self):
        assert format_result([]) == "未找到翻译结果。"