#!/usr/bin/env python3
"""
WeChat Image Fit — 微信公众号图片自适应工具
将任意尺寸图片转为 2.35:1 比例，保证内容完整显示。
"""

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageDraw
import numpy as np


TARGET_RATIO = 2.35  # 微信公众号封面比例
DEFAULT_WIDTH = 900
DEFAULT_HEIGHT = 383  # 900 / 2.35 ≈ 383


def parse_ratio(ratio_str: str) -> float:
    """Parse ratio string like '2.35:1' or '16:9'."""
    parts = ratio_str.split(":")
    if len(parts) == 2:
        return float(parts[0]) / float(parts[1])
    return float(ratio_str)


def create_blur_background(img: Image.Image, canvas_w: int, canvas_h: int, blur_radius: int = 30) -> Image.Image:
    """Create a blurred version of the image as background canvas."""
    bg = img.copy()
    bg = bg.resize((canvas_w, canvas_h), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    # Darken slightly for better contrast
    from PIL import ImageEnhance
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.7)
    return bg


def create_solid_background(canvas_w: int, canvas_h: int, color: str = "#ffffff") -> Image.Image:
    """Create a solid color background canvas."""
    return Image.new("RGB", (canvas_w, canvas_h), color)


def create_gradient_background(img: Image.Image, canvas_w: int, canvas_h: int) -> Image.Image:
    """Create a gradient background derived from image edge colors."""
    # Sample colors from left and right edges
    img_small = img.resize((10, 10), Image.LANCZOS)
    pixels = np.array(img_small)

    left_color = pixels[:, 0, :3].mean(axis=0).astype(int)
    right_color = pixels[:, -1, :3].mean(axis=0).astype(int)

    # Create horizontal gradient
    gradient = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    for x in range(canvas_w):
        t = x / max(canvas_w - 1, 1)
        gradient[:, x] = (left_color * (1 - t) + right_color * t).astype(np.uint8)

    return Image.fromarray(gradient)


def smart_crop(img: Image.Image, canvas_w: int, canvas_h: int) -> Image.Image:
    """Crop to target ratio using center-weighted approach."""
    img_w, img_h = img.size
    target_ratio = canvas_w / canvas_h
    current_ratio = img_w / img_h

    if current_ratio > target_ratio:
        # Image is wider — crop width
        new_w = int(img_h * target_ratio)
        left = (img_w - new_w) // 2
        cropped = img.crop((left, 0, left + new_w, img_h))
    else:
        # Image is taller — crop height
        new_h = int(img_w / target_ratio)
        top = (img_h - new_h) // 3  # Bias toward top (faces are usually upper)
        cropped = img.crop((0, top, img_w, top + new_h))

    return cropped.resize((canvas_w, canvas_h), Image.LANCZOS)


def fit_image(
    img: Image.Image,
    canvas_w: int,
    canvas_h: int,
    mode: str = "blur",
    bg_color: str = "#ffffff",
    blur_radius: int = 30,
) -> Image.Image:
    """Fit image onto canvas with specified mode."""
    img_w, img_h = img.size
    target_ratio = canvas_w / canvas_h
    current_ratio = img_w / img_h

    # If already close to target ratio, just resize
    if abs(current_ratio - target_ratio) < 0.05:
        return img.resize((canvas_w, canvas_h), Image.LANCZOS)

    # Smart crop mode
    if mode == "crop":
        return smart_crop(img, canvas_w, canvas_h)

    # For other modes: create background, then overlay original
    if mode == "blur":
        canvas = create_blur_background(img, canvas_w, canvas_h, blur_radius)
    elif mode == "solid":
        canvas = create_solid_background(canvas_w, canvas_h, bg_color)
    elif mode == "gradient":
        canvas = create_gradient_background(img, canvas_w, canvas_h)
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Calculate size to fit original image within canvas (contain)
    scale = min(canvas_w / img_w, canvas_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)

    # Resize original
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Center on canvas
    x_offset = (canvas_w - new_w) // 2
    y_offset = (canvas_h - new_h) // 2

    # Handle transparency
    if resized.mode == "RGBA":
        canvas.paste(resized, (x_offset, y_offset), resized)
    else:
        canvas.paste(resized, (x_offset, y_offset))

    return canvas


def get_output_path(input_path: str, output_path: str | None) -> str:
    """Generate output path if not specified."""
    if output_path:
        return output_path
    p = Path(input_path)
    return str(p.parent / f"{p.stem}_wechat{p.suffix}")


def process_image(
    input_path: str,
    output_path: str | None = None,
    mode: str = "blur",
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    bg_color: str = "#ffffff",
    blur_radius: int = 30,
    quality: int = 95,
) -> str:
    """Process a single image and return output path."""
    img = Image.open(input_path)

    # Convert to RGB if needed (handle RGBA, P mode, etc.)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    result = fit_image(img, width, height, mode, bg_color, blur_radius)

    out_path = get_output_path(input_path, output_path)

    # Ensure output is RGB for JPEG
    if out_path.lower().endswith((".jpg", ".jpeg")) and result.mode == "RGBA":
        result = result.convert("RGB")

    # Save
    save_kwargs = {}
    if out_path.lower().endswith((".jpg", ".jpeg")):
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif out_path.lower().endswith(".png"):
        save_kwargs["optimize"] = True

    result.save(out_path, **save_kwargs)

    img_w, img_h = Image.open(input_path).size
    print(f"✓ {input_path} ({img_w}×{img_h}) → {out_path} ({width}×{height}) [{mode}]")
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="WeChat Image Fit — 将任意图片转为微信公众号 2.35:1 封面比例"
    )
    parser.add_argument("input", nargs="+", help="输入图片路径")
    parser.add_argument("-o", "--output", help="输出路径（单文件时）")
    parser.add_argument(
        "--mode",
        choices=["blur", "solid", "gradient", "crop"],
        default="blur",
        help="填充模式 (default: blur)",
    )
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help=f"输出宽度 (default: {DEFAULT_WIDTH})")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help=f"输出高度 (default: {DEFAULT_HEIGHT})")
    parser.add_argument("--ratio", help="目标比例，如 2.35:1 或 16:9（覆盖 width/height）")
    parser.add_argument("--bg-color", default="#ffffff", help="solid 模式背景色 (default: #ffffff)")
    parser.add_argument("--blur-radius", type=int, default=30, help="blur 模式模糊半径 (default: 30)")
    parser.add_argument("--quality", type=int, default=95, help="JPEG 输出质量 (default: 95)")

    args = parser.parse_args()

    # Handle ratio override
    width, height = args.width, args.height
    if args.ratio:
        ratio = parse_ratio(args.ratio)
        height = int(width / ratio)
        print(f"Using ratio {args.ratio} → {width}×{height}")

    # Process files
    results = []
    for i, input_path in enumerate(args.input):
        if not os.path.exists(input_path):
            print(f"✗ File not found: {input_path}", file=sys.stderr)
            continue

        out = args.output if (args.output and len(args.input) == 1) else None
        out_path = process_image(
            input_path=input_path,
            output_path=out,
            mode=args.mode,
            width=width,
            height=height,
            bg_color=args.bg_color,
            blur_radius=args.blur_radius,
            quality=args.quality,
        )
        results.append(out_path)

    if results:
        print(f"\n完成！共处理 {len(results)} 张图片。")
    else:
        print("没有成功处理任何图片。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
