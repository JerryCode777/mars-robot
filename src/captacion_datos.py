# -*- coding: utf-8 -*-
# =====================================================================
#  MARS-ROBOT  ·  Sistema de captación de datos
#  Programación de Sistemas — UNSA
# ---------------------------------------------------------------------
#  Plataforma : mBot2 (CyberPi + mBot2 Shield)  /  MicroPython (mBlock)
#  Modo de ejecución: "Subir/Cargar" (Upload)
# =====================================================================

import time
import cyberpi
import mbuild
import mbot2

# ---------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------
PERIODO_S = 0.1          # Intervalo MÍNIMO entre muestras (segundos)
IDX_QUAD  = 1            # Índice del sensor Quad RGB en mBuild
CADA_PANTALLA = 10       # Refrescar pantalla cada N muestras
DIAM_RUEDA_CM = 4.8      # Diámetro de la rueda del mBot2 (cm)

# --- Ajuste del seguidor de línea ---
VEL_BASE  = 20           # Velocidad en recta
VEL_SUAVE = 12           # Rueda interior en corrección leve
VEL_FUERTE = 4           # Rueda interior en corrección fuerte

# Batería LiPo de 1 celda del mBot2
V_MIN = 3.3              # Voltaje batería vacía
V_MAX = 4.2              # Voltaje batería llena

# Voltaje opcional por divisor resistivo
PIN_VOLTAJE = None       # "S1" si está conectado; None = estimar por %
DIV_R1 = 10000.0
DIV_R2 = 20000.0
ADC_MAX = 100.0
ADC_VREF = 3.3


# ---------------------------------------------------------------------
# DETECCIÓN SEGURO DE ENCODERS
# ---------------------------------------------------------------------
_encoder_init = False
_fn_vel = None
_fn_ang = None
_arg_vel = None
_arg_ang = None

def _resolver(mod, nombres):
    for n in nombres:
        fn = getattr(mod, n, None)
        if fn is not None:
            return fn
    return None

def _detectar_arg(fn):
    if fn is None:
        return None
    for arg in (1, "EM1"):
        try:
            fn(arg)
            return arg
        except:
            pass
    return None

def inicializar_encoders():
    global _encoder_init, _fn_vel, _fn_ang, _arg_vel, _arg_ang
    if _encoder_init:
        return
    _encoder_init = True
    try:
        _fn_vel = _resolver(mbot2, ("EM_get_speed", "encoder_motor_get_speed", "get_speed"))
        _fn_ang = _resolver(mbot2, ("EM_get_angle", "encoder_motor_get_angle", "get_angle"))
        _arg_vel = _detectar_arg(_fn_vel)
        _arg_ang = _detectar_arg(_fn_ang)
    except:
        pass


# ---------------------------------------------------------------------
# LECTURAS DE SENSORES Y MOTORES
# ---------------------------------------------------------------------
def detener_motores():
    """Detiene motores sin importar la versión de API."""
    try:
        mbot2.EM_stop()
    except:
        pass
    try:
        mbot2.drive_speed(0, 0)
    except:
        pass


def leer_voltaje():
    pct = cyberpi.get_battery()
    if PIN_VOLTAJE:
        try:
            lectura = mbot2.read_analog(PIN_VOLTAJE)
            v_pin = lectura / ADC_MAX * ADC_VREF
            return pct, v_pin * (DIV_R1 + DIV_R2) / DIV_R2
        except:
            pass
    return pct, V_MIN + (pct / 100.0) * (V_MAX - V_MIN)


def _motor2(arg):
    return 2 if arg == 1 else "EM2"


def leer_velocidades(vel_comandada):
    inicializar_encoders()
    if _arg_vel is not None:
        try:
            return _fn_vel(_arg_vel), _fn_vel(_motor2(_arg_vel)), True
        except:
            pass
    return vel_comandada, vel_comandada, False


def leer_distancia():
    inicializar_encoders()
    if _arg_ang is not None:
        try:
            ang = _fn_ang(_arg_ang)
            return abs(ang) / 360.0 * 3.1416 * DIAM_RUEDA_CM
        except:
            pass
    return 0.0


def leer_extras():
    try:
        gx = cyberpi.get_gyro("x")
        gy = cyberpi.get_gyro("y")
        gz = cyberpi.get_gyro("z")
    except:
        gx = gy = gz = 0.0

    try:
        ofs = mbuild.quad_rgb_sensor.get_offset_track(IDX_QUAD)
    except:
        ofs = 0

    try:
        bat2 = cyberpi.get_extra_battery()
    except:
        bat2 = 0

    try:
        luz = cyberpi.get_brightness()
    except:
        luz = 0

    return gx, gy, gz, ofs, bat2, luz


# ---------------------------------------------------------------------
# LECTURA DE SENSOR DE LÍNEA MULTINIVEL
# ---------------------------------------------------------------------
def obtener_estado_sensor():
    """Prueba múltiples métodos para obtener el estado binario del sensor."""
    # Método 1: get_ground_sta
    try:
        return mbuild.quad_rgb_sensor.get_ground_sta("all", IDX_QUAD)
    except:
        pass

    # Método 2: get_line_sta
    try:
        return mbuild.quad_rgb_sensor.get_line_sta("all", IDX_QUAD)
    except:
        pass

    # Método 3: Reconstrucción manual con is_line (L2=8, L1=4, R1=2, R2=1)
    try:
        l2 = 1 if mbuild.quad_rgb_sensor.is_line("L2", IDX_QUAD) else 0
        l1 = 1 if mbuild.quad_rgb_sensor.is_line("L1", IDX_QUAD) else 0
        r1 = 1 if mbuild.quad_rgb_sensor.is_line("R1", IDX_QUAD) else 0
        r2 = 1 if mbuild.quad_rgb_sensor.is_line("R2", IDX_QUAD) else 0
        return (l2 << 3) | (l1 << 2) | (r1 << 1) | r2
    except:
        pass

    return 0


# ---------------------------------------------------------------------
# SEGUIDOR DE LÍNEA
# ---------------------------------------------------------------------
_ultimo_lado = 0

def seguir_linea():
    global _ultimo_lado

    estado = obtener_estado_sensor()

    # --- CENTRADO (L1 + R1) ---
    if estado == 6:
        izq, der = VEL_BASE, VEL_BASE
        _ultimo_lado = 0

    # --- DESVIACIÓN IZQUIERDA ---
    elif estado in (14, 12, 4):          # Leve / Media
        izq, der = VEL_SUAVE, VEL_BASE
        _ultimo_lado = -1
    elif estado == 8:                    # Fuerte
        izq, der = VEL_FUERTE, VEL_BASE
        _ultimo_lado = -1

    # --- DESVIACIÓN DERECHA ---
    elif estado in (7, 3, 2):            # Leve / Media
        izq, der = VEL_BASE, VEL_SUAVE
        _ultimo_lado = 1
    elif estado == 1:                    # Fuerte
        izq, der = VEL_BASE, VEL_FUERTE
        _ultimo_lado = 1

    # --- LÍNEA PERDIDA (Memoria) ---
    else:
        if _ultimo_lado < 0:
            izq, der = 0, VEL_BASE
        elif _ultimo_lado > 0:
            izq, der = VEL_BASE, 0
        else:
            izq, der = VEL_SUAVE, VEL_SUAVE

    mbot2.drive_speed(izq, -der)
    vel_cmd = (izq + der) // 2
    return estado, vel_cmd


def registrar(t, estado, vel_cmd, con_pantalla):
    pct, volt       = leer_voltaje()
    roll            = cyberpi.get_roll()
    pitch           = cyberpi.get_pitch()
    yaw             = cyberpi.get_yaw()
    ax              = cyberpi.get_acc("x")
    ay              = cyberpi.get_acc("y")
    az              = cyberpi.get_acc("z")
    v1, v2, v_real  = leer_velocidades(vel_cmd)
    dist            = leer_distancia()
    gx, gy, gz, ofs, bat2, luz = leer_extras()

    print(
        "{:.1f},{},{:.2f},{:.1f},{:.1f},{:.1f},{:.2f},{:.2f},{:.2f},{:.1f},{},{},"
        "{:.1f},{:.1f},{:.1f},{:.1f},{:.1f},{},{},{}".format(
            t, pct, volt, roll, pitch, yaw, ax, ay, az,
            v1, 1 if v_real else 0, estado,
            v2, dist, gx, gy, gz, ofs, bat2, luz
        )
    )

    if con_pantalla:
        cyberpi.display.show_label("{:.1f}V  {}%".format(volt, pct), 12, 0, 0, index=0)
        cyberpi.display.show_label("R{:.0f} P{:.0f} Y{:.0f}".format(roll, pitch, yaw), 12, 0, 20, index=1)
        cyberpi.display.show_label("est {}  {:.0f}cm".format(estado, dist), 12, 0, 40, index=2)


# ---------------------------------------------------------------------
# PROGRAMA PRINCIPAL
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
    if cyberpi.controller.is_press("a") and not capturando:
        capturando = True
        inicializar_encoders()
        inicio = time.ticks_ms()
        ultimo = inicio
        muestras = 0
        cyberpi.display.clear()
        print(
            "t_s,bateria_pct,voltaje_v,roll,pitch,yaw,acc_x,acc_y,acc_z,vel_rpm,vel_real,estado,"
            "vel2_rpm,dist_cm,gyro_x,gyro_y,gyro_z,ofs_linea,bat2_pct,luz"
        )

    if cyberpi.controller.is_press("b") and capturando:
        capturando = False
        detener_motores()
        print("# --- fin de la captura ---")
        cyberpi.display.clear()
        cyberpi.display.show_label("FIN captura", 16, 0, 20, index=0)

    if capturando:
        estado, vel_cmd = seguir_linea()

        ahora = time.ticks_ms()
        if time.ticks_diff(ahora, ultimo) >= int(PERIODO_S * 1000):
            ultimo = ahora
            t = time.ticks_diff(ahora, inicio) / 1000.0
            muestras += 1
            registrar(t, estado, vel_cmd, muestras % CADA_PANTALLA == 1)
