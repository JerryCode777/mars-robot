# MARS-ROBOT

Sistema de captación de datos del recorrido de un vehículo (mBot2) sobre un terreno de
inclinación variable. **Curso: Programación de Sistemas — UNSA, semestre 2026-A.**
Equipo de 6 integrantes.

> **Este README es también el documento de traspaso del proyecto.** Contiene hallazgos de
> plataforma no obvios que costaron mucho tiempo descubrir. **Léelo completo antes de tocar
> el código o el entorno**, especialmente la sección "Hallazgos críticos".

---

## 1. Objetivo

Registrar cómo se comporta el vehículo (**velocidad**, **batería/voltaje** y **consumo
eléctrico**) según la **inclinación** de una plataforma que varía en 3 ejes hasta **±25°**,
durante un recorrido **rectilíneo** garantizado por seguimiento de línea.

La idea central: como el recorrido es siempre el mismo (la línea), la **única variable** que
cambia es la inclinación, lo que permite atribuirle los cambios de velocidad y consumo.

## 2. Hardware

- **mBot2** de Makeblock = controlador **CyberPi** (ESP32) + **mBot2 Shield** + chasis.
- **Sensor Quad RGB** → seguimiento de línea (4 sondas: L2, L1, R1, R2).
- **Giroscopio/acelerómetro integrado en el CyberPi** → mide la inclinación real del robot.
  *No hace falta un IMU aparte en la plataforma: el robot mide la inclinación que sufre.*
- **Motores con encoder** (puertos EM1/EM2) → velocidad.
- **Batería LiPo de 1 celda**, 2500 mAh (3,3 V vacía – 4,2 V llena).
- Lenguaje: **MicroPython** dentro del robot.

---

## 3. ⚠️ Hallazgos críticos (LEER ANTES DE TOCAR NADA)

### 3.1 El código SOLO funciona en modo "Subir/Cargar" (Upload), NUNCA en "En línea" (Online)

Este es **el hallazgo más importante del proyecto**. Se verificó inspeccionando la librería
del host en `/Applications/mLink2.app/.../site-packages/makeblock/`:

| API que usa nuestro código | ¿Existe en la librería del PC (modo "En línea")? |
|---|---|
| `mbot2.drive_speed` | ❌ NO existe |
| `mbot2.EM_stop` | ❌ NO existe |
| `mbot2.forward` | ❌ NO existe |
| `mbuild.quad_rgb_sensor` | ❌ NO existe |
| `get_ground_sta` | ❌ NO existe |

La librería del PC expone una API **totalmente distinta y basada en clases**
(`EncoderMotor`, `Color`, `Ultrasonic`, …) y **ni siquiera incluye el sensor Quad RGB**.

👉 **Conclusión:** el seguimiento de línea y el control de motores existen **solo dentro del
robot**. Por eso todo se ejecuta en modo **Upload**. No pierdas tiempo intentando hacerlo
funcionar en modo "En línea": es imposible sin reescribirlo entero, y aun así falta el sensor
de línea.

### 3.2 Cómo llegan los datos a la PC (la solución que sí funciona)

Como el robot corre en modo Upload (aislado del PC), la salida se hace por **cable USB**:

1. El robot imprime el CSV con **`print()`** (no `cyberpi.console.println`, que solo va a la
   pantalla del robot).
2. En la PC, `tools/leer_datos.py` (pyserial) lee el puerto USB y guarda el CSV.
3. Puerto del robot en este equipo: **`/dev/cu.usbserial-10`**, a **115200 baudios**.

⚠️ **El puerto USB no se puede compartir.** Hay que **desconectar el robot en mBlock/mLink**
antes de correr el lector, o dará "puerto ocupado".

### 3.3 Problemas del entorno ya resueltos (no repetirlos)

| Problema | Causa | Solución aplicada |
|---|---|---|
| El editor no ejecutaba nada | Firmware desactualizado | Actualizado por **cable USB** (obligatorio, no por Bluetooth) |
| "No se obtuvo el servicio de Python" | Faltaba **mLink 2** | Instalado `mLink2 v2.1.1` en `/Applications/mLink2.app` |
| mLink no conectaba desde el navegador | **Safari bloquea** el servicio local de mLink | **Usar Google Chrome** (nunca Safari) |
| La bandera verde 🏳️ no ejecutaba el Python | La bandera verde corre **bloques**, no Python | Usar el **Editor de Python** (Ajuste → Editor de Python) con su botón **"correr"** |
| `AttributeError: ... no attribute 'get_shield'` | Bug conocido del paquete `cyberpi` **0.0.7** | Parcheado `~/.mcode/site-packages/cyberpi/__init__.py`: los 94 alias envueltos en `getattr(..., None)`. Respaldo en `__init__.py.bak` |
| Pedía numpy → oset → parmed sin parar | El `mbuild` de `~/.mcode/site-packages` es el **paquete equivocado** (simulación molecular de PyPI, con `Compound`/`coarse_graining`), no el de Makeblock | Se abandonó esa vía (ver 3.1). Se instaló numpy 1.19.5 pero **es irrelevante** |

> ℹ️ Si mBlock/mLink se actualizan, pueden **regenerar** `cyberpi/__init__.py` y revivir el bug
> de `get_shield`. En ese caso, volver a aplicar el parche de `getattr`.

---

## 4. API del dispositivo verificada

Confirmada contra los ejemplos oficiales de Makeblock (no son suposiciones):

```python
# --- cyberpi ---
cyberpi.get_battery()              # nivel de batería en % (0-100). ¡NO da voltios!
cyberpi.get_extra_battery()        # batería EXTRA (mBot2 Shield, la de los motores) en %
cyberpi.get_roll() / get_pitch() / get_yaw()    # inclinación en grados
cyberpi.get_acc("x"|"y"|"z")       # aceleración m/s² (incluye gravedad)
cyberpi.get_gyro(eje)              # velocidad angular °/s
cyberpi.get_brightness()           # luz ambiente (sensor del CyberPi)
cyberpi.get_rotation(eje)          # ángulo acumulado desde reset_rotation()
cyberpi.get_loudness("maximum")    # sonoridad del micrófono
cyberpi.display.show_label(texto, tamaño, x, y, index=n)
cyberpi.display.clear()
cyberpi.console.println(texto)     # SOLO pantalla del robot (no sale por USB)
cyberpi.controller.is_press("a"|"b")

# --- mbot2 (motores) ---
mbot2.drive_speed(EM1, EM2)        # ¡recto = drive_speed(v, -v)!
mbot2.EM_stop()
mbot2.forward/backward/turn_left/turn_right(velocidad, tiempo)
mbot2.straight(cm) / mbot2.turn(grados)

# --- mbuild (sensor de línea) ---
mbuild.quad_rgb_sensor.get_ground_sta("all", 1)   # devuelve un entero de estado
mbuild.quad_rgb_sensor.is_line("L1"|"L2"|"R1"|"R2", 1)
mbuild.quad_rgb_sensor.get_offset_track(1)        # desviación de la línea: -100..+100
mbuild.quad_rgb_sensor.get_line_sta("all", 1)     # estado referido a la línea
mbuild.quad_rgb_sensor.get_light("L1")            # reflectancia cruda por sonda

# --- mbuild (otros módulos del kit) ---
mbuild.ultrasonic2.get(1)          # distancia en cm (si se monta el sensor ultrasónico)
```

> ⚠️ La función para LEER el encoder sigue sin confirmar (no está en la documentación
> pública). `captacion_datos.py` prueba `EM_get_speed` / `EM_get_angle` y variantes con
> respaldo automático; `src/probe_encoder.py` los confirma con `dir(mbot2)`.

### ⚠️ Los motores están montados EN ESPEJO

Para avanzar **recto** las ruedas llevan **signos opuestos**: `drive_speed(30, -30)`.
Si se usa `drive_speed(30, 30)` el robot **gira sobre su propio eje**. (Este bug ya se sufrió.)

### Estados del sensor de línea (determinados empíricamente)

Bits de las 4 sondas `[L2 L1 R1 R2]`:

| Estado | Significado | Acción |
|---|---|---|
| `6` | centrado | recto |
| `14`, `12`, `4` | desviado a un lado | corrección suave |
| `8` | desviado fuerte (sonda externa) | corrección fuerte |
| `7`, `3`, `2` | desviado al otro lado | corrección suave |
| `1` | desviado fuerte (sonda externa) | corrección fuerte |
| `0`, `15` | **línea perdida** | girar hacia el último lado visto |

### Batería → voltaje (el firmware no da voltios)

`cyberpi.get_battery()` devuelve **porcentaje**, no voltios. Se convierte con el rango
conocido de la celda LiPo 1S:

```
V = 3.3 + (porcentaje / 100) × 0.9        # 3.3 V vacía … 4.2 V llena
```

Detalle completo y método de calibración sin multímetro en `docs/01-medicion-voltaje.md`.

---

## 5. Estructura del proyecto

```
proyecto/
├── README.md                          ← este documento (traspaso)
├── datos_20260713_183211.csv          ← datos de la 1ª prueba real (377 muestras)
├── src/                               ← código que corre DENTRO del robot
│   ├── captacion_datos.py             ← programa principal (línea + captura)
│   └── probe_encoder.py               ← sonda de diagnóstico del encoder (pendiente de correr)
├── tools/                             ← código que corre en la PC
│   ├── leer_datos.py                  ← lector USB (pyserial) → guarda el CSV
│   ├── dashboard.py                   ← lector USB + panel web en vivo (localhost:8765)
│   └── dashboard_web.html             ← interfaz del panel (la sirve dashboard.py)
└── docs/
    ├── 01-medicion-voltaje.md         ← método % → voltios
    └── Informe_Prueba_Captura_MARS-ROBOT.docx ← informe de la 1ª prueba (APA)
```

> 📌 `docs/Informe_Final_MARS-ROBOT.docx` (19/07/2026) es el **informe final** del
> proyecto: resumen, fundamentos, diseño completo del sistema, prueba de validación,
> conclusiones y referencias APA. Tiene marcadores en rojo de dos tipos: `INSERTAR
> CAPTURA` (4 capturas del panel) y `PENDIENTE` (datos de la prueba final sobre la
> plataforma, con tabla de resultados por inclinación lista para llenar). Se genera
> con `python-docx`.

---

## 6. Cómo ejecutar (procedimiento probado)

**El orden importa** — el cable USB no se puede compartir entre mBlock y el lector.

1. Abrir el **Editor de Python de mBlock en Google Chrome** (`python.mblock.cc`), con **mLink 2
   corriendo**.
2. Poner el modo en **"Subir al dispositivo" / "Cargar"** (NO "En línea").
3. Pegar `src/captacion_datos.py` y **subirlo** al robot. El robot mostrará "MARS-ROBOT / A: iniciar".
4. **Desconectar** el robot en mBlock (libera el puerto USB).
5. En una Terminal, desde la carpeta del proyecto:
   ```bash
   python3 tools/leer_datos.py
   ```
6. Colocar el robot sobre la línea y **pulsar A**. Los datos aparecen en pantalla y se guardan
   en `datos_AAAAMMDD_HHMMSS.csv`.
7. **Pulsar B** en el robot para detener; **Ctrl+C** en la Terminal para cerrar el archivo.

### Panel en tiempo real (alternativa al lector simple)

`tools/dashboard.py` hace lo mismo que `leer_datos.py` (lee el USB y guarda el CSV)
y además sirve un **panel web local** con gráficos en vivo: velocidad, inclinación
(roll/pitch), voltaje y estado del seguidor de línea, con ventana de 30 s / 60 s /
2 min / todo, tema claro/oscuro y tabla de datos.

```bash
python3 tools/dashboard.py                 # con el robot (mismo flujo: paso 4 antes)
# abrir  http://localhost:8765  en el navegador
```

Para probarlo **sin robot**:

```bash
python3 tools/dashboard.py --replay datos_20260713_183211.csv   # reproduce una captura real
python3 tools/dashboard.py --demo                               # datos sintéticos continuos
```

No usa internet ni librerías extra (solo pyserial para el modo USB). El panel es
solo visualización: el CSV se sigue guardando igual que siempre.

### Dependencias de la PC
- `pyserial` (instalado: 3.5) → `python3 -m pip install pyserial`
- `python-docx` (para regenerar los informes Word)

---

## 7. Formato de los datos

Desde julio 2026 son **20 columnas** (las 12 primeras idénticas al formato original,
por compatibilidad):

```
t_s,bateria_pct,voltaje_v,roll,pitch,yaw,acc_x,acc_y,acc_z,vel_rpm,vel_real,estado,
vel2_rpm,dist_cm,gyro_x,gyro_y,gyro_z,ofs_linea,bat2_pct,luz
```

| Columna | Descripción |
|---|---|
| `t_s` | tiempo desde el inicio (s) |
| `bateria_pct` | nivel de batería del CyberPi (%) |
| `voltaje_v` | voltaje estimado (V) — derivado del % |
| `roll`, `pitch`, `yaw` | inclinación en 3 ejes (grados) |
| `acc_x/y/z` | aceleración (m/s², incluye gravedad) |
| `vel_rpm` | velocidad rueda **izquierda** EM1 (RPM) |
| `vel_real` | **1** = viene del encoder · **0** = es la velocidad comandada (respaldo) |
| `estado` | estado crudo del sensor de línea |
| `vel2_rpm` | velocidad rueda **derecha** EM2 (RPM) |
| `dist_cm` | distancia recorrida (cm), del ángulo acumulado del encoder (0 si no hay encoder) |
| `gyro_x/y/z` | velocidad angular (°/s) |
| `ofs_linea` | desviación respecto a la línea: −100 (izq) … +100 (der) |
| `bat2_pct` | batería extra del mBot2 Shield (%) — la que alimenta los motores |
| `luz` | luz ambiente del CyberPi |

Muestreo: `PERIODO_S = 0.1` como intervalo mínimo; la tasa real la fija el bucle
(la pantalla del robot solo se refresca 1 de cada 10 muestras para no frenarlo).
Las herramientas de la PC leen **ambos formatos** (12 o 20 columnas).

---

## 8. Estado actual

### ✅ Funcionando
- Seguimiento de línea estable (con corrección graduada y recuperación al perder la línea).
- Captura sincronizada de batería, voltaje, inclinación 3 ejes, aceleración y velocidad.
- Transmisión por USB a la PC y guardado automático en CSV.
- Primera prueba real completada: **377 muestras en 115,8 s**.
- Informe de la prueba en Word con formato APA (`docs/Informe_Prueba_Captura_MARS-ROBOT.docx`).

### 📊 Resultados de la 1ª prueba (`datos_20260713_183211.csv`)
| Variable | Resultado | Lectura |
|---|---|---|
| Muestras | 377 en 115,8 s (~3,3/s) | captura continua, sin pérdidas |
| Batería / Voltaje | 50 % / 3,75 V (constante) | recorrido corto, sin caída apreciable |
| Roll / Pitch | −4° a 3° | superficie **plana** (falta la plataforma) |
| Yaw | −179° a 174° | el robot giró bastante siguiendo la línea |
| Aceleración Z | ≈ −9,75 m/s² | coincide con la gravedad → sensor válido |
| Velocidad | 10–20 RPM (prom. 15,6) | corrección del seguidor de línea |
| `vel_real` | **0 en todas** | ⚠️ el encoder aún NO se está leyendo |

### ⏳ Pendiente
1. **Activar la lectura del encoder** (`vel_real` debe salir 1). El nombre de la función aún es
   desconocido: `mbot2.encoder_motor_get_speed()` **no está confirmado**. Para resolverlo se
   creó `src/probe_encoder.py`, que lista `dir(mbot2)` y prueba 7 nombres candidatos.
   **Siguiente paso: subir esa sonda y leer su salida.**
2. **Construir la plataforma inclinable** (±25° en 3 ejes) — parte mecánica, no iniciada.
3. **Confirmar con el docente** el alcance de "electricidad de forma detallada": el mBot2 **no
   tiene sensor de corriente**. Si se exige medir corriente/potencia, hace falta un **INA219**
   o **ACS712** externo.
4. Campañas de medición a distintas inclinaciones y análisis velocidad/consumo vs. inclinación.
5. Para la demo final: migrar la transmisión de USB a **Wi-Fi** para que el robot se mueva libre.

---

## 9. Parámetros de ajuste del seguidor de línea

En `src/captacion_datos.py`:

```python
VEL_BASE   = 20   # velocidad en recto. Se sale en curvas -> bajar a 16 o 14
VEL_SUAVE  = 12   # rueda interior en corrección leve. Zigzaguea -> subir a 15
VEL_FUERTE = 4    # rueda interior en corrección fuerte. No gira lo suficiente -> bajar a 2
PERIODO_S  = 0.2  # segundos entre muestras de datos
```

El seguimiento de línea se ejecuta en **cada vuelta** del bucle (para ir fluido), mientras que
el registro de datos está **limitado a cada `PERIODO_S`** para no saturar el enlace USB.
