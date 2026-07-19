# -*- coding: utf-8 -*-
# =====================================================================
#  MARS-ROBOT · SONDA del encoder
# ---------------------------------------------------------------------
#  Programa de diagnóstico: le pregunta al robot qué funciones tiene
#  realmente para LEER la velocidad del encoder.
#
#  USO:
#   1) Súbelo al robot (modo "Subir / Cargar")
#   2) Desconecta en mBlock (libera el USB)
#   3) En la Terminal:  python3 tools/leer_datos.py
#   4) Pulsa A en el robot
#   5) Copia lo que salga y pásamelo
# =====================================================================

import cyberpi
import mbot2
import mbuild
import time

cyberpi.display.clear()
cyberpi.display.show_label("SONDA encoder", 16, 0, 0, index=0)
cyberpi.display.show_label("A: iniciar", 12, 0, 30, index=1)

while not cyberpi.controller.is_press("a"):
    pass

cyberpi.display.clear()
cyberpi.display.show_label("Sondeando...", 16, 0, 20, index=0)

# --- 1) Todas las funciones del módulo mbot2 ---
print("### INICIO SONDA ###")
print("### FUNCIONES DE mbot2 ###")
for nombre in dir(mbot2):
    if not nombre.startswith("_"):
        print("mbot2." + nombre)

# --- 2) Probar los nombres candidatos para leer velocidad ---
print("### PRUEBA DE CANDIDATOS ###")
candidatos = [
    "EM_get_speed",
    "EM_get_angle",
    "encoder_motor_get_speed",
    "encoder_motor_get_angle",
    "get_speed",
    "get_angle",
    "encoder_motor_get_pos",
    "motor_get_speed",
    "get_encoder_speed",
]

# El robot debe estar MOVIÉNDOSE para que el encoder marque algo
mbot2.drive_speed(30, -30)
time.sleep(1)

for c in candidatos:
    fn = getattr(mbot2, c, None)
    if fn is None:
        print(c + " -> NO EXISTE")
        continue
    # Probar distintas formas de llamarla
    for arg in ("EM1", "em1", 1, None):
        try:
            valor = fn() if arg is None else fn(arg)
            print(c + "(" + str(arg) + ") -> " + str(valor))
        except Exception as e:
            print(c + "(" + str(arg) + ") -> ERROR " + str(e))

mbot2.EM_stop()

# --- 3) Funciones de mbuild (por si el encoder está ahí) ---
print("### FUNCIONES DE mbuild ###")
for nombre in dir(mbuild):
    if not nombre.startswith("_"):
        print("mbuild." + nombre)

print("### FIN SONDA ###")
cyberpi.display.clear()
cyberpi.display.show_label("FIN sonda", 16, 0, 20, index=0)
