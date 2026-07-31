import json
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
import config
from modules.buscador import buscar_producto as _buscar, info_catalogo
from modules.calculadora import calcular_cotizacion as _calcular, formatear_tabla_cotizacion
from modules.competencia import _buscar_precios_async, formatear_tabla_competencia
from groq import Groq
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

def cotizar_y_analizar(query: str, margen_pct: float) -> str:
    """
    CRÍTICO: ÚLTIMA HERRAMIENTA DISPONIBLE. Úsala SIEMPRE que te pidan cotizar o buscar un neumático.
    Esta función hace todo el trabajo pesado:
    1. Busca el neumático en el Excel.
    2. Calcula el precio final con el margen dado.
    3. Busca los precios de la competencia.
    4. Extrae la foto oficial.
    
    Retorna un texto consolidado con todos los datos. Solo debes tomar ese texto, darle un formato bonito para WhatsApp y entregarlo al usuario.
    """
    try:
        # 1. Buscar
        resultados = _buscar(query)
        if not resultados:
            return f"No se encontró el neumático '{query}' en el sistema."
            
        p = resultados[0] # Tomar el mejor resultado
        precio_base = p['precio_base']
        codigo = p['codigo']
        
        # 2. Calcular
        precio_excel = p.get("precios_listas", {}).get(margen_pct)
        calc = _calcular(precio_base, margen_pct, 1, 0.0, precio_excel)
        tabla_cotizacion = formatear_tabla_cotizacion(calc, p['descripcion'], codigo, p['stock'], p['marca'])
        
        # 3. Competencia
        tabla_competencia = buscar_precios_competencia(query)
        
        # 4. Ficha
        ficha = solicitar_ficha_neumatico(p['descripcion'])
        
        return f"DATOS OBTENIDOS EXITOSAMENTE:\n\n{tabla_cotizacion}\n\n{tabla_competencia}\n\n{ficha}"
    except Exception as e:
        return f"Error en la automatización: {e}"

# ----------------- Configuracion del Agente -----------------

import json

class GroqChatSession:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("No se encontró la variable de entorno GROQ_API_KEY")
        self.client = Groq(api_key=api_key)
        self.instrucciones = """
Eres el asistente de ventas experto en NEUMÁTICOS PESADOS de Avantti. Tu única función es ayudar al dueño de la distribuidora a responder consultas de clientes en WhatsApp con rapidez y precisión.

REGLAS ABSOLUTAS:
1. Ante cualquier consulta, ejecuta la herramienta `cotizar_y_analizar`. Si el usuario no dio margen, asume 20.
2. La herramienta te devolverá TODOS los datos (cálculo, stock, competencia y foto).
3. Tu trabajo es simplemente leer esos datos y redactarlos en un mensaje persuasivo y claro de WhatsApp, listo para copiar y pegar.
4. Si el stock es menor a 10 unidades, usa el emoji ⚠️.
"""
        self.messages = [
            {"role": "system", "content": self.instrucciones}
        ]
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "cotizar_y_analizar",
                    "description": "Busca un neumático, calcula el precio final, busca precios de competencia y extrae la foto oficial.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "El modelo o medida del neumático buscado."
                            },
                            "margen_pct": {
                                "type": "number",
                                "description": "El porcentaje de margen de ganancia (ej. 15 para 15%)."
                            }
                        },
                        "required": ["query", "margen_pct"]
                    }
                }
            }
        ]

    def send_message(self, prompt: str):
        self.messages.append({"role": "user", "content": prompt})
        
        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=self.messages,
            tools=self.tools,
            tool_choice="auto",
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        if tool_calls:
            self.messages.append(response_message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except:
                    function_args = {"query": prompt, "margen_pct": 20}
                
                if function_name == "cotizar_y_analizar":
                    function_response = cotizar_y_analizar(
                        query=function_args.get("query", prompt),
                        margen_pct=function_args.get("margen_pct", 20)
                    )
                    self.messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": function_response,
                    })
            
            second_response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=self.messages,
            )
            final_text = second_response.choices[0].message.content
            self.messages.append({"role": "assistant", "content": final_text})
            
            class DummyResponse:
                def __init__(self, text):
                    self.text = text
            return DummyResponse(final_text)
        else:
            final_text = response_message.content
            self.messages.append({"role": "assistant", "content": final_text})
            class DummyResponse:
                def __init__(self, text):
                    self.text = text
            return DummyResponse(final_text)

def get_chat_session():
    """Inicializa la sesión de chat con el modelo y herramientas de Groq."""
    return GroqChatSession()
