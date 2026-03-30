"""
nonebot_plugin_nbnhhsh.render
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
使用 nonebot-plugin-htmlkit 将文字渲染为图片。
"""

from __future__ import annotations

from nonebot import require

require("nonebot_plugin_htmlkit")

from nonebot_plugin_htmlkit import html_to_pic


async def text_to_image(text: str) -> bytes:
    """
    将文本渲染为 PNG 图片，返回字节数据。

    :param text: 要渲染的文本
    :returns:    PNG 格式的图片字节
    """
    # 解析文本格式：[缩写] 翻译1、翻译2、翻译3...
    lines = text.strip().split('\n')
    html_parts = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('[') and '] ' in line:
            # 提取缩写和翻译
            abbr_part, meaning_part = line.split('] ', 1)
            abbr = abbr_part[1:]  # 去掉 [
            
            # 分割翻译项
            meanings = [m.strip() for m in meaning_part.split('、') if m.strip()]
            
            # 构建HTML
            html_parts.append(f'<div class="abbr">{abbr}</div>')
            if meanings:
                meaning_items = ''.join(
                    f'<div class="meaning-item">{meaning}</div>'
                    for meaning in meanings
                )
                html_parts.append(f'<div class="meaning-list">{meaning_items}</div>')
        else:
            # 非标准格式，直接显示
            html_parts.append(f'<div class="text">{line}</div>')
    
    html_content = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 24px;
  background: #fff8f1;
  font-family: 'Noto Sans CJK SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #2b2b2b;
}}
.panel {{
  background: #fffdf9;
  border: 2px solid #ffd7a8;
  border-radius: 20px;
  box-shadow: 0 10px 24px rgba(180, 118, 33, 0.10);
  padding: 18px;
}}
.heading {{
  font-size: 21px;
  font-weight: 800;
  color: #b45309;
  margin-bottom: 6px;
}}
.desc {{
  font-size: 12px;
  color: #92400e;
  margin-bottom: 14px;
}}
.abbr {{
  font-size: 24px;
  font-weight: 800;
  color: #c2410c;
  margin-bottom: 12px;
  letter-spacing: 1px;
}}
.meaning-list {{
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}}
.meaning-item {{
  padding: 10px 16px;
  background: transparent;
  border-radius: 16px;
  font-size: 15px;
  font-weight: 500;
  color: #92400e;
}}
.text {{
  font-size: 15px;
  line-height: 1.6;
  color: #2b2b2b;
  margin-bottom: 12px;
}}
.note {{
  margin-top: 16px;
  font-size: 11px;
  color: #a16207;
}}
</style>
</head>
<body>
  <div class="panel">
    <div class="heading">缩写翻译</div>
    <div class="desc">NBNHHSH 缩写翻译结果</div>
    {''.join(html_parts)}
  </div>
</body>
</html>"""
    
    return await html_to_pic(
        html_content,
        max_width=720,
        dpi=96.0,
        allow_refit=True,
        image_format="png"
    )