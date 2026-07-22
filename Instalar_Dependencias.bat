@echo off
title Instalador de Dependencias - VA Agente Neumaticos
color 0A

echo ===================================================
echo INSTALADOR DE DEPENDENCIAS - AGENTE NEUMATICOS
echo ===================================================
echo.
echo Este script instalara todo lo necesario para que tu Agente funcione.
echo Por favor, asegurate de tener Python instalado en tu computadora.
echo.
pause

echo.
echo [1/3] Instalando librerias desde requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    color 0C
    echo ERROR: Hubo un problema al instalar las librerias.
    echo Asegurate de tener Python instalado y agregado al PATH.
    pause
    exit /b
)

echo.
echo [2/3] Instalando el navegador interno de Playwright (necesario para buscar precios)...
playwright install chromium
if %errorlevel% neq 0 (
    echo.
    color 0C
    echo ERROR: Hubo un problema al instalar Playwright.
    pause
    exit /b
)

echo.
echo [3/3] Verificando archivo de credenciales .env...
if not exist ".env" (
    echo.
    color 0E
    echo ADVERTENCIA: No se encontro el archivo .env
    echo Por favor, pidele al desarrollador el archivo .env con las credenciales y colocalo en esta carpeta.
) else (
    echo El archivo .env existe.
)

echo.
echo ===================================================
echo ¡INSTALACION COMPLETADA CON EXITO!
echo ===================================================
echo Ya puedes ir a Antigravity, abrir la configuracion (Settings),
echo ir a MCP Servers y agregar la ruta de "mcp_server.py".
echo.
pause
