"""Gera o icone do DX Select no runner (nada de binario no repo).

Icone proprio, relacionado a funcao — pilha de fotos + check verde —
e nao o simbolo da DX Labs (regra dele: cada app com seu icone).
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets")
os.makedirs(OUT, exist_ok=True)


def build(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Tres fotos empilhadas, levemente deslocadas.
    for dx, dy, color in ((28, 44, "#9aa5b1"), (14, 30, "#5b7fa6"), (0, 16, "#ffffff")):
        x0, y0 = 44 + dx, 40 + dy
        x1, y1 = 168 + dx, 176 + dy
        d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=color,
                            outline="#1c2b3a", width=3)
        # "Paisagem" dentro da foto da frente.
        if color == "#ffffff":
            d.polygon([(x0 + 14, y1 - 14), (x0 + 52, y0 + 56),
                       (x0 + 84, y1 - 14)], fill="#7fb069")
            d.ellipse([x0 + 78, y0 + 18, x0 + 104, y0 + 44], fill="#f2b705")
    # Check verde em circulo, no canto.
    cx, cy, r = 188, 188, 52
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#1a7a3a", outline="white", width=5)
    d.line([(cx - 28, cy + 2), (cx - 8, cy + 24), (cx + 30, cy - 26)],
           fill="white", width=11, joint="curve")
    return img


if __name__ == "__main__":
    icon = build(256)
    icon.save(os.path.join(OUT, "icon.png"))
    icon.save(os.path.join(OUT, "icon.ico"), sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print("assets/icon.png + assets/icon.ico gerados")
