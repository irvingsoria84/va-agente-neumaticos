"""
config.py — Configuración central de VA Agente Neumáticos
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ── Rutas base ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"

COTIZACIONES_DIR = DATA_DIR / "cotizaciones"
HISTORIAL_FILE = COTIZACIONES_DIR / "historial.json"
SESSION_FILE = DATA_DIR / "session_state.json"  # Para Playwright

# El archivo de stock oficial
STOCK_FILE = BASE_DIR / "STOCK EXCEL OFICIAL.xlsx"

# ── Credenciales Neumachile ───────────────────────────────────────────────────
NEUMACHILE_USER = os.getenv("NEUMACHILE_USER", "")
NEUMACHILE_PASS = os.getenv("NEUMACHILE_PASS", "")

# ── Parámetros de negocio ─────────────────────────────────────────────────────
MARGEN_DEFAULT = 20.0          # % margen por defecto
DESCUENTO_COMPRA = 0.35        # 35% descuento para costo base
IVA = 0.19                     # IVA Chile
ISLR = 0.125                   # Provisión ISLR
STOCK_MINIMO_AVISO = 10        # Umbral para avisar de bajo stock

# ── Sitios de competencia ─────────────────────────────────────────────────────
COMPETIDORES = {
    "Neumachile": "https://www.neumachile.cl",
    "Neumatruck": "https://www.neumatruck.cl",
    "Full Neumaticos": "https://www.fullneumaticos.cl",
    "Servisantiago": "https://servisantiago.cl",
}

TIMEOUT_SCRAPING = 20_000  # ms por sitio en Playwright

# ── Búsqueda fuzzy ────────────────────────────────────────────────────────────
SCORE_MIN_PRODUCTO = 40    # Score mínimo para resultados de productos
TOP_N_PRODUCTOS = 5        # Máximo de productos a retornar
