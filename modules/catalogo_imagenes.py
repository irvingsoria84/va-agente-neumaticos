"""
modules/catalogo_imagenes.py
Módulo para buscar imágenes de neumáticos desde el catálogo PDF local de Avantti.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

# Archivo de índice generado por build_catalog_index.py
BASE_DIR = Path(__file__).parent.parent
INDEX_FILE = BASE_DIR / "data" / "catalog_index.json"
CATALOG_DIR = BASE_DIR / "data" / "catalog_images"

_index: Optional[dict] = None


def _normalizar(texto: str) -> str:
    """Normaliza texto para comparación (minúsculas, sin tildes, sin puntuación extra)."""
    if not isinstance(texto, str):
        return ""
    texto = texto.lower()
    mapa = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for k, v in mapa.items():
        texto = texto.replace(k, v)
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _cargar_indice() -> dict:
    global _index
    if _index is None:
        if INDEX_FILE.exists():
            with open(INDEX_FILE, encoding="utf-8") as f:
                _index = json.load(f)
        else:
            _index = {}
    return _index


def _tokens(texto: str) -> set:
    return set(_normalizar(texto).split())


def _extraer_tokens_clave(texto: str) -> set:
    """
    Extrae solo los tokens clave de una descripcion de neumatico:
    medida (ej: 295/80, R22.5, R20), numero de capas (ej: 16PR, 18PR).
    Ignora nombres de modelos que varian entre PDF y Excel.
    """
    # Normalizar pero preservar puntos dentro de numeros para "22.5"
    texto_norm = texto.lower()
    mapa = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for k, v in mapa.items():
        texto_norm = texto_norm.replace(k, v)

    clave = set()

    # Buscar patrones: R22.5, R20, R15, etc. (con o sin decimal)
    for m in re.finditer(r'r\d+(?:\.\d+)?', texto_norm):
        clave.add(m.group())

    # Buscar NNpr (numero de capas): 16pr, 18pr, 20pr, etc.
    for m in re.finditer(r'\d+pr', texto_norm):
        clave.add(m.group())

    # Buscar la parte numerica de la medida: "295", "315", "285", "10", "11", etc.
    # Son los numeros antes de "/" o al inicio
    for m in re.finditer(r'\b(\d{2,3})\b', texto_norm):
        clave.add(m.group())

    return clave


def buscar_imagen_local(query: str) -> Optional[str]:
    """
    Busca la imagen más coincidente con el query en el catálogo PDF local.
    Hace matching basado en la medida (dimensión + número de capas) ignorando
    diferencias de nombre de modelo entre PDF y Excel.
    Retorna la ruta absoluta de la imagen si hay coincidencia suficiente, o None.
    """
    indice = _cargar_indice()
    if not indice:
        return None

    q_tokens = _extraer_tokens_clave(query)
    
    # LOGGING
    try:
        with open(BASE_DIR / "scratch" / "query_log.txt", "a", encoding="utf-8") as f:
            f.write(f"QUERY: '{query}' -> TOKENS: {q_tokens}\n")
    except Exception:
        pass
        
    if not q_tokens:
        return None

    best_score = 0.0
    best_path = None
    best_ply_diff = 999  # Para desempatar por numero de capas

    # Extraer el numero de capas del query para desempatar
    q_ply = None
    for m in re.finditer(r'(\d+)pr', query.lower()):
        q_ply = int(m.group(1))

    for key, entry in indice.items():
        e_tokens = _extraer_tokens_clave(entry["medida"])
        if not e_tokens:
            continue
        interseccion = q_tokens & e_tokens
        # Score: fraccion de tokens clave del query que coinciden
        score = len(interseccion) / len(q_tokens)

        # Calcular diferencia de capas para desempatar
        ply_diff = 999
        if q_ply:
            for m in re.finditer(r'(\d+)pr', entry["medida"].lower()):
                ply_diff = abs(int(m.group(1)) - q_ply)
                break

        if score > best_score or (score == best_score and ply_diff < best_ply_diff):
            best_score = score
            best_path = entry["imagen"]
            best_ply_diff = ply_diff

    # Umbral: al menos 75% de los tokens clave deben coincidir
    if best_score >= 0.75 and best_path:
        path = Path(best_path)
        if path.exists():
            return str(path.resolve())

    return None


def buscar_imagen_local_fmt(query: str) -> Optional[str]:
    """
    Igual que buscar_imagen_local pero retorna una URL file:/// lista para Markdown.
    """
    import urllib.parse
    ruta = buscar_imagen_local(query)
    if ruta:
        ruta_f = ruta.replace("\\", "/")
        return urllib.parse.quote(ruta_f, safe=":/")\
               .replace("%3A", ":")  # Dejar : sin encode para la URL de Windows
    return None
