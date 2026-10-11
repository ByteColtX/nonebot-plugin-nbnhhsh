"""从完整字体里裁一个小子集，供测试使用。

测试环境（CI / 无中文字体的机器）不一定有中文字体，而渲染测试必须真画一次图，
所以把测试用到的那几十个字裁成一份 ~100KB 的子集放进 ``tests/assets/``。

用法::

    uv run --with fonttools python tests/assets/make_test_font.py <完整字体路径>

例如::

    uv run --with fonttools python tests/assets/make_test_font.py ~/NotoSansSC.ttf
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools import subset  # type: ignore[import-untyped]

# 测试里会画到的所有字符（含标点、拉丁字母与数字）
CHARS = (
    "能不能好好说话？数据源：神奇的海螺"
    "未找到翻译结果。暂可能是"
    "永远的神单身、你我他她它"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789 []"
)


def main() -> None:
    """生成 ``tests/assets/test-font.ttf``。"""
    if len(sys.argv) < 2:
        raise SystemExit("用法：python make_test_font.py <完整字体路径>")
    source = Path(sys.argv[1]).expanduser()
    target = Path(__file__).resolve().parent / "test-font.ttf"

    options = subset.Options()
    options.layout_features = ["*"]
    options.drop_tables += ["DSIG"]
    font = subset.load_font(str(source), options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text=CHARS)
    subsetter.subset(font)
    subset.save_font(font, str(target), options)
    print(f"已生成 {target}（{target.stat().st_size / 1024:.0f} KB）")  # noqa: T201


if __name__ == "__main__":
    main()
