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
from rapidfuzz import fuzz

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

def _tokenize(text: str) -> set:
    if not text:
        return set()
    text = text.upper().replace("NEUMATICO", "").replace("NEUMÁTICO", "").replace("CHILE", "")
    tokens = set(re.findall(r'[A-Z0-9]+', text))
    return {t for t in tokens if len(t) > 1 or t.isdigit()}

def es_el_mismo_neumatico(query: str, titulo: str) -> bool:
    """Verifica si el titulo encontrado contiene todos los identificadores clave del query."""
    if not titulo: return False
    tq = _tokenize(query)
    tt = _tokenize(titulo)
    
    if not tq: return False
    
    # Extraer PR (Ply Rating) si existe en el query
    pr_query = {t for t in tq if "PR" in t}
    pr_titulo = {t for t in tt if "PR" in t}
    
    # Si el query tiene un PR (ej. 20PR), y el titulo tiene otro distinto (ej. 18PR), es invalido
    if pr_query and pr_titulo and pr_query != pr_titulo:
        return False
        
    # Calcular inclusión de tokens
    interseccion = tq.intersection(tt)
    score = len(interseccion) / len(tq)

    
    # Exigir que TODOS los tokens del query estén presentes (score 1.0) para evitar CUALQUIER falso positivo
    if score >= 0.99:
        return True
        
    return False

# ── Scrapers por sitio ────────────────────────────────────────────────────────

async def _scrape_neumachile(page, query: str) -> dict:
    """Scraper específico para Neumachile (Premium) que además extrae la imagen."""
    import urllib.parse
    nombre_tienda = "Neumachile"
    
    url_base = "https://premium.neumachile.cl/"
    
    try:
        await page.goto(url_base, wait_until="domcontentloaded", timeout=TIMEOUT_SCRAPING)
        await page.wait_for_timeout(2000)
        
        # Llenar la barra de busqueda
        search_loc = page.locator("input[placeholder*='buscando' i]").first
        if await search_loc.count() > 0:
            # Extraer modelo (token con letras y numeros o de mas de 4 caracteres)
            tokens = query.split()
            modelos = [t for t in tokens if any(c.isalpha() for c in t) and any(c.isdigit() for c in t) and len(t) > 3]
            clean_query = modelos[-1] if modelos else tokens[-1]
            print(f"Neumachile Scraper buscando: {clean_query}")
            
            await search_loc.fill(clean_query)
            await search_loc.press("Enter")
            
            # Wait for search results or a specific timeout
            try:
                await page.wait_for_function(f"document.body.innerText.includes('{clean_query}')", timeout=8000)
            except:
                pass
            await page.wait_for_timeout(2000)
            
            # Find all potential product cards
            cards = await page.locator(".single_product, .product_content").all()
            
            for product_card in cards:
                texto_card = await product_card.inner_text()
                if not texto_card or clean_query not in texto_card:
                    continue
                
                # Extraer nombre (normalmente la primera linea)
                lineas = [l.strip() for l in texto_card.split('\n') if l.strip()]
                nombre_encontrado = lineas[0] if lineas else ""
                
                # Extraer precio
                precio_texto = ""
                for l in lineas:
                    if "$" in l or "CLP" in l:
                        precio_texto = l
                        break
                precio_encontrado = _limpiar_precio(precio_texto)
                
                print(f"Nombre extraido del card: {nombre_encontrado}")
                print(f"Precio extraido: {precio_encontrado}")
                
                # Imagen
                imagen_url = ""
                # Si estamos en single_product, la imagen podria estar un nivel arriba, busquemos global o relativa
                # Mejor buscamos la imagen dentro del contenedor padre
                parent = product_card.locator("xpath=..").first
                if await parent.count() > 0:
                    img_loc = parent.locator("img").first
                else:
                    img_loc = product_card.locator("img").first
                    
                if await img_loc.count() > 0:
                    try:
                        img_path = str(SESSION_FILE.parent / "last_image.jpg")
                        await img_loc.screenshot(path=img_path)
                        img_path_f = img_path.replace(chr(92), '/')
                        imagen_url = urllib.parse.quote(img_path_f, safe=':/')
                    except Exception:
                        pass
                else:
                    # Alternativa: intentar buscar imagen globalmente
                    img_loc = page.locator("img[alt*='neumatico' i], img[src*='/products/']").first
                    if await img_loc.count() > 0:
                        try:
                            img_path = str(SESSION_FILE.parent / "last_image.jpg")
                            await img_loc.screenshot(path=img_path)
                            img_path_f = img_path.replace(chr(92), '/')
                            imagen_url = urllib.parse.quote(img_path_f, safe=':/')
                        except Exception:
                            pass
                
                # Validacion para retornar
                if es_el_mismo_neumatico(query, nombre_encontrado):
                    return {
                        "tienda": nombre_tienda,
                        "producto": nombre_encontrado,
                        "precio": precio_encontrado,
                        "precio_fmt": _fp(precio_encontrado) if precio_encontrado else "Sin Precio",
                        "estado": "ok" if precio_encontrado else "Sin Precio",
                        "url": page.url,
                        "imagen_url": imagen_url,
                        "ficha_tecnica": "\n".join(lineas[1:]) if len(lineas) > 1 else ""
                    }
                    
    except Exception as e:
        print(f"Error scraping Neumachile: {e}")
        pass

    # Si falla o no lo encuentra
    return {"tienda": nombre_tienda, "producto": None, "precio": None, "precio_fmt": "-", "estado": "No encontrado", "url": url_base}






async def _scrape_google_search(page, query: str) -> list[dict]:
    """Busca en Google y extrae los resultados del carrusel de Shopping."""
    url = f"https://www.google.cl/search?q={query.replace(' ', '+')}+precio+chile"
    resultados = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_SCRAPING)
        await page.wait_for_timeout(3000) # Dar tiempo a que cargue el carrusel de shopping
        
        # Buscar enlaces que parecen ser de Google Shopping
        # data-merchant-id o data-offer-id suelen estar presentes en los enlaces patrocinados
        elements = await page.locator("a[data-merchant-id], a[data-offer-id], a.pla-unit").all()
        
        if not elements:
            # Alternativa: Buscar divs que contengan la palabra CLP o $
            elements = await page.locator("a:has(span:has-text('CLP')), a:has(span:has-text('$'))").all()

        for el in elements:
            texto = await el.inner_text()
            if not texto:
                continue
                
            lineas = [l.strip() for l in texto.split('\n') if l.strip()]
            if len(lineas) >= 3:
                # Normalmente la primera linea es el titulo, luego el precio, luego la tienda
                producto = lineas[0]
                precio_txt = lineas[1]
                tienda = lineas[2]
                
                # A veces el precio incluye "CLP" o "$"
                precio = _limpiar_precio(precio_txt)
                if not precio and len(lineas) > 3:
                    precio = _limpiar_precio(lineas[2])
                    tienda = lineas[3]
                    
                if precio and precio > 10000: # Evitar falsos positivos como accesorios baratos
                    # Validacion estricta para asegurar que es el mismo neumático
                    if es_el_mismo_neumatico(query, producto):
                        # Evitar agregar la misma tienda múltiples veces
                        if not any(r["tienda"] == tienda for r in resultados):
                            resultados.append({
                                "tienda": tienda,
                                "producto": producto,
                                "precio": precio,
                                "precio_fmt": _fp(precio),
                                "estado": "ok"
                            })
                            if len(resultados) >= 5:
                                break
                            
    except Exception as e:
        pass
        
    return resultados


async def _scrape_servisantiago(page, query: str) -> Optional[dict]:
    """Busca en servisantiago.cl"""
    try:
        url = f"https://servisantiago.cl/?s={query.replace(' ', '+')}&post_type=product"
        await page.goto(url, timeout=20000, wait_until='domcontentloaded')
        
        # Esperar un poco a que cargue
        await page.wait_for_timeout(2000)
        
        # Puede ser un loop o un single product redirect
        titulo_el = await page.query_selector('.product_title')
        if not titulo_el:
            titulo_el = await page.query_selector('.woocommerce-loop-product__title')
            
        precio_el = await page.query_selector('.price')
        
        if titulo_el and precio_el:
            t = await titulo_el.inner_text()
            p = await precio_el.inner_text()
            p_limpio = _limpiar_precio(p)
            if p_limpio:
                # Validar tokens
                if es_el_mismo_neumatico(query, t):
                    return {
                        "tienda": "Servisantiago",
                        "precio": p_limpio,
                        "precio_fmt": _fp(p_limpio),
                        "url": page.url,
                        "producto": t
                    }
    except Exception as e:
        pass
    return None

async def _scrape_fullneumaticos(page, query: str) -> Optional[dict]:
    """Busca en fullneumaticos.cl"""
    try:
        url = f"https://www.fullneumaticos.cl/?s={query.replace(' ', '+')}&post_type=product"
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_timeout(2000)
        
        titulo_el = await page.query_selector('.product_title')
        if not titulo_el:
            titulo_el = await page.query_selector('.woocommerce-loop-product__title')
            
        precio_el = await page.query_selector('.price')
        
        if titulo_el and precio_el:
            t = await titulo_el.inner_text()
            p = await precio_el.inner_text()
            p_limpio = _limpiar_precio(p)
            if p_limpio:
                if es_el_mismo_neumatico(query, t):
                    return {
                        "tienda": "Full Neumaticos",
                        "precio": p_limpio,
                        "precio_fmt": _fp(p_limpio),
                        "url": page.url,
                        "producto": t
                    }
    except Exception as e:
        pass
    return None

async def _scrape_neumatruck_price(page, query: str) -> Optional[dict]:
    """Busca precio en neumatruck.cl (directo, no solo imagen)."""
    import urllib.parse
    url = f"https://www.neumatruck.cl/search?q={query.replace(' ', '+')}"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)
        
        elements = await page.locator("a[href*='/product/'], a[href*='/producto/']").all()
        
        for el in elements:
            nombre = await el.inner_text()
            if not nombre:
                continue
                
            lineas = [l for l in nombre.split('\n') if l.strip()]
            if lineas:
                producto_texto = lineas[0]
                
                if es_el_mismo_neumatico(query, producto_texto):
                    precio_texto = ""
                    for linea in lineas:
                        if "$" in linea or "CLP" in linea:
                            precio_texto = linea
                            break
                    
                    precio_val = _limpiar_precio(precio_texto)
                    
                    # Intentar sacar screenshot para la imagen
                    imagen_url = ""
                    img_loc = el.locator("img").first
                    if await img_loc.count() > 0:
                        try:
                            img_path = str(SESSION_FILE.parent / "last_image.jpg")
                            await img_loc.screenshot(path=img_path)
                            img_path_f = img_path.replace(chr(92), '/')
                            imagen_url = urllib.parse.quote(img_path_f, safe=':/')
                        except Exception:
                            pass
                            
                    return {
                        "tienda": "Neumatruck",
                        "producto": producto_texto,
                        "precio": precio_val,
                        "precio_fmt": _fp(precio_val) if precio_val else "-",
                        "estado": "ok",
                        "url": url,
                        "imagen_url": imagen_url,
                        "ficha_tecnica": f"Respaldo obtenido desde Neumatruck.\n{producto_texto}"
                    }
    except Exception:
        pass
        
    return None


async def _buscar_precios_async(query: str) -> list[dict]:
    """Busca precios en los 5 competidores fijos en paralelo con Playwright."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

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

        page_google = await context_public.new_page()
        page_neumachile = await context_private.new_page()
        page_fullneumaticos = await context_public.new_page()
        page_servisantiago = await context_public.new_page()
        page_neumatruck = await context_public.new_page()
        
        # Ejecutar TODOS en paralelo (5 competidores + Google Shopping)
        tareas = [
            _scrape_google_search(page_google, query),
            _scrape_neumachile(page_neumachile, query),
            _scrape_fullneumaticos(page_fullneumaticos, query),
            _scrape_servisantiago(page_servisantiago, query),
            _scrape_neumatruck_price(page_neumatruck, query)
        ]
        
        resultados_brutos = await asyncio.gather(*tareas, return_exceptions=True)
        
        # Google Shopping results (lista)
        resultados = resultados_brutos[0] if isinstance(resultados_brutos[0], list) else []
        # Neumachile (dict especial con imagen)
        neumachile_result = resultados_brutos[1] if isinstance(resultados_brutos[1], dict) else {"tienda": "Neumachile", "producto": None, "precio": None, "precio_fmt": "-", "estado": "No encontrado", "url": ""}
        # Full Neumáticos (dict o None)
        full_res = resultados_brutos[2] if isinstance(resultados_brutos[2], dict) else None
        # Servisantiago (dict o None)
        servi_res = resultados_brutos[3] if isinstance(resultados_brutos[3], dict) else None
        # Neumatruck (dict o None)
        neumatruck_res = resultados_brutos[4] if isinstance(resultados_brutos[4], dict) else None
        
        if full_res:
            resultados.append(full_res)
        if servi_res:
            resultados.append(servi_res)
        if neumatruck_res:
            resultados.append(neumatruck_res)
            # Guardar imagen de Neumatruck si la hay
            if neumatruck_res.get("imagen_url"):
                img_file = SESSION_FILE.parent / "last_image.txt"
                img_file.write_text(neumatruck_res["imagen_url"], encoding="utf-8")
            if neumatruck_res.get("ficha_tecnica"):
                ficha_file = SESSION_FILE.parent / "last_ficha.txt"
                ficha_file.write_text(neumatruck_res["ficha_tecnica"], encoding="utf-8")
                    
        resultados.append(neumachile_result)
        
        await browser.close()

    return resultados


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
    """Formatea resultados a Markdown con listas y emojis."""
    lineas = []
    if query:
        lineas.append(f"**PRECIOS MERCADO (GOOGLE) - {query.upper()}**\n")

    if not resultados:
        lineas.append("❌ *No se encontraron competidores online para este neumático (búsqueda en Google, Neumatruck y Neumachile). Al no haber precios de referencia, no es posible realizar un análisis comparativo.*")
        return "\n".join(lineas)

    precios_encontrados = []
    neumachile_img = None
    neumachile_ficha = None
    neumachile_str = ""
    
    for r in resultados:
        tienda = r["tienda"]
        precio_fmt = r.get("precio_fmt", "-")
        producto = r.get("producto", "")

        if len(producto or "") > 40:
            producto = producto[:37] + "..."

        if tienda == "Neumachile":
            if r.get("imagen_url"):
                neumachile_img = r["imagen_url"]
                neumachile_ficha = r.get("ficha_tecnica", "")
                
            if r.get("producto"):
                neumachile_str = f"⭐ **PROVEEDOR PRINCIPAL ({tienda}):** 💵 **{precio_fmt}** ({producto})"
            elif not neumachile_str or "❌" in neumachile_str:
                neumachile_str = f"⭐ **PROVEEDOR PRINCIPAL ({tienda}):** ❌ No encontrado en su web"
            continue
            
        lineas.append(f"🏬 **{tienda}:** 💵 {precio_fmt} ({producto})")
        
        if r.get("precio"):
            precios_encontrados.append(r["precio"])

    # Insertar Neumachile justo después del título
    if neumachile_str:
        if len(lineas) > 0 and "**PRECIOS" in lineas[0]:
            lineas.insert(1, "\n" + neumachile_str + "\n")
        else:
            lineas.insert(0, neumachile_str + "\n")

    if precios_encontrados:
        promedio = sum(precios_encontrados) / len(precios_encontrados)
        lineas.append("")
        lineas.append(f"✅ **Resumen:** Promedio mercado 💰 **{_fp(int(promedio))}** (basado en {len(precios_encontrados)} competidores)")

    if neumachile_img:
        lineas.append("")
        lineas.append(f"📄 *Imagen y especificaciones disponibles en el proveedor principal (Neumachile). Pídelas si las necesitas.*")
        Path(SESSION_FILE.parent / "last_image.txt").write_text(neumachile_img, encoding="utf-8")
        Path(SESSION_FILE.parent / "last_ficha.txt").write_text(neumachile_ficha, encoding="utf-8")

    return "\n".join(lineas)
