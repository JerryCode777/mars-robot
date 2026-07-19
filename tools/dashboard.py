#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARS-ROBOT · Panel de datos en tiempo real (local)
--------------------------------------------------
Sirve un panel web local con gráficos en vivo. La conexión con el robot se
inicia DESDE EL PANEL con el botón "Iniciar captura" (equivale a correr
leer_datos.py): el panel confirma la conexión, pide pulsar A en el carrito,
y desde ahí grafica los datos y guarda el CSV igual que siempre.

Uso (con el robot, mismo flujo de siempre):
    1) Subir src/captacion_datos.py al robot (modo Cargar) y desconectar en mBlock
    2) python3 tools/dashboard.py
    3) Abrir  http://localhost:8765  y pulsar "Iniciar captura"
    4) Pulsar A en el robot cuando el panel lo pida

Modos de prueba SIN robot (mismo flujo con botón):
    python3 tools/dashboard.py --replay datos_20260713_183211.csv
    python3 tools/dashboard.py --demo

Detener: botón "Detener" en el panel (el CSV queda guardado) o Ctrl+C aquí.
Requisitos: pyserial (solo para el modo USB).
"""

import argparse
import json
import math
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CABECERA = ("t_s,bateria_pct,voltaje_v,roll,pitch,yaw,acc_x,acc_y,acc_z,vel_rpm,vel_real,estado,"
            "vel2_rpm,dist_cm,gyro_x,gyro_y,gyro_z,ofs_linea,bat2_pct,luz")
NUM_COLS = len(CABECERA.split(","))          # formato nuevo: 20 columnas
NUM_COLS_VIEJO = 12                          # capturas anteriores a julio 2026
AQUI = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------
# ALMACÉN COMPARTIDO (hilo lector <-> servidor web)
# ---------------------------------------------------------------------
class Datos:
    def __init__(self):
        self.lock = threading.Lock()
        self.filas = []          # cada fila = lista de 12 números
        self.captura = 0         # +1 cada vez que llega la cabecera (pulsación de A)
        self.fin = False         # se vio "# --- fin de la captura ---"
        self.estado = "inactivo" # inactivo | conectando | escuchando | error
        self.mensaje = ""
        self.meta = {"modo": "", "puerto": "", "archivo": ""}
        self.stop = threading.Event()
        self.hilo = None

    def nueva_captura(self):
        with self.lock:
            self.captura += 1
            self.filas = []
            self.fin = False

    def agregar(self, fila):
        with self.lock:
            self.filas.append(fila)

    def marcar_fin(self):
        with self.lock:
            self.fin = True

    def snapshot(self, desde, captura_cliente):
        with self.lock:
            # Si el cliente viene de otra captura, se le manda todo desde cero
            if captura_cliente != self.captura:
                desde = 0
            desde = max(0, min(desde, len(self.filas)))
            return {
                "captura": self.captura,
                "desde": desde,
                "total": len(self.filas),
                "filas": self.filas[desde:],
                "fin": self.fin,
                "estado": self.estado,
                "mensaje": self.mensaje,
                "meta": self.meta,
            }


def parsear_fila(linea):
    """
    CSV -> lista de 20 números, o None si la línea no es una fila válida.
    Las capturas viejas (12 columnas) se rellenan con None al final para que
    el panel las siga pudiendo reproducir.
    """
    partes = linea.split(",")
    if len(partes) not in (NUM_COLS, NUM_COLS_VIEJO):
        return None
    try:
        fila = [float(p) for p in partes]
    except ValueError:
        return None
    if len(fila) < NUM_COLS:
        fila += [None] * (NUM_COLS - len(fila))
    return fila


def procesar_linea(linea, datos, archivo_csv):
    """Trata una línea recibida: cabecera, comentario o fila de datos."""
    if linea.startswith("t_s,"):
        datos.nueva_captura()
        if archivo_csv and archivo_csv.tell() == 0:
            archivo_csv.write(linea + "\n")
            archivo_csv.flush()
        return
    if linea.startswith("#"):
        if "fin" in linea.lower():
            datos.marcar_fin()
        return
    fila = parsear_fila(linea)
    if fila is not None:
        datos.agregar(fila)
        if archivo_csv:
            archivo_csv.write(linea + "\n")
            archivo_csv.flush()


# ---------------------------------------------------------------------
# FUENTES DE DATOS (arrancan con el botón "Iniciar captura" del panel)
# ---------------------------------------------------------------------
def fuente_serial(datos, config):
    """Lee el puerto USB del robot y guarda el CSV (mismo flujo que leer_datos.py)."""
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        datos.estado = "error"
        datos.mensaje = "Falta pyserial en la PC. Instálalo con: python3 -m pip install pyserial"
        return

    puerto = config["puerto"]
    if not puerto:
        candidatos = []
        for p in list_ports.comports():
            nombre = (p.device or "")
            desc = ((p.description or "") + " " + (p.manufacturer or "")).lower()
            if "usbserial" in nombre or "usbmodem" in nombre or \
               any(k in desc for k in ("ch340", "cp210", "silicon", "wch", "usb")):
                candidatos.append(p.device)
        if not candidatos:
            datos.estado = "error"
            datos.mensaje = ("No se encontró el puerto USB del robot. "
                             "¿Está conectado por cable y desconectado en mBlock/mLink?")
            return
        puerto = candidatos[0]

    try:
        ser = serial.Serial(puerto, config["baud"], timeout=1)
    except serial.SerialException as e:
        datos.estado = "error"
        datos.mensaje = ("No se pudo abrir {} (¿el puerto sigue ocupado por mBlock/mLink? "
                         "Desconecta el robot ahí y reintenta). Detalle: {}".format(puerto, e))
        return

    salida = config["salida"]
    base = salida[:-4] if salida.endswith(".csv") else salida
    ruta = "{}_{}.csv".format(base, datetime.now().strftime("%Y%m%d_%H%M%S"))
    datos.meta.update({"modo": "usb", "puerto": puerto, "archivo": os.path.basename(ruta)})
    datos.estado = "escuchando"
    datos.mensaje = puerto
    print("Conectado a {} · guardando en {}".format(puerto, ruta))

    try:
        with open(ruta, "w", encoding="utf-8") as f:
            while not datos.stop.is_set():
                linea = ser.readline().decode("utf-8", errors="replace").strip()
                if linea:
                    procesar_linea(linea, datos, f)
    finally:
        ser.close()
        datos.estado = "inactivo"
        datos.mensaje = "Captura cerrada. CSV guardado: " + os.path.basename(ruta)
        print("Puerto cerrado. CSV guardado:", ruta)


def fuente_replay(datos, config):
    """Reproduce un CSV ya grabado respetando los tiempos (para probar sin robot)."""
    ruta, factor = config["replay"], config["factor"]
    datos.meta.update({"modo": "replay", "puerto": "-",
                       "archivo": os.path.basename(ruta) + " (replay)"})
    datos.estado = "escuchando"
    datos.mensaje = "replay — la 'pulsación de A' llega sola en unos segundos"
    try:
        with open(ruta, encoding="utf-8") as f:
            lineas = [l.strip() for l in f if l.strip()]
    except OSError as e:
        datos.estado = "error"
        datos.mensaje = "No se pudo leer el CSV: {}".format(e)
        return
    time.sleep(3)                       # simula la espera hasta pulsar A
    if datos.stop.is_set():
        datos.estado = "inactivo"
        return
    datos.nueva_captura()
    t_previo = None
    for linea in lineas:
        if datos.stop.is_set():
            break
        fila = parsear_fila(linea)
        if fila is None:
            continue
        if t_previo is not None:
            time.sleep(max(0.0, (fila[0] - t_previo)) / factor)
        t_previo = fila[0]
        datos.agregar(fila)
    datos.marcar_fin()
    datos.estado = "inactivo"
    datos.mensaje = "Replay terminado."


def fuente_demo(datos, config):
    """Genera datos sintéticos parecidos a una corrida real (para probar sin robot)."""
    import random
    datos.meta.update({"modo": "demo", "puerto": "-", "archivo": "(demo, no se guarda)"})
    datos.estado = "escuchando"
    datos.mensaje = "demo — la 'pulsación de A' llega sola en unos segundos"
    time.sleep(4)                       # simula la espera hasta pulsar A
    if datos.stop.is_set():
        datos.estado = "inactivo"
        return
    datos.nueva_captura()
    t, pct, dist = 0.0, 78, 0.0
    pitch_ant = roll_ant = 0.0
    while not datos.stop.is_set():
        t += 0.15
        pitch = 18 * math.sin(t / 9) + random.uniform(-1.5, 1.5)
        roll = 6 * math.sin(t / 5 + 1) + random.uniform(-1, 1)
        yaw = 25 * math.sin(t / 15)
        gx = (roll - roll_ant) / 0.15 + random.uniform(-3, 3)
        gy = (pitch - pitch_ant) / 0.15 + random.uniform(-3, 3)
        roll_ant, pitch_ant = roll, pitch
        if random.random() < 0.005:
            pct = max(5, pct - 1)
        volt = 3.3 + pct / 100 * 0.9
        vel = 16 + 4 * math.sin(t / 4) + random.uniform(-2, 2) - abs(pitch) * 0.15
        vel2 = vel + random.uniform(-1.5, 1.5)
        dist += max(0, vel) / 60 * 15.1 * 0.15    # RPM -> cm con rueda de ~4,8 cm
        estado = random.choices([6, 4, 2, 14, 7, 8, 1, 0],
                                weights=[55, 10, 10, 6, 6, 5, 5, 3])[0]
        ofs = {6: 0, 4: -30, 14: -30, 12: -30, 2: 30, 7: 30, 3: 30,
               8: -80, 1: 80}.get(estado, 100) + random.randint(-10, 10)
        az = -9.8 + random.uniform(-0.3, 0.3)
        datos.agregar([round(t, 1), pct, round(volt, 2), round(roll, 1),
                       round(pitch, 1), round(yaw, 1), round(random.uniform(-0.5, 0.5), 2),
                       round(random.uniform(-0.5, 0.5), 2), round(az, 2),
                       round(max(0, vel), 1), 1, estado,
                       round(max(0, vel2), 1), round(dist, 1),
                       round(gx, 1), round(gy, 1), round(random.uniform(-5, 5), 1),
                       max(-100, min(100, ofs)), pct, random.randint(38, 46)])
        time.sleep(0.15)
    datos.marcar_fin()
    datos.estado = "inactivo"
    datos.mensaje = "Demo detenida."


FUENTES = {"usb": fuente_serial, "replay": fuente_replay, "demo": fuente_demo}


def iniciar_fuente(datos, config):
    """Arranca el hilo lector si no está ya corriendo. Devuelve (ok, mensaje)."""
    if datos.hilo is not None and datos.hilo.is_alive():
        return True, "ya estaba iniciado"
    datos.stop.clear()
    datos.estado = "conectando"
    datos.mensaje = ""
    datos.fin = False
    datos.hilo = threading.Thread(target=FUENTES[config["modo"]], args=(datos, config))
    datos.hilo.daemon = True
    datos.hilo.start()
    return True, "iniciando"


# ---------------------------------------------------------------------
# SERVIDOR WEB LOCAL
# ---------------------------------------------------------------------
class Manejador(BaseHTTPRequestHandler):
    datos = None    # se asignan en main()
    config = None

    def _responder(self, cuerpo, tipo):
        self.send_response(200)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj):
        self._responder(json.dumps(obj).encode("utf-8"), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            try:
                with open(os.path.join(AQUI, "dashboard_web.html"), "rb") as f:
                    self._responder(f.read(), "text/html")
            except OSError:
                self.send_error(500, "Falta tools/dashboard_web.html")
        elif u.path == "/datos":
            q = parse_qs(u.query)
            desde = int(q.get("desde", ["0"])[0])
            captura = int(q.get("captura", ["-1"])[0])
            self._json(self.datos.snapshot(desde, captura))
        else:
            self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/iniciar":
            ok, msj = iniciar_fuente(self.datos, self.config)
            self._json({"ok": ok, "mensaje": msj})
        elif u.path == "/detener":
            self.datos.stop.set()
            self._json({"ok": True, "mensaje": "deteniendo"})
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass  # silenciar el log por cada petición


def main():
    ap = argparse.ArgumentParser(description="Panel web local del MARS-ROBOT")
    ap.add_argument("--puerto", help="Puerto serie del robot (autodetecta si se omite)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--salida", default="datos.csv", help="Base del CSV de salida")
    ap.add_argument("--web", type=int, default=8765, help="Puerto del panel web")
    ap.add_argument("--replay", metavar="CSV", help="Reproducir un CSV grabado (sin robot)")
    ap.add_argument("--factor", type=float, default=1.0, help="Velocidad del replay (2 = doble)")
    ap.add_argument("--demo", action="store_true", help="Datos sintéticos (sin robot)")
    args = ap.parse_args()

    modo = "replay" if args.replay else ("demo" if args.demo else "usb")
    Manejador.datos = Datos()
    Manejador.datos.meta["modo"] = modo
    Manejador.config = {"modo": modo, "puerto": args.puerto, "baud": args.baud,
                        "salida": args.salida, "replay": args.replay, "factor": args.factor}

    servidor = ThreadingHTTPServer(("127.0.0.1", args.web), Manejador)
    print("Panel disponible en  http://localhost:{}".format(args.web))
    print("La captura se inicia desde el panel con el botón 'Iniciar captura'. Ctrl+C para salir.")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
        Manejador.datos.stop.set()
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
