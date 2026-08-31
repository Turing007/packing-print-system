# -*- coding: utf-8 -*-
"""
生成 装箱打印系统 图标 (icon.ico)。

设计原则：
1. 正面 2D 剪影为主，小尺寸下不糊
2. 主体（箱子）留一圈呼吸空间，不贴边
3. 配色克制：深蓝底 + 牛皮纸色箱 + 白底黑条码标签
4. 条形码作为视觉焦点，居中，模拟真实运单
5. 顶面用窄横带表示"已封箱"即可，不画 3D
"""

import os
from PIL import Image, ImageDraw

# ============== 配色（克制 / 企业风） ==============
BG          = (28, 64, 110)    # 深海军蓝
BG_LIGHT    = (45, 88, 140)    # 蓝渐变高光端
BOX_FILL    = (180, 142, 92)   # 牛皮纸色
BOX_FILL_DK = (148, 112, 70)   # 牛皮纸色（暗）
BAND_BLUE   = (60, 110, 170)   # 封箱带深蓝
TAG_FILL    = (252, 252, 250)  # 标签近白
TAG_LINE    = (28, 28, 28)     # 条码深黑


def draw_icon(size: int) -> Image.Image:
    """绘制一个 size×size 的图标（高分辨率画再缩放）

    自适应策略：
    - size >= 64: 完整版（条码 + 数字 SKU）
    - size < 64:  简化版（条码只画粗条，不画数字）— 小尺寸可读
    """
    simplified = size < 64
    SCALE = 8
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ---- 背景：圆角矩形 + 自上向下渐变 ----
    pad = int(big * 0.06)
    bg_layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_layer)
    bg_draw.rounded_rectangle(
        (0, 0, big - 1, big - 1),
        radius=int(big * 0.18),
        fill=BG_LIGHT,
    )
    # 用一个全屏蓝色画 + 渐变 mask 模拟
    gradient = Image.new("RGB", (1, big))
    for y in range(big):
        t = y / big
        r = int(BG[0] * (1 - t) + BG_LIGHT[0] * t)
        g = int(BG[1] * (1 - t) + BG_LIGHT[1] * t)
        b = int(BG[2] * (1 - t) + BG_LIGHT[2] * t)
        gradient.putpixel((0, y), (r, g, b))
    gradient = gradient.resize((big, big))
    # 把渐变贴进圆角蒙版
    bg_mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(bg_mask).rounded_rectangle(
        (0, 0, big - 1, big - 1),
        radius=int(big * 0.18),
        fill=255,
    )
    img.paste(gradient, (0, 0), bg_mask)

    # 重画 draw（img 经过 paste 后 draw 还能用）
    draw = ImageDraw.Draw(img)

    # ---- 箱子（正面 2D）----
    # 留一圈呼吸空间
    box_left   = int(big * 0.16)
    box_right  = int(big * 0.84)
    box_top    = int(big * 0.27)
    box_bottom = int(big * 0.88)

    # 阴影（轻微偏移，让主体从背景浮起）
    shadow_off = int(big * 0.012)
    shadow_layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    sd.rounded_rectangle(
        (box_left + shadow_off, box_top + shadow_off,
         box_right + shadow_off, box_bottom + shadow_off),
        radius=int(big * 0.025),
        fill=(0, 0, 0, 90),
    )
    img.alpha_composite(shadow_layer)

    # 箱子主体（圆角矩形）
    draw.rounded_rectangle(
        (box_left, box_top, box_right, box_bottom),
        radius=int(big * 0.025),
        fill=BOX_FILL,
        outline=BOX_FILL_DK,
        width=max(1, int(big * 0.006)),
    )

    # ---- 顶面（窄横带 + 简单立体暗示）----
    # 不画完整 3D 透视，只用一条窄横带表示"封箱顶面"，避免小尺寸糊
    band_h = int(big * 0.04)
    band_y = box_top + int(big * 0.015)
    draw.rectangle(
        (box_left, band_y, box_right, band_y + band_h),
        fill=BOX_FILL_DK,
    )
    # 顶面中央再叠一条亮色（暗示胶带）
    tape_h = int(big * 0.018)
    tape_y = band_y + band_h // 2 - tape_h // 2
    draw.rectangle(
        (box_left, tape_y, box_right, tape_y + tape_h),
        fill=BAND_BLUE,
    )

    # ---- 标签（白色，贴在箱子正面中央偏下，让出封箱带）----
    tag_w = int(big * 0.52)
    tag_h = int(big * 0.30)
    tag_x = box_left + (box_right - box_left) // 2 - tag_w // 2
    tag_y = box_top + (box_bottom - box_top) // 2 - int(big * 0.04)  # 略偏上，留底缘

    # 标签微圆角（与图标风格统一）
    tag_radius = int(big * 0.012)
    draw.rounded_rectangle(
        (tag_x, tag_y, tag_x + tag_w, tag_y + tag_h),
        radius=tag_radius,
        fill=TAG_FILL,
        outline=(180, 180, 180),
        width=max(1, int(big * 0.003)),
    )

    # ---- 条码（在标签上，居中）----
    bc_top = tag_y + int(tag_h * 0.20)
    # 完整版留 25% 给数字；简化版不画数字，条码占更大区域
    if simplified:
        bc_bottom = tag_y + int(tag_h * 0.78)
    else:
        bc_bottom = tag_y + int(tag_h * 0.65)
    bc_pad_x = int(tag_w * 0.10)
    bc_x0 = tag_x + bc_pad_x
    bc_x1 = tag_x + tag_w - bc_pad_x
    bc_w = bc_x1 - bc_x0

    if simplified:
        # 简化版：5 根粗条，黑白分明，去掉所有数字
        bars = [
            ("thick", 0.18),
            ("thin",  0.06),
            ("thick", 0.24),
            ("thin",  0.08),
            ("thick", 0.20),
        ]
        gap = 0.06
    else:
        bars = [
            ("thick",  0.04),
            ("thin",   0.015),
            ("thick",  0.06),
            ("thin",   0.02),
            ("thick",  0.035),
            ("thin",   0.012),
            ("thick",  0.05),
            ("thin",   0.025),
            ("thick",  0.04),
            ("thin",   0.018),
            ("thick",  0.06),
            ("thin",   0.015),
            ("thick",  0.035),
        ]
        gap = 0.018
    total_ratio = sum(w for _, w in bars) + gap * (len(bars) - 1)
    x_cursor = bc_x0
    for kind, w_ratio in bars:
        bar_w = int(bc_w * w_ratio / total_ratio)
        draw.rectangle(
            (x_cursor, bc_top, x_cursor + bar_w, bc_bottom),
            fill=TAG_LINE,
        )
        x_cursor += bar_w + int(bc_w * gap / total_ratio)

    # 数字（只有完整版才画）
    if not simplified:
        num_y = bc_bottom + int(big * 0.018)
        num_text = "8 901234 567890"
        font_size = max(int(big * 0.045), 18)
        try:
            from PIL import ImageFont as IF
            font = IF.truetype("consola.ttf", font_size)
        except Exception:
            try:
                from PIL import ImageFont as IF
                font = IF.truetype("consolab.ttf", font_size)
            except Exception:
                try:
                    from PIL import ImageFont as IF
                    font = IF.truetype("courbd.ttf", font_size)
                except Exception:
                    font = ImageFont.load_default()
        try:
            bbox = draw.textbbox((0, 0), num_text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w, text_h = font_size * len(num_text) // 2, font_size
        text_x = tag_x + (tag_w - text_w) // 2
        draw.text((text_x, num_y), num_text, font=font, fill=TAG_LINE)

    # ---- 顶部小印记：极简 "P"（品牌符号，放箱子左上角）----
    # 用一个深蓝小方块 + 白色"扣" 暗示打印输出
    mark_size = int(big * 0.05)
    mark_x = box_left + int(big * 0.03)
    mark_y = box_top + int(big * 0.03)
    # 跳过这层，保持简洁——上一版的左上白点被批评多余

    # 缩回目标尺寸（高质缩放）
    return img.resize((size, size), Image.LANCZOS)


def main():
    sizes = [256, 128, 64, 48, 32, 16]
    imgs = [draw_icon(s) for s in sizes]

    out = "icon.ico"
    imgs[0].save(
        out,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=imgs[1:],
    )
    print(f"图标已生成: {out} ({os.path.getsize(out)/1024:.1f} KB, 尺寸: {sizes})")

    # 预览
    imgs[0].save("icon_preview.png", format="PNG")
    # 同时预览小尺寸（看 32/16 表现）
    Image.new("RGBA", (256 * 3 + 40, 256 + 20), (240, 240, 240, 255)).save("icon_sizes.png")
    canvas = Image.open("icon_sizes.png")
    canvas.paste(imgs[1], (10, 10))     # 128
    canvas.paste(imgs[2].resize((128, 128), Image.LANCZOS), (138, 10))
    canvas.paste(imgs[3].resize((128, 128), Image.LANCZOS), (266, 10))
    canvas.save("icon_sizes.png")
    print("预览: icon_preview.png (256), icon_sizes.png (128+64+48)")


if __name__ == "__main__":
    main()