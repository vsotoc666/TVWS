# CONTEXTO: Proyecto Radio Cognitiva TVWS (UNI, Perú)

Documento de contexto para asistente IA. Proyecto de investigación universitaria. Densidad alta, sin redundancia.

## RESUMEN EN UNA FRASE
Sistema de radio cognitiva que lleva Internet desde una localidad con fibra (nodo Gateway) hasta una comunidad rural (nodo Cliente) vía enlace inalámbrico punto a punto full-duplex de 10–15 km sobre espectro TV no usado (TVWS, UHF 470–698 MHz). Producto principal entregable: bloque de software GNU Radio modular con IA de sensado espectral. Objetivo TRL-4.

## IDENTIDAD
- Institución: Universidad Nacional de Ingeniería (UNI), Facultad IEE-IITMC, Lima, Perú
- Programa: VRI Formativa 2026, fondos estatales vía portal RNP, presupuesto S/40,000
- Periodo: 18 mayo → 15 diciembre 2026
- PI: Galvez Legua, Mauricio Pedro
- Equipo: Franco Espinoza (F1: dataset+IA), Victor Soto (F2: integración SDR+MAC), Sandro Niño (F3: enlace piloto)

## CONCEPTO CLAVE
- Producto = el BLOQUE DE SOFTWARE (GNU Radio + CNN). El enlace de 10–15 km es la VALIDACIÓN, no el producto.
- Arquitectura ASIMÉTRICA: toda la inteligencia cognitiva (CNN, decisión de canal) corre en el Gateway. El Cliente solo demodula y obedece órdenes de salto de canal.
- Gateway está en localidad CON fibra; Cliente en comunidad rural SIN conectividad (la recibe por el enlace TVWS).

## ARQUITECTURA FÍSICA
```
Internet → [Router fibra] → Ethernet → [Mini PC GATEWAY: Core Ultra 5, Ubuntu 22.04]
  → [bladeRF 2.0 SDR] →📡 enlace TVWS OFDM 6MHz full-duplex 10-15km 📡→ [SDR Cliente]
  → [Orange Pi 5 CLIENTE: RK3588 ARM64, Ubuntu 22.04] → [AP WiFi local] → usuarios
```
- Downlink (DL, Gateway→Cliente): lado fuerte. Uplink (UL, Cliente→Gateway): lado débil.
- Full-duplex real: DL y UL simultáneos. 4 antenas LPDA totales (TX+RX dedicadas por nodo, sin conmutador).

## HARDWARE POR NODO

### Gateway
- SDR: bladeRF 2.0 micro xA4 (2TX/2RX, 12 bits, VCTCXO ±1ppm). TX1=DL datos, RX1=UL datos, RX2=sensado dedicado.
- PC: Mini PC Intel Core Ultra 5 225 (10 núcleos híbridos P+E, hasta 4.9GHz, 32GB DDR5, 1TB SSD). Corre GNU Radio + inferencia CNN ONNX.
- PA: lineal clase AB, 400–1000MHz, 2W/+33dBm, +27dB ganancia. Solo el Gateway tiene PA.
- LNA RX: NF≤1dB, +15–25dB, montado junto a antena.
- Antenas: LPDA TX (10dBi) + LPDA RX (10dBi) + discone omni (sensado RX2).
- Salida a Internet: Ethernet RJ45 a router de fibra.

### Cliente
- SDR: por definir (full-duplex, ADC 12 bits, ≥30 MSPS USB 3.0, TCXO ±2ppm). Candidato previo LimeSDR Mini 2.0. NO definido aún.
- SBC: Orange Pi 5 (16GB RAM, RK3588, ARM64). Hardware propio del equipo.
- LNA RX: NF≤1dB. SIN PA (decisión por consumo energético rural + costo + asimetría de tráfico).
- Antenas: LPDA TX (10dBi) + LPDA RX (10dBi).
- Conectividad local al usuario: AP WiFi / router ya disponibles (no requieren compra).

## CAPA OFDM (canal de datos)
- BW 6 MHz, 512 subportadoras (FFT), ~420 datos, ~55 pilotos, ~52 guardas, 3 de control (#254/#256/#257; #255 evitada por DC offset).
- CP=1/4 (~56µs), símbolo ~89µs, 7.68 MSPS.
- Modulación adaptativa BPSK/QPSK/16-QAM (la elige la CNN según calidad de canal). FEC convolucional o LDPC, tasa 1/2 o 3/4.

### Throughput neto (factor corrección incluido)
| Modo | Neto |
|---|---|
| BPSK 1/2 | ~1.9 Mbps |
| QPSK 1/2 | ~3.9 Mbps |
| QPSK 3/4 | ~5.8 Mbps |
| 16-QAM 3/4 | ~11.6 Mbps |
DL y UL alcanzan estos valores SIMULTÁNEAMENTE (full-duplex). Objetivo conservador campo (10–15km, NLOS): ≥1.9 Mbps DL y UL en BPSK.

## BLOQUE DE SOFTWARE (producto principal) — 6 capas
1. `RadioInterface` — abstrae el hardware SDR (bladeRF vs SDR Cliente), unifica API, resuelve drivers/DC offset/IQ.
2. `SpectralSensor` — el bladeRF tiene ~56 MHz instantáneos máx, NO cubre los 228 MHz de TVWS de una vez. Hace BARRIDO de 5 posiciones de 56 MHz sobre RX2; calcula PSD (FFT 512, Welch, Hann) por sub-banda.
3. `ChannelClassifier` (CNN 1D ONNX) + `SpectralOccupancyMap` — clasifica UNA sub-banda de 56MHz por inferencia (dual-head: ocupación + SNR/margen estimado por canal). Ensambla las 5 sub-bandas en mapa global de 39 canales con timestamp (no es foto instantánea).
4. `CognitiveEngine` — política de selección de canal (lowest_free/max_margin/least_used) + protocolo de salto + canal refugio pre-acordado.
5. `InbandControlLayer` — control Opción A: inyecta next_ch+t_hop+CRC en subportadoras #254–257. Latencia <1ms.
6. `MonitoringDashboard` — dashboard Qt/WebSocket: espectrograma, ocupación, canal activo, saltos, throughput, BER, estado CNN.

## CNN SENSADO
- 1D-CNN dual-head, entrada PSD, ~350–600K params, 2–4MB ONNX, inferencia <10ms.
- Entrenada PyTorch/Colab T4, desplegada ONNX Runtime.
- Domain mismatch: dataset captura con RTL-SDR (8 bits) → inferencia en bladeRF (12 bits). Mitigación: normalización por rango dinámico.
- KPIs conservadores: accuracy >85%, falsos negativos <10%, evacuación de canal <300ms.
- ESTADO: modelo dual-head implementado y validado SOLO sobre dataset SINTÉTICO. Dataset real TVWS aún NO capturado.

## CONTROL IN-BAND (Opción A)
- Campo de control viaja en subportadoras OFDM dedicadas, BPSK fija (sobrevive cuando datos en 16-QAM fallan).
- Mensaje: preámbulo + next_ch + t_hop + flags(normal/salto/refugio/resync) + CRC. Repetición continua + votación mayoría.
- Sin canal fuera de banda. LoRa fue ELIMINADO (restricción presupuestal).
- Contingencia degradación abrupta: ambos nodos saltan a canal refugio pre-acordado (470 MHz) sin coordinación explícita.

## LINK BUDGET (15km, NLOS 15dB, full-duplex)
- DL: EIRP +41.7dBm (con PA), PRx ~−77dBm, margen BPSK ~+18dB / QPSK ~+15dB. Holgado.
- UL: EIRP +20dBm (SIN PA), PRx ~−96dBm, margen BPSK ~+3.7dB / QPSK +0.7dB (marginal). UL es el lado frágil.
- A 10km o en LOS/NLOS suave: márgenes mejoran sustancialmente (~+3.5dB solo por distancia).
- Latencias: propagación 0.05ms, inferencia CNN <10ms, control <1ms, sensado 100-200ms, E2E datos 10–30ms, evacuación canal <300ms.

## CÓMPUTO TIEMPO REAL (Gateway)
- Core Ultra 5 es híbrido P-core/E-core. Linux scheduler puede asignar mal el flowgraph a E-cores → jitter/underruns USB.
- Solución: identificar P-cores (`lscpu`, `/sys/devices/cpu_core/cpus`), aislar con `isolcpus` en GRUB, anclar GNU Radio con `taskset -c`, desactivar irqbalance y enrutar IRQs USB lejos de P-cores aislados.

## CRONOGRAMA (reestructurado, retraso 25 días en F1)
| Fase | Periodo | Días | Contenido |
|---|---|---|---|
| F1 (extendida) | 18/05→10/07 | 53 | Dataset + entrenamiento IA + compras |
| F2 (comprimida) | 10/07→31/08 | 52 | Integración SDR + MAC + bloque cognitivo |
| F3 (comprimida) | 01/09→20/10 | 50 | Enlace piloto urbano (azotea UNI) |
| F4 (comprimida) | 21/10→02/12 | 43 | Despliegue rural 10–15km + validación |
| F5 | 03/12→15/12 | 13 | Análisis + informe final |

## ESTADO ACTUAL (ref. 15/06/2026)
COMPLETADO: arquitectura completa del bloque (6 capas); control in-band Opción A; protocolo refugio; specs hardware ambos nodos; decisión full-duplex 4 antenas (sin conmutador SPDT); PC Gateway Core Ultra 5 + estrategia afinidad CPU; link budget full-duplex; CNN dual-head implementada + pipeline (dataset sintético, entrenamiento, export ONNX, inferencia) validado end-to-end SOBRE SINTÉTICO.
PENDIENTE INMEDIATO: publicación RNP; captura dataset TVWS REAL; fine-tuning CNN sobre datos reales; prueba inferencia ONNX en hardware real.

## DECISIONES DE DISEÑO (vs propuesta original)
| Aspecto | Original | Actual |
|---|---|---|
| SDR Cliente | PlutoSDR (USB 2.0) | full-duplex genérico USB 3.0 ≥30MSPS 12 bits (modelo por definir) |
| Control | LoRa SX1262 fuera de banda | In-band Opción A + refugio (LoRa eliminado) |
| LNA Gateway | no había | añadido NF≤1dB (margen UL +0.9→+3.7dB) |
| Antenas | full-duplex 2 antenas / o TDD con switch | full-duplex 4 LPDA dedicadas (sin switch SPDT) |
| PC Cliente | Mini PC N100 | Orange Pi 5 16GB ARM64 |
| PC Gateway | Ryzen 9 8945HS | Core Ultra 5 225 (afinidad P-core) |
| Distancia | 15–20 km | 10–15 km |

## SOFTWARE
- Gateway (Ubuntu 22.04 x86_64): GNU Radio 3.10.x, gr-bladeRF, ONNX Runtime ≥1.16, PyTorch ≥2.0, Python ≥3.10, taskset.
- Cliente (Ubuntu 22.04 ARM64): GNU Radio 3.10.x, driver del SDR elegido (compilar desde fuente en ARM64), Python ≥3.10.
- Dev: PyTorch+Colab Pro (entrenamiento), GitHub, Overleaf, Notion.
- Nota: el Gateway viene con Ubuntu 25.04 preinstalado; reinstalar 22.04 LTS para compatibilidad GNU Radio.

## PUNTOS ABIERTOS / NO RESUELTOS
- Modelo final del SDR Cliente.
- Captura del dataset espectral real (protocolo definido, no ejecutado).
- Integración red↔radio (puente TUN/TAP entre pila IP de Linux y GNU Radio) — no implementada.
- Arquitectura de red (DHCP, NAT vs routing, MTU, DNS, QoS) — no definida.
- Validación de autointerferencia TX→RX en el mismo nodo (full-duplex): se controla por separación física/angular + misma polarización en las 4 antenas, a medir en F3.
