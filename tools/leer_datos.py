#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MARS-ROBOT · Lector de datos por USB
------------------------------------
Lee el CSV que el mBot2 imprime por el cable USB (modo "Subir") y lo
guarda en un archivo .csv en la computadora.

Uso:
    python3 tools/leer_datos.py
    python3 tools/leer_datos.py --puerto /dev/cu.usbserial-10 --salida datos.csv

Detener: Ctrl+C  (el archivo queda guardado).

Requisitos: pyserial   (pip install pyserial)

IMPORTANTE: antes de correr esto, DESCONECTA el robot en el editor de
mBlock (o cierra mLink), para que el puerto USB quede libre.
"""

import argparse
import sys
import time
from datetime import datetime

try:
    import serial               # pyserial
    from serial.tools import list_ports
except ImportError:
    print("Falta 'pyserial'. Instálalo con:  python3 -m pip install pyserial")
    sys.exit(1)

# La cabecera se detecta por su prefijo (sirve para el formato viejo de 12
# columnas y el nuevo de 20)
PREFIJO_CABECERA = "t_s,"


def detectar_puerto():
    """Busca un puerto USB-serial típico del CyberPi."""
    candidatos = []
    for p in list_ports.comports():
        nombre = (p.device or "")
        desc = ((p.description or "") + " " + (p.manufacturer or "")).lower()
        if "usbserial" in nombre or "usbmodem" in nombre or \
           any(k in desc for k in ("ch340", "cp210", "silicon", "wch", "usb")):
            candidatos.append(p.device)
    return candidatos


def main():
    ap = argparse.ArgumentParser(description="Lector de datos USB del mBot2 (MARS-ROBOT)")
    ap.add_argument("--puerto", help="Puerto serie (ej: /dev/cu.usbserial-10). Si se omite, se autodetecta.")
    ap.add_argument("--baud", type=int, default=115200, help="Baudios (por defecto 115200)")
    ap.add_argument("--salida", default="datos.csv", help="Archivo CSV de salida")
    args = ap.parse_args()

    puerto = args.puerto
    if not puerto:
        encontrados = detectar_puerto()
        if not encontrados:
            print("No se encontró ningún puerto USB. Puertos disponibles:")
            for p in list_ports.comports():
                print("   ", p.device, "-", p.description)
            print("\nConecta el robot por USB y vuelve a intentar,")
            print("o indica el puerto con --puerto /dev/cu.XXXX")
            sys.exit(1)
        puerto = encontrados[0]
        if len(encontrados) > 1:
            print("Varios puertos posibles:", encontrados)
        print("Puerto autodetectado:", puerto)

    print("Abriendo {} a {} baudios...".format(puerto, args.baud))
    try:
        ser = serial.Serial(puerto, args.baud, timeout=1)
    except serial.SerialException as e:
        print("ERROR al abrir el puerto:", e)
        print("¿Está el robot conectado y DESCONECTADO en mBlock/mLink?")
        sys.exit(1)

    # Nombre con marca de tiempo para no sobrescribir capturas previas
    base = args.salida
    if base.endswith(".csv"):
        base = base[:-4]
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta = "{}_{}.csv".format(base, sello)

    print("Guardando en:", ruta)
    print("Esperando datos del robot... (pulsa A en el mBot2)")
    print("Ctrl+C para detener y guardar.\n")

    filas = 0
    cabecera_escrita = False
    with open(ruta, "w", encoding="utf-8") as f:
        try:
            while True:
                linea = ser.readline().decode("utf-8", errors="replace").strip()
                if not linea:
                    continue
                print(linea)                    # eco en pantalla
                # Guarda la cabecera y las filas de datos; ignora comentarios "#"
                if linea.startswith("#"):
                    continue
                if linea.startswith(PREFIJO_CABECERA):
                    # La cabecera se reimprime cada vez que se pulsa A;
                    # solo se guarda la primera
                    if cabecera_escrita:
                        continue
                    cabecera_escrita = True
                else:
                    filas += 1
                f.write(linea + "\n")
                f.flush()
        except KeyboardInterrupt:
            print("\nDetenido. Filas de datos guardadas:", filas)
        finally:
            ser.close()
    print("Archivo guardado:", ruta)


if __name__ == "__main__":
    main()
