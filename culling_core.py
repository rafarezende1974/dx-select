"""Nucleo do DX Select v0.1 — selecao (culling) de fotos JPG.

Sem IA de rosto e sem servico em nuvem, de proposito, para o prototipo
ser rapido, offline e explicavel:

1. Leitura: varre a pasta (recursiva) buscando .jpg / .jpeg.
2. Agrupamento: fotos parecidas, tiradas em sequencia, viram um grupo.
   Similaridade = dHash (diferenca de brilho entre pixels vizinhos) +
   proximidade no tempo (EXIF, ou data do arquivo se nao houver EXIF).
3. Pontuacao: cada foto ganha uma nota 0-100 combinando nitidez
   (variacao do gradiente em tons de cinza) e exposicao (media de
   brilho: penaliza foto muito escura ou muito estourada).
4. Sugestao: a melhor nota de cada grupo e sugerida como "Manter".
   A decisao final e sempre do fotografo — nada e apagado aqui.
5. Exportacao: COPIA (nunca move) as mantidas para a pasta de destino,
   preservando a subpasta de origem, e grava selecao.csv com o relatorio.

Originais nunca sao alterados. Decisoes sao salvas em .dxselect.json
dentro da pasta de origem, para a sessao continuar de onde parou.
"""

import csv
import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
from PIL import Image, ImageOps

IMAGE_EXTS = {".jpg", ".jpeg"}
SESSION_FILE = ".dxselect.json"

# Limites do agrupamento (ajustaveis sem quebrar o resto do app).
HASH_MAX_DISTANCE = 8   # em 64 bits de dHash: 0 = identicas
TIME_MAX_SECONDS = 60   # sequencia: fotos do mesmo momento


@dataclass
class Photo:
    path: str
    rel: str
    taken: float  # timestamp (EXIF ou mtime)
    dhash: int = 0
    sharpness: float = 0.0
    brightness: float = 0.0
    score: float = 0.0
    group: int = 0
    decision: str = "undecided"  # keep | reject | undecided
    suggested: bool = False


def dhash_of(image: Image.Image) -> int:
    """dHash 9x8 -> 64 bits. Robusto a pequena mudanca de brilho/tamanho."""
    gray = image.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(gray.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _exif_taken(image: Image.Image):
    try:
        exif = image.getexif()
        for tag in (36867, 306):  # DateTimeOriginal, DateTime
            raw = exif.get(tag)
            if raw:
                return datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").timestamp()
    except Exception:
        pass
    return None


def analyse(path: str, rel: str) -> Photo:
    """Abre a foto uma vez e extrai tudo que o agrupamento precisa."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        taken = _exif_taken(im)
        if taken is None:
            taken = os.path.getmtime(path)
        thumb = im.copy()
        thumb.thumbnail((512, 512), Image.LANCZOS)
        gray = np.asarray(thumb.convert("L"), dtype=np.float32)
    dhash = dhash_of(thumb)
    # Nitidez: variacao do gradiente. Foto tremida tem gradiente fraco.
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    sharpness = float(np.mean(gx) + np.mean(gy))
    brightness = float(np.mean(gray))
    return Photo(path=path, rel=rel, taken=taken, dhash=dhash,
                 sharpness=sharpness, brightness=brightness)


def score_photo(photo: Photo, max_sharpness: float) -> float:
    """Nota 0-100. Nitidez pesa 70, exposicao 30 (curva em sino)."""
    sharp = 0.0
    if max_sharpness > 0:
        # Log comprime a escala: foto 2x mais nitida nao vale 2x a nota.
        sharp = min(100.0, 100.0 * math.log1p(photo.sharpness) / math.log1p(max_sharpness))
    # Exposicao ideal perto de 128; penalidade cresce para os extremos.
    exposure = max(0.0, 100.0 - abs(photo.brightness - 128.0) * 0.9)
    return round(0.7 * sharp + 0.3 * exposure, 1)


def scan_folder(folder: str, progress=None):
    """Varre a pasta, analisa e agrupa. Retorna lista de Photo ordenada."""
    files = []
    for root, _dirs, names in os.walk(folder):
        for name in sorted(names):
            if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
                full = os.path.join(root, name)
                files.append(full)
    photos = []
    for i, full in enumerate(files):
        try:
            photos.append(analyse(full, os.path.relpath(full, folder)))
        except Exception:
            continue  # arquivo corrompido ou ilegivel: pula, nao trava a sessao
        if progress:
            progress(i + 1, len(files))
    photos.sort(key=lambda p: (p.taken, p.rel))
    max_sharp = max((p.sharpness for p in photos), default=0.0)
    for p in photos:
        p.score = score_photo(p, max_sharp)
    # Agrupamento sequencial: compara com a foto anterior da mesma sequencia.
    group_id = 0
    previous = None
    for p in photos:
        if (previous is None
                or hamming(p.dhash, previous.dhash) > HASH_MAX_DISTANCE
                or (p.taken - previous.taken) > TIME_MAX_SECONDS
                or (p.taken - previous.taken) < 0):
            group_id += 1
        p.group = group_id
        previous = p
    # Sugestao: melhor nota de cada grupo.
    best = {}
    for p in photos:
        if p.group not in best or p.score > best[p.group].score:
            best[p.group] = p
    for p in best.values():
        p.suggested = True
    # Aplica decisoes salvas de uma sessao anterior, se houver.
    saved = load_session(folder)
    for p in photos:
        if p.rel in saved:
            p.decision = saved[p.rel]
    return photos


def groups_of(photos):
    """Lista de grupos, cada um uma lista de Photo, na ordem do tempo."""
    out = {}
    for p in photos:
        out.setdefault(p.group, []).append(p)
    return [out[k] for k in sorted(out)]


def save_session(folder: str, photos):
    data = {p.rel: p.decision for p in photos if p.decision != "undecided"}
    try:
        with open(os.path.join(folder, SESSION_FILE), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except Exception:
        pass  # pasta so-leitura: a sessao continua em memoria


def load_session(folder: str):
    try:
        with open(os.path.join(folder, SESSION_FILE), encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if v in ("keep", "reject", "undecided")}
    except Exception:
        return {}


def export_kept(photos, dest_folder: str):
    """Copia as mantidas (decisao keep, ou sugestao se nada marcado)
    e grava selecao.csv. Retorna (n_copiadas, caminho_csv)."""
    kept = [p for p in photos if p.decision == "keep"]
    if not kept:
        kept = [p for p in photos if p.suggested]
    os.makedirs(dest_folder, exist_ok=True)
    copied = 0
    for p in kept:
        dest = os.path.join(dest_folder, p.rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.abspath(dest) != os.path.abspath(p.path):
            shutil.copy2(p.path, dest)
            copied += 1
    csv_path = os.path.join(dest_folder, "selecao.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arquivo", "grupo", "decisao", "nota", "nitidez", "brilho", "sugerida"])
        for p in photos:
            w.writerow([p.rel, p.group, p.decision, p.score,
                        round(p.sharpness, 2), round(p.brightness, 1),
                        "sim" if p.suggested else "nao"])
    return copied, csv_path
