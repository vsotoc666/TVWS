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
7. [Canal de Control In-Band — Opción A](#7-canal-de-control-in-band--opción-a)
8. [Modelo de IA — CNN de Sensado Espectral](#8-modelo-de-ia--cnn-de-sensado-espectral)
9. [Link Budget y Parámetros de Rendimiento](#9-link-budget-y-parámetros-de-rendimiento)
10. [Cronograma Actualizado](#10-cronograma-actualizado)
11. [Estado del Proyecto](#11-estado-del-proyecto)
12. [Software y Dependencias](#12-software-y-dependencias)

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
│  │  Capa de Control In-Band (Opción A)  │◀─────────┘             │
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
Abstracción del hardware SDR. Expone una API uniforme independientemente de si el SDR subyacente es un bladeRF, LimeSDR u otro. Resuelve internamente las diferencias de driver (`gr-bladeRF` vs `gr-limesdr`), calibración de DC offset, corrección IQ, y configuración de frecuencia/ganancia.

**Parámetros configurables:**
- Frecuencia central (Hz)
- Ancho de banda de muestreo (MSPS)
- Ganancia RX (dB)
- Tipo de hardware (`bladerf` | `limesdr` | `generic`)

#### Capa 2 — Sensado espectral (`SpectralSensor`)
Captura continua del espectro vía RX2 del bladeRF (canal dedicado a sensado). Calcula la PSD mediante FFT de 1024 puntos sobre las muestras I/Q y la entrega al clasificador CNN.

**Parámetros configurables:**
- Banda de sensado (frecuencia inicial/final)
- Ancho de canal (Hz) — define la granularidad del sensado
- Tamaño FFT (puntos)
- Período de barrido (ms)

#### Capa 3 — Clasificador CNN (`ChannelClassifier`)
Modelo CNN 1D ejecutado vía ONNX Runtime. Clasifica cada canal TVWS como libre u ocupado a partir del vector PSD. Diseñado para ser agnóstico al modelo: acepta cualquier archivo `.onnx` que cumpla la interfaz de entrada/salida especificada.

**Parámetros configurables:**
- Ruta del modelo ONNX (`model_path`)
- Umbral de decisión (0.0–1.0)
- Número de canales a clasificar
- Frecuencia de actualización (ms)

#### Capa 4 — Decisión cognitiva (`CognitiveEngine`)
Implementa la política de selección de canal y el protocolo de salto. Incluye el mecanismo de canal refugio pre-acordado como contingencia ante degradación abrupta del canal de datos.

**Parámetros configurables:**
- Política de selección (`lowest_free` | `max_margin` | `least_used`)
- Canal(es) de refugio pre-acordados
- Tiempo de pre-anuncio del salto (slots de 10 ms)
- Número de confirmaciones CRC requeridas antes de ejecutar el salto
- Umbral de degradación para activar protocolo de emergencia

#### Capa 5 — Control in-band (`InbandControlLayer`)
Implementa la Opción A: inyección del campo de control (next_ch + t_hop + CRC-16) en las subportadoras OFDM #254–257, y su extracción en el receptor. Latencia de señalización <1 ms.

**Parámetros configurables:**
- Índices de subportadoras de control (defecto: 254, 256, 257)
- Esquema de modulación del campo de control (BPSK por defecto)
- Número de repeticiones del pre-anuncio

#### Capa 6 — Interfaz de monitoreo (`MonitoringDashboard`)
Dashboard en tiempo real que muestra el estado completo del sistema cognitivo. Implementado como interfaz Qt integrada en GNU Radio con opción de servidor WebSocket para monitoreo remoto.

**Paneles:**
- Espectrograma de la banda TVWS (470–698 MHz)
- Mapa de ocupación de canales con nivel de confianza CNN
- Canal activo y próximo canal anunciado
- Historial de saltos con timestamps
- Métricas en tiempo real: throughput DL/UL, SNR estimado, BER, margen de enlace
- Estado del clasificador: última inferencia, tiempo de inferencia, accuracy acumulada

---

## 3. Arquitectura del Sistema de Validación

El bloque cognitivo se valida sobre un enlace punto a punto real:

```
[Comunidad rural — 10-15 km]              [Localidad con fibra]
  Usuarios locales
       │
  [AP WiFi local]
       │
  Orange Pi 5 (16GB)  ←──── OFDM TVWS ────→  Mini PC Ryzen 9 8945HS
  + LimeSDR Mini 2.0                           + bladeRF 2.0 micro xA4
  Nodo CLIENTE                                 Nodo GATEWAY
  (demodula, ejecuta)                          (CNN + decisión cognitiva)
       │                                              │
  LPDA 10dBi                                   LPDA 10dBi + discone
  Switch SPDT TDD                              Switch SPDT TDD
  LNA (NF≤1dB)                                LNA (NF≤1dB) + PA 2W
                                                      │
                                               Router fibra óptica
                                                      │
                                                  Internet
```

**Principio de operación:** El bloque cognitivo corre íntegramente en el Gateway. El Cliente solo ejecuta las órdenes de salto recibidas via el campo de control in-band, sin lógica cognitiva propia.

### 3.1 Planos de comunicación

| Plano | Medio | Dirección | Implementación |
|---|---|---|---|
| **Datos** | OFDM 6 MHz, 470–698 MHz | DL y UL (TDD) | GNU Radio, bladeRF TX1/RX1 + LimeSDR |
| **Control** | Subportadoras OFDM #254–257 | DL Gateway→Cliente | Opción A in-band, <1 ms latencia |
| **Sensado** | bladeRF RX2 | Gateway escucha espectro | Canal dedicado, antena discone |

> **Nota:** El canal de control LoRa (SX1262) fue eliminado del diseño final por restricción presupuestal. El control cognitivo opera íntegramente in-band. El protocolo de canal refugio pre-acordado cubre el escenario de degradación abrupta del canal de datos.

### 3.2 Banda de operación

- **TVWS UHF:** 470–698 MHz (plan de atribución peruano)
- **Canales disponibles:** 39 canales de 6 MHz
- **Frecuencia de referencia para cálculos:** 600 MHz (centro de banda)
- **RX2 sensado:** barrido continuo 470–698 MHz, período 100–200 ms

---

## 4. Hardware por Nodo

### 4.1 Nodo Gateway

| Componente | Especificación | Función |
|---|---|---|
| SDR | bladeRF 2.0 micro xA4 — 2TX/2RX, 12 bits, VCTCXO ±1 ppm | TX datos DL (TX1) + RX uplink (RX1) + RX sensado CNN (RX2) |
| PC | Mini PC Ryzen 9 8945HS, 32 GB DDR5, Radeon 780M | GNU Radio + inferencia CNN ONNX Runtime |
| PA | 400–1000 MHz, 2W (33 dBm), clase AB | Amplificar TX antes de la antena |
| LNA RX | 400–1000 MHz, NF ≤1 dB, ganancia 15–25 dB | Bajar NF del receptor uplink a ~1 dB efectivo |
| Switch SPDT | 400–1000 MHz, pérd. inserción ≤2.5 dB, control TTL | TDD: conmuta LPDA entre TX1 (DL) y RX1 (UL) |
| Antena enlace | LPDA 400–2700 MHz, 10 dBi, N-hembra | TX downlink + RX uplink (compartida vía switch TDD) |
| Antena sensado | Discone 25–1300 MHz, omnidireccional | Entrada dedicada de RX2 para sensado espectral continuo |
| GDT | N-H/N-M, DC–3 GHz, ≤0.3 dB, ≥5 kA (8/20µs), IP67 | Protección de sobretensión en 3 ramas RF |

**Cadena RF TX Gateway:**
```
bladeRF TX1 (+6 dBm)
  → RG-316 pigtail 0.6m (SMA-M↔SMA-M)
  → PA 2W (+27 dB)
  → LMR-400 3.5m + GDT (N-M↔N-M)
  → Switch SPDT (−1.7 a −2.5 dB pérdida inserción)
  → LMR-400 jumper 0.5m (Switch → LPDA)
  → LPDA 10 dBi
  → EIRP: ~+39 dBm (con pérdidas reales del switch)
```

**Cadena RF RX Gateway (uplink):**
```
LPDA 10 dBi
  → LMR-400 jumper 0.5m
  → Switch SPDT
  → LMR-400 3.5m + GDT (N-M↔N-M)
  → LNA (NF ≤1 dB, +20 dB) — montar próximo al switch
  → RG-316 pigtail 0.3-0.5m (SMA-M↔N-H)
  → bladeRF RX1
  → NF sistema total: ~1.3 dB (con switch + GDT acumulados)
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
| SDR | LimeSDR Mini 2.0 (LMS7002M), SISO, 12 bits, ±2 ppm | RX datos DL + TX uplink |
| SBC | Orange Pi 5, 16 GB RAM, RK3588 (ARM64) | GNU Radio RX/TX, scripts de prueba, monitoreo remoto |
| LNA RX | 400–1000 MHz, NF ≤1 dB, ganancia 15–25 dB | Bajar NF downlink a ~1 dB efectivo |
| Switch SPDT | 400–1000 MHz, control TTL | TDD: conmuta LPDA entre RX (DL) y TX (UL) |
| Antena enlace | LPDA 400–2700 MHz, 10 dBi, N-hembra | RX downlink + TX uplink (compartida vía switch TDD) |
| Gabinete | IP65 | Protección ambiental en campo |
| GDT | N-H/N-M, DC–3 GHz, ≤0.3 dB, ≥5 kA (8/20µs), IP67 | Protección de sobretensión en rama principal |

**Limitaciones conocidas del LimeSDR Mini 2.0:**
- DC offset / LO leakage en subportadora central → calibrar con LimeSuite antes de cada sesión
- IQ imbalance → bloque IQ Corrector en GNU Radio (tiempo real)
- SISO (un solo canal RX externo) → sin sensado espectral continuo independiente
- Sin timestamping hardware preciso → ventana de guarda de 10 ms en saltos de canal
- Driver `gr-limesdr` distinto a `gr-bladeRF` → resuelto por la capa `RadioInterface`
- GNU Radio en ARM64: requiere compilación desde fuente de `gr-limesdr` (verificado disponible para RK3588)

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
| Subportadoras de control | 3 útiles (#254, #256, #257) | Campo de control in-band — Opción A |
| Prefijo cíclico (CP) | 1/4 del símbolo (~56 µs) | Protección contra multipath |
| Duración símbolo OFDM | ~89 µs (CP + FFT) | 640 muestras a 7.68 MSPS |
| Modulaciones soportadas | BPSK / QPSK / 16-QAM | Selección adaptativa por CNN |
| Tasa de código FEC | 1/2 o 3/4 (convolucional o LDPC) | Protección contra errores de canal |

### 5.2 Distribución del vector IFFT (512 puntos)

```
Índice   0–25:   Banda de guarda inferior (26 sub → 0+0j)
Índice  26–253:  Datos + pilotos dispersos (~228 sub)
Índice 254–257:  Campo de control in-band (Opción A)
                   #254 → bit 0 del mensaje de control (BPSK)
                   #255 → EVITADA (DC offset del LimeSDR)
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

> Los valores de throughput en campo deben interpretarse como teóricos. Los objetivos conservadores validados en Fase 4 (10–15 km, NLOS 15 dB) son **≥1.9 Mbps DL** (BPSK R=1/2) y **≥1.9 Mbps UL** condicionado a que el link budget cierre.

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
[RF]  PA 2W → GDT → switch SPDT → LMR-400 → LPDA
    ↓
[AIRE] EIRP ~+39 dBm | PRx Cliente ≈ −80 dBm a 15 km
```

### 6.2 Flujo RX Downlink (en el Cliente)

```
[LPDA → LNA → switch SPDT → LMR-400 → LimeSDR ADC 12 bits]
    ↓
[SYNC] Schmidl-Cox: detecta inicio de símbolo, estima CFO
    ↓
[CORR] DC offset (LimeSuite) + IQ Corrector (GNU Radio)
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

### 6.3 Flujo TX Uplink (Cliente → Gateway, TDD)

```
[Orange Pi 5 / datos usuario hacia Internet]
    ↓
[MAC + FEC + BPSK] — modulación forzada (margen ajustado en UL)
    ↓
[OFDM] IFFT 512 + CP 128 (sin campo de control in-band en UL)
    ↓
[SDR] LimeSDR TX +10 dBm (sin PA)
    ↓
[RF]  LMR-400 → switch SPDT → GDT → LPDA 10 dBi
    ↓
[AIRE] EIRP +20 dBm | PRx Gateway ≈ −99 dBm a 15 km
```

### 6.4 Flujo RX Uplink (en el Gateway)

```
[LPDA → switch SPDT → GDT → LNA → LimeSDR RX1]
    ↓
[SYNC + FFT + EQ] — misma cadena que el Cliente en DL
    ↓
[DEMOD] BPSK → Viterbi → paquetes IP → router fibra → Internet
```

> **TDD:** RX1 y TX1 del bladeRF comparten la LPDA vía switch SPDT. RX2 (sensado) tiene su propia discone y opera en paralelo de forma continua e independiente del ciclo TDD.

---

## 7. Canal de Control In-Band — Opción A

### 7.1 Principio

El campo de control viaja **embebido en cada símbolo OFDM** usando 3 subportadoras dedicadas (#254, #256, #257). No requiere hardware adicional ni canal fuera de banda. Latencia de entrega: <1 ms.

### 7.2 Estructura del mensaje de control

```
Mensaje de 32 bits, transmitido en 11 símbolos OFDM consecutivos (3 bits/símbolo):

Bits  0–5:   next_ch    — índice del canal TVWS destino (0–38, 6 bits)
Bits  6–13:  t_hop      — tiempo hasta el salto en slots de 10 ms (8 bits)
Bits 14–15:  flags      — 00=normal, 01=refugio, 10=resync, 11=reservado
Bits 16–31:  CRC-16     — checksum de bits 0–15

Tiempo de transmisión completa: 11 × 89 µs ≈ 0.98 ms
Repetición: cada símbolo OFDM durante el período de pre-anuncio (10–20 tramas ≈ 100–200 ms)
```

### 7.3 TX del campo de control (Gateway)

```python
# Pseudocódigo — implementación en GNU Radio Python Block
def build_control_packet(next_ch, t_hop, flag=0b00):
    payload = (next_ch & 0x3F) | ((t_hop & 0xFF) << 6) | ((flag & 0x3) << 14)
    crc = crc16(payload.to_bytes(2, 'big'))
    return payload | (crc << 16)  # 32 bits totales

# Tagged Stream Mux inyecta los bits en sub #254, #256, #257
# antes del OFDM Carrier Allocator en el flowgraph del Gateway
```

### 7.4 RX del campo de control (Cliente)

```python
# Pseudocódigo — implementación en GNU Radio Python Block
def process_control_symbol(sub254, sub256, sub257):
    bits = [decode_bpsk(sub254), decode_bpsk(sub256), decode_bpsk(sub257)]
    buffer.append(bits)
    if len(buffer) == 11:  # mensaje completo
        word = bits_to_uint32(buffer)
        if verify_crc16(word):
            next_ch = word & 0x3F
            t_hop   = (word >> 6) & 0xFF
            flag    = (word >> 14) & 0x3
            schedule_hop(next_ch, t_hop * 10e-3)
        buffer.clear()
```

### 7.5 Robustez

Con PER del 10% y pre-anuncio de 20 repeticiones: P(fallo total) = 0.1²⁰ ≈ 10⁻²⁰. El campo de control es prácticamente irrompible mientras el canal de datos sea demodulable.

### 7.6 Protocolo de canal refugio (contingencia)

Si el SNR del canal activo cae por debajo de un umbral configurable, ambos nodos saltan de forma autónoma al canal de refugio pre-acordado (por defecto: canal más bajo de la banda, 470 MHz, mejor difracción NLOS). No requiere coordinación explícita porque el destino está pre-acordado en el firmware de ambos nodos.

---

## 8. Modelo de IA — CNN de Sensado Espectral

### 8.1 Arquitectura

| Parámetro | Valor |
|---|---|
| Tipo | Red neuronal convolucional 1D (1D-CNN) |
| Entrada | Vector PSD de 1024 puntos (FFT sobre muestras I/Q del RX2) |
| Salida | Vector de probabilidad de ocupación por canal TVWS (39 valores, 0.0–1.0) |
| Parámetros | ~350,000–600,000 |
| Tamaño modelo ONNX | ~2–4 MB |
| Inferencia en campo | <10 ms (Ryzen 9 8945HS + Radeon 780M, ONNX Runtime) |
| Entrenamiento | PyTorch — Google Colab Pro (T4 GPU) |
| Despliegue | `torch.onnx.export()` → ONNX Runtime |
| Ciclo de sensado | 100–200 ms (RX2 bladeRF, barrido continuo) |

### 8.2 Interfaz del clasificador

```python
# Contrato de interfaz — ChannelClassifier
class ChannelClassifier:
    def __init__(self, model_path: str, threshold: float = 0.5):
        ...

    def classify(self, psd_vector: np.ndarray) -> dict:
        """
        Args:
            psd_vector: array de 1024 puntos float32 (PSD normalizada)
        Returns:
            {
                'occupancy': np.ndarray,  # [39] probabilidades por canal
                'free_channels': list[int],  # índices de canales libres
                'inference_ms': float,  # tiempo de inferencia
                'confidence': float  # confianza promedio de la decisión
            }
        """
```

### 8.3 Dataset y domain mismatch

| Etapa | Hardware | ADC | Banda |
|---|---|---|---|
| Captura dataset (Fase 1) | RTL-SDR | 8 bits | 470–698 MHz |
| Inferencia en campo | bladeRF 2.0 | 12 bits | 470–698 MHz |

**Mitigación:** Normalización por rango dinámico antes de la FFT en el preprocesamiento. El proyecto documenta el impacto medido de este domain mismatch en la accuracy del modelo como contribución técnica.

### 8.4 KPIs del modelo (objetivos conservadores)

| Métrica | Objetivo | Condición |
|---|---|---|
| Accuracy en dataset de prueba | >85% | Laboratorio |
| Tasa de falsos negativos (libre→ocupado) | <10% | Laboratorio |
| Tiempo de inferencia | <10 ms | Ryzen 9 + ONNX |
| Tiempo de evacuación de canal E2E | <300 ms | Campo real |

---

## 9. Link Budget y Parámetros de Rendimiento

### 9.1 Link budget (valores conservadores con componentes reales)

Los márgenes incluyen pérdidas reales acumuladas del switch SPDT (1.7–2.5 dB), GDT (0.3 dB por tramo) y cables LMR-400.

| Parámetro | Downlink | Uplink |
|---|---|---|
| EIRP TX | ~+39 dBm (con switch) | +20 dBm (sin PA) |
| FSPL + NLOS (15 km, 600 MHz) | −126 dB | −126 dB |
| Ganancia antena RX | +10 dBi | +10 dBi |
| Potencia recibida estimada | ~−77 dBm | ~−96 dBm |
| NF receptor | ~1.0 dB (LNA CLI) | ~1.3 dB (LNA GW + switch) |
| Sensibilidad BPSK | −100.7 dBm | −100.4 dBm |
| **Margen BPSK (peor caso)** | **~+14 dB** | **~+1.0 dB** |
| Sensibilidad QPSK | −97.7 dBm | — |
| **Margen QPSK** | **~+11 dB** | **no aplica UL** |

> **Alerta UL:** El uplink tiene margen de solo ~+1.0 dB en el peor caso (15 km, NLOS 15 dB). Susceptible a degradación por lluvia intensa o NLOS mayor al estimado. Se evalúa adición de PA en el Cliente (S/1,100) en Fase 4 según mediciones reales de Fase 3.

### 9.2 Latencias del sistema

| Componente | Valor | Origen |
|---|---|---|
| Propagación RF (15 km) | 0.050 ms | Física |
| Símbolo OFDM | ~89 µs | 640 muestras / 7.68 MSPS |
| Inferencia CNN (ONNX) | <10 ms | Ryzen 9 + Radeon 780M |
| Señalización control in-band | <1 ms | Subportadoras #254–257 |
| Ciclo de sensado CNN | 100–200 ms | bladeRF RX2 barrido |
| Ventana de guarda en salto | 10 ms | PLL lock + margen |
| **Latencia E2E datos** | **10–30 ms** | Propagación + GNU Radio |
| **Evacuación de canal** | **<300 ms** | Sensado + CNN + control + guarda |

---

## 10. Cronograma Actualizado

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

## 11. Estado del Proyecto

**Fecha de referencia: 15 de junio de 2026**

### ✅ Completado

- Arquitectura completa del bloque cognitivo GNU Radio (todas las capas)
- Diseño del esquema de control in-band Opción A (subportadoras #254–257)
- Protocolo de canal refugio pre-acordado como contingencia
- Especificación técnica completa de hardware (ambos nodos)
- Cadena RF completa diseñada: 11 cables, 3 GDT, 2 switches SPDT
- Link budget real calculado con pérdidas de todos los componentes
- Decisiones de diseño documentadas: eliminación LoRa, TDD con switch, LNA GW, Orange Pi 5 como nodo Cliente

### 🔄 En progreso / Pendiente inmediato

- Publicación de adquisiciones en portal RNP
- Captura de dataset espectral TVWS 470–698 MHz (protocolo definido, pendiente ejecución)
- Entrenamiento y validación del modelo CNN 1D
- Exportación a ONNX y prueba de inferencia en hardware real

### 📋 Pendiente por fase

- **F2:** Implementación del flowgraph GNU Radio completo, integración ONNX, pruebas de banco
- **F3:** Enlace piloto en azotea UNI, medición de link budget real, validación CNN con primarios TV
- **F4:** Despliegue rural a 10–15 km, validación end-to-end
- **F5:** Análisis de resultados, informe final, preparación de publicación

### Cambios respecto a la propuesta original

| # | Aspecto | Original | Actualizado |
|---|---|---|---|
| 1 | SDR Cliente | PlutoSDR (USB 2.0) | LimeSDR Mini 2.0 (USB 3.0, ≥30 MSPS) |
| 2 | Canal de control | LoRa SX1262 (915 MHz, fuera de banda) | Control in-band Opción A + protocolo de refugio |
| 3 | LNA Gateway | No contemplado | Añadido (NF≤1 dB), margen UL: +0.9→+1.0 dB |
| 4 | Arquitectura antena | Full-duplex simultáneo | TDD con switch SPDT, RX2 con discone dedicada |
| 5 | PC Cliente | Mini PC Intel N100 | Orange Pi 5 16 GB (hardware del equipo, ARM64) |
| 6 | Distancia de enlace | 15–20 km | 10–15 km (sitio confirmado + criterio conservador) |
| 7 | Duración F2/F3/F4 | 61/60/47 días | 52/50/43 días (compresión por retraso F1) |

---

## 12. Software y Dependencias

### Nodo Gateway (Ubuntu 22.04 LTS, x86_64)

| Herramienta | Versión | Uso |
|---|---|---|
| GNU Radio | 3.10.x | Procesamiento de señal SDR |
| gr-bladeRF | última | Driver bladeRF 2.0 |
| ONNX Runtime | ≥1.16 | Inferencia CNN en campo |
| PyTorch | ≥2.0 | Entrenamiento CNN (Colab) |
| Python | ≥3.10 | Lógica cognitiva y control |
| NumPy / SciPy | latest | Preprocesamiento PSD |

### Nodo Cliente (Ubuntu 22.04 LTS, ARM64 — Orange Pi 5)

| Herramienta | Versión | Uso |
|---|---|---|
| GNU Radio | 3.10.x | Demodulación OFDM |
| gr-limesdr | compilado desde fuente (ARM64) | Driver LimeSDR Mini 2.0 |
| LimeSuite | última | Calibración DC offset y IQ |
| Python | ≥3.10 | Scripts de prueba y monitoreo |

### Herramientas de desarrollo

| Herramienta | Uso |
|---|---|
| PyTorch + Google Colab Pro | Entrenamiento CNN (GPU T4) |
| GitHub (este repositorio) | Control de versiones y documentación |
| Overleaf | Informes técnicos en LaTeX |
| Notion | Gestión de tareas y wiki del equipo |

---

*Última actualización: 15 de junio de 2026 | Contacto: PI Galvez Legua, Mauricio Pedro — UNI FIEE-IITMC*
