FROM python:3.10-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos requeridos
COPY requirements.txt .

# Instalar dependencias del sistema requeridas por Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgconf-2-4 \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libx11-xcb1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar los navegadores de Playwright (solo Chromium para hacer la imagen mas ligera)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar el codigo fuente
COPY . .

# Exponer el puerto de Streamlit
EXPOSE 8501

# Comando para ejecutar Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
