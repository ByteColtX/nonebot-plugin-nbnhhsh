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
    """
    提取文本中所有长度 ≥ 2 的字母/数字串，用逗号拼接。

    等价于原 JS：``text.match(/[a-z0-9]{2,}/ig).join(',')``
    """
    return ",".join(re.findall(r"[a-zA-Z0-9]{2,}", text))


def has_abbr(text: str) -> bool:
    """判断文本是否包含至少一个有效缩写。"""
    return bool(re.search(r"[a-zA-Z0-9]{2,}", text))


# ── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class Translation:
    """单条翻译，拆分主体与括号内来源注释。"""

    text: str
    note: str | None = None

    def __str__(self) -> str:
        return f"{self.text}（{self.note}）" if self.note else self.text


@dataclass
class Tag:
    """一个缩写词条及其翻译结果。"""

    name: str
    translations: list[Translation] | None  # None = 明确无对应
    inputting: list[str] = field(default_factory=list)

    @property
    def has_translation(self) -> bool:
        return bool(self.translations)

    def format(self) -> str:
        """返回适合在聊天中展示的字符串。"""
        if self.has_translation:
            trans_str = "、 ".join(str(t) for t in self.translations)  # type: ignore[union-attr]
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
    """将 API 原始列表解析为 :class:`Tag` 列表。"""
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
