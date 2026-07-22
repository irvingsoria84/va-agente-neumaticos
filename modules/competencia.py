"""
modules/competencia.py
Scraping de precios en sitios web de competidores de neumáticos.
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import COMPETIDORES, TIMEOUT_SCRAPING, SESSION_FILE

def _limpiar_precio(texto: str) -> Optional[int]:
    """Extrae el primer precio CLP de un string de texto."""
    if not texto:
        return None
    texto = texto.replace("\xa0", " ").replace("$", "").strip()
    texto = re.sub(r"[^\d.,]", "", texto)
    if not texto:
        return None
    # Asumimos que los miles están con punto y no hay decimales, o al revés.
    texto = texto.replace(".", "").replace(",", "")
    try:
        valor = int(texto)
        if 1_000 <= valor <= 10_000_000:
            return valor
    except ValueError:
        pass
    return None

def _fp(valor: int) -> str:
    return f"${valor:,}".replace(",", ".")

# ── Scrapers por sitio ────────────────────────────────────────────────────────

async def _scrape_generic(page, query: str, nombre_tienda: str, url_search: str) -> dict:
    """Scraper genérico para la mayoría de tiendas WooCommerce / Shopify."""
    try:
        await page.goto(url_search, wait_until="domcontentloaded", timeout=TIMEOUT_SCRAPING)
        await page.wait_for_timeout(2000)

        selectores_precio = [
            ".woocommerce-Price-amount bdi", ".price .amount", ".product-price", 
            "[class*='price']", ".vtex-product-price-1-x-sellingPrice"
        ]
        selectores_nombre = [
            ".woocommerce-loop-product__title", ".product-title", "h2", "h3", 
            "[class*='productName']"
        ]

        nombre_encontrado = ""
        precio_encontrado = None

        for sel in selectores_nombre:
            try:
                el = page.locator(sel).first
                if await el.count() > 0:
                    nombre_encontrado = (await el.text_content() or "").strip()
                    if nombre_encontrado:
                        break
            except Exception:
                continue

        for sel in selectores_precio:
            try:
                elements = page.locator(sel)
                count = await elements.count()
                for i in range(min(count, 5)):
                    texto = (await elements.nth(i).text_content() or "").strip()
                    precio = _limpiar_precio(texto)
                    if precio:
                        precio_encontrado = precio
                        break
                if precio_encontrado:
                    break
            except Exception:
                continue

        if precio_encontrado:
            return {
                "tienda": nombre_tienda,
                "producto": nombre_encontrado or query,
                "precio": precio_encontrado,
                "precio_fmt": _fp(precio_encontrado),
                "estado": "ok",
                "url": url_search,
            }
        return {"tienda": nombre_tienda, "producto": None, "precio": None,
                "precio_fmt": "—", "estado": "No encontrado", "url": url_search}

    except asyncio.TimeoutError:
        return {"tienda": nombre_tienda, "producto": None, "precio": None, "precio_fmt": "—", "estado": "Timeout", "url": ""}
    except Exception:
        return {"tienda": nombre_tienda, "producto": None, "precio": None, "precio_fmt": "—", "estado": "Error de acceso", "url": ""}


async def _scrape_neumachile(page, query: str) -> dict:
    """Scraper específico para Neumachile que además extrae la imagen."""
    nombre_tienda = "Neumachile"
    url = f"https://www.neumachile.cl/?s={query.replace(' ', '+')}&post_type=product"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_SCRAPING)
        await page.wait_for_timeout(3000)

        # Precio
        precio_encontrado = None
        nombre_encontrado = ""
        imagen_url = ""
        ficha_tecnica = ""

        # Intentar extraer datos del primer producto
        product_card = page.locator(".product").first
        if await product_card.count() > 0:
            nombre_encontrado = (await product_card.locator(".woocommerce-loop-product__title").text_content() or "").strip()
            
            # Buscar precio (puede estar oculto o requerir login, si la sesión funcionó, se mostrará)
            precio_txt = await product_card.locator(".price").text_content() or ""
            precio_encontrado = _limpiar_precio(precio_txt)

            # Buscar imagen
            img_loc = product_card.locator("img").first
            if await img_loc.count() > 0:
                imagen_url = await img_loc.get_attribute("src")

            # Buscar especificaciones técnicas básicas si existe la sección de descripción corta
            try:
                # Extraer una pequeña ficha técnica
                desc_loc = product_card.locator(".woocommerce-product-details__short-description").first
                if await desc_loc.count() > 0:
                    ficha_tecnica = (await desc_loc.text_content() or "").strip()
                    # Limpiar saltos de línea excesivos
                    ficha_tecnica = re.sub(r'\n+', '\n', ficha_tecnica)
            except Exception:
                pass

        if precio_encontrado or nombre_encontrado:
            return {
                "tienda": nombre_tienda,
                "producto": nombre_encontrado or query,
                "precio": precio_encontrado,
                "precio_fmt": _fp(precio_encontrado) if precio_encontrado else "Requiere Login/No disp.",
                "estado": "ok" if precio_encontrado else "Sin Precio",
                "url": url,
                "imagen_url": imagen_url,
                "ficha_tecnica": ficha_tecnica
            }
        return {"tienda": nombre_tienda, "producto": None, "precio": None, "precio_fmt": "—", "estado": "No encontrado", "url": url}

    except Exception:
        return {"tienda": nombre_tienda, "producto": None, "precio": None, "precio_fmt": "—", "estado": "Error", "url": url}


async def _buscar_precios_async(query: str) -> list[dict]:
    """Busca precios en los sitios de la competencia en paralelo."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        # Contexto genérico para competidores públicos
        context_public = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Contexto privado para Neumachile (usando sesión guardada si existe)
        if SESSION_FILE.exists():
            context_private = await browser.new_context(
                storage_state=str(SESSION_FILE),
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
            )
        else:
            context_private = context_public

        # Páginas
        pages = {
            "Neumastore": await context_public.new_page(),
            "Neumatruck": await context_public.new_page(),
            "Rosso Store": await context_public.new_page(),
            "Red Barrera": await context_public.new_page(),
            "Implementos": await context_public.new_page(),
            "Caren": await context_public.new_page(),
            "Neumachile": await context_private.new_page()
        }

        # Ejecutar en paralelo
        q_url = query.replace(' ', '+')
        tareas = [
            _scrape_generic(pages["Neumastore"], query, "Neumastore", f"https://neumastore.cl/?s={q_url}&post_type=product"),
            _scrape_generic(pages["Neumatruck"], query, "Neumatruck", f"https://neumatruck.cl/?s={q_url}&post_type=product"),
            _scrape_generic(pages["Rosso Store"], query, "Rosso Store", f"https://www.rossostore.cl/?s={q_url}&post_type=product"),
            _scrape_generic(pages["Red Barrera"], query, "Red Barrera", f"https://redbarrera.cl/?s={q_url}&post_type=product"),
            _scrape_generic(pages["Implementos"], query, "Implementos", f"https://www.implementos.cl/search?q={q_url}"),
            _scrape_generic(pages["Caren"], query, "Caren", f"https://www.caren.cl/search?q={q_url}"),
            _scrape_neumachile(pages["Neumachile"], query)
        ]

        resultados = await asyncio.gather(*tareas, return_exceptions=False)
        await browser.close()

    return list(resultados)


def buscar_precios(query: str) -> list[dict]:
    """Interfaz sincrónica."""
    try:
        return asyncio.run(_buscar_precios_async(query))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_buscar_precios_async(query))
        finally:
            loop.close()


def formatear_tabla_competencia(resultados: list[dict], query: str = "") -> str:
    """Formatea resultados a Markdown."""
    lineas = []
    if query:
        lineas.append(f"**PRECIOS COMPETENCIA - {query.upper()}**\n")
    lineas.append("| Tienda | Producto encontrado | Precio CLP |")
    lineas.append("|--------|---------------------|------------|")

    precios_encontrados = []
    neumachile_img = None
    neumachile_ficha = None

    for r in resultados:
        tienda = r["tienda"]
        estado = r.get("estado", "")
        precio_fmt = r.get("precio_fmt", "—")
        producto = r.get("producto") or estado

        if len(producto or "") > 40:
            producto = producto[:37] + "..."

        lineas.append(f"| {tienda} | {producto} | {precio_fmt} |")

        if r.get("precio"):
            precios_encontrados.append(r["precio"])
            
        if tienda == "Neumachile" and r.get("imagen_url"):
            neumachile_img = r["imagen_url"]
            neumachile_ficha = r.get("ficha_tecnica", "")

    if precios_encontrados:
        promedio = sum(precios_encontrados) / len(precios_encontrados)
        lineas.append("")
        lineas.append(f"**Resumen:** Promedio mercado {_fp(int(promedio))} (basado en {len(precios_encontrados)} tiendas)")

    if neumachile_img:
        lineas.append("")
        lineas.append(f"*Imagen y especificaciones disponibles en Neumachile. Pidelas si las necesitas.*")
        # Guardar temporalmente en un archivo para el mcp_server si se requiere
        Path(SESSION_FILE.parent / "last_image.txt").write_text(neumachile_img, encoding="utf-8")
        Path(SESSION_FILE.parent / "last_ficha.txt").write_text(neumachile_ficha, encoding="utf-8")

    return "\n".join(lineas)
