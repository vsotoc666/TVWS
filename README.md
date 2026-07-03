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

El aporte central de este proyecto no es el enlace de radio en sí, sino el **bloque de software GNU Radio** que implementa la radio cognitiva completa: desde el sensado espectral con CNN hasta la señalización de salto de canal in-band. El enlace de 10–15 km en Fase 4 es la validación de ese bloque en condiciones reales.

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

### 2.2 Capas del bloque

#### Capa 1 — Adquisición (`RadioInterface`)
Abstracción del hardware SDR. Expone una API uniforme independientemente de si el SDR subyacente es un bladeRF, el SDR full-duplex del Cliente (modelo por definir) u otro. Resuelve internamente las diferencias de driver (`gr-bladeRF` vs el driver específico del SDR Cliente elegido), calibración de DC offset, corrección IQ, y configuración de frecuencia/ganancia.

**Parámetros configurables:** frecuencia central, ancho de banda de muestreo, ganancia RX, tipo de hardware (`bladerf` | `cliente_fd` | `generic`).

#### Capa 2 — Sensado espectral (`SpectralSensor`)
El bladeRF (AD9361) tiene ~56 MHz de ancho de banda instantáneo máximo: es físicamente imposible capturar los 228 MHz de la banda TVWS (470–698 MHz) en una sola FFT. Esta capa orquesta un **barrido de 5 posiciones de sintonización** sobre el RX2 (canal dedicado a sensado, independiente del TX/RX de datos), cada una cubriendo una sub-banda de 56 MHz con 7–9 canales TVWS visibles. Por cada sub-banda capturada calcula la PSD (FFT de 512 puntos, ventana Hann, método Welch) y la entrega normalizada al clasificador CNN. Luego de las 5 capturas, ensambla el mapa global de los 39 canales (ver Capa 3 y §8).

**Parámetros configurables:** posiciones de barrido, ancho de sub-banda, tamaño FFT, período de ciclo.

#### Capa 3 — Clasificador CNN (`ChannelClassifier`) + mapa de ocupación (`SpectralOccupancyMap`)
Modelo CNN 1D ejecutado vía ONNX Runtime. Clasifica **una sub-banda de 56 MHz por inferencia** (no la banda completa de una sola vez — ver Capa 2), con dos salidas: probabilidad de ocupación por canal y margen/SNR estimado en dB por canal (esta segunda cabeza existe para que la política `max_margin` de la Capa 4 tenga un valor continuo que comparar entre canales libres, no solo probabilidades saturadas cerca de 0). `SpectralOccupancyMap` agrega las 5 sub-bandas del ciclo en el mapa global de 39 canales, con timestamp por canal — las sub-bandas no se capturan simultáneamente, así que el mapa nunca es una foto instantánea uniforme. Agnóstico al modelo: acepta cualquier `.onnx` que cumpla la interfaz de entrada/salida especificada.

**Parámetros configurables:** ruta del modelo ONNX, umbral de decisión, número de canales por sub-banda, frecuencia de actualización.

#### Capa 4 — Decisión cognitiva (`CognitiveEngine`)
Implementa la política de selección de canal y el protocolo de salto. Genera y mantiene actualizada la **Lista de Respaldo Proactiva** (Top 4 canales más limpios según la CNN), que se transmite continuamente al Cliente vía Formato B (ver §7). Ante degradación abrupta, ejecuta el protocolo de **Targeted Rendezvous** (ver §7.4).

**Parámetros configurables:** política de selección (`lowest_free` | `max_margin` | `least_used`), tamaño de la lista de respaldo (1–4), tiempo de pre-anuncio, número de confirmaciones CRC, umbral de degradación, timeout de rendezvous.

#### Capa 5 — Control in-band (`InbandControlLayer`)
Implementa la señalización bidireccional in-band mediante 3 formatos de mensaje de 32 bits sobre las subportadoras OFDM #254–257 (BPSK, 3 bits/símbolo, ~1 ms por mensaje). **Formato A** (DL): Salto Inmediato. **Formato B** (DL): Actualización de Respaldo Proactiva con canal, modulación recomendada, flag de potencia y flag de silencio. **Formato C** (UL): ACK del Cliente con métricas RSSI/SNR. Ver §7 para la especificación completa.

**Parámetros configurables:** índices de subportadoras de control, esquema de modulación del campo de control, número de repeticiones del pre-anuncio, tamaño de la lista de respaldo.

#### Capa 6 — Interfaz de monitoreo (`MonitoringDashboard`)
Dashboard en tiempo real que muestra el estado completo del sistema cognitivo. Implementado como interfaz Qt integrada en GNU Radio con opción de servidor WebSocket para monitoreo remoto (relevante para acceso desde laptop externa al nodo Cliente).

**Paneles:** espectrograma de la banda TVWS, mapa de ocupación de canales con confianza CNN, canal activo y próximo canal anunciado, historial de saltos, métricas en tiempo real (throughput DL/UL, SNR, BER, margen de enlace), estado del clasificador (última inferencia, tiempo de inferencia, accuracy acumulada).

---

## 3. Arquitectura del Sistema de Validación

El bloque cognitivo se valida sobre un enlace punto a punto real **full-duplex**:

```
[Comunidad rural — 10-15 km]              [Localidad con fibra]
  Usuarios locales
       │
  [AP WiFi local]
       │
  Orange Pi 5 (16GB)  ←──── OFDM TVWS ────→  Mini PC Core Ultra 5
  + SDR full-duplex (TBD)                       + bladeRF 2.0 micro xA4
  Nodo CLIENTE                                 Nodo GATEWAY
  (demodula, ejecuta)                          (CNN + decisión cognitiva)
       │                                              │
  LPDA TX + LPDA RX                            LPDA TX + LPDA RX + discone
  (full-duplex, 2 antenas)                     (full-duplex, 2 antenas + sensado)
  LNA (NF≤1dB)                                LNA (NF≤1dB) + PA 2W
                                                      │
                                               Router fibra óptica
                                                      │
                                                  Internet
```

**Principio de operación:** El bloque cognitivo corre íntegramente en el Gateway. El Cliente solo ejecuta las órdenes de salto recibidas vía el campo de control in-band, sin lógica cognitiva propia.

### 3.1 Arquitectura full-duplex (actualización de diseño)

El sistema opera en **full-duplex real**, aprovechando la capacidad 2TX/2RX simultáneos del bladeRF 2.0 micro xA4 y la operación full-duplex del SDR del Cliente (modelo por definir, ver §4.2). Cada nodo utiliza **dos antenas LPDA dedicadas** —una para TX y otra para RX— eliminando la necesidad de conmutación TDD.

> **Cambio de diseño respecto a versiones anteriores:** Se descartó la arquitectura TDD con conmutador SPDT por dos motivos: (1) la dificultad de aprovisionamiento de conmutadores RF de las especificaciones requeridas en el mercado local, y (2) el full-duplex con antenas dedicadas preserva el throughput simultáneo de ambas direcciones y recupera la pérdida de inserción del conmutador (1.7–2.5 dB), mejorando el margen de enlace en ambos sentidos.

**Implicaciones de la arquitectura full-duplex:**
- 4 antenas LPDA en total (2 por nodo: TX y RX), más la discone de sensado en el Gateway
- Sin pérdida de inserción de conmutador → mejora de ~2 dB en margen DL y UL
- DL y UL operan simultáneamente, sin división temporal del canal
- Requiere separación física/angular adecuada entre las LPDA de TX y RX de un mismo nodo para minimizar el acoplamiento directo TX→RX (autointerferencia)

### 3.2 Planos de comunicación

| Plano | Medio | Dirección | Implementación |
|---|---|---|---|
| **Datos** | OFDM 6 MHz, 470–698 MHz | DL y UL (full-duplex) | GNU Radio, bladeRF TX1/RX1 + SDR Cliente |
| **Control** | Subportadoras OFDM #254–257 | Bidireccional (DL + UL) | In-Band: 3 formatos (Salto, Respaldo Proactivo, ACK Uplink), <1 ms latencia |
| **Sensado** | bladeRF RX2 | Gateway escucha espectro | Canal dedicado, antena discone |

> **Nota:** El control cognitivo opera íntegramente in-band. No se utiliza canal de control fuera de banda. La contingencia ante degradación abrupta se resuelve mediante el protocolo de Targeted Rendezvous (ver §7.4).

### 3.3 Banda de operación

- **TVWS UHF:** 470–698 MHz (plan de atribución peruano)
- **Canales disponibles:** 39 canales de 6 MHz
- **Frecuencia de referencia para cálculos:** 600 MHz
- **RX2 sensado:** barrido continuo 470–698 MHz, período 100–200 ms

---

## 4. Hardware por Nodo

### 4.1 Nodo Gateway

| Componente | Especificación | Función |
|---|---|---|
| SDR | bladeRF 2.0 micro xA4 — 2TX/2RX, 12 bits, VCTCXO ±1 ppm | TX datos DL (TX1) + RX uplink (RX1) + RX sensado CNN (RX2) |
| PC | Mini PC Intel Core Ultra 5 225 (10 núcleos, hasta 4.9 GHz), 32 GB DDR5, 1 TB SSD | GNU Radio + inferencia CNN ONNX Runtime |
| PA | 400–1000 MHz, 2W (33 dBm), clase AB | Amplificar TX antes de la antena |
| LNA RX | 400–1000 MHz, NF ≤1 dB, ganancia 15–25 dB | Bajar NF del receptor uplink a ~1 dB efectivo |
| Antena TX | LPDA 400–2700 MHz, 10 dBi, N-hembra | Transmisión downlink (dedicada) |
| Antena RX | LPDA 400–2700 MHz, 10 dBi, N-hembra | Recepción uplink (dedicada) |
| Antena sensado | Discone 25–1300 MHz, omnidireccional | Entrada dedicada de RX2 para sensado continuo |
| GDT | N-H/N-M, DC–3 GHz, ≤0.3 dB, ≥5 kA (8/20µs), IP67 | Protección de sobretensión por rama RF |

**Cadena RF TX Gateway (downlink):**
```
bladeRF TX1 (+6 dBm)
  → RG-316 pigtail 0.6m (SMA-M↔SMA-M)
  → PA 2W (+27 dB)
  → LMR-400 3.5m + GDT (N-M↔N-M)
  → LPDA TX 10 dBi
  → EIRP: ~+41.7 dBm (sin pérdida de conmutador)
```

**Cadena RF RX Gateway (uplink):**
```
LPDA RX 10 dBi
  → LMR-400 3.5m + GDT (N-M↔N-M)
  → LNA (NF ≤1 dB, +20 dB) — montar próximo a la antena
  → RG-316 pigtail 0.3-0.5m (SMA-M↔N-H)
  → bladeRF RX1
  → NF sistema total: ~1.04 dB
```

**Cadena RF RX2 (sensado espectral — independiente):**
```
Discone omnidireccional
  → LMR-400 3.5m + GDT (N-M↔SO239/N adaptador)
  → bladeRF RX2
  → Barrido continuo 470–698 MHz → CNN cada 100–200 ms
```

### 4.2 Nodo Cliente

| Componente | Especificación | Función |
|---|---|---|
| SDR | Por definir — full-duplex, ADC 12 bits, ≥30 MSPS (USB 3.0), TCXO ±2 ppm típico | RX datos DL + TX uplink (simultáneos) |
| SBC | Orange Pi 5, 16 GB RAM, RK3588 (ARM64) | GNU Radio RX/TX, scripts de prueba, monitoreo remoto |
| LNA RX | 400–1000 MHz, NF ≤1 dB, ganancia 15–25 dB | Bajar NF downlink a ~1 dB efectivo |
| Antena RX | LPDA 400–2700 MHz, 10 dBi, N-hembra | Recepción downlink (dedicada) |
| Antena TX | LPDA 400–2700 MHz, 10 dBi, N-hembra | Transmisión uplink (dedicada) |
| Gabinete | IP65 | Protección ambiental en campo |
| GDT | N-H/N-M, DC–3 GHz, ≤0.3 dB, ≥5 kA (8/20µs), IP67 | Protección de sobretensión por rama RF |

**Consideraciones generales para el SDR Cliente (modelo final por definir):**
- DC offset / LO leakage en subportadora central → calibrar con la herramienta del fabricante antes de cada sesión (procedimiento específico depende del modelo elegido)
- IQ imbalance → bloque IQ Corrector en GNU Radio (tiempo real)
- Timestamping hardware: a verificar según el modelo; si no es preciso, mantener ventana de guarda de 10 ms en saltos de canal
- Driver específico del fabricante (p. ej. `gr-limesdr`, `gr-plutosdr`, según el SDR finalmente seleccionado) distinto a `gr-bladeRF` → resuelto por la capa `RadioInterface`
- GNU Radio en ARM64: puede requerir compilación desde fuente del driver del SDR elegido (verificar disponibilidad para RK3588)

---

## 5. Parámetros OFDM del Canal de Datos

### 5.1 Configuración de la trama

| Parámetro | Valor | Justificación |
|---|---|---|
| Ancho de banda | 6 MHz | Canal TVWS estándar peruano |
| Subportadoras totales (FFT) | 512 puntos | Resolución frecuencial adecuada |
| Subportadoras de datos | ~420 | Resto son guardas y pilotos |
| Subportadoras piloto | ~55 dispersas | Estimación de canal + corrección CFO |
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
                   #255 → EVITADA (DC offset / LO leakage del SDR Cliente)
                   #256 → bit 1 del mensaje de control (BPSK)
                   #257 → bit 2 del mensaje de control (BPSK)
Índice 258–486:  Datos + pilotos dispersos (~229 sub)
Índice 487–511:  Banda de guarda superior (25 sub → 0+0j)
```

### 5.3 Throughput por modo

| Modulación | Tasa FEC | Throughput bruto | Factor corrección | Throughput neto |
|---|---|---|---|---|
| BPSK | 1/2 | 6 Mbps | × 0.321 | ~1.9 Mbps |
| BPSK | 3/4 | 6 Mbps | × 0.482 | ~2.9 Mbps |
| QPSK | 1/2 | 12 Mbps | × 0.321 | ~3.9 Mbps |
| QPSK | 3/4 | 12 Mbps | × 0.482 | ~5.8 Mbps |
| 16-QAM | 3/4 | 24 Mbps | × 0.482 | ~11.6 Mbps |

> Con full-duplex, DL y UL alcanzan estos valores **simultáneamente** (no divididos en el tiempo como ocurriría en TDD). Objetivos conservadores validados en Fase 4 (10–15 km, NLOS 15 dB): **≥1.9 Mbps DL** y **≥1.9 Mbps UL** en BPSK R=1/2.

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
[RF]  PA 2W → GDT → LMR-400 → LPDA TX (dedicada)
    ↓
[AIRE] EIRP ~+41.7 dBm | PRx Cliente ≈ −77 dBm a 15 km
```

### 6.2 Flujo RX Downlink (en el Cliente)

```
[LPDA RX → LNA → LMR-400 → SDR Cliente ADC 12 bits]
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

### 6.3 Flujo TX Uplink (Cliente → Gateway, simultáneo con RX)

```
[Orange Pi 5 / datos usuario hacia Internet]
    ↓
[MAC + FEC + BPSK] — modulación forzada (margen ajustado en UL)
    ↓
[OFDM] IFFT 512 + CP 128 (incluye campo de control in-band Formato C: ACK + RSSI + SNR)
    ↓
[SDR] SDR Cliente TX +10 dBm (sin PA, valor de referencia — ajustar según modelo final)
    ↓
[RF]  LMR-400 → LPDA TX (dedicada)
    ↓
[AIRE] EIRP +20 dBm | PRx Gateway ≈ −96 dBm a 15 km
```

### 6.4 Flujo RX Uplink (en el Gateway)

```
[LPDA RX → GDT → LNA → SDR Cliente RX1]
    ↓
[SYNC + FFT + EQ] — misma cadena que el Cliente en DL
    ↓
[DEMOD] BPSK → Viterbi → paquetes IP → router fibra → Internet
```

> **Full-duplex:** TX1 y RX1 del bladeRF operan simultáneamente sobre antenas LPDA dedicadas. RX2 (sensado) opera en paralelo con su propia discone. Las tres cadenas RF del Gateway funcionan de forma concurrente e independiente.

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

### 7.5 Robustez del campo de control

Con PER del 10% y pre-anuncio de 20 repeticiones: P(fallo total) = 0.1²⁰ ≈ 10⁻²⁰. El campo de control es prácticamente irrompible mientras el canal de datos sea demodulable. El CRC-16 detecta el 100% de ráfagas de error ≤16 bits y el 99.998% de ráfagas mayores.

### 7.6 Pseudocódigo de referencia

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

### 9.1 Link budget (full-duplex, sin pérdida de conmutador)

La eliminación del conmutador SPDT recupera 1.7–2.5 dB de margen en ambas direcciones respecto al diseño TDD anterior. Los valores incluyen las pérdidas reales de GDT y cables LMR-400.

| Parámetro | Downlink | Uplink |
|---|---|---|
| EIRP TX | +41.7 dBm (PA 2W) | +20 dBm (sin PA) |
| FSPL + NLOS (15 km, 600 MHz) | −126 dB | −126 dB |
| Ganancia antena RX | +10 dBi | +10 dBi |
| Potencia recibida estimada | ~−77 dBm | ~−96 dBm |
| NF receptor | ~1.0 dB (LNA CLI) | ~1.04 dB (LNA GW) |
| Sensibilidad BPSK | −100.7 dBm | −100.7 dBm |
| **Margen BPSK** | **~+18 dB** | **~+3.7 dB** |
| Sensibilidad QPSK | −97.7 dBm | — |
| **Margen QPSK** | **~+15 dB** | **+0.7 dB (marginal)** |

> **Mejora por full-duplex:** Al eliminar el conmutador, el margen UL BPSK sube de ~+1.4 dB (diseño TDD) a ~+3.7 dB, dando un colchón mucho más robusto frente a lluvia o NLOS mayor al estimado. El PA en el Cliente queda como contingencia documentada para Fase 4 solo si las mediciones reales lo requieren.

### 9.2 Latencias del sistema

| Componente | Valor | Origen |
|---|---|---|
| Propagación RF (15 km) | 0.050 ms | Física |
| Símbolo OFDM | ~89 µs | 640 muestras / 7.68 MSPS |
| Inferencia CNN (ONNX) | <10 ms | Core Ultra 5 225 |
| Señalización control in-band | <1 ms | Subportadoras #254–257 |
| Ciclo de sensado CNN | 100–200 ms | bladeRF RX2 barrido |
| Ventana de guarda en salto | 10 ms | PLL lock + margen |
| **Latencia E2E datos** | **10–30 ms** | Propagación + GNU Radio |
| **Evacuación de canal** | **<300 ms** | Sensado + CNN + control + guarda |

---

## 10. Configuración de Cómputo en Tiempo Real

El nodo Gateway usa un procesador Intel Core Ultra 5 225 con **arquitectura híbrida (P-cores + E-cores)**. GNU Radio requiere latencia consistente, por lo que el flowgraph debe anclarse explícitamente a los P-cores para evitar que el scheduler de Linux lo asigne a E-cores (más lentos), lo que causaría jitter o underruns en el flujo USB del bladeRF.

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
| **F4** comprimida | Despliegue rural 10–15 km + validación | 21/10/2026 | 02/12/2026 | 43 | Equipo completo |
| **F5** | Análisis + informe final | 03/12/2026 | 15/12/2026 | 13 | Equipo completo |

> **Alerta F5:** Solo 13 días para el cierre. La redacción del informe final debe iniciarse en paralelo desde F4.

---

## 12. Estado del Proyecto

**Fecha de referencia: 15 de junio de 2026**

### ✅ Completado

- Arquitectura completa del bloque cognitivo GNU Radio (todas las capas)
- Diseño del esquema de control in-band con 3 formatos (A: Salto, B: Respaldo Proactivo, C: ACK Uplink)
- Protocolo de Targeted Rendezvous como contingencia (reemplaza canal refugio fijo)
- Especificación técnica completa de hardware (ambos nodos)
- Decisión de arquitectura full-duplex con 4 antenas LPDA (eliminación de conmutadores SPDT)
- Selección de PC Gateway (Core Ultra 5 225) y estrategia de afinidad de CPU para tiempo real
- Link budget recalculado con la mejora de margen del full-duplex
- Decisiones de diseño documentadas: eliminación canal fuera de banda, full-duplex, LNA GW, Orange Pi 5 como nodo Cliente
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
- **F4:** Despliegue rural a 10–15 km, validación end-to-end
- **F5:** Análisis de resultados, informe final, preparación de publicación

### Cambios respecto a la propuesta original

| # | Aspecto | Original | Actualizado |
|---|---|---|---|
| 1 | SDR Cliente | PlutoSDR (USB 2.0) | SDR full-duplex genérico, USB 3.0, ≥30 MSPS, ADC 12 bits (modelo final por definir) |
| 2 | Canal de control | LoRa SX1262 (915 MHz, fuera de banda) | Control in-band bidireccional (3 formatos) + Targeted Rendezvous |
| 3 | LNA Gateway | No contemplado | Añadido (NF≤1 dB), margen UL: +0.9→+3.7 dB |
| 4 | Arquitectura de antena | Full-duplex simultáneo (2 antenas) | **Full-duplex con 4 antenas LPDA dedicadas** (sin conmutador TDD) |
| 5 | PC Cliente | Mini PC Intel N100 | Orange Pi 5 16 GB (hardware del equipo, ARM64) |
| 6 | PC Gateway | Mini PC Ryzen 9 8945HS | Mini PC Intel Core Ultra 5 225 (con config. de afinidad P-core) |
| 7 | Distancia de enlace | 15–20 km | 10–15 km (sitio confirmado + criterio conservador) |
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
| Driver del SDR Cliente | compilado desde fuente (ARM64), específico al modelo elegido | Driver GNU Radio del SDR Cliente (p. ej. `gr-limesdr`, `gr-plutosdr`, según selección final) |
| Herramienta de calibración del fabricante | según modelo elegido | Calibración DC offset e IQ (p. ej. LimeSuite si se selecciona un LimeSDR) |
| Python | ≥3.10 | Scripts de prueba y monitoreo |

### Herramientas de desarrollo

| Herramienta | Uso |
|---|---|
| PyTorch + Google Colab Pro | Entrenamiento CNN (GPU T4) |
| GitHub (este repositorio) | Control de versiones y documentación |
| Overleaf | Informes técnicos en LaTeX |
| Notion | Gestión de tareas y wiki del equipo |

---

*Última actualización: junio de 2026 | Contacto: PI Galvez Legua, Mauricio Pedro — UNI FIEE-IITMC*
