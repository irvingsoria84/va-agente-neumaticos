"""
modules/buscador.py
Búsqueda de neumáticos en el Excel de stock.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import STOCK_FILE, SCORE_MIN_PRODUCTO, TOP_N_PRODUCTOS, STOCK_MINIMO_AVISO

_catalogo: Optional[list[dict]] = None
_archivo_cargado: Optional[str] = None


def _normalizar(texto: str) -> str:
    """Normaliza texto para comparación fuzzy (minúsculas, sin puntuación extra)."""
    if not isinstance(texto, str):
        return ""
    texto = texto.lower()
    mapa = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for k, v in mapa.items():
        texto = texto.replace(k, v)
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def _evaluar_stock(valor) -> str:
    """
    Evalúa el stock y devuelve un texto descriptivo.
    Si es menor a 10, devuelve una advertencia.
    """
    if pd.isna(valor):
        return "Sin información"
    
    val_str = str(valor).strip().lower()
    if val_str == "disponibles" or val_str == "disponible":
        return "Disponible (Abundante)"
    
    try:
        cantidad = int(float(valor))
        if cantidad < STOCK_MINIMO_AVISO:
            return f"Aviso: Stock critico ({cantidad} unidades)"
        return f"{cantidad} unidades"
    except (ValueError, TypeError):
        return val_str


def _cargar_catalogo(forzar: bool = False) -> list[dict]:
    """Carga y cachea el catálogo desde el Excel de neumáticos."""
    global _catalogo, _archivo_cargado

    if not STOCK_FILE.exists():
        raise FileNotFoundError(f"No se encontró el archivo de stock en: {STOCK_FILE}")

    if _catalogo is not None and not forzar and str(STOCK_FILE) == _archivo_cargado:
        return _catalogo

    df = pd.read_excel(STOCK_FILE)
    
    productos: list[dict] = []

    for _, row in df.iterrows():
        try:
            codigo = str(row.get("CODIGO", "")).strip()
            descripcion = str(row.get("DESCRIPCION", "")).strip()
            marca = str(row.get("MARCA", "")).strip()
            
            precio_raw = row.get("PRECIO")
            if pd.isna(precio_raw):
                continue
            precio = int(float(precio_raw))
            
            stock_raw = row.get("DISPONIBLE")
            stock_texto = _evaluar_stock(stock_raw)
            
            # Solo agregar si tiene código y descripción
            if codigo and descripcion and codigo != 'nan' and descripcion != 'nan':
                productos.append({
                    "codigo": codigo,
                    "descripcion": descripcion,
                    "marca": marca,
                    "precio_base": precio,
                    "stock": stock_texto,
                    "_normalizado": _normalizar(descripcion) + " " + _normalizar(codigo)
                })
        except Exception:
            continue

    _catalogo = productos
    _archivo_cargado = str(STOCK_FILE)
    return _catalogo


def buscar_producto(query: str, top_n: int = TOP_N_PRODUCTOS) -> list[dict]:
    """
    Busca neumáticos en el catálogo usando búsqueda fuzzy.
    """
    catalogo = _cargar_catalogo()
    if not catalogo:
        return []

    query_norm = _normalizar(query)
    descripciones = [p["_normalizado"] for p in catalogo]

    resultados = process.extract(
        query_norm,
        descripciones,
        scorer=fuzz.token_set_ratio,
        limit=top_n * 3,
    )

    output: list[dict] = []
    codigos_vistos: set[str] = set()

    for _desc_norm, score, idx in resultados:
        if score < SCORE_MIN_PRODUCTO:
            continue
        producto = catalogo[idx]
        if producto["codigo"] in codigos_vistos:
            continue
        codigos_vistos.add(producto["codigo"])
        
        output.append({
            k: v for k, v in producto.items() if k != "_normalizado"
        } | {"similitud": round(score, 1)})

    return output[:top_n]


def info_catalogo() -> dict:
    """Retorna estadísticas del catálogo cargado."""
    catalogo = _cargar_catalogo()
    marcas = {p["marca"] for p in catalogo if p["marca"]}
    return {
        "total_productos": len(catalogo),
        "total_marcas": len(marcas),
        "archivo": STOCK_FILE.name,
        "marcas": sorted(marcas),
    }
