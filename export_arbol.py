"""
Convierte un archivo .canvas de Obsidian en una imagen arbol.png para la
pagina web. Vuelve a correr este script cada vez que edites el arbol en
Obsidian, y luego corre agent.py para que la pagina se actualice.

Uso:
    python export_arbol.py
    python export_arbol.py --canvas "RUTA\\a\\tu\\archivo.canvas"
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

COLORS = {
    "1": "#e07a5f", "2": "#f2cc8f", "3": "#81b29a",
    "4": "#3d5a80", "5": "#98c1d9", "6": "#c9ada7",
}


def load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        lines.append(current)
    return lines


def export(canvas_path: Path, out_path: Path) -> None:
    data = json.loads(canvas_path.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in data.get("nodes", [])}
    edges = data.get("edges", [])
    if not nodes:
        raise SystemExit(f"El canvas '{canvas_path}' todavia no tiene nodos.")

    margin = 40
    max_x = max(n["x"] + n["width"] for n in nodes.values()) + margin
    max_y = max(n["y"] + n["height"] for n in nodes.values()) + margin

    img = Image.new("RGB", (int(max_x), int(max_y)), "white")
    draw = ImageDraw.Draw(img)
    font = load_font(15)

    for edge in edges:
        a = nodes.get(edge["fromNode"])
        b = nodes.get(edge["toNode"])
        if not a or not b:
            continue
        ax, ay = a["x"] + a["width"] / 2, a["y"] + a["height"]
        bx, by = b["x"] + b["width"] / 2, b["y"]
        draw.line([(ax, ay), (bx, by)], fill="#888888", width=2)

    for node in nodes.values():
        x, y, w, h = node["x"], node["y"], node["width"], node["height"]
        fill = COLORS.get(str(node.get("color", "")), "#eeeeee")
        draw.rounded_rectangle([x, y, x + w, y + h], radius=10,
                                fill=fill, outline="#333333", width=2)
        text = node.get("text", "").replace("#", "").strip()
        lines = wrap_text(draw, text, font, w - 20)
        line_h = 18
        total_h = len(lines) * line_h
        ty = y + (h - total_h) / 2
        for line in lines:
            tw = draw.textlength(line, font=font)
            draw.text((x + (w - tw) / 2, ty), line, fill="#111111", font=font)
            ty += line_h

    img.save(out_path)
    print(f"Arbol exportado a {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canvas", default=os.getenv("OBSIDIAN_CANVAS_PATH", ""))
    parser.add_argument("--out", default=str(ROOT / "arbol.png"))
    args = parser.parse_args()

    if not args.canvas:
        raise SystemExit(
            "Define OBSIDIAN_CANVAS_PATH en .env (ruta a tu archivo .canvas) "
            "o pasa --canvas \"RUTA\"."
        )
    export(Path(args.canvas), Path(args.out))


if __name__ == "__main__":
    main()
