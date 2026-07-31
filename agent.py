import json
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
import config
from modules.buscador import buscar_producto as _buscar, info_catalogo
from modules.calculadora import calcular_cotizacion as _calcular, formatear_tabla_cotizacion
from modules.competencia import _buscar_precios_async, formatear_tabla_competencia
import google.generativeai as genai
import os

# ----------------- Funciones de Herramientas -----------------

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

def buscar_neumatico(query: str) -> str:
    """Busca un neumatico en el stock local (Excel) y devuelve precio base, stock y codigo."""
    try:
        try:
            (config.SESSION_FILE.parent / "last_query.txt").write_text(query, encoding="utf-8")
        except:
            pass

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
    """Calcula precio de venta, costo (aplicando el 35% de descuento) y ganancias."""
    try:
        precio_excel = None
        if codigo_producto and margen_pct in [10, 12, 15, 20, 25]:
            resultados = _buscar(codigo_producto)
            for r in resultados:
                if r["codigo"] == codigo_producto:
                    precio_excel = r.get("precios_listas", {}).get(margen_pct)
                    break

        calc = _calcular(
            precio_base=precio_base,
            margen_pct=margen_pct,
            cantidad=cantidad,
            flete=flete,
            precio_excel=precio_excel,
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

def buscar_precios_competencia(query: str) -> str:
    """Busca precios en Neumatruck, Neumastore, Neumachile, etc."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # Si ya hay un event loop (ej: Streamlit puede correr en uno), usamos una tarea sincrona wrapper o asyncio.run no funcionara.
            import threading
            resultados = []
            def run_in_thread():
                nonlocal resultados
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                resultados = new_loop.run_until_complete(_buscar_precios_async(query))
                new_loop.close()
            t = threading.Thread(target=run_in_thread)
            t.start()
            t.join()
        else:
            resultados = asyncio.run(_buscar_precios_async(query))
            
        return formatear_tabla_competencia(resultados, query=query)
    except Exception as e:
        return f"Error: {str(e)}"

def solicitar_ficha_neumatico(nombre_producto: str = "") -> str:
    """
    Devuelve la imagen del neumatico desde la extraccion web mas reciente.
    CRITICO: Debes pasar el nombre COMPLETO del producto.
    Usalo SOLO si el usuario pide explicitamente ver una imagen o especificaciones.
    """
    respuesta = []
    
    archivo_img = config.SESSION_FILE.parent / "last_image.txt"
    archivo_ficha = config.SESSION_FILE.parent / "last_ficha.txt"

    if archivo_img.exists():
        url = archivo_img.read_text(encoding="utf-8").strip()
        if url:
            img_src = url if url.startswith("http") else f"file:///{url}"
            respuesta.append(
                f"Aqui tienes la imagen referencial obtenida de la web:\n\n"
                f"![Imagen de Neumatico]({img_src})\n"
                f"*(URL directa: {img_src})*"
            )

    if archivo_ficha.exists():
        ficha = archivo_ficha.read_text(encoding="utf-8").strip()
        if ficha:
            respuesta.append(f"**Especificaciones Tecnicas:**\n{ficha}")

    if respuesta:
        return "\n\n".join(respuesta)

    return (
        f"No se encontro imagen para '{nombre_producto}'. "
        "Intenta buscar primero con buscar_precios_competencia para que el sistema "
        "intente extraer una imagen de la web."
    )

# ----------------- Configuracion del Agente -----------------

def get_chat_session():
    """Inicializa la sesión de chat con el modelo y herramientas."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("No se encontró la variable de entorno GEMINI_API_KEY")
        
    genai.configure(api_key=api_key)
    
    instrucciones = """
Eres el asistente de ventas experto en NEUMÁTICOS PESADOS.

TU ROL:
Ayudas al dueño de la distribuidora a responder consultas de clientes con rapidez: precios, stock y competencia.

CUÁNDO USAR CADA HERRAMIENTA:
- buscar_neumatico: SIEMPRE que pregunten por un neumático (por código o medida). 
  Usa esto para ver el precio real y stock ANTES de cotizar.
- calcular_cotizacion: SIEMPRE después de buscar. 
  Recuerda pasarle el "precio_base" que te da buscar_neumatico.
- buscar_precios_competencia: Para comparar precios de mercado.
- solicitar_ficha_neumatico: SOLO si el usuario pide explícitamente ver una imagen o la ficha técnica del producto.

REGLAS:
1. Nunca inventes precios.
2. Si el stock es menor a 10, DEBES advertir al usuario.
3. **SIEMPRE pregunta** al usuario (o al gerente) qué porcentaje de margen o descuento quiere aplicar para darle el precio final si no te lo especificó en su mensaje inicial.
4. Si el cliente no pide la imagen ni ficha, no uses solicitar_ficha_neumatico.
5. PROHIBIDO GENERAR IMÁGENES por tu cuenta.
6. Tu output final SIEMPRE debe ser un formato de WhatsApp listo para copiar y pegar.
"""

    model = genai.GenerativeModel(
        model_name="gemini-flash-latest",
        tools=[buscar_neumatico, calcular_cotizacion, buscar_precios_competencia, solicitar_ficha_neumatico],
        system_instruction=instrucciones
    )
    
    # enable_automatic_function_calling=True hace que Gemini ejecute las funciones localmente y responda solo con el resultado final
    return model.start_chat(enable_automatic_function_calling=True)
