"""
nonebot_plugin_nbnhhsh.parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
文本预处理与翻译结果结构化解析。
"""

from __future__ import annotations

import re
from typing import Any
from dataclasses import field, dataclass

# ── 文本预处理 ──────────────────────────────────────────────────────────────


def extract_abbrs(text: str) -> str:
    """提取文本中的有效缩写并用逗号拼接。

    等价于原 JS：``text.match(/[a-z0-9]{2,}/ig).join(',')``。

    Args:
        text: 输入文本。

    Returns:
        提取后的缩写字符串。若未命中，则返回空字符串。
    """
    return ",".join(re.findall(r"[a-zA-Z0-9]{2,}", text))


def has_abbr(text: str) -> bool:
    """判断文本是否包含至少一个有效缩写。

    Args:
        text: 输入文本。

    Returns:
        是否命中至少一个长度不小于 2 的字母或数字串。
    """
    return bool(re.search(r"[a-zA-Z0-9]{2,}", text))


# ── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class Translation:
    """单条翻译。

    Attributes:
        text: 翻译主体。
        note: 可选的来源或备注信息。
    """

    text: str
    note: str | None = None

    def __str__(self) -> str:
        return f"{self.text}（{self.note}）" if self.note else self.text


@dataclass
class Tag:
    """一个缩写词条及其翻译结果。

    Attributes:
        name: 缩写原文。
        translations: 已录入的翻译列表。
        inputting: 可能的候选释义列表。
    """

    name: str
    translations: list[Translation] = field(default_factory=list)
    inputting: list[str] = field(default_factory=list)

    @property
    def has_translation(self) -> bool:
        return bool(self.translations)

    def format(self) -> str:
        """返回适合在聊天中展示的字符串。

        Returns:
            单个词条的展示文本。
        """
        if self.has_translation:
            trans_str = "、 ".join(str(t) for t in self.translations)
            return f"[{self.name}] {trans_str}"
        hint = f"可能是：{'、'.join(self.inputting)}" if self.inputting else ""
        return f"[{self.name}] 暂未录入\n{hint}"


# ── 解析函数 ────────────────────────────────────────────────────────────────


def _parse_translation(raw: str) -> Translation:
    m = re.match(r"^(.+?)([（(](.+?)[）)])?$", raw.strip())
    if m:
        return Translation(text=m.group(1), note=m.group(3))
    return Translation(text=raw)


def parse_tags(data: list[dict[str, Any]]) -> list[Tag]:
    """将 API 原始列表解析为词条列表。

    Args:
        data: API 返回的原始词条列表。

    Returns:
        解析后的 :class:`Tag` 列表。
    """
    result = []
    for item in data:
        name = item.get("name", "")
        inputting = item.get("inputting") or []
        raw_trans = item.get("trans")
        if raw_trans:
            # trans 有值：有人工录入的翻译
            translations: list[Translation] = [_parse_translation(t) for t in raw_trans]
        else:
            # trans 不存在或为空列表：暂未录入，fallback 到 inputting
            translations = []
        result.append(Tag(name=name, translations=translations, inputting=inputting))
    return result
