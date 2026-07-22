"""
auth_neumachile.py
Script independiente para iniciar sesión en neumachile.cl y guardar la sesión
(cookies y localStorage) en data/session_state.json
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).parent))
from config import SESSION_FILE, DATA_DIR, NEUMACHILE_USER, NEUMACHILE_PASS

async def login():
    if not NEUMACHILE_USER or not NEUMACHILE_PASS:
        print("Error: No se encontraron las credenciales en .env")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # Headless=False para depurar o ver qué pasa
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("[*] Navegando a neumachile.cl...")
        try:
            # Neumachile suele usar WooCommerce o similar
            await page.goto("https://www.neumachile.cl/mi-cuenta/", timeout=30000)
            
            print("[*] Llenando credenciales...")
            # Detectar selectores comunes de login
            if await page.locator("input[name='username']").count() > 0:
                await page.fill("input[name='username']", NEUMACHILE_USER)
                await page.fill("input[name='password']", NEUMACHILE_PASS)
                await page.click("button[name='login'], button[value='Acceder']")
            elif await page.locator("input[type='email']").count() > 0:
                await page.fill("input[type='email']", NEUMACHILE_USER)
                await page.fill("input[type='password']", NEUMACHILE_PASS)
                await page.click("button[type='submit']")
            else:
                print("No se encontraron los campos de login estándar.")
                # Pausar para interactuar manualmente si es necesario
                await page.pause()

            # Esperar a que la página cargue tras el login
            await page.wait_for_load_state("networkidle")
            
            # Guardar el estado
            await context.storage_state(path=str(SESSION_FILE))
            print(f"[+] Sesión guardada exitosamente en {SESSION_FILE}")

        except Exception as e:
            print(f"Error durante el login: {e}")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(login())
