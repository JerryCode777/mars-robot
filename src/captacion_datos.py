# -*- coding: utf-8 -*-
# =====================================================================
#  MARS-ROBOT  ·  Sistema de captación de datos
#  Programación de Sistemas — UNSA
# ---------------------------------------------------------------------
#  Plataforma : mBot2 (CyberPi + mBot2 Shield)  /  MicroPython (mBlock)
#  Modo de ejecución: "Subir/Cargar" (Upload) — ver README §3.1
#
#  El robot SIGUE LA LÍNEA (recorrido rectilíneo) y, al mismo tiempo,
#  registra una fila CSV cada PERIODO_S segundos con:
#     - tiempo
#     - batería (%) y voltaje estimado (V)  +  batería extra del shield (%)
#     - inclinación en 3 ejes: roll, pitch, yaw (grados)
#     - aceleración en 3 ejes (m/s²)  +  giroscopio en 3 ejes (°/s)
#     - velocidad de AMBAS ruedas (RPM, del encoder si el firmware lo expone)
#     - distancia recorrida (cm, del ángulo acumulado del encoder)
#     - estado del sensor de línea + desviación de la línea (-100..100)
#     - luz ambiente (sensor del CyberPi)
#
#  Botón A = iniciar   ·   Botón B = detener
#
#  MODO DE USO: subir al dispositivo (Upload). El CSV se imprime con
#  print(), que sale por el cable USB, y el lector de la PC
#  (tools/leer_datos.py) lo guarda en datos.csv.
# =====================================================================

import time
import cyberpi
import mbuild
import mbot2

# ---------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------
PERIODO_S = 0.1          # intervalo MÍNIMO entre muestras (la tasa real la pone el bucle)
IDX_QUAD  = 1            # índice del sensor Quad RGB en la cadena mBuild
CADA_PANTALLA = 10       # refrescar la pantalla del robot 1 de cada N muestras (es lenta)
DIAM_RUEDA_CM = 4.8      # diámetro de la rueda del mBot2 — CALIBRAR: rodar 100 cm
                         # midiendo dist_cm y ajustar este valor en proporción

# --- Ajuste del seguidor de línea ---
# Si se sale en las curvas: BAJA VEL_BASE. Si va muy lento: súbela.
VEL_BASE  = 20          # velocidad recto (antes 30). Más lento = más control
VEL_SUAVE = 12          # rueda interior en corrección leve
VEL_FUERTE = 4          # rueda interior en corrección fuerte

# Batería LiPo de 1 celda del mBot2 (ver docs/01-medicion-voltaje.md)
V_MIN = 3.3              # voltaje con batería vacía
V_MAX = 4.2             # voltaje con batería llena

# --- Voltaje REAL por divisor resistivo en el puerto de extensión (opcional) ---
# El % de get_battery() casi no varía, así que el voltaje derivado es grueso.
# Con 2 resistencias (batería+ → R1 → S1 → R2 → GND) se mide el voltaje REAL:
#   se activa poniendo PIN_VOLTAJE = "S1"  (ver docs/01-medicion-voltaje.md §8)
PIN_VOLTAJE = None       # "S1" cuando el divisor esté conectado; None = estimar por %
DIV_R1 = 10000.0         # ohmios, resistencia superior (a batería +)
DIV_R2 = 20000.0         # ohmios, resistencia inferior (a GND)
ADC_MAX = 100.0          # mbot2.read_analog devuelve 0..100
ADC_VREF = 3.3           # voltaje de referencia del ADC (V)


# ---------------------------------------------------------------------
# LECTURAS
# ---------------------------------------------------------------------
def leer_voltaje():
    """
    Devuelve (pct, voltios). Si PIN_VOLTAJE está configurado, el voltaje es
    REAL (divisor resistivo en el puerto de extensión); si no, se estima
    desde el % de batería (grueso: el % casi no varía en recorridos cortos).
    """
    pct = cyberpi.get_battery()                 # 0–100 (%)
    if PIN_VOLTAJE:
        try:
            lectura = mbot2.read_analog(PIN_VOLTAJE)          # 0..100
            v_pin = lectura / ADC_MAX * ADC_VREF              # voltios en el pin
            return pct, v_pin * (DIV_R1 + DIV_R2) / DIV_R2    # deshacer el divisor
        except:
            pass
    return pct, V_MIN + (pct / 100) * (V_MAX - V_MIN)


# --- Encoder: resolver la función y su forma de llamada UNA sola vez ---
# (el nombre exacto no está documentado; ver src/probe_encoder.py)
def _resolver(mod, nombres):
    for n in nombres:
        fn = getattr(mod, n, None)
        if fn is not None:
            return fn
    return None


def _detectar_arg(fn):
    """Descubre si la función se llama con 1/2 o con "EM1"/"EM2"."""
    if fn is None:
        return None
    for arg in (1, "EM1"):
        try:
            fn(arg)
            return arg
        except:
            pass
    return None


_fn_vel = _resolver(mbot2, ("EM_get_speed", "encoder_motor_get_speed", "get_speed"))
_fn_ang = _resolver(mbot2, ("EM_get_angle", "encoder_motor_get_angle", "get_angle"))
_arg_vel = _detectar_arg(_fn_vel)
_arg_ang = _detectar_arg(_fn_ang)


def _motor2(arg):
    return 2 if arg == 1 else "EM2"


def leer_velocidades(vel_comandada):
    """
    Velocidad de AMBAS ruedas en RPM (encoder), si el firmware lo expone.
    Si no, usa la velocidad comandada como respaldo (el script no falla).
    Devuelve (vel_em1, vel_em2, es_real).
    """
    if _arg_vel is not None:
        try:
            return _fn_vel(_arg_vel), _fn_vel(_motor2(_arg_vel)), True
        except:
            pass
    return vel_comandada, vel_comandada, False


def leer_distancia():
    """Distancia recorrida (cm) desde el ángulo acumulado del encoder EM1."""
    if _arg_ang is not None:
        try:
            ang = _fn_ang(_arg_ang)
            return abs(ang) / 360.0 * 3.1416 * DIAM_RUEDA_CM
        except:
            pass
    return 0.0


def leer_extras():
    """Sensores adicionales; cada uno con respaldo a 0 si no está disponible."""
    try:
        gx, gy, gz = cyberpi.get_gyro("x"), cyberpi.get_gyro("y"), cyberpi.get_gyro("z")
    except:
        gx = gy = gz = 0.0
    try:
        ofs = mbuild.quad_rgb_sensor.get_offset_track(IDX_QUAD)  # -100..100
    except:
        ofs = 0
    try:
        bat2 = cyberpi.get_extra_battery()   # batería del mBot2 Shield (%)
    except:
        bat2 = 0
    try:
        luz = cyberpi.get_brightness()       # luz ambiente del CyberPi
    except:
        luz = 0
    return gx, gy, gz, ofs, bat2, luz


# ---------------------------------------------------------------------
# SEGUIDOR DE LÍNEA  (lógica probada con get_ground_sta)
# ---------------------------------------------------------------------
# Memoria del último lado donde se vio la línea (para recuperarla si se pierde)
#   -1 = línea hacia un lado   ·   +1 = hacia el otro   ·   0 = centrada
_ultimo_lado = 0
_ultimo_estado = 6      # último estado válido del sensor (arranca como "centrado")
_error_sensor = False   # ya se reportó un error del sensor de línea


def seguir_linea():
    """
    Sigue la línea con corrección graduada y RECUPERACIÓN cuando la pierde.
    Recto = drive_speed(v, -v)  (el motor derecho lleva signo negativo).
    Devuelve (estado_sensor, vel_comandada).
    """
    global _ultimo_lado, _ultimo_estado, _error_sensor
    # El bus mBuild puede fallar (lectura esporádica perdida o sensor
    # desconectado): si la lectura falla, se usa el último estado conocido en
    # vez de detener el programa, y el error real se reporta UNA vez por USB
    # y en la pantalla para poder diagnosticarlo.
    try:
        estado = mbuild.quad_rgb_sensor.get_ground_sta("all", IDX_QUAD)
        _ultimo_estado = estado
    except Exception as e:
        if not _error_sensor:
            _error_sensor = True
            print("# ERROR sensor de linea:", repr(e))
            cyberpi.display.show_label("ERR sensor linea!", 12, 0, 60, index=3)
        estado = _ultimo_estado

    # --- CENTRADO: sondas centrales sobre la línea ---
    if estado == 6:
        izq, der = VEL_BASE, VEL_BASE
        _ultimo_lado = 0

    # --- DESVIACIÓN A UN LADO (grupo "izquierda") ---
    elif estado in (14, 12, 4):          # leve / media -> corrección suave
        izq, der = VEL_SUAVE, VEL_BASE
        _ultimo_lado = -1
    elif estado == 8:                    # fuerte (solo sonda externa)
        izq, der = VEL_FUERTE, VEL_BASE
        _ultimo_lado = -1

    # --- DESVIACIÓN AL OTRO LADO (grupo "derecha") ---
    elif estado in (7, 3, 2):            # leve / media -> corrección suave
        izq, der = VEL_BASE, VEL_SUAVE
        _ultimo_lado = 1
    elif estado == 1:                    # fuerte (solo sonda externa)
        izq, der = VEL_BASE, VEL_FUERTE
        _ultimo_lado = 1

    # --- LÍNEA PERDIDA (estado 0, 15, u otro): girar a buscarla ---
    else:
        if _ultimo_lado < 0:             # se vio por última vez a un lado
            izq, der = 0, VEL_BASE       # pivota hacia ese lado
        elif _ultimo_lado > 0:
            izq, der = VEL_BASE, 0       # pivota al otro lado
        else:
            izq, der = VEL_SUAVE, VEL_SUAVE   # sin memoria: avanza lento

    mbot2.drive_speed(izq, -der)
    vel_cmd = (izq + der) // 2
    return estado, vel_cmd


def registrar(t, estado, vel_cmd, con_pantalla):
    """Lee todos los sensores e imprime una fila CSV (20 columnas)."""
    pct, volt      = leer_voltaje()
    roll           = cyberpi.get_roll()
    pitch          = cyberpi.get_pitch()
    yaw            = cyberpi.get_yaw()
    ax             = cyberpi.get_acc("x")
    ay             = cyberpi.get_acc("y")
    az             = cyberpi.get_acc("z")
    v1, v2, v_real = leer_velocidades(vel_cmd)
    dist           = leer_distancia()
    gx, gy, gz, ofs, bat2, luz = leer_extras()

    print(
        "{:.1f},{},{:.2f},{:.1f},{:.1f},{:.1f},{:.2f},{:.2f},{:.2f},{:.1f},{},{},"
        "{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{},{},{}".format(
            t, pct, volt, roll, pitch, yaw, ax, ay, az,
            v1, 1 if v_real else 0, estado,
            v2, dist, gx, gy, gz, ofs, bat2, luz
        )
    )
    # Vista rápida en la pantalla del robot (lenta: solo 1 de cada CADA_PANTALLA)
    if con_pantalla:
        cyberpi.display.show_label("{:.1f}V  {}%".format(volt, pct), 12, 0, 0, index=0)
        cyberpi.display.show_label("R{:.0f} P{:.0f} Y{:.0f}".format(roll, pitch, yaw), 12, 0, 20, index=1)
        cyberpi.display.show_label("est {}  {:.0f}cm".format(estado, dist), 12, 0, 40, index=2)


# ---------------------------------------------------------------------
# PROGRAMA PRINCIPAL  (bucle que vigila los botones)
# ---------------------------------------------------------------------
cyberpi.display.clear()
cyberpi.display.show_label("MARS-ROBOT", 16, 0, 0, index=0)
cyberpi.display.show_label("A: iniciar", 12, 0, 30, index=1)
cyberpi.display.show_label("B: detener", 12, 0, 45, index=2)
print("# Listo. Pulsa A en el robot para iniciar.")

capturando = False
inicio = 0
ultimo = 0
muestras = 0

while True:
    # --- Botón A: iniciar la captura ---
    if cyberpi.controller.is_press("a") and not capturando:
        capturando = True
        inicio = time.ticks_ms()
        ultimo = inicio
        muestras = 0
        cyberpi.display.clear()
        print(
            "t_s,bateria_pct,voltaje_v,roll,pitch,yaw,acc_x,acc_y,acc_z,vel_rpm,vel_real,estado,"
            "vel2_rpm,dist_cm,gyro_x,gyro_y,gyro_z,ofs_linea,bat2_pct,luz"
        )

    # --- Botón B: detener la captura ---
    if cyberpi.controller.is_press("b") and capturando:
        capturando = False
        mbot2.EM_stop()
        print("# --- fin de la captura ---")
        cyberpi.display.clear()
        cyberpi.display.show_label("FIN captura", 16, 0, 20, index=0)

    # --- Mientras captura: seguir la línea + registrar datos ---
    if capturando:
        estado, vel_cmd = seguir_linea()     # cada vuelta (fluido)

        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, ultimo) >= int(PERIODO_S * 1000):
            ultimo = ahora
            t = time.ticks_diff(ahora, inicio) / 1000.0
            muestras += 1
            registrar(t, estado, vel_cmd, muestras % CADA_PANTALLA == 1)
