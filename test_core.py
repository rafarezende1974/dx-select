"""Teste do nucleo com fotos simuladas (sem fotos reais, sem GUI).

Cenario:
  - cena A: 3 fotos parecidas (base, base + brilho, base borrada)
  - cena B: 1 foto bem diferente
  - cena C: 1 foto quase preta
Espera-se: A vira 1 grupo, B e C ficam separados; dentro de A, a
foto nitida pontua mais que a borrada; a foto escura pontua pouco
em exposicao; exportar copia so as mantidas e grava selecao.csv.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from culling_core import export_kept, groups_of, scan_folder


def make_scene(path, bg, shape):
    img = Image.new("RGB", (400, 300), bg)
    d = ImageDraw.Draw(img)
    if shape == "circle":
        d.ellipse([100, 60, 300, 240], fill=(220, 60, 60))
        d.rectangle([40, 230, 360, 260], fill=(40, 120, 60))
    else:
        d.polygon([(200, 40), (340, 240), (60, 240)], fill=(40, 80, 200))
        d.rectangle([40, 230, 360, 260], fill=(200, 180, 40))
    d.text((20, 20), "TESTE", fill=(255, 255, 255))
    img.save(path, quality=92)


def main():
    tmp = tempfile.mkdtemp(prefix="dxselect-test-")
    src = os.path.join(tmp, "origem")
    os.makedirs(src)
    make_scene(os.path.join(src, "a1.jpg"), (135, 206, 235), "circle")
    base = Image.open(os.path.join(src, "a1.jpg"))
    ImageEnhance.Brightness(base).enhance(1.08).save(os.path.join(src, "a2.jpg"), quality=92)
    base.filter(ImageFilter.GaussianBlur(3)).save(os.path.join(src, "a3.jpg"), quality=92)
    make_scene(os.path.join(src, "b1.jpg"), (30, 30, 60), "triangle")
    ImageEnhance.Brightness(base).enhance(0.15).save(os.path.join(src, "c1.jpg"), quality=92)

    photos = scan_folder(src)
    groups = groups_of(photos)
    by_rel = {p.rel: p for p in photos}
    assert len(photos) == 5, f"esperava 5 fotos, veio {len(photos)}"
    assert by_rel["a1.jpg"].group == by_rel["a2.jpg"].group == by_rel["a3.jpg"].group, "cena A devia agrupar"
    assert by_rel["b1.jpg"].group != by_rel["a1.jpg"].group, "cena B devia separar"
    assert by_rel["a1.jpg"].score > by_rel["a3.jpg"].score, "nitida devia pontuar mais que borrada"
    assert by_rel["a1.jpg"].suggested, "melhor de A devia ser sugerida"
    assert by_rel["c1.jpg"].brightness < 50, f"foto escura devia ter brilho baixo, veio {by_rel['c1.jpg'].brightness:.0f}"

    by_rel["a1.jpg"].decision = "keep"
    by_rel["b1.jpg"].decision = "keep"
    dest = os.path.join(tmp, "selecionadas")
    copied, csv_path = export_kept(photos, dest)
    assert copied == 2, f"esperava 2 copiadas, veio {copied}"
    assert os.path.exists(os.path.join(dest, "a1.jpg"))
    assert os.path.exists(os.path.join(dest, "b1.jpg"))
    assert not os.path.exists(os.path.join(dest, "a3.jpg"))
    assert os.path.exists(csv_path)
    # Originais intactos.
    assert len(os.listdir(src)) == 5, "originais nao deviam ser movidos"
    print(f"OK: {len(photos)} fotos, {len(groups)} grupos, exportou {copied}, csv em {csv_path}")
    print("Grupos:", [(g[0].group, [p.rel for p in g]) for g in groups])
    print("Notas:", {p.rel: p.score for p in photos})
    shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
