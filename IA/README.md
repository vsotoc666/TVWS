# SpectralSense — IA de Sensado Espectral para Radio Cognitiva TVWS

Módulo de inteligencia artificial del proyecto **Radio Cognitiva TVWS**, desarrollado por el Grupo de Investigación VRI 2024–2026, Facultad de Ingeniería Eléctrica y Electrónica (IITMC), Universidad Nacional de Ingeniería, Lima, Perú.

Este repositorio contiene la red neuronal convolucional (CNN) que detecta canales de TV White Space (TVWS) libres en la banda UHF peruana 470–698 MHz, su pipeline de entrenamiento, y su despliegue en el nodo Gateway del sistema.

---

## Tabla de contenidos

- [Contexto del sistema](#contexto-del-sistema)
- [Arquitectura del modelo](#arquitectura-del-modelo)
- [Formato de entrada y salida](#formato-de-entrada-y-salida)
- [Hardware del Gateway](#hardware-del-gateway)
- [Pipeline de inferencia en campo](#pipeline-de-inferencia-en-campo)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Instalación](#instalación)
- [Uso rápido](#uso-rápido)
- [Métricas del modelo](#métricas-del-modelo)
- [Roadmap](#roadmap)

---

## Contexto del sistema

El proyecto implementa un enlace de radio cognitiva punto a punto para llevar conectividad a comunidades rurales aisladas, usando espectro TVWS como recurso secundario no licenciado.

```
[Fibra óptica]
      │
┌─────▼──────────────────────────────┐
│      NODO GATEWAY                   │
│  PC Intel Core Ultra 5 225          │
│  bladeRF 2.0 xA4 (TX/RX + sensado)  │
│  ◄── ESTE MÓDULO CORRE AQUÍ ──►     │
│  CNN + CognitiveEngine              │
└─────────────┬────────────────────────┘
              │ Enlace OFDM 6 MHz full-duplex (datos), 10-15 km
              │ Control in-band: subportadoras OFDM #254/256/257
              │ (sin canal fuera de banda — LoRa eliminado del diseño)
┌─────────────▼────────────────────────┐
│      NODO CLIENTE                    │
│  LimeSDR Mini 2.0 — solo demodula    │
│  Sin IA — ejecuta órdenes de salto   │
└────────────────────────────────────────┘
```

Toda la inteligencia del sistema reside en el Gateway. El modelo clasifica una sub-banda de 56 MHz por inferencia (el bladeRF no puede capturar los 228 MHz de la banda TVWS de una sola vez); en cada ciclo (~100–200 ms, 5 posiciones de barrido) produce el mapa de ocupación de los 39 canales (14–52), que consume el `CognitiveEngine` para decidir el salto y comunicarlo al Cliente embebido en las subportadoras de control del propio canal OFDM de datos.

---

## Arquitectura del modelo

**SpectralSenseCNN** — Red Neuronal Convolucional 1D con backbone compartido y dos cabezas (multi-task).

```
Input: PSD de 512 puntos (56 MHz de sub-banda, normalizado [0,1])
   │
   ▼
Bloque 1 — Conv1D(32, k=45) → BN → ReLU → MaxPool(2)     [silueta espectral, ~5 MHz]
   │
   ▼
Bloque 2 — Conv1D(64, k=9) ×2 → BN → ReLU → MaxPool(2)   [textura intra-canal, ~1 MHz]
   │
   ▼
Bloque 3 — Conv1D(128, k=5) → BN → ReLU                  [correlación inter-canal, ~2 MHz]
   │
   ▼
GlobalAveragePool1D → (128,)
   │
   ▼
Dense(64) → ReLU → Dropout(0.3)  [tronco compartido]
   │
   ├──▶ cabeza_ocupacion: Dense(9) → Sigmoid → P(ocupado) por canal visible
   │
   └──▶ cabeza_margen:    Dense(9) → margen/SNR estimado en dB por canal
```

**~108,000 parámetros** · **~25–30 KB en ONNX** · **~0.1 ms de latencia en CPU (medido)**

### Por qué esta arquitectura

| Decisión | Justificación |
|---|---|
| Conv1D, no Conv2D | El PSD es una señal 1D nativa; no requiere espectrograma temporal |
| Kernels decrecientes (45→9→5) | Imitan la jerarquía de reconocimiento: silueta gruesa → textura fina → contexto entre canales |
| GlobalAveragePool, no Flatten | Evita una explosión de parámetros (Flatten daría ~1M solo en la primera capa densa) y regulariza implícitamente |
| Salida multi-etiqueta (9 logits) por sub-banda, no 39 de una vez | El bladeRF no puede capturar los 228 MHz de la banda en una sola FFT (~56 MHz de ancho de banda instantáneo máximo); el modelo clasifica una sub-banda por inferencia y `SpectralOccupancyMap` (en `inferencia.py`) agrega las 5 sub-bandas del ciclo en el mapa global de 39 canales |
| Cabeza de margen además de ocupación | El `CognitiveEngine` tiene una política `max_margin`; P(ocupado) cerca de 0 no distingue cuál canal libre está más limpio (todos saturan igual). El margen estimado en dB sí da un valor continuo comparable, casi sin costo extra de parámetros por compartir el backbone |
| Sin Sigmoid en el forward | `BCEWithLogitsLoss` es numéricamente más estable; Sigmoid se aplica solo en inferencia |

El documento completo de arquitectura, con el razonamiento capa por capa y los cálculos de campo receptivo, está en [`arquitectura_ia_tvws.md`](arquitectura_ia_tvws.md) (parcialmente desactualizado respecto a la cabeza de margen — el razonamiento de los 3 bloques convolucionales sigue vigente).

---

## Formato de entrada y salida

### Entrada

El bladeRF no puede capturar los 228 MHz de la banda TVWS de una sola vez (su ancho de banda instantáneo máximo es 56 MHz). El sensado se hace en **5 posiciones de barrido**, cada una cubriendo entre 7 y 9 canales:

| Posición | Centro | Canales TVWS cubiertos |
|---|---|---|
| 0 | 498 MHz | 14–22 |
| 1 | 536 MHz | 22–30 |
| 2 | 578 MHz | 30–38 |
| 3 | 626 MHz | 38–46 |
| 4 | 670 MHz | 46–52 |

Cada inferencia recibe el PSD normalizado de **una** de estas sub-bandas.

### Salida — por sub-banda (`ChannelClassifier.classify_subbanda`)

```python
{
    "prob_por_canal":   {14: 0.03, 15: 0.91, ...},    # por canal global
    "margen_por_canal": {14: 18.2, 15: -4.1, ...},    # dB, por canal global
    "libres_globales":  [14, 17, 21],
    "inference_ms":      0.10,
    "confidence":        0.87,                         # mean(|p-0.5|*2)
}
```

### Salida — ciclo completo, 5 sub-bandas (`SpectralOccupancyMap.mapa_actual`)

```python
{
    "canales": {
        14: {"prob_ocupado": 0.03, "margen_db": 18.2, "libre": True,  "antiguedad_ms": 12},
        15: {"prob_ocupado": 0.91, "margen_db": -4.1,  "libre": False, "antiguedad_ms": 12},
        # ... 14-52
    },
    "libres_por_indice": [14, 17, 21, ...],   # orden de canal, SIN preordenar por política
    "confianza_global":  0.87,
}
```

`antiguedad_ms` existe porque las 5 sub-bandas no se capturan simultáneamente — se barren secuencialmente a lo largo del ciclo (~100–200 ms), así que cada canal del mapa tiene una frescura distinta. El ranking por política (`lowest_free`/`max_margin`/`least_used`) es responsabilidad exclusiva del `CognitiveEngine`, que es quien consume este `dict` para decidir el salto y comunicarlo al nodo Cliente embebido en las subportadoras de control in-band del propio canal OFDM (sin canal fuera de banda — ver `README.md` raíz, §7).

---

## Hardware del Gateway

| Componente | Especificación |
|---|---|
| Modelo | OptiWork SFF 3050 |
| CPU | Intel Core Ultra 5 225 (10 núcleos, hasta 4.9 GHz) |
| RAM | 32 GB DDR5 4800 MHz |
| Almacenamiento | 1 TB SSD |
| GPU | Intel Graphics integrada (Xe-LPG) |
| Red | LAN Gigabit Ethernet |
| SO objetivo | **Ubuntu 22.04 LTS** (re-instalar; el equipo trae 25.04 no-LTS) |
| SDR | bladeRF 2.0 micro xA4 — USB 3.0, full-duplex 2TX/2RX |

### Sobre la inferencia y la GPU

El modelo es lo bastante liviano (~0.5 ms en CPU pura, medido con benchmark) que **no necesita aceleración por GPU** para cumplir el presupuesto de tiempo del ciclo de sensado (~137 ms para las 5 sub-bandas). Por simplicidad y portabilidad, el wrapper `SpectralSenseInferencia` usa `CPUExecutionProvider` de ONNX Runtime por defecto.

Si en el futuro se quisiera acelerar por hardware, la ruta correcta en Linux + Intel es **OpenVINO Execution Provider** (no DirectML, que es exclusivo de Windows):

```bash
pip install onnxruntime-openvino
```

El código detecta automáticamente si `OpenVINOExecutionProvider` está disponible y lo usa; si no, cae en CPU sin error.

---

## Pipeline de inferencia en campo

```
┌──────────────────────────────────────────────────────────────────┐
│              BUCLE DE SENSADO (~100-200 ms/ciclo)                 │
│                                                                    │
│  1. bladeRF RX2 captura sub-banda (56 MHz, posición i de 5)       │
│        ↓  ZMQ (IPC en RAM, sin disco)                             │
│  2. Procesador PSD: FFT 512 pts → DC offset → percentil 5/95      │
│        ↓                                                          │
│  3. ONNX Runtime: ChannelClassifier.classify() (~0.1 ms medido)   │
│        ↓  ocupación (9,) + margen_db (9,)                         │
│  4. SpectralOccupancyMap.actualizar(i, resultado, timestamp)      │
│        ↓  repetir 1-4 para las 5 posiciones de barrido            │
│  5. CognitiveEngine: política de selección + canal refugio        │
│     (fuera de este repo — consume mapa_actual())                  │
│        ↓                                                          │
│  6. Campo de control in-band (next_ch + t_hop + CRC-16) embebido  │
│     en subportadoras OFDM #254/256/257 del downlink — <1 ms       │
└──────────────────────────────────────────────────────────────────┘
```

Cada etapa corre en su propio thread Python dentro de un único proceso en el Gateway, comunicados por colas thread-safe (`queue.Queue`) y, entre GNU Radio y el procesador PSD, por sockets ZeroMQ. No hay canal de control fuera de banda — LoRa fue eliminado del diseño; ver `README.md` raíz §3.2 y §7.

---

## Estructura del repositorio

```
IA/
├── README.md                      # este archivo
├── arquitectura_ia_tvws.md        # arquitectura completa, capa por capa
├── pipeline_dataset_v2.md         # pipeline de recolección y construcción del dataset
│
├── nucleo.py                      # constantes, preprocesamiento PSD, modelo (SpectralSenseCNN), pérdidas
├── inferencia.py                  # ChannelClassifier (ONNX, por sub-banda) + SpectralOccupancyMap
├── entrenamiento.py                # TVWSDataset, bucle de entrenamiento, exportación ONNX (CLI)
├── generar_dataset_sintetico.py   # generador sintético (sub-banda completa + margen_db)
├── evaluar_modelo.py              # evaluación: ROC, matriz de confusión, benchmark de latencia
├── analizar_entrenamiento.py      # gráficas de loss/AUC/F1 desde historial.json
│
├── dataset/                       # (real, Fase 1) train/val/test en .npz — formato per-canal
├── modelos/                       # (generado) checkpoints .pt y modelo .onnx
└── graficas/                      # (generado) gráficas de evaluación y entrenamiento
```

No hay `captura_sesion.py`/`setup_entorno.sh`/`docs/` todavía — son trabajo pendiente de Fase 1 (captura real con RTL-SDR), no scripts ya implementados.

---

## Instalación

Requiere Python 3.11 o 3.12 (evitar 3.13/3.14 — varias dependencias científicas aún no publican wheels precompiladas para esas versiones).

```bash
git clone <url-del-repo>
cd TVWS

python3.11 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\Activate.ps1     # Windows PowerShell

pip install -r requirements.txt
cd IA
```

En Linux, para captura con RTL-SDR (Fase 1, todavía no implementado en este repo):

```bash
sudo apt install librtlsdr-dev rtl-sdr
sudo cp /usr/lib/udev/rules.d/rtl-sdr.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

---

## Uso rápido

### 1. Generar dataset (sintético, para pruebas sin hardware)

```bash
python generar_dataset_sintetico.py --n_muestras 6000 --salida ./dataset_v2
```

### 2. Entrenar

```bash
python entrenamiento.py --modo entrenar --dataset ./dataset_v2 --epocas 80
```

Exporta automáticamente a ONNX al finalizar.

### 3. Evaluar

```bash
python evaluar_modelo.py --dataset ./dataset_v2 --checkpoint ./modelos/mejor_modelo.pt --onnx ./modelos/spectral_sense.onnx
```

Genera curvas ROC por canal, matriz de confusión, distribución de probabilidades y benchmark de latencia.

### 4. Analizar el historial de entrenamiento

```bash
python analizar_entrenamiento.py --historial ./modelos/historial.json
```

### 5. Captura real con RTL-SDR (Fase 1, recolección de dataset)

Pendiente — protocolo definido en `pipeline_dataset_v2.md`, script aún no implementado.

### 6. Inferencia en campo (uso en producción dentro del Gateway)

```python
from inferencia import ChannelClassifier, SpectralOccupancyMap
from nucleo import iq_a_psd_normalizado
import time

clasificador = ChannelClassifier("./modelos/spectral_sense.onnx")
mapa = SpectralOccupancyMap()

for posicion_idx, iq in enumerate(capturas_del_ciclo):   # 5 capturas, una por posición
    resultado = clasificador.classify_subbanda(iq, posicion_idx)
    mapa.actualizar(posicion_idx, resultado, timestamp=time.time())

print(mapa.mapa_actual()["libres_por_indice"])   # ej: [14, 17, 21]
```

---

## Métricas del modelo

El modelo cambió de una sola cabeza (9 logits) a backbone compartido + cabeza dual (ocupación + margen) — las métricas de la cabeza de ocupación deberían ser comparables a las de la arquitectura anterior, pero **están pendientes de re-medición sobre un entrenamiento completo** tras este cambio (no sobre las 3 épocas usadas para validar que el pipeline corre sin errores). Reemplazar esta sección con el resultado de:

```bash
python entrenamiento.py --modo entrenar --dataset ./dataset_v2 --epocas 80
python evaluar_modelo.py --dataset ./dataset_v2 --checkpoint ./modelos/mejor_modelo.pt --onnx ./modelos/spectral_sense.onnx
```

El umbral operativo (`UMBRAL_LIBRE = 0.20`, no 0.5) está elegido deliberadamente para minimizar falsos negativos: en radio cognitiva, declarar "libre" un canal que en realidad tiene un primario activo es un error regulatorio grave, mientras que declarar "ocupado" un canal libre solo cuesta eficiencia espectral.

> Estas métricas son sobre dataset **sintético**. Pendiente: validación con dataset real capturado en Fase 1 (ver `pipeline_dataset_v2.md`).

---

## Roadmap

- [x] Arquitectura del modelo definida y validada (backbone + cabeza dual ocupación/margen)
- [x] División en módulos: `nucleo.py` / `inferencia.py` / `entrenamiento.py`
- [x] Pipeline de entrenamiento con manejo correcto de etiquetas desconocidas (`BCEWithLogitsLossMasked`, `MargenLossMasked`)
- [x] Dataset sintético v2 (formato de sub-banda completa, igual al de campo, con etiqueta de margen)
- [x] `SpectralOccupancyMap`: agregación de 5 sub-bandas en mapa de 39 canales con timestamp por canal
- [x] Eliminación de LoRa: inferencia usa OpenVINO/CPU, sin ninguna dependencia de transporte de control
- [ ] Re-entrenamiento completo y medición de métricas con la arquitectura de cabeza dual
- [ ] Captura de dataset real con RTL-SDR V4 en Lima (Fase 1)
- [ ] Re-entrenamiento y validación con dataset real
- [ ] Integración con `CognitiveEngine` (Fase 2) — política de selección, canal refugio, control in-band
- [ ] Despliegue e inferencia en el Gateway (OptiWork SFF 3050)
- [ ] Pruebas de campo en enlace piloto urbano (Fase 3)

---

## Proyecto

**Diseño y Validación de un prototipo de Radio Cognitiva basado en Hardware SDR asimétrico y Deep Learning para el acceso dinámico a TVWS en zonas rurales**
Universidad Nacional de Ingeniería · Facultad de Ingeniería Eléctrica y Electrónica (IITMC)
Grupo de Investigación VRI 2024–2026 · Mayo–Diciembre 2026

PI: Galvez Legua, Mauricio Pedro
