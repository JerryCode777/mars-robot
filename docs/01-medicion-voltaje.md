# Medición de voltaje de la batería en el mBot2

> Proyecto **MARS-ROBOT** — Programación de Sistemas
> Documento: método para obtener el **voltaje** de la batería usando solo el mBot2 (sin instrumentos externos).

## 1. El problema

El enunciado pide registrar el estado de la **batería**. Lo natural sería leer el
**voltaje (V)** directamente, pero el mBot2 **no expone el voltaje en voltios**:

- La función de firmware `cyberpi.get_battery()` devuelve el **nivel de carga en
  porcentaje (0 – 100 %)**, no en voltios.
- El "bloque de voltaje" del entorno de bloques reporta `0.0` y no es fiable.

Por lo tanto, para "hallar el voltaje" con lo que tenemos, hay que **convertir el
porcentaje a voltios** usando las características conocidas de la batería.

## 2. Datos de la batería del mBot2

La batería integrada en el **mBot2 Shield** es una celda de litio (LiPo) de **1 celda**:

| Parámetro | Valor |
|---|---|
| Química | Li-ion / LiPo (1 celda, "1S") |
| Capacidad | 2500 mAh |
| Voltaje nominal | 3.7 V |
| Voltaje **lleno** (100 %) | **4.2 V** |
| Voltaje **vacío** / corte seguro (~0 %) | **≈ 3.3 V** |
| Voltaje recomendado de almacenamiento | 3.85 V |

Fuente: documentación oficial de Makeblock (*About mBot2/Neo Shield*).

## 3. La conversión: porcentaje → voltios

Como conocemos el rango real de la celda, mapeamos el porcentaje a voltios de forma
lineal:

```
V = V_MIN + (porcentaje / 100) × (V_MAX − V_MIN)
```

Con los valores del mBot2 (`V_MIN = 3.3`, `V_MAX = 4.2`):

```
V = 3.3 + (porcentaje / 100) × 0.9
V = 3.3 + porcentaje × 0.009
```

Ejemplos:

| Batería (%) | Voltaje estimado (V) |
|---|---|
| 100 % | 4.20 V |
| 75 %  | 3.98 V |
| 50 %  | 3.75 V |
| 25 %  | 3.53 V |
| 0 %   | 3.30 V |

## 4. Precisión: ¿qué tan bueno es este estimado?

Es una **aproximación**. La curva real de descarga del litio **no es una línea recta**:
se mantiene bastante plana alrededor de 3.7 V durante gran parte de la descarga y cae
rápido cerca de los extremos. Aun así, la estimación lineal es **suficiente para el
objetivo del proyecto**, porque lo que nos interesa no es el voltaje absoluto exacto,
sino **cómo cambia el consumo/la batería según la inclinación** (comportamiento
relativo).

En el informe conviene reportarlo con honestidad como:

> *"Voltaje estimado a partir del nivel de carga (%) reportado por el firmware,
> mapeado al rango conocido de la celda LiPo 1S del mBot2 (3.3 V – 4.2 V)."*

## 5. Calibración SIN multímetro

No tenemos multímetro, pero igual podemos **anclar** la fórmula con dos puntos que el
propio robot nos da gratis:

1. **Punto alto (batería llena):** justo después de una carga completa, el robot marca
   ~100 %. Una celda LiPo recién cargada está en **4.2 V**. → Confirma `V_MAX = 4.2`.
2. **Punto bajo (batería casi vacía):** cuando el CyberPi muestra el aviso de batería
   baja o se está por apagar, la celda está en **≈ 3.3 V**. → Confirma `V_MIN = 3.3`.

Con esos dos anclas, la recta queda definida sin necesidad de instrumento. Si algún día
consiguen un multímetro, basta medir en 2–3 niveles y ajustar `V_MIN`/`V_MAX` para
mejorar la exactitud.

## 6. Implementación (MicroPython)

```python
import cyberpi

# Batería LiPo de 1 celda del mBot2
V_MIN = 3.3   # vacía / corte seguro
V_MAX = 4.2   # llena

def leer_voltaje():
    """Devuelve (porcentaje, voltaje_estimado)."""
    pct = cyberpi.get_battery()                 # 0–100 (%)
    v = V_MIN + (pct / 100) * (V_MAX - V_MIN)   # % -> voltios
    return pct, v
```

Esta función es la que usa el script de captación (`src/captacion_datos.py`) para
registrar el voltaje junto con la velocidad y la inclinación.

## 7. Verificación en el equipo real

- [ ] Cargar la batería al 100 % y confirmar que `get_battery()` reporta ~100.
- [ ] Ejecutar `leer_voltaje()` y confirmar que muestra ~4.2 V con batería llena.
- [ ] Dejar descargar y confirmar que el valor baja de forma coherente.
- [ ] (Opcional) Si aparece un multímetro, medir y afinar `V_MIN` / `V_MAX`.
