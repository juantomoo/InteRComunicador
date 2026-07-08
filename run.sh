#!/bin/bash
# Script para iniciar InteRComunicador

# Cambiar al directorio del script
cd "$(dirname "$0")"

# Verificar si existe el entorno virtual
if [ ! -d "venv" ]; then
    echo "Configurando entorno virtual de Python..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install textual fastapi uvicorn websockets
else
    # Asegurar que las dependencias de la web estén instaladas
    ./venv/bin/pip install -q fastapi uvicorn websockets
fi

clear
echo "============================================================"
echo "                   InteRComunicador IRC                     "
echo "============================================================"
echo "Elige el tipo de interfaz para iniciar:"
echo "1) Interfaz Web Premium (Recomendado - Carga masiva rápida y sin bloqueos)"
echo "2) Interfaz de Terminal (Textual CLI - Consola clásica)"
echo "============================================================"
read -p "Elige una opción [1-2, por defecto 1]: " opcion

if [ "$opcion" = "2" ]; then
    echo "Iniciando InteRComunicador CLI de consola..."
    ./venv/bin/python intercomunicador.py
else
    echo "Iniciando servidor web de InteRComunicador..."
    echo "Abre tu navegador en: http://localhost:8000"
    ./venv/bin/python web_server.py
fi
