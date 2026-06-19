# -*- coding: utf-8 -*-
"""
=============================================================================
SIMULACIÓN - OLIMPIADAS DE PYTHON
UTN FRC - Ingeniería en Sistemas de Información
TP5 - Grupo 18 - Ciclo lectivo 2026
=============================================================================
PUNTO DE ENTRADA PRINCIPAL Y SERVIDOR WEB
-----------------------------------------------------------------------------
Este archivo levanta un servidor HTTP embebido local que:
1. Sirve la interfaz de usuario (index.html, index.css, main.js).
2. Recibe peticiones POST en '/simular' con parámetros y ejecuta la simulación
   importando la lógica modular.

Para ejecutar:
  python simulacion.py
Luego abrir:
  http://localhost:8000
=============================================================================
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from simulador import simular

# ─────────────────────────────────────────────────────────────────────────────
#  SERVIDOR HTTP EMBEBIDO (PARA SERVIR ESTÁTICOS Y PROCESAR PETICIONES)
# ─────────────────────────────────────────────────────────────────────────────

class SimulacionHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Silenciar los logs de las peticiones para mantener limpia la consola
        pass
    
    def _enviar_cors(self):
        """Permite llamadas cruzadas (CORS) si se abre la UI desde un archivo local."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._enviar_cors()
        self.end_headers()
    
    def do_GET(self):
        # Sanitizar ruta para servir archivos estáticos (HTML, CSS, JS)
        ruta_solicitada = self.path.split('?')[0]
        
        if ruta_solicitada == '/' or ruta_solicitada == '/index.html':
            nombre_archivo = 'index.html'
            content_type = 'text/html; charset=utf-8'
        elif ruta_solicitada == '/index.css':
            nombre_archivo = 'index.css'
            content_type = 'text/css; charset=utf-8'
        elif ruta_solicitada == '/main.js':
            nombre_archivo = 'main.js'
            content_type = 'application/javascript; charset=utf-8'
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Archivo no encontrado')
            return

        try:
            ruta_completa = os.path.join(os.path.dirname(__file__), nombre_archivo)
            with open(ruta_completa, 'rb') as f:
                contenido = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self._enviar_cors()
            self.end_headers()
            self.wfile.write(contenido)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f'{nombre_archivo} no encontrado'.encode('utf-8'))
    
    def do_POST(self):
        if self.path == '/simular':
            # Leer el cuerpo de la petición (parámetros en JSON)
            largo = int(self.headers.get('Content-Length', 0))
            body  = self.rfile.read(largo)
            
            try:
                params = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                params = {}
            
            # Ejecutar el motor de simulación modular
            resultado = simular(params)
            respuesta = json.dumps(resultado, ensure_ascii=False)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self._enviar_cors()
            self.end_headers()
            self.wfile.write(respuesta.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == '__main__':
    PUERTO = 8000
    servidor = HTTPServer(('localhost', PUERTO), SimulacionHandler)
    print("=" * 60)
    print("  SIMULACIÓN OLIMPIADAS - UTN FRC - Grupo 18")
    print("  ARQUITECTURA MODULAR")
    print("=" * 60)
    print(f"  Servidor corriendo en http://localhost:{PUERTO}")
    print(f"  Abre http://localhost:{PUERTO} en tu navegador")
    print("  Presiona Ctrl+C para detener")
    print("=" * 60)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
