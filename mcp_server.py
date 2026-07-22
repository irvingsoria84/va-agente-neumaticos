#!/usr/bin/env python3
"""
mcp_server.py — VA Agente Neumáticos
Servidor MCP para Antigravity.
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP

import config
from modules.buscador import buscar_producto as _buscar, info_catalogo
from modules.calculadora import calcular_cotizacion as _calcular, formatear_tabla_cotizacion
from modules.competencia import buscar_precios as _buscar_precios, formatear_tabla_competencia

mcp = FastMCP(
    name="VA Agente Neumaticos",
    instructions="""
Eres el asistente de ventas experto en NEUMÁTICOS PESADOS.

TU ROL:
Ayudas al dueño de la distribuidora a responder consultas de clientes con rapidez: precios, stock y competencia.

CUÁNDO USAR CADA HERRAMIENTA:
- buscar_neumatico: SIEMPRE que pregunten por un neumático (por código o medida). 
  Usa esto para ver el precio real y stock ANTES de cotizar.
- calcular_cotizacion: SIEMPRE después de buscar. 
  Recuerda pasarle el "precio_base" que te da buscar_neumatico. La herramienta calculará el costo con 35% de descuento internamente.
- buscar_precios_competencia: Para comparar precios de mercado (Neumatruck, Neumastore, etc. y Neumachile).
- solicitar_ficha_neumatico: SOLO si el usuario pide explícitamente ver una imagen o la ficha técnica del producto.

REGLAS:
1. Nunca inventes precios.
2. Si el stock es menor a 10, DEBES advertir al usuario usando la información que devuelve el buscador.
3. Al usar calcular_cotizacion, el sistema usa un margen por defecto. **SIEMPRE pregunta** al usuario (o al gerente) qué porcentaje de margen o descuento quiere aplicar para darle el precio final si no te lo especificó en su mensaje inicial.
4. Si el cliente no pide la imagen ni ficha, no uses solicitar_ficha_neumatico.
""",
)

def _guardar_historial(entrada: dict) -> None:
    try:
        config.COTIZACIONES_DIR.mkdir(parents=True, exist_ok=True)
        historial = []
        if config.HISTORIAL_FILE.exists():
            with open(config.HISTORIAL_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        entrada["timestamp"] = datetime.now().isoformat()
        historial.append(entrada)
        with open(config.HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _formato_precio(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")


@mcp.tool()
def buscar_neumatico(query: str) -> str:
    """
    Busca un neumático en la base de stock.
    Retorna precio base, stock y código.
    """
    try:
        resultados = _buscar(query)
        if not resultados:
            info = info_catalogo()
            return f"No se encontro: **{query}**.\nMarcas disponibles: {', '.join(info['marcas'][:5])}..."

        lineas = [f"**Resultados para: '{query}'**\n"]
        for i, p in enumerate(resultados, 1):
            lineas.append(
                f"**{i}. {p['descripcion']}** (Marca: {p['marca']})\n"
                f"   Codigo: `{p['codigo']}`\n"
                f"   Precio Base (Sin dcto): **{_formato_precio(p['precio_base'])}**\n"
                f"   Stock: {p['stock']}\n"
            )
        lineas.append("\n*Usa calcular_cotizacion con el precio_base para ver costos y venta final.*")
        return "\n".join(lineas)
    except Exception as e:
        return f"Error: {str(e)}\n{traceback.format_exc()}"


@mcp.tool()
def calcular_cotizacion(
    precio_base: float,
    margen_pct: float = config.MARGEN_DEFAULT,
    cantidad: int = 1,
    nombre_producto: str = "",
    codigo_producto: str = "",
    stock_producto: str = "",
    marca_producto: str = "",
    flete: float = 0.0,
) -> str:
    """
    Calcula precio de venta, costo (aplicando el 35% de descuento) y ganancias.
    """
    try:
        calc = _calcular(
            precio_base=precio_base,
            margen_pct=margen_pct,
            cantidad=cantidad,
            flete=flete,
        )
        tabla = formatear_tabla_cotizacion(
            calc,
            nombre_producto=nombre_producto,
            codigo=codigo_producto,
            stock=stock_producto,
            marca=marca_producto
        )
        _guardar_historial({
            "tipo": "cotizacion",
            "producto": nombre_producto,
            "codigo": codigo_producto,
            "precio_base": precio_base,
            "margen_pct": margen_pct,
            "cantidad": cantidad,
        })
        return tabla
    except Exception as e:
        return f"Error al calcular: {str(e)}"


@mcp.tool()
def buscar_precios_competencia(query: str) -> str:
    """Busca precios en Neumatruck, Neumastore, Neumachile, etc."""
    try:
        resultados = _buscar_precios(query)
        return formatear_tabla_competencia(resultados, query=query)
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def solicitar_ficha_neumatico() -> str:
    """
    Devuelve la URL de la última imagen extraída de neumachile.cl y su ficha técnica resumida.
    Úsalo SOLO si el usuario pide explícitamente ver una imagen o especificaciones.
    """
    archivo_img = config.SESSION_FILE.parent / "last_image.txt"
    archivo_ficha = config.SESSION_FILE.parent / "last_ficha.txt"
    
    respuesta = []
    
    if archivo_img.exists():
        url = archivo_img.read_text(encoding="utf-8").strip()
        if url:
            respuesta.append(f"Aquí tienes la imagen referencial obtenida de Neumachile:\n\n![Imagen de Neumático]({url})\n\n*(URL directa: {url})*")
    
    if archivo_ficha.exists():
        ficha = archivo_ficha.read_text(encoding="utf-8").strip()
        if ficha:
            respuesta.append(f"**Especificaciones Tecnicas:**\n{ficha}")
            
    if respuesta:
        return "\n\n".join(respuesta)
        
    return "No se extrajo ninguna imagen ni ficha tecnica en la ultima busqueda de competencia. Intenta buscar el precio del neumatico primero en la competencia."


if __name__ == "__main__":
    config.COTIZACIONES_DIR.mkdir(parents=True, exist_ok=True)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("[*] VA Agente Neumáticos -- Iniciando...")
    mcp.run()
