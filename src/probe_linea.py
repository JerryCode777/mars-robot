# -*- coding: utf-8 -*-
# =====================================================================
#  MARS-ROBOT · SONDA del sensor de línea (Quad RGB)
# ---------------------------------------------------------------------
#  Diagnóstico del error "module object has no attribute get_ground_sta":
#  pregunta al firmware qué hay realmente dentro de mbuild y de
#  quad_rgb_sensor, y prueba la lectura con varios índices.
#
#  USO:
#   1) Subir al robot (modo "Subir/Cargar") y desconectar en mBlock
#   2) python3 tools/dashboard.py  (o leer_datos.py) y pulsar A
#   3) Copiar la salida y revisarla
# =====================================================================

import cyberpi
import mbuild

cyberpi.display.clear()
cyberpi.display.show_label("SONDA linea", 16, 0, 0, index=0)
cyberpi.display.show_label("A: iniciar", 12, 0, 30, index=1)

while not cyberpi.controller.is_press("a"):
    pass

cyberpi.display.clear()
cyberpi.display.show_label("Sondeando...", 16, 0, 20, index=0)

print("### INICIO SONDA LINEA ###")

print("### CONTENIDO DE mbuild ###")
for nombre in dir(mbuild):
    if not nombre.startswith("_"):
        print("mbuild." + nombre)

print("### CONTENIDO DE mbuild.quad_rgb_sensor ###")
try:
    for nombre in dir(mbuild.quad_rgb_sensor):
        if not nombre.startswith("_"):
            print("quad_rgb_sensor." + nombre)
except Exception as e:
    print("no se pudo listar:", repr(e))

print("### PRUEBAS DE LECTURA ###")
for indice in (1, 2, 0):
    try:
        v = mbuild.quad_rgb_sensor.get_ground_sta("all", indice)
        print("get_ground_sta('all', {}) -> {}".format(indice, v))
    except Exception as e:
        print("get_ground_sta('all', {}) -> ERROR {}".format(indice, repr(e)))
try:
    v = mbuild.quad_rgb_sensor.get_offset_track(1)
    print("get_offset_track(1) ->", v)
except Exception as e:
    print("get_offset_track(1) -> ERROR", repr(e))

print("### FIN SONDA LINEA ###")
cyberpi.display.clear()
cyberpi.display.show_label("FIN sonda", 16, 0, 20, index=0)
