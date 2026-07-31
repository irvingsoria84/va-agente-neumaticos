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

        print("[*] Navegando a premium.neumachile.cl...")
        try:
            await page.goto("https://premium.neumachile.cl/", timeout=30000)
            
            print("[*] Llenando credenciales...")
            # Detectar selectores del portal premium
            if await page.locator("#email").count() > 0:
                await page.fill("#email", NEUMACHILE_USER)
                await page.fill("#email", NEUMACHILE_USER)
                await page.wait_for_timeout(500)
                await page.fill("#pass", NEUMACHILE_PASS)
                await page.wait_for_timeout(500)
                await page.click("#btn-login")
                
                # Esperar a que la URL cambie, significa que el login fue exitoso
                try:
                    await page.wait_for_url("**/pedidos**", timeout=15000)
                    print("[*] Login exitoso, redirigido al dashboard.")
                except Exception as e:
                    print("[!] No se redirigió al dashboard, posible error de credenciales o timeout.")
                    await page.screenshot(path="scratch/login_error.png")
            else:
                print("No se encontraron los campos de login estándar.")
                await page.pause()

            # Esperar a que la página cargue tras el login
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)
            
            # Guardar el estado
            await context.storage_state(path=str(SESSION_FILE))
            print(f"[+] Sesión guardada exitosamente en {SESSION_FILE}")

        except Exception as e:
            print(f"Error durante el login: {e}")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(login())
