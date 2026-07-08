#!/bin/bash
# Desktop launcher script for InteRComunicador

cd "/home/juan/Datos/Datos Juan/ProyectosSoftware/Co-Libri Learning/InteRComunicador"

# Check if the port 8000 is already active
if lsof -pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    # Already running, just open the browser
    xdg-open "http://127.0.0.1:8000"
else
    # Start the server (web_server.py will automatically open the browser via startup event)
    ./venv/bin/python web_server.py
fi
