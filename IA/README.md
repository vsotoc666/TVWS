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
┌─────▼──────────────────────────┐
│      NODO GATEWAY               │
│  PC Intel Core Ultra 5 225      │
│  bladeRF 2.0 xA4 (TX + sensado) │
│  ◄── ESTE MÓDULO CORRE AQUÍ ──► │
│  CNN + árbitro + control LoRa   │
└─────────────┬────────────────────┘
              │ Enlace OFDM 6 MHz (datos) — hasta 20 km
              │ LoRa 915 MHz (control, out-of-band)
┌─────────────▼────────────────────┐
│      NODO CLIENTE                │
│  LimeSDR Mini 2.0 — solo demodula│
│  Sin IA — ejecuta órdenes        │
└───────────────────────────────────┘
```

Toda la inteligencia del sistema reside en el Gateway. El modelo decide, ciclo a ciclo (~137 ms), qué canales de los 39 disponibles (14–52) están libres de usuarios primarios (emisoras de TV), y comunica el mejor candidato al nodo Cliente por el canal de control LoRa.

---

## Arquitectura del modelo

**SpectralSenseCNN** — Red Neuronal Convolucional 1D con cabeza de clasificación multi-etiqueta.

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
Dense(64) → ReLU → Dropout(0.3) → Dense(9)
   │
   ▼
Output: 9 logits → Sigmoid → P(ocupado) por canal visible
```

**~107,000 parámetros** · **~25 KB en ONNX** · **~0.5 ms de latencia en CPU**

### Por qué esta arquitectura

| Decisión | Justificación |
|---|---|
| Conv1D, no Conv2D | El PSD es una señal 1D nativa; no requiere espectrograma temporal |
| Kernels decrecientes (45→9→5) | Imitan la jerarquía de reconocimiento: silueta gruesa → textura fina → contexto entre canales |
| GlobalAveragePool, no Flatten | Evita una explosión de parámetros (Flatten daría ~1M solo en la primera capa densa) y regulariza implícitamente |
| Salida multi-etiqueta (9 logits) | Una sola inferencia clasifica los ~9 canales visibles en la sub-banda de 56 MHz, en vez de 9 inferencias separadas |
| Sin Sigmoid en el forward | `BCEWithLogitsLoss` es numéricamente más estable; Sigmoid se aplica solo en inferencia |

El documento completo de arquitectura, con el razonamiento capa por capa y los cálculos de campo receptivo, está en [`docs/arquitectura_ia_tvws.md`](docs/arquitectura_ia_tvws.md).

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

### Salida — por sub-banda

```python
{
    "prob_ocupado":     {14: 0.03, 15: 0.91, ...},   # por canal global
    "libres_globales":  [14, 17, 21],                 # ordenados de más a menos limpio
    "ocupados_globales":[15, 16],
    "mejor_canal":       14,
    "latencia_ms":       0.47
}
```

### Salida — ciclo completo (las 5 sub-bandas)

```python
{
    "timestamp":        1748123456.789,
    "canales":          { 14: {"prob_ocupado": 0.03, "libre": True}, ... },  # 14–52
    "libres_ordenados": [14, 17, 52, 31],
    "mejor_canal":       14
}
```

Este `dict` es lo único que consume el árbitro de decisión para construir la trama de control LoRa de 10 bytes que se envía al nodo Cliente.

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
┌─────────────────────────────────────────────────────────────┐
│              BUCLE DE SENSADO (~137 ms/ciclo)                │
│                                                               │
│  1. bladeRF RX2 captura sub-banda (56 MHz)                   │
│        ↓  ZMQ (IPC en RAM, sin disco)                        │
│  2. Procesador PSD: FFT → normalización percentil 5/95        │
│        ↓                                                      │
│  3. ONNX Runtime: inferencia (~0.5 ms)                        │
│        ↓                                                      │
│  4. Repetir para las 5 posiciones de barrido                 │
│        ↓                                                      │
│  5. Árbitro de decisión: reglas R1–R7 (histéresis,            │
│     confirmación de 3 ciclos, cuarentena post-salto)          │
│        ↓                                                      │
│  6. Trama LoRa de 10 bytes → nodo Cliente                    │
└─────────────────────────────────────────────────────────────┘
```

Cada etapa corre en su propio thread Python dentro de un único proceso en el Gateway, comunicados por colas thread-safe (`queue.Queue`) y, entre GNU Radio y el procesador PSD, por sockets ZeroMQ.

---

## Estructura del repositorio

```
.
├── README.md                          # este archivo
├── requirements.txt                   # dependencias Python (CPU, Windows/Linux)
├── .env                                # variables de entorno (NO subir con datos reales)
├── setup_entorno.sh                   # script de instalación automática (Linux)
│
├── spectral_sense.py                  # modelo, entrenamiento, exportación ONNX, inferencia
├── generar_dataset_sintetico_v2.py    # generador de dataset sintético (sub-banda completa)
├── captura_sesion.py                  # captura real con RTL-SDR (control de calidad incluido)
├── evaluar_modelo.py                  # evaluación: ROC, matriz de confusión, benchmark latencia
├── analizar_entrenamiento.py          # gráficas de loss/AUC/F1 desde historial.json
│
├── docs/
│   ├── arquitectura_ia_tvws.md        # arquitectura completa, capa por capa
│   └── pipeline_dataset_v2.md         # pipeline de recolección y construcción del dataset
│
├── dataset/                           # (generado) train/val/test en .npz
├── modelos/                           # (generado) checkpoints .pt y modelo .onnx
└── graficas_eval/                     # (generado) gráficas de evaluación
```

---

## Instalación

Requiere Python 3.11 o 3.12 (evitar 3.13/3.14 — varias dependencias científicas aún no publican wheels precompiladas para esas versiones).

```bash
git clone <url-del-repo>
cd spectral-sense-tvws

python3.11 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\Activate.ps1     # Windows PowerShell

pip install -r requirements.txt
```

En Linux, para captura con RTL-SDR:

```bash
sudo apt install librtlsdr-dev rtl-sdr
sudo cp /usr/lib/udev/rules.d/rtl-sdr.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

O usar el script automatizado: `./setup_entorno.sh`

---

## Uso rápido

### 1. Generar dataset (sintético, para pruebas sin hardware)

```bash
python generar_dataset_sintetico_v2.py --n_muestras 4000
```

### 2. Entrenar

```bash
python spectral_sense.py --modo entrenar --dataset ./dataset_v2 --epocas 80
```

Exporta automáticamente a ONNX al finalizar.

### 3. Evaluar

```bash
python evaluar_modelo.py --dataset ./dataset_v2 --checkpoint ./modelos/mejor_modelo.pt
```

Genera curvas ROC por canal, matriz de confusión, distribución de probabilidades y benchmark de latencia.

### 4. Analizar el historial de entrenamiento

```bash
python analizar_entrenamiento.py --historial ./modelos/historial.json
```

### 5. Captura real con RTL-SDR (Fase 1, recolección de dataset)

```bash
python captura_sesion.py --ubicacion uni_rimac --sesion prime_time --repeticiones 5
```

### 6. Inferencia en campo (uso en producción dentro del Gateway)

```python
from spectral_sense import SpectralSenseInferencia
import numpy as np

inferenciador = SpectralSenseInferencia("./modelos/spectral_sense.onnx")

# iq: muestras I/Q crudas de una sub-banda (complex64)
resultado = inferenciador.clasificar_subbanda(iq, posicion_idx=0)
print(resultado["libres_globales"])   # ej: [14, 17, 21]
print(resultado["mejor_canal"])       # ej: 14
```

---

## Métricas del modelo

Resultados sobre split de test (dataset sintético v2, 600 sub-bandas, 5,162 etiquetas válidas):

| Métrica | Valor |
|---|---|
| AUC-ROC global | **0.9211** |
| Sensibilidad (umbral 0.20, campo) | **0.9831** — solo 29 falsos negativos sobre 1,716 canales ocupados |
| F1(β=2) | 0.8363 |
| Latencia de inferencia (CPU) | 0.47 ms promedio · 0.84 ms P99 |

El umbral operativo (`UMBRAL_LIBRE = 0.20`, no 0.5) está elegido deliberadamente para minimizar falsos negativos: en radio cognitiva, declarar "libre" un canal que en realidad tiene un primario activo es un error regulatorio grave, mientras que declarar "ocupado" un canal libre solo cuesta eficiencia espectral.

> Estas métricas son sobre dataset **sintético**. Pendiente: validación con dataset real capturado en Fase 1 (ver `docs/pipeline_dataset_v2.md`).

---

## Roadmap

- [x] Arquitectura del modelo definida y validada
- [x] Pipeline de entrenamiento con manejo correcto de etiquetas desconocidas (`BCEWithLogitsLossMasked`)
- [x] Dataset sintético v2 (formato de sub-banda completa, igual al de campo)
- [x] Evaluación exhaustiva (ROC, matriz de confusión, benchmark de latencia)
- [ ] Captura de dataset real con RTL-SDR V4 en Lima (Fase 1)
- [ ] Re-entrenamiento y validación con dataset real
- [ ] Integración con árbitro de decisión y protocolo LoRa (Fase 2)
- [ ] Despliegue e inferencia en el Gateway (OptiWork SFF 3050)
- [ ] Pruebas de campo en enlace piloto urbano (Fase 3)

---

## Proyecto

**Diseño y Validación de un prototipo de Radio Cognitiva basado en Hardware SDR asimétrico y Deep Learning para el acceso dinámico a TVWS en zonas rurales**
Universidad Nacional de Ingeniería · Facultad de Ingeniería Eléctrica y Electrónica (IITMC)
Grupo de Investigación VRI 2024–2026 · Mayo–Diciembre 2026

PI: Galvez Legua, Mauricio Pedro
