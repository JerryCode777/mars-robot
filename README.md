# MARS-ROBOT

**Sistema de Captación de Datos del Recorrido de un Vehículo sobre una Plataforma de
Inclinación Variable.** Curso: Programación de Sistemas — UNSA, semestre 2026-A.

**Integrantes:** Quispe Puma, Usiel Suriel · Chirinos Rojas, Kennedy ·
Huaynacho Mango, Jerry Anderson · Velazque Quispe, Flor de Liz

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
- **Dos baterías**: la del CyberPi (`get_battery()`) y la del **Shield, LiPo 1S de
  2500 mAh** (3,3–4,2 V), que alimenta los motores (`get_extra_battery()` → `bat2_pct`).
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
2. En la PC, `tools/dashboard.py` (panel web, recomendado) o `tools/leer_datos.py`
   (lector simple) leen el puerto USB con pyserial y guardan el CSV.
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
│   ├── dashboard.py                   ← lector USB + panel web en vivo (localhost:8765)
│   ├── dashboard_web.html             ← interfaz del panel (la sirve dashboard.py)
│   └── leer_datos.py                  ← lector simple de terminal (alternativa mínima)
└── docs/
    ├── 01-medicion-voltaje.md         ← voltaje: estimación por % y divisor resistivo en S1
    ├── Informe_Final_MARS-ROBOT.docx  ← INFORME FINAL en APA 7 (ver nota)
    └── Informe_Prueba_Captura_MARS-ROBOT.docx ← informe histórico de la 1ª prueba
```

> 📌 `docs/Informe_Final_MARS-ROBOT.docx` es el **informe final** en formato APA 7
> (portada, resumen, fundamentos, sensores, diccionario de las 20 columnas, guía de
> recuperación de datos, resultados y referencias). Tiene marcadores en rojo de dos
> tipos: `INSERTAR CAPTURA` (6 figuras: foto del carrito, 4 capturas del panel y la
> curva final) y `PENDIENTE` (docente, fecha y datos de la prueba final, con la Tabla 5
> por inclinación lista para llenar). Se genera con `python-docx`.

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
   python3 tools/dashboard.py
   ```
   y abrir **http://localhost:8765** en el navegador.
6. Pulsar **▶ Iniciar captura** en el panel (abre el puerto USB y guía cada paso).
7. Colocar el robot sobre la línea y **pulsar A** cuando el panel lo pida: los gráficos
   se actualizan en vivo y todo se guarda en `datos_AAAAMMDD_HHMMSS.csv`.
8. **Pulsar B** en el robot para detener el recorrido y **■ Detener** en el panel para
   liberar el puerto (el CSV queda cerrado y guardado).

### El panel web (tools/dashboard.py)

App de una sola página con tres secciones: **Inicio** (presentación del proyecto),
**Panel en vivo** (6 indicadores + 5 gráficos: velocidad de ambas ruedas, inclinación
roll/pitch, voltaje, franja del seguidor de línea y **velocidad según inclinación** —
la curva que revela la pendiente máxima) y **Datos** (tabla, guía del formato y
descarga del CSV de la sesión). Ventana de 30 s / 60 s / 2 min / todo y tema
claro/oscuro automático. No usa internet ni librerías extra (solo pyserial para el
modo USB).

Para probarlo **sin robot** (mismo flujo con botón):

```bash
python3 tools/dashboard.py --replay datos_20260713_183211.csv   # reproduce una captura real
python3 tools/dashboard.py --demo                               # datos sintéticos continuos
```

Alternativa mínima sin panel: `python3 tools/leer_datos.py` (solo terminal + CSV).

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
| `voltaje_v` | voltaje (V) — estimado por %, o **real** si el divisor está en S1 (`PIN_VOLTAJE = "S1"`) |
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
- Captura sincronizada de **20 variables** por muestra (batería ×2, voltaje, inclinación,
  aceleración y giroscopio 3 ejes, velocidad de ambas ruedas, distancia, desviación de
  línea, luz), a 0,1 s de intervalo mínimo.
- Transmisión por USB a la PC y guardado automático en CSV.
- **Panel web local** con captura guiada por botón, 5 gráficos en vivo (incluida la curva
  velocidad vs inclinación), tabla y descarga del CSV.
- Voltaje real por divisor resistivo **implementado en el código** (falta montar las 2
  resistencias y poner `PIN_VOLTAJE = "S1"`).
- Primera prueba real completada: **377 muestras en 115,8 s**.
- **Informe final en APA 7** (`docs/Informe_Final_MARS-ROBOT.docx`) a falta de capturas
  y de los datos de la prueba final.
- Proyecto en GitHub: **https://github.com/JerryCode777/mars-robot** (público).

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
1. **Confirmar la lectura del encoder** (`vel_real` debe salir 1). El nombre exacto no está
   en la documentación pública; `captacion_datos.py` ya prueba solo los candidatos más
   probables (`EM_get_speed`/`EM_get_angle`, por el patrón de `EM_stop`). Si la próxima
   captura sigue con `vel_real=0`, subir `src/probe_encoder.py` y leer su salida.
   ⚠️ Sin encoder, la curva velocidad vs inclinación no refleja la pérdida real de fuerza.
2. **Montar el divisor de voltaje** (10 kΩ + 20 kΩ → pin S1) y activar `PIN_VOLTAJE = "S1"`
   — ver `docs/01-medicion-voltaje.md` §8.
3. **Construir la plataforma inclinable** (±25° en 3 ejes) — parte mecánica, no iniciada.
4. **Confirmar con el docente** el alcance de "electricidad de forma detallada": el mBot2 **no
   tiene sensor de corriente**. Si se exige medir corriente/potencia, hace falta un **INA219**
   o **ACS712** externo.
5. **Prueba final**: campañas a distintas inclinaciones; con su CSV se llenan la Tabla 5,
   el análisis y las conclusiones del informe final. Insertar las 6 figuras (foto del
   carrito + capturas del panel).
6. Para la demo final: migrar la transmisión de USB a **Wi-Fi** para que el robot se mueva libre.

---

## 9. Parámetros de ajuste

En `src/captacion_datos.py`:

```python
VEL_BASE   = 20    # velocidad en recto. Se sale en curvas -> bajar a 16 o 14
VEL_SUAVE  = 12    # rueda interior en corrección leve. Zigzaguea -> subir a 15
VEL_FUERTE = 4     # rueda interior en corrección fuerte. No gira lo suficiente -> bajar a 2
PERIODO_S  = 0.1   # intervalo mínimo entre muestras (la tasa real la pone el bucle)
CADA_PANTALLA = 10 # refrescar la pantalla del robot 1 de cada N muestras (es lenta)
DIAM_RUEDA_CM = 4.8  # diámetro de rueda para dist_cm — calibrar rodando 100 cm
PIN_VOLTAJE = None   # poner "S1" cuando esté montado el divisor de voltaje
```

El seguimiento de línea se ejecuta en **cada vuelta** del bucle (para ir fluido), mientras que
el registro de datos está **limitado a cada `PERIODO_S`** y la pantalla a 1 de cada
`CADA_PANTALLA` muestras para no frenar la captura.
