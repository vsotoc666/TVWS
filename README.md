# Radio Cognitiva TVWS — GNU Radio Cognitive Block

> **Producto principal:** Bloque de software GNU Radio modular con IA sensadora integrada para acceso dinámico al espectro TVWS. Nivel de madurez tecnológica objetivo: **TRL-4** (componente validado en entorno de laboratorio y campo).

**Universidad Nacional de Ingeniería (UNI) — Facultad IITMC**
**Proyecto VRI 2026 | 18 mayo → 15 diciembre 2026**
**PI: Galvez Legua, Mauricio Pedro**

---

## Tabla de contenidos

1. [Identidad del Proyecto](#1-identidad-del-proyecto)
2. [Producto Principal — Bloque Cognitivo GNU Radio](#2-producto-principal--bloque-cognitivo-gnu-radio)
3. [Arquitectura del Sistema de Validación](#3-arquitectura-del-sistema-de-validación)
4. [Hardware por Nodo](#4-hardware-por-nodo)
5. [Parámetros OFDM del Canal de Datos](#5-parámetros-ofdm-del-canal-de-datos)
6. [Canal de Datos — TX/RX Downlink y Uplink](#6-canal-de-datos--txrx-downlink-y-uplink)
7. [Canal de Control In-Band](#7-canal-de-control-in-band)
8. [Modelo de IA — CNN de Sensado Espectral](#8-modelo-de-ia--cnn-de-sensado-espectral)
9. [Link Budget y Parámetros de Rendimiento](#9-link-budget-y-parámetros-de-rendimiento)
10. [Configuración de Cómputo en Tiempo Real](#10-configuración-de-cómputo-en-tiempo-real)
11. [Cronograma Actualizado](#11-cronograma-actualizado)
12. [Estado del Proyecto](#12-estado-del-proyecto)
13. [Software y Dependencias](#13-software-y-dependencias)

---

## 1. Identidad del Proyecto

| Campo | Valor |
|---|---|
| Nombre completo | Diseño y Validación de un Prototipo de Radio Cognitiva basado en Hardware SDR Asimétrico y Deep Learning para el Acceso Dinámico a TVWS en Zonas Rurales |
| Universidad | Universidad Nacional de Ingeniería (UNI), Lima, Perú |
| Facultad | Ingeniería Eléctrica y Electrónica — IITMC |
| Tipo | Investigación Aplicada — VRI Grupo de Investigación |
| Presupuesto total | S/ 40,000 |
| Financiamiento | Fondos estatales — portal RNP |

**Equipo:**
- Franco Rafael Espinoza — Fase 1 (dataset e IA)
- Victor Manuel Soto — Fase 2 (integración SDR y MAC)
- Sandro Gonzalo Niño — Fase 3 (enlace piloto urbano)

---

## 2. Producto Principal — Bloque Cognitivo GNU Radio

El aporte central de este proyecto no es el enlace de radio en sí, sino el **bloque de software GNU Radio** que implementa la radio cognitiva completa: desde el sensado espectral con CNN hasta la señalización de salto de canal in-band. El enlace de 4 km en Fase 4 es la validación de ese bloque en condiciones reales (actualizado 28/08/2026, ver §9.1 — antes 5–6 km, y antes de eso 10–15 km).

### 2.1 Arquitectura del bloque

```
┌─────────────────────────────────────────────────────────────────┐
│                  TVWS Cognitive GNU Radio Block                  │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │  Capa de     │    │  Capa de     │    │  Capa de          │  │
│  │  Adquisición │───▶│  Sensado IA  │───▶│  Decisión         │  │
│  │  RadioInterface    │  CNN 1D ONNX │    │  Cognitiva        │  │
│  └──────────────┘    └──────────────┘    └────────┬──────────┘  │
│                                                    │             │
│  ┌──────────────────────────────────────┐          │             │
│  │  Capa de Control In-Band (3 formatos) │◀─────────┘             │
│  │  Subportadoras OFDM #254–257         │                        │
│  └──────────────────────────────────────┘                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  Interfaz de Monitoreo (dashboard tiempo real)            │    │
│  │  Espectrograma · Canal activo · CNN confidence · BER     │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

> **Nota sobre el diagrama:** las flechas Adquisición→Sensado, Sensado→Decisión y Decisión↔Control son conexiones por **puertos de mensajes** (PMT, asíncronas) del scheduler de GNU Radio — no puertos de flujo. La única ruta de streaming en tiempo real (con deadline de símbolo OFDM, ~89 µs) es RX1/TX1 dentro de la Capa de Adquisición y su paso por la Capa de Control In-Band. El barrido de sensado (RX2), el cómputo de PSD, la inferencia CNN y la decisión cognitiva corren en rutas de ejecución independientes de esa ruta de streaming — ver §2.2 para el detalle por capa.

### 2.2 Capas del bloque

#### Capa 1 — Adquisición (`RadioInterface`)
No es una única clase con llamadas bloqueantes tipo `leer_iq()` — ese modelo no encaja con el scheduler de flujo continuo de GNU Radio. Se divide en dos sub-bloques con roles distintos:

- **`RadioInterfaceDatos`** (RX1/TX1): wiring nativo del flowgraph. El source/sink de `gr-bladeRF` (mismo driver en Gateway y Cliente — ambos nodos usan bladeRF 2.0 micro xA4) conectado directamente por **puertos de flujo** a la cadena OFDM — no expone una API Python de "pedir muestras", es topología de flowgraph pura, como cualquier bloque nativo de GNU Radio.
- **`RadioInterfaceSensado`** (RX2): bloque de captura por ráfagas para el barrido de la Capa 2. Expone un **puerto de mensajes de entrada** (`retune`) que recibe la próxima posición de sintonía como PMT y reconfigura `set_center_freq()` de forma asíncrona, y un **puerto de mensajes de salida** (`captura`) que publica el vector IQ de la ráfaga una vez completada.

Ambos sub-bloques resuelven internamente la calibración de DC offset (`bladerf_set_correction()`/`libbladeRF`) y corrección IQ — igual en ambos nodos, ya no hace falta abstraer drivers distintos — pero el punto de integración con el resto del bloque cognitivo es siempre un puerto de mensajes o un puerto de flujo, nunca una llamada de método bloqueante entre hilos Python.

**Parámetros configurables:** frecuencia central, ancho de banda de muestreo, ganancia RX, rol de nodo (`gateway` | `cliente`, mismo tipo de hardware `bladerf` en ambos).

#### Capa 2 — Sensado espectral (`SpectralSensor`)
El bladeRF (AD9361) tiene ~56 MHz de ancho de banda instantáneo máximo: es físicamente imposible capturar los 228 MHz de la banda TVWS (470–698 MHz) en una sola FFT. Esta capa orquesta un **barrido de 5 posiciones de sintonización** sobre el RX2 (canal dedicado a sensado, independiente del TX/RX de datos), cada una cubriendo una sub-banda de 56 MHz con 7–9 canales TVWS visibles.

Implementada como bloque GNU Radio **sin puertos de flujo** (`io_signature(0, 0, 0)`) — solo puertos de mensajes, porque es una máquina de estados de barrido, no parte de la ruta de muestras. Publica comandos de sintonía al puerto `retune` de `RadioInterfaceSensado` y se suscribe a su puerto `captura`; al recibir una ráfaga, calcula la PSD (FFT de 512 puntos, ventana Hann, método Welch — reusa `calcular_psd`/`normalizar_psd` de `IA/nucleo.py`) en el propio handler de mensaje y publica el vector normalizado por un puerto de mensajes propio (`psd_out`) hacia la Capa 3, luego avanza el estado y ordena la siguiente posición. Como este cómputo no tiene un deadline de símbolo OFDM encima, el handler puede usar NumPy/SciPy sin comprometer el jitter del flowgraph de datos — el barrido de sensado y el canal de datos son rutas de ejecución independientes dentro del scheduler de GNU Radio, no compiten por el mismo `work()`. Tras las 5 capturas del ciclo, el mapa global de los 39 canales lo ensambla la Capa 3 (ver §8), no esta capa.

**Parámetros configurables:** posiciones de barrido, ancho de sub-banda, tamaño FFT, período de ciclo.

#### Capa 3 — Clasificador CNN (`ChannelClassifier`) + mapa de ocupación (`SpectralOccupancyMap`)
Modelo CNN 1D ejecutado vía ONNX Runtime. Clasifica **una sub-banda de 56 MHz por inferencia** (no la banda completa de una sola vez — ver Capa 2), con dos salidas: probabilidad de ocupación por canal y margen/SNR estimado en dB por canal (esta segunda cabeza existe para que la política `max_margin` de la Capa 4 tenga un valor continuo que comparar entre canales libres, no solo probabilidades saturadas cerca de 0). `SpectralOccupancyMap` agrega las 5 sub-bandas del ciclo en el mapa global de 39 canales, con timestamp por canal — las sub-bandas no se capturan simultáneamente, así que el mapa nunca es una foto instantánea uniforme. Agnóstico al modelo: acepta cualquier `.onnx` que cumpla la interfaz de entrada/salida especificada.

**Parámetros configurables:** ruta del modelo ONNX, umbral de decisión, número de canales por sub-banda, frecuencia de actualización.

#### Capa 4 — Decisión cognitiva (`CognitiveEngine`)
Implementa la política de selección de canal y el protocolo de salto. Genera y mantiene actualizada la **Lista de Respaldo Proactiva** (Top 4 canales más limpios según la CNN), que se transmite continuamente al Cliente vía Formato B (ver §7). Ante degradación abrupta, ejecuta el protocolo de **Targeted Rendezvous** (ver §7.4).

**Parámetros configurables:** política de selección (`lowest_free` | `max_margin` | `least_used`), tamaño de la lista de respaldo (1–4), tiempo de pre-anuncio, número de confirmaciones CRC, umbral de degradación, timeout de rendezvous.

#### Capa 5 — Control in-band (`InbandControlLayer`)
Implementa la señalización bidireccional in-band (DL y UL, cada uno dentro de su propio slot TDD — ver §3.1) mediante 3 formatos de mensaje de 32 bits sobre las subportadoras OFDM #254–257 (BPSK, 3 bits/símbolo, ~1 ms por mensaje). **Formato A** (DL): Salto Inmediato. **Formato B** (DL): Actualización de Respaldo Proactiva con canal, modulación recomendada, flag de potencia y flag de silencio. **Formato C** (UL): ACK del Cliente con métricas RSSI/SNR. Ver §7 para la especificación completa de los 3 formatos y del protocolo de contingencia Targeted Rendezvous.

Separa explícitamente la ruta de decisión (asíncrona, por mensajes) de la ruta de inyección/extracción de bits (síncrona, por símbolo OFDM, con el deadline real de ~89 µs):

- **TX (`InbandControlTX`)**: bloque de flujo con puerto de mensajes de entrada `orden_salto`. `CognitiveEngine` publica ahí el paquete de control ya armado (el formato correspondiente — A, B o C — con su CRC-16) cuando decide un salto o una actualización; el handler solo actualiza una palabra de 32 bits en el estado interno del bloque. En cada símbolo OFDM, `work()` únicamente lee esa palabra ya calculada y escribe el bit correspondiente en las subportadoras #254/#256/#257 — el cómputo de CRC/empaquetado nunca ocurre dentro de `work()`. Implementación real: `SDR/inband_control.py`.
- **RX (`InbandControlRX`)**: bloque de flujo con puerto de entrada por streaming (salida del FFT del receptor) y puerto de mensajes de salida `control_recibido`. En `work()` solo extrae y acumula los 3 bits de control por símbolo; al completar los 11 símbolos del mensaje, valida CRC-16, identifica el formato por `Flag_Type` y publica el paquete decodificado por el puerto de mensajes (o lo descarta si falla el CRC) — sin bloquear el flujo de datos.

El **ejecutor del salto** (retuning real de `RadioInterfaceDatos` al llegar `t_hop`, o la actualización de la lista de respaldo del Formato B) se suscribe al puerto `control_recibido` y programa la reconfiguración por temporizador — es un componente explícito de esta capa, no queda implícito entre la decisión (Capa 4) y la radio (Capa 1).

**Parámetros configurables:** índices de subportadoras de control, esquema de modulación del campo de control, número de repeticiones del pre-anuncio, tamaño de la lista de respaldo.

#### Capa 6 — Interfaz de monitoreo (`MonitoringDashboard`)
Dashboard en tiempo real que muestra el estado completo del sistema cognitivo. Implementado como interfaz Qt integrada en GNU Radio con opción de servidor WebSocket para monitoreo remoto (relevante para acceso desde laptop externa al nodo Cliente).

**Paneles:** espectrograma de la banda TVWS, mapa de ocupación de canales con confianza CNN, canal activo y próximo canal anunciado, historial de saltos, métricas en tiempo real (throughput DL/UL, SNR, BER, margen de enlace), estado del clasificador (última inferencia, tiempo de inferencia, accuracy acumulada).

---

## 3. Arquitectura del Sistema de Validación

El bloque cognitivo se valida sobre un enlace punto a punto real, en **half-duplex por TDD (software, sin switch RF)** — ver §3.1 para la decisión y por qué reemplazó al full-duplex real que este documento describía antes del 26/07/2026:

```
[Comunidad rural — 4 km]                   [Localidad con fibra]
  Usuarios locales
       │
  [AP WiFi local]
       │
  Orange Pi 5 (16GB)  ←──── OFDM TVWS ────→  Mini PC Core Ultra 5
  + bladeRF 2.0 micro xA4                       + bladeRF 2.0 micro xA4
  Nodo CLIENTE                                 Nodo GATEWAY
  (demodula, ejecuta)                          (CNN + decisión cognitiva)
       │                                              │
  LPDA TX + LPDA RX                            LPDA TX + LPDA RX + discone
  (TDD por software, 2 antenas)                (TDD por software, 2 antenas + sensado)
  LNA (NF≤1dB)                                LNA (NF≤1dB) + PA 2W
                                                      │
                                               Router fibra óptica
                                                      │
                                                  Internet
```

**Principio de operación:** El bloque cognitivo corre íntegramente en el Gateway. El Cliente solo ejecuta las órdenes de salto recibidas vía el campo de control in-band, sin lógica cognitiva propia.

### 3.1 Arquitectura half-duplex por TDD software (decisión 26/07/2026)

> **Historial de esta decisión (para que quede trazable, no se reescribe en silencio):**
> 1. Diseño original: TDD con conmutador SPDT físico.
> 2. 2026-07: se reemplazó por **full-duplex real** (2TX/2RX simultáneos del bladeRF, antenas TX/RX dedicadas) — ver el registro anterior de esta sección más abajo, conservado como nota histórica.
> 3. **26/07/2026: el full-duplex real se descarta** al analizar el aislamiento TX→RX requerido (~90-110 dB) vs. el disponible solo por separación de antenas (~30-50 dB) — un déficit que ninguna cancelación pasiva por antena cierra. Se adopta **TDD por software**: mismo hardware de 2 antenas dedicadas por nodo (sin switch, sin filtro), pero DL y UL alternan en el tiempo apagando digitalmente el TX propio durante el slot de recepción. Análisis completo, alternativas descartadas (SIC, FDD con filtro) y lo que falta medir: `claudedocs/riesgos_arquitectura_transmision.md` ("Problema 1").

**Implicaciones de la arquitectura TDD por software:**
- 4 antenas LPDA en total (2 por nodo: TX y RX — el hardware de antena **no cambió** respecto al full-duplex; lo que cambió es que ya no transmiten simultáneamente), más la discone de sensado en el Gateway.
- **DL y UL ya NO operan simultáneamente** — comparten el canal en el tiempo (trama TDD con slot DL, slot UL, ventanas de guarda). **Slot y duty cycle decididos (20/08/2026):** slot de 20 símbolos OFDM (~1.78 ms) por dirección, duty cycle **50/50 simétrico** DL/UL, ganancia manual (AGC deshabilitado) en TX/RX durante los slots para eliminar el settling de AGC como incógnita de la guarda. Guarda de diseño: rango 25–70 µs (settling de bias del PA + retardo de propagación a 4 km, ~13 µs de ida — el settling de PA todavía no está medido en banco, ver `claudedocs/riesgos_arquitectura_transmision.md`, "Problema 1"). Con guarda pesimista (70 µs) la eficiencia de slot es ~96.2%. El throughput de §5.3 y la latencia E2E de §9.2 ya están recalculados con este duty cycle.
- No hay pérdida de inserción de conmutador (nunca la hubo con antenas dedicadas; eso no cambia con TDD por software) — el margen de enlace de §9.1 (que depende de EIRP/FSPL/NF, no de si DL/UL son simultáneos) **sigue siendo válido tal cual**.
- Pendiente de medir antes de Fase 4: aislamiento real de "TX apagado" y el settling real del bias del PA al conmutar TX on/off (detalle en el doc de riesgos) — la guarda de 25–70 µs es un rango de diseño, no una medición.

> **Nota histórica (registro previo a la decisión del 26/07/2026, ya no vigente):** *"El sistema opera en full-duplex real, aprovechando la capacidad 2TX/2RX simultáneos del bladeRF 2.0 micro xA4 — mismo modelo en Gateway y Cliente. Cada nodo utiliza dos antenas LPDA dedicadas —una para TX y otra para RX— eliminando la necesidad de conmutación TDD."* Se descartó por el déficit de aislamiento TX→RX explicado arriba — la premisa de que antenas dedicadas bastaban para full-duplex real resultó incorrecta.

### 3.2 Planos de comunicación

| Plano | Medio | Dirección | Implementación |
|---|---|---|---|
| **Datos** | OFDM 6 MHz, 470–698 MHz | DL y UL (TDD por software, no simultáneo — ver §3.1) | GNU Radio, bladeRF 2.0 micro xA4 TX1/RX1 en ambos nodos |
| **Control** | Subportadoras OFDM #254–257 | Bidireccional (DL + UL, dentro de sus respectivos slots TDD) | In-Band: 3 formatos (Salto, Respaldo Proactivo, ACK Uplink) + Targeted Rendezvous, <1 ms latencia por mensaje |
| **Sensado** | bladeRF RX2 | Gateway escucha espectro | Canal dedicado, antena discone |

> **Nota:** El control cognitivo opera íntegramente in-band. No se utiliza canal de control fuera de banda. La contingencia ante degradación abrupta se resuelve mediante el protocolo de Targeted Rendezvous (ver §7.4).

### 3.3 Banda de operación

- **TVWS UHF:** 470–698 MHz (plan de atribución peruano)
- **Canales disponibles:** 39 canales de 6 MHz
- **Frecuencia de referencia para cálculos:** 600 MHz
- **RX2 sensado:** barrido continuo 470–698 MHz, período 100–200 ms

---

## 4. Hardware por Nodo

> **Fuente única de las características de cada equipo: `SPECS EQUIPOS/`**
> (actualizado 28/08/2026) — un archivo por equipo, con la hoja técnica real
> del modelo ya comprado. Esta sección solo cita esos archivos; si una cifra
> cambia, se corrige ahí primero. `PRESUPUESTO COMPLETO.xlsx` sigue siendo la
> referencia de cantidades/ítems de compra (los # de esta sección son su
> número de fila), pero ya no es la fuente de las especificaciones técnicas.
> El plano de montaje físico completo (orden de componentes en el mástil,
> conectores por tramo) vive en `claudedocs/estructura_fisica_instalacion.md`
> — las tablas y diagramas de esta sección son la lista de equipos y la
> cadena lógica, no la geometría de instalación.
>
> **GDT eliminado del diseño (28/08/2026):** el proyecto decidió no usar
> descargador de sobretensión en ninguna rama RF — el enlace de validación
> opera de forma continua solo ~3 horas, no como instalación permanente
> expuesta a temporada de tormentas, así que el riesgo que el GDT mitigaría
> no aplica a esta ventana de uso. No hay, de hecho, ninguna línea de GDT en
> el presupuesto real. Ver `claudedocs/estructura_fisica_instalacion.md`
> para el razonamiento completo — si el proyecto pasa a una instalación
> permanente más adelante, reintroducir GDT ahí antes de dejar el enlace
> desatendido por temporada de lluvias/tormentas.

### 4.1 Nodo Gateway

| Componente | Especificación real (`SPECS EQUIPOS/`) | Función |
|---|---|---|
| SDR | bladeRF 2.0 micro xA4 — 47 MHz–6 GHz, 2×2 MIMO full-duplex, AD9361, 12 bits, VCTCXO 38.4MHz ±1ppm, 4× SMA-hembra (2TX/2RX), bias-tee 3.3V integrado y controlado por software en **todos** los puertos RF (`SDR_ENLACE`, presupuesto #11, x2 total, 1 por nodo) | TX datos DL (TX1) + RX uplink (RX1) + RX sensado CNN (RX2) |
| PC | Mini PC (10-20 núcleos, 32 GB DDR5, 1 TB SSD, PSU 300-500W 80+ Bronze — `COMPUTADORA_GATEWAY`, presupuesto #14) | GNU Radio + inferencia CNN ONNX Runtime — **spec de adquisición genérica, sin marca/modelo confirmado**; §10 (afinidad P-core/E-core) asume un Intel Core Ultra 5 225 como referencia, a confirmar contra la unidad realmente entregada |
| PA | "OEM 2W 1-900MHz", clase **A**, 1-900 MHz, P1dB **>32 dBm**, salida máxima +33 dBm, ganancia típica **30 dB a 500 MHz** (máx. 42 dB), entrada máxima tolerada **+3 dBm**, SMA-hembra ambos lados, 12V DC 300-400mA, PCB sobre disipador pasivo (`PA.md`, presupuesto #15, x2: 1 Gateway + 1 Cliente) | Amplificar TX antes de la antena — **⚠ la entrada máxima tolerada (+3 dBm) es menor que el TX máximo del bladeRF (+6 dBm): hay que operar el bladeRF a ganancia TX reducida por software antes de conectar el PA, no a su máximo — ver `claudedocs/requisitos_pa_lna.md`** |
| LNA RX | Nooelec LaNA — 20 MHz–4 GHz, ganancia +20 dB a 1000 MHz, NF 0.8-1.0 dB (0.9 típico) a 1000 MHz, entrada máx. 0 dBm, SMA-hembra ambos lados, bias-tee/USB/pines (`LNA.md`, presupuesto #4, x2: Gateway RX1 + Cliente RX1) | Bajar NF del receptor uplink a ~0.94 dB efectivo — montado en la boca de la antena, alimentado por bias-tee del propio bladeRF (ver cadena RX abajo) |
| LNA sensado | Mismo modelo Nooelec LaNA (presupuesto, "Gastos de subvención" #4, x1, solo Gateway) | Bajar NF de RX2 — igual que el LNA de datos, montado en la boca de la discone |
| Antena TX | LPDA PCB WA5VJB, 400-1000 MHz, **5 dBi a 500 MHz**, montaje SMA para PCB (o cable soldado directo), sustrato fibra de vidrio (`ANTENA_DIRECCIONAL`, presupuesto #10, x4 total: 2 Gateway + 2 Cliente) | Transmisión downlink (dedicada) — `LINK_BUDGET/` ya usa 5 dBi (hoja técnica real, no el spec de compra de ≥10 dBi que nunca se confirmó con el fabricante) |
| Antena RX | Misma LPDA WA5VJB, 5 dBi a 500 MHz, SMA (presupuesto #10, mismo lote que la antena TX) | Recepción uplink (dedicada) |
| Antena sensado | Discone Tram 1411, 25-1300 MHz, VSWR ≤1.5:1, **conector SO-239 (UHF hembra) confirmado**, montaje en mástil ≤35mm de diámetro (`ANTENA_OMNIDIRECCIONAL`, presupuesto #12, x1, solo Gateway) | Entrada dedicada de RX2 para sensado continuo — **⚠ 35mm de mástil máximo no calza con ninguno de los 2 tramos del mástil real (60mm/48mm, ver §5 de `claudedocs/estructura_fisica_instalacion.md`) — necesita reductor** |

**Cadena RF TX Gateway (downlink):**
```
bladeRF TX1 — ganancia TX reducida por software (NO al máximo +6 dBm: el
  PA solo tolera +3 dBm de entrada, ver nota de la tabla)
  → RG-316 pigtail (SMA-M↔SMA-M)
  → PA "OEM 2W 1-900MHz" (P1dB real 32 dBm, backoff 7.5 dB → salida
    promedio +24.5 dBm, clase A)
  → LMR-400 (conectores a confirmar — todo lo demás en esta cadena es
    SMA; longitud según instalación real, no fija, ver
    claudedocs/estructura_fisica_instalacion.md)
  → LPDA TX 5 dBi (SMA)
  → EIRP: ~+28.8 dBm (recalculado 28/08/2026 con hojas técnicas reales
    de SPECS EQUIPOS/ — antes +30.8 dBm con P1dB/ganancia de antena
    genéricos sin datasheet)
```

**Cadena RF RX Gateway (uplink):**
```
LPDA RX 5 dBi (SMA)
  → jumper corto (antena→LNA, pérdida ≈0 dB, ambos conectores SMA)
  → LNA Nooelec LaNA (NF 0.9 dB, +20 dB) — atornillado directo a la
    antena, en el tope del mástil, alimentado por bias-tee del propio
    bladeRF (circuito integrado en el puerto RX del SDR — sin inyector
    de hardware adicional, ver claudedocs/estructura_fisica_instalacion.md §6.1)
  → LMR-400 (longitud según instalación real, baja el mástil)
  → RG-316 pigtail (SMA-M↔SMA-H)
  → bladeRF RX1
  → NF sistema total: ~0.94 dB (se cumple porque el LNA va ANTES del
    tramo largo de cable, no después — ver claudedocs/estructura_fisica_instalacion.md §3.2)
```

**Cadena RF RX2 (sensado espectral — independiente):**
```
Discone Tram 1411 (SO-239)
  → adaptador SO-239↔SMA (todo lo demás en la cadena es SMA)
  → LNA de sensado — en el tope del mástil, junto a la discone, bias-tee
  → LMR-400 (longitud según instalación real)
  → bladeRF RX2
  → Barrido continuo 470–698 MHz → CNN cada 100–200 ms
```

### 4.2 Nodo Cliente

| Componente | Especificación real (`SPECS EQUIPOS/`) | Función |
|---|---|---|
| SDR | bladeRF 2.0 micro xA4 — mismo modelo que el Gateway, ver tabla 4.1 (`SDR_ENLACE`, presupuesto #11) | RX datos DL + TX uplink (no simultáneos — TDD por software, ver §3.1) |
| SBC | Orange Pi 5, 16 GB RAM, RK3588 (ARM64) | GNU Radio RX/TX, scripts de prueba, monitoreo remoto |
| PA TX | "OEM 2W 1-900MHz" — mismo modelo real que el Gateway, ver tabla 4.1 (`PA.md`, presupuesto #15) | Cierra el enlace UL con margen amplio (+34.5 dB BPSK a 4 km, LOS confirmado, §9.1) — misma advertencia de entrada máxima +3 dBm que el Gateway |
| LNA RX | Nooelec LaNA — mismo modelo que el Gateway (`LNA.md`, presupuesto #4) | Bajar NF downlink a ~0.94 dB efectivo — montado en la boca de la antena, bias-tee del propio bladeRF |
| Antena RX | LPDA WA5VJB, 5 dBi a 500 MHz, SMA (`ANTENA_DIRECCIONAL`, presupuesto #10) | Recepción downlink (dedicada) |
| Antena TX | Misma LPDA WA5VJB, 5 dBi a 500 MHz, SMA (presupuesto #10) | Transmisión uplink (dedicada) |
| Gabinete | IP65, 300×250×150mm (presupuesto #13, x2 comprados — 1 asignado al Cliente, ver `claudedocs/estructura_fisica_instalacion.md` §7 para el destino del segundo) | Protección ambiental en campo — aloja bladeRF, PA y Orange Pi 5 |

> **Cambio de diseño:** el candidato previo (LimeSDR Mini 2.0, en trámite de aduana) fue reemplazado por un segundo bladeRF 2.0 micro xA4 — mismo modelo que el Gateway. Esto elimina la necesidad de soportar un driver/calibración distintos para el Cliente.

> **Alimentación del Cliente — sin resolver:** el presupuesto no tiene
> ningún ítem de panel solar, batería o controlador de carga, pese a que
> el sitio no tiene red eléctrica confiable. El PA real consume 12V DC
> 300-400mA (`PA.md`) — un dato concreto para dimensionar la batería, que
> antes no existía. Ver `claudedocs/estructura_fisica_instalacion.md` §6.2
> — bloqueante para F4 si no se resuelve antes.

**Consideraciones generales para el SDR Cliente (bladeRF 2.0 micro xA4, mismo modelo que el Gateway):**
- DC offset / LO leakage en subportadora central (RFIC AD9361) → calibrar con `bladerf_set_correction()` / calibración nativa de `libbladeRF` antes de cada sesión — mismo procedimiento que el Gateway, ya no depende de "el modelo elegido"
- IQ imbalance → bloque IQ Corrector en GNU Radio (tiempo real)
- Timestamping: mismo VCTCXO ±1 ppm que el Gateway — a verificar en banco, pero ya no es una incógnita de hardware; mantener de todos modos la ventana de guarda de 10 ms en saltos de canal como margen conservador
- Driver: `gr-bladeRF`, igual que el Gateway — ya no hace falta soportar `gr-limesdr`/`gr-plutosdr` ni una capa de abstracción entre drivers distintos
- GNU Radio en ARM64: `gr-bladeRF`/`libbladeRF` deben compilarse desde fuente para RK3588 (sin wheels/paquetes precompilados garantizados) — reservar tiempo en F2 para esto

---

## 5. Parámetros OFDM del Canal de Datos

### 5.1 Configuración de la trama

| Parámetro | Valor | Justificación |
|---|---|---|
| Ancho de banda | 6 MHz | Canal TVWS estándar peruano |
| Subportadoras totales (FFT) | 512 puntos | Resolución frecuencial adecuada |
| Subportadoras de datos | 399 (offset 0, peor caso) / 400 (offsets 1-7) | Resto son guardas y pilotos — ver §5.2 |
| Subportadoras piloto | 57-58 según offset (comb escalonado, stride 8) | Estimación de canal + corrección CFO — ver §5.2 |
| Subportadoras de guarda | ~52 (26 por extremo) | Separación espectral con canales vecinos |
| Subportadoras de control | 3 útiles (#254, #256, #257) | Campo de control in-band (Formatos A/B/C) |
| Prefijo cíclico (CP) | 1/4 del símbolo (~56 µs) | Protección contra multipath |
| Duración símbolo OFDM | ~89 µs (CP + FFT) | 640 muestras a 7.68 MSPS |
| Modulaciones soportadas | BPSK / QPSK / 16-QAM | Selección adaptativa por CNN |
| Tasa de código FEC | 1/2 o 3/4 (convolucional o LDPC) | Protección contra errores de canal |

### 5.2 Distribución del vector IFFT (512 puntos)

```
Índice   0–25:   Banda de guarda inferior (26 sub → 0+0j)
Índice  26–253:  Datos + pilotos dispersos (~228 sub)
Índice 254–257:  Campo de control in-band (Formatos A/B/C, ver §7)
                   #254 → bit 0 del mensaje de control (BPSK)
                   #255 → EVITADA (DC offset / LO leakage del RFIC AD9361 — aplica a ambos nodos, mismo bladeRF)
                   #256 → bit 1 del mensaje de control (BPSK)
                   #257 → bit 2 del mensaje de control (BPSK)
Índice 258–486:  Datos + pilotos dispersos (~229 sub)
Índice 487–511:  Banda de guarda superior (25 sub → 0+0j)
```

**Patrón de subportadoras piloto (cerrado 07/09/2026):** comb-type
escalonado (staggered), stride 8, igual que LTE — el subconjunto de
pilotos rota símbolo a símbolo para cubrir toda la grilla de frecuencia
en un ciclo de 8 símbolos sin overhead adicional de pilotos fijos.

- **Pool lógico** (todo lo que no es guarda ni control, índices FFT
  `26–253` ∪ `258–486`): 457 posiciones.
- **Fórmula:** `offset = indice_simbolo % 8`; las posiciones piloto de
  ese símbolo son `pool[offset::8]` (el resto del pool, ese símbolo, son
  datos).
- **Ejemplo concreto — offset 0** (58 pilotos, el peor caso): primeros
  cinco índices FFT `26, 34, 42, 50, 58`; últimos tres `470, 478, 486`.
  Datos ese símbolo: 399. Offsets 1-7 dan 57 pilotos / 400 datos cada
  uno. La suma de pilotos de los 8 offsets es 457 — cobertura exacta del
  pool en un ciclo de 8 símbolos, sin solape ni huecos.
- **Valores piloto:** BPSK fijo (+1.0/−1.0), alternando según la
  *posición del piloto dentro del símbolo* (el primero es +1.0, el
  segundo −1.0, etc.) — no según el índice FFT absoluto. Determinista,
  hardcodeado igual en ambos nodos (enlace simétrico, mismo firmware),
  sin negociación en tiempo de ejecución.
- **Irregularidad aceptada (no es bug):** el espaciado del peine se
  ensancha de 8 a 12 subportadoras justo alrededor del hueco de control
  (#254-257), porque el peine ignora ese hueco al calcular las
  posiciones.
- Para el listado exhaustivo de índices por offset (los 457×8 valores),
  la fuente de verdad es el código:
  `TRANSMISION/pruebas/fase2_integracion_por_pares/prueba10_ofdm_tx/ofdm_symbol.py`,
  variables `PILOTOS_POR_OFFSET` / `DATOS_IDX_POR_OFFSET` — no se
  duplica aquí. Detalle de por qué se decidió este patrón (y qué se
  descartó) en `claudedocs/riesgos_arquitectura_transmision.md`,
  Problema 4.

### 5.3 Throughput por modo

| Modulación | Tasa FEC | Throughput bruto | Factor corrección FEC | Throughput neto (1 dirección, sin TDD) | **Throughput TDD 50/50 (por dirección)** |
|---|---|---|---|---|---|
| BPSK | 1/2 | 6 Mbps | × 0.321 | ~1.9 Mbps | **~0.92 Mbps** |
| BPSK | 3/4 | 6 Mbps | × 0.482 | ~2.9 Mbps | **~1.4 Mbps** |
| QPSK | 1/2 | 12 Mbps | × 0.321 | ~3.9 Mbps | **~1.9 Mbps** |
| QPSK | 3/4 | 12 Mbps | × 0.482 | ~5.8 Mbps | **~2.8 Mbps** |
| 16-QAM | 3/4 | 24 Mbps | × 0.482 | ~11.6 Mbps | **~5.6 Mbps** |

> **Recalculado bajo TDD (20/08/2026):** slot y duty cycle ya decididos
> (§3.1: 20 símbolos/slot, **50/50 simétrico** DL/UL, guarda pesimista 70
> µs → eficiencia de slot ~96.2%). Columna TDD = neto × 0.5 (duty cycle) ×
> 0.962 (eficiencia de guarda) ≈ neto × 0.481. Con el margen de enlace
> confirmado (§9.1: +25.5 dB incluso en 16-QAM a 4 km LOS, ambas direcciones),
> **16-QAM ya es viable en ambas direcciones**, no solo en Downlink — el
> límite ahora es el duty cycle, no el margen de enlace como antes del
> PA de 2 W en el Cliente (ver `claudedocs/requisitos_pa_lna.md`).

---

## 6. Canal de Datos — TX/RX Downlink y Uplink

### 6.1 Flujo TX Downlink (Gateway → Cliente)

```
[Internet / datos usuario]
    ↓
[MAC] Empaquetado: seq_num | next_ch | mod_scheme | CRC
    ↓
[FEC] Codificación convolucional o LDPC (tasa 1/2 o 3/4)
    ↓
[MOD] Mapeador: bits → símbolos I+jQ según BPSK/QPSK/16-QAM
    ↓
[OFDM] Carrier Allocator 512 sub → IFFT → CP 128 muestras
    ↓
[SDR] bladeRF DAC 12 bits → up-convert canal TVWS activo
    ↓
[RF]  PA 2W real (backoff 7.5 dB) → LMR-400 (longitud según instalación,
      sin GDT — ver §4.1) → LPDA TX (dedicada)
    ↓
[AIRE] EIRP ~+28.8 dBm | PRx Cliente ≈ −66.2 dBm a 4 km (LOS)
```

### 6.2 Flujo RX Downlink (en el Cliente)

```
[LPDA RX → LNA → LMR-400 → bladeRF Cliente ADC 12 bits]
    ↓
[SYNC] Schmidl-Cox: detecta inicio de símbolo, estima CFO
    ↓
[CORR] DC offset (herramienta de calibración del fabricante) + IQ Corrector (GNU Radio)
    ↓
[FFT]  512 puntos → 512 símbolos complejos en frecuencia
    ↓
[EQ]   Ecualización por canal usando pilotos como referencia
    ↓
[CTRL] Extrae sub #254, #256, #257 → decodifica next_ch + t_hop → verifica CRC-16
    ↓
[DEMOD] Demapeo constelación → Viterbi/LDPC → paquetes IP
    ↓
[APP]  Orange Pi 5 → AP WiFi → usuario final
```

### 6.3 Flujo TX Uplink (Cliente → Gateway, en su slot TDD — ver §3.1)

```
[Orange Pi 5 / datos usuario hacia Internet]
    ↓
[MAC + FEC + modulación adaptativa BPSK/QPSK/16-QAM] — ya no forzado a BPSK (ver nota abajo)
    ↓
[OFDM] IFFT 512 + CP 128 (incluye campo de control in-band Formato C: ACK + RSSI + SNR)
    ↓
[SDR] bladeRF 2.0 micro xA4 Cliente TX +6 dBm → PA 2W (backoff 7.5 dB)
    ↓
[RF]  LMR-400 (longitud según instalación, sin GDT — ver §4.1) → LPDA TX (dedicada)
    ↓
[AIRE] EIRP ~+28.8 dBm | PRx Gateway ≈ −66.2 dBm a 4 km (LOS)
```

> **Actualizado 20/08/2026 — UL ya no fuerza BPSK:** hasta esta fecha el
> Cliente transmitía sin PA (EIRP +12 dBm) y el margen UL no cerraba ni en
> BPSK a 15 km (§9.1 tenía el registro de las dos correcciones que llevaron
> a eso, 26/07 y 29/07). Con PA de 2 W confirmado también en el Cliente y
> la distancia final del enlace (4 km, actualizado 28/08/2026 — antes 6 km),
> el Uplink queda **simétrico al Downlink** (+34.5/+31.5/+25.5 dB
> BPSK/QPSK/16-QAM, §9.1 — recalculado 05/09/2026 con LOS confirmado por
> estudio de sitio, hojas técnicas reales de `SPECS EQUIPOS/` y la distancia
> final) — la modulación adaptativa por CNN aplica igual en ambas
> direcciones, ya no hay razón para forzar BPSK
> en UL por margen de enlace.

### 6.4 Flujo RX Uplink (en el Gateway)

```
[LPDA RX → LNA → LMR-400 → bladeRF Cliente RX1]
    ↓
[SYNC + FFT + EQ] — misma cadena que el Cliente en DL
    ↓
[DEMOD] Demapeo BPSK/QPSK/16-QAM (adaptativo, ver §6.3) → Viterbi/LDPC → paquetes IP → router fibra → Internet
```

> **TDD por software (§3.1):** TX1 y RX1 del bladeRF usan antenas LPDA dedicadas pero **no transmiten/reciben datos simultáneamente** — alternan por slot (DL/UL). RX2 (sensado) sigue operando en paralelo con su propia discone, sin relación con el esquema TDD de datos — es un canal independiente que no comparte antena ni cadena con TX1/RX1.

---

## 7. Canal de Control In-Band

El sistema opera control bidireccional **íntegramente in-band**, embebido en las subportadoras OFDM #254, #256 y #257 (BPSK, evadiendo la fuga DC en #255). No requiere hardware adicional ni canal fuera de banda. Capacidad: **3 bits por símbolo OFDM**.

Los mensajes de control son de **32 bits (4 bytes)**, fragmentados a lo largo de **11 símbolos OFDM** consecutivos (~1 ms). Se definen tres formatos según el tipo de instrucción.

### 7.1 Formato A — Salto Inmediato (Gateway → Cliente)

Se usa cuando la CNN predice degradación gradual del canal y hay tiempo de evacuar ordenadamente.

| Campo | Bits | Descripción |
|---|---|---|
| `Flag_Type` | 2 | `00` — Identifica este formato |
| `next_ch` | 6 | ID del canal TVWS destino (0–38) |
| `t_hop` | 8 | Tiempo hasta el salto (en slots de 10 ms) |
| **CRC-16** | 16 | Detección de errores (checksum de bits 0–15) |
| **Total** | **32** | |

### 7.2 Formato B — Actualización de Respaldo Proactiva (Gateway → Cliente)

Se transmite **continuamente** durante el periodo de enlace estable (horas/días). El Gateway actualiza al Cliente con los mejores canales de respaldo, uno a la vez, incluyendo instrucciones precisas de comportamiento al aterrizar.

| Campo | Bits | Descripción |
|---|---|---|
| `Flag_Type` | 2 | `01` — Identifica este formato |
| `Rank_ID` | 2 | Posición en la lista de respaldo (0 a 3) |
| `Channel_ID` | 6 | Canal TVWS asignado a esa posición |
| `Mod_Scheme` | 2 | Modulación recomendada al llegar (`00`=BPSK, `01`=QPSK, `10`=16QAM, `11`=reservado) |
| `Power_Flag` | 1 | `1`= Reducir ganancia TX si canal adyacente a TV activo (mitigación OOBE) |
| `Quiet_Flag` | 1 | `1`= Guardar silencio 10 ms al aterrizar para que la CNN re-confirme el canal |
| `Reservado` | 2 | Bits reservados para expansión futura |
| **CRC-16** | 16 | Detección de errores (checksum de bits 0–15) |
| **Total** | **32** | |

> **Nota sobre `Power_Flag`:** El Cliente no posee PA externo; la reducción de potencia se aplica directamente sobre la ganancia de transmisión (TX gain) del SDR vía software.

### 7.3 Formato C — ACK y Métricas Uplink (Cliente → Gateway)

El Cliente usa sus subportadoras in-band en el uplink para confirmar comandos y reportar la salud del enlace.

| Campo | Bits | Descripción |
|---|---|---|
| `Flag_Type` | 2 | `10` — Identifica este formato |
| `ACK_Type` | 2 | `00`=Respaldo recibido, `01`=Salto completado, `10`=Heartbeat, `11`=Reservado |
| `Rank_ACK` | 2 | Posición de respaldo que se confirma (si aplica) |
| `RSSI_rx` | 5 | Nivel de señal recibida (mapeado de −100 a −68 dBm, paso 1 dB) |
| `SNR_rx` | 5 | Relación señal a ruido (mapeado de 0 a 31 dB) |
| **CRC-16** | 16 | Detección de errores (checksum de bits 0–15) |
| **Total** | **32** | |

### 7.4 Protocolo de Targeted Rendezvous (contingencia ante caída abrupta)

El sistema reemplaza el enfoque de "canal refugio fijo" por un mecanismo dinámico de **Targeted Rendezvous**, que explota la asimetría Gateway inteligente / Cliente ciego para minimizar el tiempo de reconexión.

**Durante el periodo estable:** El Gateway transmite continuamente mensajes Formato B, manteniendo en el Cliente una lista actualizada de los mejores canales de respaldo (Top 4), ordenados por calidad según la CNN.

**Cuando el enlace colapsa abruptamente:**

1. **Gateway (inteligente):**
   - Detecta la caída (ausencia de ACKs Formato C en el uplink).
   - Consulta la lista Top 4 compartida con el Cliente.
   - La CNN verifica instantáneamente cuáles de esos canales siguen libres.
   - Salta al primer canal disponible de la lista y emite balizas de sincronización OFDM (preámbulo Schmidl-Cox repetido).

2. **Cliente (ciego):**
   - Al expirar su timeout de recepción, inicia la secuencia de contingencia.
   - **No barre los 39 canales al azar.** Salta exclusivamente siguiendo el orden de la lista de respaldo pre-acordada.
   - Se detiene ~20 ms en cada canal, buscando el preámbulo del Gateway.
   - Al encontrar la baliza, configura los parámetros asociados (modulación, potencia) y el enlace se restaura.

**Time-to-Rendezvous (TTR):** Con una lista de 4 canales y 20 ms por canal, el peor caso es **80 ms** — imperceptible para capas superiores (TCP/IP).

> **Nota histórica:** antes de adoptar Targeted Rendezvous (08/09/2026), la contingencia era un **canal de refugio fijo** pre-acordado (470 MHz, extremo de menor frecuencia de la banda TVWS del proyecto). Se descartó en favor del mecanismo dinámico de arriba, pero el dato técnico que motivó esa elección de frecuencia sigue siendo válido si alguna vez hiciera falta un canal de refugio de última instancia (p. ej. arranque en frío, sin lista Top 4 aún poblada): a 4 km, 470 MHz tiene ~3.4 dB menos pérdida de trayecto (FSPL) que 698 MHz, el extremo superior de la banda (`LINK_BUDGET/core.py::fspl_db`) — más margen de enlace justo cuando el enlace ya está degradado y necesita el colchón adicional.

### 7.5 Arquitectura de bloques GNU Radio — TX (`InbandControlTX`) / RX (`InbandControlRX`)

Implementación real: `SDR/inband_control.py` (con pruebas en `SDR/test_inband_control.py`). El pseudocódigo abajo documenta el patrón de wiring en GNU Radio — separación explícita entre la ruta de decisión (asíncrona, por mensajes) y la ruta de inyección/extracción de bits (síncrona, por símbolo OFDM, con el deadline real de ~89 µs):

```python
# Pseudocódigo — GNU Radio sync_block con puerto de mensajes de entrada.
# El armado del paquete (build_format_a/b/c, ver §7.7) ocurre en el handler
# (asíncrono); work() solo lee estado ya calculado, para no meter cómputo
# en la ruta de tiempo real.

class InbandControlTX(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, name="inband_control_tx",
                                in_sig=[...], out_sig=[...])
        self.message_port_register_in(pmt.intern("orden_control"))
        self.set_msg_handler(pmt.intern("orden_control"), self._on_orden_control)
        self._palabra_control = 0  # última palabra de 32 bits lista para inyectar

    def _on_orden_control(self, msg):
        # publicado por CognitiveEngine (Capa 4): un paquete Formato A, B o C
        # ya armado con su CRC-16 (build_format_a/b/c, §7.7) — el handler solo
        # guarda la palabra, nunca arma/calcula CRC dentro de work()
        self._palabra_control = pmt_a_uint32(msg)

    def work(self, input_items, output_items):
        # por símbolo OFDM: escribe el bit correspondiente de self._palabra_control
        # en sub #254/#256/#257 — sin CRC ni empaquetado aquí
        ...
```

```python
# Pseudocódigo — GNU Radio sync_block con puerto de mensajes de salida.
# work() solo extrae/acumula bits por símbolo (deadline real); la validación
# de CRC y la identificación del formato (por Flag_Type) se disparan una vez
# completado el mensaje, no en cada símbolo.

class InbandControlRX(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, name="inband_control_rx",
                                in_sig=[...], out_sig=None)
        self.message_port_register_out(pmt.intern("control_recibido"))
        self._buffer = []

    def work(self, input_items, output_items):
        sub254, sub256, sub257 = self._extraer_subportadoras(input_items)
        self._buffer.append([decode_bpsk(sub254), decode_bpsk(sub256), decode_bpsk(sub257)])
        if len(self._buffer) == 11:  # mensaje completo (11 símbolos × 3 bits)
            word = bits_to_uint32(self._buffer)
            if verify_crc16(word):
                self.message_port_pub(pmt.intern("control_recibido"),
                                       uint32_a_pmt(word))  # Flag_Type identifica A/B/C
            self._buffer.clear()
        return len(input_items[0])

# Ejecutor del control (fuera de este bloque) — se suscribe a 'control_recibido'
# y despacha según Flag_Type: Formato A programa la retunning real de
# RadioInterfaceDatos, Formato B actualiza la lista de respaldo local, etc.
def on_control_recibido(msg):
    word = pmt_a_uint32(msg)
    despachar_por_formato(word)  # lee Flag_Type y actúa según Formato A/B/C
```

### 7.6 Robustez del campo de control

Con PER del 10% y pre-anuncio de 20 repeticiones: P(fallo total) = 0.1²⁰ ≈ 10⁻²⁰. El campo de control es prácticamente irrompible mientras el canal de datos sea demodulable. El CRC-16 detecta el 100% de ráfagas de error ≤16 bits y el 99.998% de ráfagas mayores.

### 7.7 Pseudocódigo de referencia — construcción de paquetes

```python
# --- Gateway: construcción de paquetes ---
def build_format_a(next_ch, t_hop):
    payload = (0b00) | ((next_ch & 0x3F) << 2) | ((t_hop & 0xFF) << 8)
    crc = crc16(payload.to_bytes(2, 'big'))
    return payload | (crc << 16)

def build_format_b(rank, channel, mod, power, quiet):
    payload = (0b01) | ((rank & 0x3) << 2) | ((channel & 0x3F) << 4)
    payload |= ((mod & 0x3) << 10) | ((power & 0x1) << 12) | ((quiet & 0x1) << 13)
    # bits 14-15: reservados (0)
    crc = crc16(payload.to_bytes(2, 'big'))
    return payload | (crc << 16)

# --- Cliente: construcción de ACK ---
def build_format_c(ack_type, rank_ack, rssi, snr):
    payload = (0b10) | ((ack_type & 0x3) << 2) | ((rank_ack & 0x3) << 4)
    payload |= ((rssi & 0x1F) << 6) | ((snr & 0x1F) << 11)
    crc = crc16(payload.to_bytes(2, 'big'))
    return payload | (crc << 16)
```

---

## 8. Modelo de IA — CNN de Sensado Espectral

### 8.1 Arquitectura

El modelo clasifica **una sub-banda de 56 MHz por inferencia**, no los 39 canales de toda la banda de una sola vez — el bladeRF no puede capturar 228 MHz en una sola FFT (AD9361, ~56 MHz de ancho de banda instantáneo máximo), así que comprimir la entrada a un solo vector global obligaría a sacrificar resolución espectral sin ninguna ganancia real de latencia (el presupuesto de ciclo, 100–200 ms, sobra de sobra para 5 inferencias de <1 ms cada una). Backbone de tres bloques convolucionales con kernels decrecientes + `GlobalAveragePool1D`, terminando en dos cabezas sobre un tronco compartido:

| Parámetro | Valor |
|---|---|
| Tipo | 1D-CNN, backbone compartido + 2 cabezas (multi-task) |
| Entrada | PSD de 512 puntos por sub-banda (56 MHz, ~109 kHz/bin), normalizado [0,1] |
| Salida — cabeza ocupación | 9 logits (sigmoid en inferencia) — P(ocupado) por canal local de la sub-banda |
| Salida — cabeza margen | 9 valores — margen/SNR estimado en dB por canal (negativo si hay primario, positivo si está libre) |
| Parámetros | ~108,000 |
| Tamaño modelo ONNX | ~25–30 KB |
| Inferencia por sub-banda | <1 ms (Core Ultra 5 225, ONNX Runtime CPU) — medido ~0.1 ms |
| Ciclo de sensado completo | 100–200 ms (5 sub-bandas, RX2 bladeRF, barrido continuo) |
| Entrenamiento | PyTorch — local CPU-only (modelo de ~108K parámetros entrena en segundos/época; GPU/Colab no es necesaria a esta escala, queda como opción si el dataset real crece mucho) |
| Despliegue | `torch.onnx.export()` → ONNX Runtime |

**Por qué dos cabezas:** la Capa 4 (`CognitiveEngine`) soporta una política `max_margin`, pero P(ocupado) cerca de 0 no distingue cuál de varios canales libres está más limpio — todos saturan cerca de 0 por igual. La cabeza de margen, entrenada en paralelo sobre el mismo backbone (costo casi nulo en parámetros), da un valor continuo comparable entre canales libres.

### 8.2 Interfaz del clasificador y agregación a 39 canales

```python
# Contrato de interfaz — ChannelClassifier (una sub-banda por llamada)
class ChannelClassifier:
    def __init__(self, model_path: str, threshold: float = 0.20):
        ...

    def classify(self, psd_vector: np.ndarray) -> dict:
        """
        Args:
            psd_vector: array de 512 puntos float32, PSD normalizada de UNA sub-banda
        Returns:
            {
                'occupancy':   np.ndarray,    # [9] P(ocupado) por canal local
                'margen_db':   np.ndarray,    # [9] margen estimado por canal local
                'free_local':  list[int],     # índices locales libres
                'inference_ms': float,
                'confidence':  float          # mean(|p-0.5|*2): margen real a la
                                               # decisión, no mean(occupancy)
            }
        """

# SpectralOccupancyMap agrega las 5 llamadas de classify() (una por posición
# de barrido) en el mapa global de 39 canales que consume CognitiveEngine.
# Cada canal del mapa lleva su propio timestamp: las 5 sub-bandas no se
# capturan simultáneamente, así que el mapa nunca es una foto instantánea
# uniforme — el canal recién barrido es fresco, el de la posición anterior
# puede tener hasta ~150 ms de antigüedad dentro del mismo ciclo.
```

`free_channels`/`libres_por_indice` no vienen preordenados por ninguna política — ese ranking (`lowest_free`/`max_margin`/`least_used`) es responsabilidad exclusiva de `CognitiveEngine`, no del clasificador.

### 8.3 Dataset y domain mismatch

| Etapa | Hardware | ADC | Banda |
|---|---|---|---|
| Captura dataset (Fase 1) | RTL-SDR | 8 bits | 470–698 MHz |
| Inferencia en campo | bladeRF 2.0 | 12 bits | 470–698 MHz |

**Mitigación:** normalización por percentiles robustos (5/95) antes de alimentar la CNN, idéntica en entrenamiento e inferencia. El proyecto documenta el impacto medido de este domain mismatch sobre la accuracy del modelo como contribución técnica.

### 8.4 KPIs del modelo (objetivos conservadores)

| Métrica | Objetivo | Condición |
|---|---|---|
| Tasa de falsos negativos (libre→ocupado) | <5% | Asimetría regulatoria: interferir a un primario es la falla inaceptable, no la conservadora |
| Umbral operativo de campo | 0.20 (no 0.5) | Mismo razonamiento de costo asimétrico; 0.5 se usa solo para evaluar calidad del modelo en entrenamiento |
| Tiempo de inferencia por sub-banda | <2 ms | Core Ultra 5 225, ONNX Runtime CPU — deja amplio margen sobre el ciclo de 100–200 ms |
| Tamaño ONNX | <500 KB | El diseño con GAP lo logra naturalmente; deja casi todo el presupuesto original de 2–4 MB sin usar |
| Tiempo de evacuación de canal E2E | <300 ms | Campo real (sensado + CNN + control in-band + guarda) |

### 8.5 Resultados de validación — baseline sobre dataset sintético

Primer entrenamiento completo de extremo a extremo (arquitectura → entrenamiento → ONNX → benchmark), corrido localmente en CPU, 35 épocas sobre 6,000 sub-bandas **sintéticas** (`generar_dataset_sintetico.py`, formato de producción: 9 canales/sub-banda, ambas cabezas etiquetadas):

| Métrica | Resultado |
|---|---|
| AUC-ROC global (test) | 0.8815 |
| F1(β=2) @ umbral de campo 0.20 | 0.8014 |
| Sensibilidad @ 0.20 (detección de primarios) | 98.5% (38 falsos negativos / 7,746 etiquetas) |
| Especificidad @ 0.20 | 45.3% |
| Latencia ONNX Runtime (CPU) | 0.089 ms media, 0.135 ms P99 |
| Tamaño modelo ONNX | 26.2 KB |
| Parámetros entrenables | 107,986 |

> **Esto valida el pipeline (arquitectura, entrenamiento dual-head, export ONNX, presupuesto de latencia), no el desempeño en campo.** El dataset sintético modela artefactos plausibles del bladeRF (rolloff, ripple, DC leakage, fuga espectral entre canales) pero no una señal ISDB-Tb real, ni efectos de propagación/terreno, ni el plan de asignación de canales TV real de la zona de despliegue. Estos números son un baseline de referencia para confirmar que el código funciona — la validación real depende de capturar sub-bandas reales con el bladeRF (§12) y, idealmente, hacer fine-tuning o al menos evaluación sobre esos datos antes de tratarlos como cifras de desempeño operativo.

---

## 9. Link Budget y Parámetros de Rendimiento

### 9.1 Link budget (antenas dedicadas, sin pérdida de conmutador)

> **Fuente de verdad: `LINK_BUDGET/`.** Esta tabla es un snapshot para
> lectura rápida — si cambia cualquier parámetro (potencia, antena,
> LNA/PA, distancia, modulación), recalcular con la calculadora
> (`LINK_BUDGET/README.md`) y actualizar **solo este bloque**, no otros
> documentos. Estos valores **no dependen** de si DL/UL son simultáneos
> (full-duplex) o TDD (§3.1) — son el margen de una dirección a la vez, y
> siguen siendo válidos tras la decisión de TDD del 26/07/2026; lo que sí
> cambia con TDD es el throughput/latencia efectivos (§5.3, §9.2), no
> este link budget.

La eliminación del conmutador SPDT (reemplazado por antenas TX/RX dedicadas, ver §3.1) recupera 1.7–2.5 dB de margen en ambas direcciones respecto al diseño TDD-con-switch original. Los valores incluyen las pérdidas reales de cables LMR-400 — **ya no incluyen GDT**, eliminado del diseño el 28/08/2026 (enlace de validación de solo ~3h, no instalación permanente — ver `claudedocs/estructura_fisica_instalacion.md`).

**Actualizado 05/09/2026 — LOS confirmado por estudio de sitio, distancia final 4 km, hojas técnicas reales de `SPECS EQUIPOS/`:** ambos nodos llevan el mismo PA real ("OEM 2W 1-900MHz", P1dB >32 dBm, no el nominal genérico de 33 dBm usado antes), operado con backoff 7.5 dB (salida promedio +24.5 dBm), la antena LPDA real (WA5VJB, 5 dBi a 500 MHz, no el spec de compra de ≥10 dBi nunca confirmado ni el valor conservador de 6 dBi), la distancia final del enlace es **4 km**, y un estudio de sitio confirmó **línea de vista (LOS) despejada** entre Gateway y Cliente — ya no se asume la pérdida NLOS de 15 dB usada hasta el 04/09/2026. Downlink y Uplink siguen siendo simétricos:

| Parámetro | Downlink | Uplink |
|---|---|---|
| EIRP TX | +28.8 dBm (PA real, backoff 7.5 dB, sin GDT) | +28.8 dBm (PA real, backoff 7.5 dB, sin GDT) |
| FSPL (4 km, 600 MHz, LOS confirmado por estudio de sitio — sin término NLOS) | −100.0 dB | −100.0 dB |
| Ganancia antena RX | +5 dBi | +5 dBi |
| Potencia recibida estimada | ~−66.2 dBm | ~−66.2 dBm |
| NF receptor | ~0.94 dB | ~0.94 dB |
| Sensibilidad BPSK / QPSK / 16-QAM | −100.77 / −97.77 / −91.77 dBm | −100.77 / −97.77 / −91.77 dBm |
| **Margen BPSK / QPSK / 16-QAM** | **+34.5 / +31.5 / +25.5 dB** | **+34.5 / +31.5 / +25.5 dB** |

> **LOS confirmado por estudio de sitio (05/09/2026):** hasta el 04/09/2026 este link budget asumía 15 dB de pérdida adicional por NLOS (obstrucción de línea de vista), sin revalidar para la distancia final de 4 km. Un estudio de sitio confirmó que el enlace Gateway-Cliente es **LOS** (línea de vista despejada) a 4 km — no un supuesto ni un TBD, un hallazgo de campo. Esto retira el término NLOS del presupuesto (`LINK_BUDGET/core.py`, `perdida_nlos_db` default 15.0→0.0 dB), subiendo el margen ~15 dB en cada modulación respecto al snapshot anterior (+19.5/+16.5/+10.5 dB). Ningún otro parámetro de hardware cambió.

> **Historial (vigente hasta 20/08/2026, ya no aplica):** hasta esta fecha el
> Uplink no tenía PA (EIRP +12 dBm) y no cerraba ni en BPSK a 15 km (-7.3 dB)
> tras dos correcciones (26/07: TX real del bladeRF +6 dBm, no +10 dBm;
> 29/07: ganancia de antena LPDA 6 dBi, no 10 dBi). Ver `claudedocs/requisitos_pa_lna.md`
> para el registro completo — se resolvió confirmando PA de 2 W también en
> el Cliente y la distancia real del enlace, no con un rediseño de antena o
> modulación.
>
> **Corrección con hojas técnicas reales (28/08/2026):** hasta esta fecha se
> usaba P1dB=33dBm (nominal genérico "PA de 2W") y ganancia de antena 6dBi
> (valor conservador sin datasheet). La hoja técnica real del PA
> (`SPECS EQUIPOS/PA.md`) da P1dB **>32 dBm** (Psat es la cifra de 33 dBm,
> no P1dB) y clase **A** (no AB); la de la antena (`SPECS EQUIPOS/ANTENA_DIRECCIONAL`)
> da **5 dBi a 500 MHz**. A 6 km esto habría bajado el margen ~2.9 dB en
> cada modulación respecto al snapshot con specs genéricas — pero la
> reducción de distancia a 4 km (misma fecha, ver nota abajo) recupera
> ~3.5 dB de FSPL, así que el margen final (+19.5/+16.5/+10.5 dB) queda
> mejor que el snapshot original a 6 km con specs genéricas (+18.9/+15.9/+9.9 dB).
>
> **Distancia final del enlace: 4 km (28/08/2026).** Reemplaza el rango de
> diseño de 5-6 km que se usaba desde el 20/08/2026 (y antes, 10-15 km,
> antes de tener la ubicación real de los nodos). Recalcular
> automáticamente cualquier cifra derivada de la distancia (FSPL, margen,
> potencia recibida) con `LINK_BUDGET/` — no quedan valores hand-computed
> para 5-6 km en este documento.
>
> **Backoff del PA (20/08/2026):** operar a 7.5 dB de backoff (dentro del
> rango 6-9 dB exigido para linealidad OFDM, `claudedocs/requisitos_pa_lna.md`
> §3.1/§3.2 punto 5) en vez del mínimo posible — con margen de enlace
> abundante sobra espacio para priorizar linealidad/ACPR. Esto también deja
> la potencia conducida a la antena en ~+23.8 dBm (no depende de la
> distancia), dentro del límite legal de densidad espectral (Art. 8, 12.6
> dBm/100kHz) con ~6.1-6.6 dB de margen — resuelve el excedente de PSD que
> había marcado `claudedocs/cumplimiento_normativo_tvws.md` con el modelo
> de potencia anterior (sin backoff).
>
> **⚠ Entrada máxima del PA (nuevo, 28/08/2026):** la hoja técnica real
> (`SPECS EQUIPOS/PA.md`) especifica una entrada máxima tolerada de **+3 dBm**
> — el bladeRF a su ganancia TX máxima entrega ~+5.7 dBm al PA (tras el
> pigtail), por encima de ese límite. Hay que reducir la ganancia TX del
> bladeRF por software (no operarlo a su máximo) antes de conectar el PA —
> ver `claudedocs/requisitos_pa_lna.md` y `claudedocs/estructura_fisica_instalacion.md`.

### 9.2 Latencias del sistema

> **Recalculado bajo TDD (20/08/2026):** con slot/duty cycle ya decididos
> (§3.1: 20 símbolos/slot ≈1.78 ms, 50/50 DL/UL), un paquete espera en
> promedio medio ciclo de trama (~1.83 ms) y en el peor caso un ciclo
> completo (~3.66 ms con guarda pesimista de 70 µs) para su slot — muy por
> debajo del presupuesto de evacuación de canal (<300 ms). La señalización
> de control in-band, al viajar solo durante el slot DL, hereda esa misma
> espera en el peor caso — su latencia deja de ser <1 ms "puro" y pasa a
> ser <1 ms de transmisión efectiva + hasta ~3.66 ms de espera de turno.

| Componente | Valor | Origen |
|---|---|---|
| Propagación RF (4 km) | 0.013 ms | Física |
| Símbolo OFDM | ~89 µs | 640 muestras / 7.68 MSPS |
| Slot TDD (20 símbolos) | ~1.78 ms | §3.1, decidido 20/08/2026 |
| Ventana de guarda TDD (DL↔UL) | 25–70 µs | Settling bias PA + propagación 4 km — rango de diseño, no medido en banco (§3.1) |
| Inferencia CNN (ONNX) | <10 ms | Core Ultra 5 225 |
| Señalización control in-band | <1 ms transmisión + hasta ~3.66 ms espera de slot | Subportadoras #254–257, ver nota TDD arriba |
| Ciclo de sensado CNN | 100–200 ms | bladeRF RX2 barrido |
| Ventana de guarda en salto de canal | 10 ms | PLL lock + margen (retuning de frecuencia — distinto de la guarda TDD DL/UL) |
| **Latencia E2E datos** | **~1.8–3.7 ms (espera de slot TDD) + propagación + GNU Radio** | Recalculado 20/08/2026 con duty cycle 50/50 |
| **Evacuación de canal** | **<300 ms** | Sensado + CNN + control + guarda |

---

## 10. Configuración de Cómputo en Tiempo Real

El nodo Gateway usa un procesador Intel Core Ultra 5 225 con **arquitectura híbrida (P-cores + E-cores)**. GNU Radio requiere latencia consistente, por lo que el flowgraph debe anclarse explícitamente a los P-cores para evitar que el scheduler de Linux lo asigne a E-cores (más lentos), lo que causaría jitter o underruns en el flujo USB del bladeRF.

> **Sin confirmar contra la compra real (28/08/2026):** `SPECS EQUIPOS/COMPUTADORA_GATEWAY`
> — la fuente única para specs de hardware ya comprado — solo tiene la
> especificación genérica de licitación (10-20 núcleos, etc.), sin marca ni
> modelo. Todo lo que sigue en esta sección asume que la unidad entregada es
> efectivamente un Intel Core Ultra 5 225 (o equivalente con arquitectura
> híbrida P-core/E-core) — confirmar contra la unidad real antes de aplicar
> esta configuración; si el equipo entregado no tiene núcleos híbridos, esta
> sección completa no aplica y no hace falta `isolcpus`/afinidad P-core.

### 10.1 Identificación de núcleos

```bash
lscpu --extended
cat /sys/devices/cpu_core/cpus    # lista los P-cores
cat /sys/devices/cpu_atom/cpus    # lista los E-cores
```

### 10.2 Aislamiento de P-cores (GRUB)

```bash
# En /etc/default/grub, reservar P-cores (ej. núcleos 0-3) del scheduler general:
GRUB_CMDLINE_LINUX="isolcpus=0-3"
# Luego: sudo update-grub && reboot
```

### 10.3 Anclaje del flowgraph GNU Radio

```bash
# Forzar el flowgraph del Gateway a correr solo en los P-cores aislados:
taskset -c 0-3 python3 gateway_flowgraph.py
```

### 10.4 Control de interrupciones

```bash
# Desactivar irqbalance y enrutar IRQs lejos de los P-cores aislados
sudo systemctl disable irqbalance
# Enrutar IRQs del controlador USB a un núcleo no aislado (ej. núcleo 4)
```

> La inferencia CNN (ligera y periódica) y el resto del sistema operativo se ejecutan en los E-cores restantes, sin competir con el flowgraph en tiempo real. Esta configuración se documenta como parte del setup de Fase 2.

---

## 11. Cronograma Actualizado

> Cronograma reestructurado al 15/06/2026. F1 extendida 25 días por retraso en publicación RNP. F2/F3/F4 comprimidas para mantener cierre el 15/12/2026.

| Fase | Descripción | Inicio | Fin | Días | Responsable |
|---|---|---|---|---|---|
| **F1** ⚠ extendida | Recolección dataset + entrenamiento IA + compras HW | 18/05/2026 | 10/07/2026 | 53 | Franco R. Espinoza |
| **F2** comprimida | Integración SDR + capa MAC + bloque cognitivo | 10/07/2026 | 31/08/2026 | 52 | Victor M. Soto |
| **F3** comprimida | Enlace piloto urbano (azotea UNI) | 01/09/2026 | 20/10/2026 | 50 | Sandro G. Niño |
| **F4** comprimida | Despliegue rural 4 km + validación | 21/10/2026 | 02/12/2026 | 43 | Equipo completo |
| **F5** | Análisis + informe final | 03/12/2026 | 15/12/2026 | 13 | Equipo completo |

> **Alerta F5:** Solo 13 días para el cierre. La redacción del informe final debe iniciarse en paralelo desde F4.

---

## 12. Estado del Proyecto

**Fecha de referencia: 15 de junio de 2026** (secciones individuales tienen
correcciones puntuales más recientes, con su propia fecha — ver ⚠ en §3.1,
§5.3, §9.1, §9.2; esta fecha de referencia cubre la estructura general del
documento, no cada cifra).

### ✅ Completado

- Arquitectura completa del bloque cognitivo GNU Radio (todas las capas)
- Diseño del esquema de control in-band con 3 formatos (A: Salto, B: Respaldo Proactivo, C: ACK Uplink)
- Protocolo de Targeted Rendezvous como contingencia (reemplaza canal refugio fijo)
- Especificación técnica completa de hardware (ambos nodos)
- Decisión de arquitectura de antena con 4 LPDA dedicadas (eliminación de conmutadores SPDT) — inicialmente para full-duplex real, **revisada el 26/07/2026 a TDD por software** tras evaluar el aislamiento TX→RX requerido (ver §3.1)
- Selección de PC Gateway (Core Ultra 5 225) y estrategia de afinidad de CPU para tiempo real
- Link budget recalculado con la mejora de margen de las antenas dedicadas (válido independientemente del esquema de duplexado, ver §9.1) — ahora mantenido en `LINK_BUDGET/`
- Decisiones de diseño documentadas: eliminación LoRa, antenas TX/RX dedicadas (full-duplex → TDD por software), LNA GW, Orange Pi 5 como nodo Cliente
- Implementación del modelo CNN 1D dual-head (`SpectralSenseCNN`) y del pipeline completo: dataset sintético de formato de producción, entrenamiento, export ONNX, `ChannelClassifier`/`SpectralOccupancyMap` de inferencia (ver §8)
- Entrenamiento y validación end-to-end corridos sobre dataset sintético — baseline de referencia documentado en §8.5

### 🔄 En progreso / Pendiente inmediato

- Publicación de adquisiciones en portal RNP
- Captura de dataset espectral TVWS 470–698 MHz real (protocolo definido, pendiente ejecución) — el modelo solo ha sido validado sobre datos sintéticos (§8.5)
- Validación/fine-tuning del modelo CNN 1D sobre datos reales una vez capturados
- Prueba de inferencia ONNX en el hardware de campo real (Core Ultra 5 225)

### 📋 Pendiente por fase

- **F2:** Implementación del flowgraph GNU Radio completo, integración ONNX, configuración de afinidad de CPU, pruebas de banco
- **F3:** Enlace piloto en azotea UNI, medición de link budget real, validación CNN con primarios TV
- **F4:** Despliegue rural a 4 km, validación end-to-end
- **F5:** Análisis de resultados, informe final, preparación de publicación

### Cambios respecto a la propuesta original

| # | Aspecto | Original | Actualizado |
|---|---|---|---|
| 1 | SDR Cliente | PlutoSDR (USB 2.0) → luego LimeSDR Mini 2.0 (candidato, en trámite de aduana) | **bladeRF 2.0 micro xA4 — mismo modelo que el Gateway** (reemplaza al LimeSDR) |
| 2 | Canal de control | LoRa SX1262 (915 MHz, fuera de banda) | Control in-band bidireccional (3 formatos) + Targeted Rendezvous |
| 3 | LNA Gateway | No contemplado | Añadido (NF≤1 dB), margen UL: +0.9→+3.7 dB |
| 4 | Arquitectura de antena | Full-duplex simultáneo (2 antenas) | 4 antenas LPDA dedicadas (sin conmutador TDD físico) — hardware sin cambios |
| 4b | Esquema de duplexado (26/07/2026) | Full-duplex real (DL/UL simultáneos) | **TDD por software** (DL/UL alternan en el tiempo, TX apagado digitalmente en el slot ajeno) — el full-duplex real se descartó al no cerrar el aislamiento TX→RX requerido solo con separación de antenas; detalle en §3.1 y `claudedocs/riesgos_arquitectura_transmision.md` |
| 5 | PC Cliente | Mini PC Intel N100 | Orange Pi 5 16 GB (hardware del equipo, ARM64) |
| 6 | PC Gateway | Mini PC Ryzen 9 8945HS | Mini PC Intel Core Ultra 5 225 (con config. de afinidad P-core) |
| 7 | Distancia de enlace | 15–20 km | 4 km (final, 28/08/2026 — antes 5–6 km desde 20/08/2026, y antes de eso 10–15 km) |
| 8 | Duración F2/F3/F4 | 61/60/47 días | 52/50/43 días (compresión por retraso F1) |

---

## 13. Software y Dependencias

### Nodo Gateway (Ubuntu 22.04 LTS, x86_64)

| Herramienta | Versión | Uso |
|---|---|---|
| GNU Radio | 3.10.x | Procesamiento de señal SDR |
| gr-bladeRF | última | Driver bladeRF 2.0 |
| ONNX Runtime | ≥1.16 | Inferencia CNN en campo |
| PyTorch | ≥2.0 | Entrenamiento CNN (Colab) |
| Python | ≥3.10 | Lógica cognitiva y control |
| util-linux (taskset) | sistema | Afinidad de CPU para tiempo real |

> El equipo Gateway viene con Ubuntu 25.04 preinstalado; se recomienda reinstalar Ubuntu 22.04 LTS para mantener compatibilidad con el stack GNU Radio validado.

### Nodo Cliente (Ubuntu 22.04 LTS, ARM64 — Orange Pi 5)

| Herramienta | Versión | Uso |
|---|---|---|
| GNU Radio | 3.10.x | Demodulación OFDM |
| gr-bladeRF | última (compilado desde fuente para ARM64) | Driver bladeRF 2.0 — mismo paquete que el Gateway |
| libbladeRF (`bladerf_set_correction()`) | última | Calibración DC offset e IQ, nativa del bladeRF |
| Python | ≥3.10 | Scripts de prueba y monitoreo |

### Herramientas de desarrollo

| Herramienta | Uso |
|---|---|
| PyTorch + Google Colab Pro | Entrenamiento CNN (GPU T4) |
| GitHub (este repositorio) | Control de versiones y documentación |
| Overleaf | Informes técnicos en LaTeX |
| Notion | Gestión de tareas y wiki del equipo |

---

*Última actualización: julio de 2026 | Contacto: PI Galvez Legua, Mauricio Pedro — UNI FIEE-IITMC*
