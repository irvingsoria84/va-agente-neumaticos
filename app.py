import streamlit as st
import os
from dotenv import load_dotenv

# Asegurar que el navegador este instalado (Para Hugging Face Spaces)
os.system("playwright install chromium")

# Cargar variables de entorno
load_dotenv()

from PIL import Image

# Configuración de página
icono = Image.open("assets/Avanti_LogoFinal_combinado.png") if os.path.exists("assets/Avanti_LogoFinal_combinado.png") else "🟠"
st.set_page_config(
    page_title="Avantti - Asistente de Ventas",
    page_icon=icono,
    layout="centered"
)

# Estilos adicionales
st.markdown("""
<style>
    .stChatFloatingInputContainer {
        padding-bottom: 20px;
    }
    .titulo {
        color: #ff5e00;
        text-align: center;
        font-weight: bold;
    }
    .subtitulo {
        text-align: center;
        margin-bottom: 30px;
        color: #cccccc;
    }
</style>
""", unsafe_allow_html=True)

if os.path.exists("assets/Avanti_LogoFinal_combinado.png"):
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.image("assets/Avanti_LogoFinal_combinado.png", use_container_width=True)
else:
    st.markdown("<h1 class='titulo'>Avantti Solutions 🟠</h1>", unsafe_allow_html=True)

st.markdown("<h4 class='subtitulo'>Asistente de Cotizaciones de Neumáticos Pesados</h4>", unsafe_allow_html=True)

# Inicializar sesión del chatbot
if "chat_session" not in st.session_state:
    from agent import get_chat_session
    try:
        st.session_state.chat_session = get_chat_session()
        st.session_state.messages = []
        # Mensaje de bienvenida
        st.session_state.messages.append({"role": "assistant", "content": "¡Hola! Soy tu asistente de ventas de Avantti. Dime qué neumático estás buscando y te daré stock, precios y cotizaciones listas para WhatsApp."})
    except Exception as e:
        st.error(f"Error al inicializar el asistente: {e}\nPor favor, verifica que la variable GEMINI_API_KEY esté configurada.")

# Mostrar historial de mensajes
if "messages" in st.session_state:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Input del usuario
if prompt := st.chat_input("Ej: Cotiza el neumático WD2088 al 20% de margen"):
    # Agregar mensaje del usuario al historial
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Mostrar respuesta del asistente
    with st.chat_message("assistant"):
        with st.spinner("Analizando inventario y mercado..."):
            try:
                # El automatic_function_calling maneja internamente las herramientas
                response = st.session_state.chat_session.send_message(prompt)
                respuesta_texto = response.text
                st.markdown(respuesta_texto)
                # Guardar respuesta
                st.session_state.messages.append({"role": "assistant", "content": respuesta_texto})
            except Exception as e:
                st.error(f"Error al procesar la consulta: {e}")
