# Arquitectura de Transmisión de Datos — Bloque Cognitivo TVWS

> Referencia rápida y autocontenida de las 6 capas del bloque cognitivo GNU Radio (equivalente a README.md §2 y §7, pero condensado). Usar **este archivo** en vez de leer `README.md` completo cuando se trabaje en la arquitectura de software de las capas 1-6. Si hace falta el detalle de hardware/RF/link budget, ese sí sigue solo en `README.md`.
>
> **Estado real (no confundir con diseño):** de las 6 capas, solo la **Capa 3** tiene código implementado, en `IA/` (`nucleo.py`, `inferencia.py`). Las Capas 1, 2, 4, 5, 6 son diseño de interfaz, no código — viven en `GATEWAY/`/`CLIENTE/`, que todavía no existen como directorios.

---

## Entornos y sistemas operativos

Hay **dos máquinas Linux distintas** en juego para este tramo — no confundir dónde se desarrolla/prueba con dónde corre en campo:

### Máquina de desarrollo/pruebas (donde se corren hoy las Fases 1-3 del plan de pruebas)

| Campo | Valor |
|---|---|
| SO | Ubuntu 22.04.5 LTS (Jammy Jellyfish), kernel `6.8.0-124-generic` |
| Arquitectura | x86_64 |
| CPU | Intel Core i7-12700H (12ª gen, **híbrido P-core/E-core**, 14 núcleos / 20 hilos, hasta 4.7 GHz) |
| RAM | 38 GiB |
| Python del sistema | 3.10.12 |

Es una **laptop de desarrollo**, no el hardware de campo — pero al ser también Ubuntu 22.04 LTS con CPU híbrida Intel, sirve como banco razonable para las Fases 1-3 (software puro, sin SDR) e incluso para prototipar la afinidad a P-cores de §10 antes de tener el Mini PC del Gateway.

### Nodo Gateway — destino final de campo (specs en README.md §4.1 y §13)

| Campo | Valor |
|---|---|
| SO objetivo | **Ubuntu 22.04 LTS** — el equipo viene con Ubuntu 25.04 no-LTS preinstalado; hay que reinstalar antes de desplegar, para mantener compatibilidad con el stack GNU Radio 3.10.x validado |
| Modelo PC | Mini PC OptiWork SFF 3050 |
| CPU | Intel Core Ultra 5 225 (10 núcleos, **arquitectura híbrida P-core/E-core**, hasta 4.9 GHz) — requiere aislamiento de P-cores vía GRUB (`isolcpus`) y `taskset` para el flowgraph, ver §10 del README |
| RAM | 32 GB DDR5 4800 MHz |
| Almacenamiento | 1 TB SSD |
| GPU | Intel Graphics integrada (Xe-LPG) — no se usa, ONNX Runtime corre en CPU/OpenVINO (ver `IA/README.md`) |
| Arquitectura | x86_64 |
| Software clave | GNU Radio 3.10.x, `gr-bladeRF`, ONNX Runtime ≥1.16, PyTorch ≥2.0 (solo entrenamiento), Python ≥3.10, `util-linux` (`taskset`) |

**Implicación para las pruebas:** ambas máquinas son Ubuntu 22.04 LTS x86_64 con CPU Intel híbrida — el software escrito y probado en la máquina de desarrollo debería portar sin sorpresas de compatibilidad al Gateway real. La diferencia relevante es de **cantidad** (10 vs 14 núcleos, 32 vs 38 GB RAM) y de que el Gateway necesita la reinstalación limpia de SO antes de recibir cualquier despliegue — no asumir que el Ubuntu 25.04 de fábrica sirve.

### Nodo Cliente — Orange Pi 5 (specs en README.md §4.2 y §13)

| Campo | Valor |
|---|---|
| SO | Ubuntu 22.04 LTS |
| Arquitectura | **ARM64** (no x86_64 — no asumir binarios/wheels de la máquina de desarrollo o el Gateway) |
| SBC | Orange Pi 5, RK3588 |
| RAM | 16 GB |
| SDR | bladeRF 2.0 micro xA4 — mismo modelo que el Gateway (candidato previo LimeSDR Mini 2.0 descartado) |
| Software clave | GNU Radio 3.10.x, `gr-bladeRF`/`libbladeRF` **compilado desde fuente para ARM64** (mismo driver que el Gateway, sin `gr-limesdr`/`gr-plutosdr`), Python ≥3.10 |
| Rol | Sin lógica cognitiva propia — solo demodula y ejecuta las órdenes de salto recibidas por el campo de control in-band (Capa 5) |

**Implicación para las pruebas:** es la única de las tres máquinas que no es x86_64. GNU Radio y `gr-bladeRF` ahí requieren compilación desde fuente (no hay garantía de wheels/paquetes precompilados para RK3588), y cualquier dependencia nativa (ONNX Runtime, si algo de Capa 3 terminara corriendo ahí — no debería, ver `IA/README.md`) necesitaría build ARM64 aparte. Las Fases 1-3 del plan de pruebas (software puro) se pueden validar en la máquina de desarrollo o el Gateway sin tocar el Cliente; el Cliente solo entra en juego a partir de la Fase 4 (bladeRF Gateway↔bladeRF Cliente por cable).

---

## Modelo de ejecución (léase antes de tocar cualquier capa)

GNU Radio tiene dos mecanismos de conexión entre bloques que **no deben mezclarse**:

- **Puertos de flujo (streaming)**: continuos, con deadline real de símbolo OFDM (~89 µs). Únicamente la ruta RX1/TX1 (datos) y su paso por Control In-Band usan esto.
- **Puertos de mensajes (PMT, asíncronos)**: todo lo demás — retuning de sensado, cálculo de PSD, inferencia CNN, decisión cognitiva, orden de salto. Sin deadline de símbolo. El cómputo pesado (NumPy, CRC-16, ONNX Runtime) debe vivir aquí, **nunca** dentro de un `work()` de streaming.

Error de diseño ya corregido una vez: tratar las capas 1-4 como hilos Python con `queue.Queue` y la capa 5 como `gr.sync_block` — son paradigmas incompatibles. La regla fija ahora es: **streaming solo para la ruta de datos, mensajes para todo el control-plane.**

---

## Tramo previo — Internet/Router ↔ GNU Radio (antes de Capa 1)

No es una capa nueva de las 6 de abajo — es el tramo que en README §6.1 aparece resumido en una sola línea (`[Internet/datos usuario] → [MAC] Empaquetado`). Cubre desde el cable Ethernet del router de fibra hasta el punto donde el MAC empieza a armar el frame OFDM, en ambas direcciones.

**Pieza clave — interfaz TUN, no un socket genérico:** el bloque nativo de `gr-blocks` **`blocks.tuntap_pdu`** crea/abre una interfaz de red virtual TUN en Linux (ej. `tun0`) y la expone a GNU Radio como puertos de **mensajes** (`pdu_in`/`pdu_out`), no streaming. No hay que escribir el puente a mano.

**TUN (capa 3, solo IP) vs TAP (capa 2, Ethernet completo) — decisión: TUN.** El enlace Gateway↔Cliente es punto a punto, no necesita ARP/broadcast de Ethernet, y cada byte de overhead pesa dado el presupuesto de throughput (~1.9–11.6 Mbps, README §5.3). El Cliente sí necesita L2 hacia su AP WiFi local, pero eso se resuelve *routeando* entre `tun0` (hacia el Gateway) y `wlan0` (AP local) dentro del Orange Pi, no extendiendo L2 sobre el radio.

### Downlink (Internet → Gateway → Cliente → usuario)

| Etapa | Componente | Entrada | Salida | Tipo |
|---|---|---|---|---|
| 0 | Router fibra → NIC Gateway | — | Trama Ethernet II con datagrama IP (≤1500 B) | física |
| 1 | Tabla de rutas del kernel (Gateway) | IP destinado a la subred rural (ej. `192.168.50.0/24`) | Mismo datagrama, enrutado a `tun0` | kernel |
| 2 | `blocks.tuntap_pdu` (Gateway, `tun0`) | Lectura del fd de `tun0` | PDU: `(dict metadata, u8vector payload)` — 1 paquete IP crudo por mensaje | **mensajes** |
| 3 | MAC — Empaquetado | PDU (IP crudo) | PDU con header: `seq_num`\|`next_ch`\|`mod_scheme`\|CRC + payload | mensajes |
| 4 | FEC + MOD | PDU (bits del frame MAC) | PDU de símbolos I/Q (BPSK/QPSK/16-QAM) | mensajes |
| 5 | "PDU to Tagged Stream" | PDU de símbolos | Stream `gr_complex` tageado con longitud | **frontera mensajes→streaming** |
| 6 | OFDM Carrier Allocator → IFFT → CP | Stream `gr_complex` | Stream `gr_complex[512]` → CP → continuo a 7.68 MSPS | streaming |
| 7 | `RadioInterfaceDatos` TX1 (Capa 1) | Stream `gr_complex` | RF | streaming |

Recepción en el Cliente (espejo): `RadioInterfaceDatos` RX1 → FFT → EQ (streaming) → "Tagged Stream to PDU" (frontera inversa) → DEMOD/Viterbi/LDPC (PDU) → MAC (valida CRC, quita header) (PDU) → `blocks.tuntap_pdu` del Cliente escribe en su `tun0` → kernel del Orange Pi enruta a `wlan0` (AP WiFi) → usuario final.

### Uplink (usuario → Cliente → Gateway → Internet)

Mismo pipeline espejado, con dos diferencias ya fijadas en README §6.3: **sin campo de control in-band** (el paso de Capa 5 no existe en esta dirección) y **modulación forzada BPSK** (sin selección adaptativa).

| Etapa | Componente | Entrada | Salida |
|---|---|---|---|
| 0 | Usuario → AP WiFi Orange Pi | Trama 802.11 | Datagrama IP |
| 1 | Routing/NAT del Orange Pi (`wlan0`↔`tun0`) | IP desde `wlan0` | IP enrutado a `tun0` del Cliente |
| 2 | `blocks.tuntap_pdu` (Cliente) | fd `tun0` | PDU (IP crudo) |
| 3-4 | MAC + FEC + BPSK forzado | PDU | PDU símbolos BPSK |
| 5-6 | PDU→Stream, IFFT+CP | — | Stream `gr_complex` |
| 7 | bladeRF Cliente TX | Stream | RF |

Recepción en el Gateway: RX1 → FFT → EQ → Stream→PDU → DEMOD (Viterbi, sin LDPC/16-QAM porque UL es BPSK) → MAC → `blocks.tuntap_pdu` (Gateway) escribe en `tun0` → kernel enruta al router de fibra → Internet.

### Cómo probar este tramo sin bladeRF/hardware conectado

`blocks.tuntap_pdu` no depende de ningún SDR — se puede validar la ruta Internet↔MAC en el banco (o incluso en una laptop) antes de tener hardware de campo:

```bash
# Crear el TUN de prueba (requiere privilegios de red, o setcap en el binario python)
sudo ip tuntap add dev tun0 mode tun user $USER
sudo ip addr add 10.99.0.1/30 dev tun0
sudo ip link set tun0 up

# Con un flowgraph mínimo: tuntap_pdu('tun0', MTU) -> pdu_to_tagged_stream -> ... -> loopback
# (conectar TX y RX del mismo flowgraph con un canal simulado, sin bladeRF)
# y verificar con:
ping -I tun0 10.99.0.2
```

Esto permite validar el framing MAC/FEC/MOD y la frontera PDU↔streaming de forma aislada, antes de integrar con RadioInterface (Capa 1) real.

### Decisiones abiertas de este tramo

- **NAT vs IP pública ruteada**: depende de si el ISP/RNP asigna una IP pública enrutable por nodo Cliente o solo una al Gateway — define si `tun0` del Gateway hace NAT/masquerade o solo forwarding puro.
- **MTU efectiva y fragmentación**: el MTU por defecto de `tun0` (1500 B) puede no calzar con el tamaño útil de un frame OFDM; conviene fijarlo explícitamente para evitar que el MAC tenga que fragmentar cada paquete grande en varios PDUs (el header ya reserva `seq_num` para eso, pero el tamaño óptimo no está calculado).
- **Un `tun0` o dos por nodo**: `blocks.tuntap_pdu` soporta full-duplex sobre el mismo fd, así que un solo dispositivo por nodo debería bastar — falta confirmarlo al implementar.

---

## Las 6 capas

### Capa 1 — Adquisición, dos sub-bloques

**`RadioInterfaceDatos`** (RX1/TX1 — bladeRF Gateway o bladeRF Cliente, mismo modelo)
- Sin API Python de "pedir muestras". Es wiring de flowgraph puro.
- Entrada: puerto de flujo (sink TX1) — `gr_complex`, tasa de símbolo (~7.68 MSPS)
- Salida: puerto de flujo (source RX1) — `gr_complex`, misma tasa

**`RadioInterfaceSensado`** (RX2 — barrido de sensado)
- Entrada: mensaje `retune` — PMT (índice de posición 0-4, o frecuencia en Hz)
- Salida: mensaje `captura` — PMT vector `gr_complex[N]`
- **Abierto:** N (tamaño de ráfaga) no está fijado. Welch necesita varios segmentos con solape para una PSD razonable, no basta con 512 muestras crudas.

Parámetros configurables: frecuencia central, ancho de banda de muestreo, ganancia RX, `hardware` (`bladerf`|`cliente_fd`|`generic`).

### Capa 2 — `SpectralSensor`

Bloque **sin puertos de flujo** (`io_signature(0,0,0)`), solo mensajes — es una máquina de estados de barrido, no parte de la ruta de muestras.

- Entrada: mensaje `captura` (de Capa 1)
- Salida: mensaje `retune` (a Capa 1) — avanza a la siguiente de las 5 posiciones
- Salida: mensaje `psd_out` (a Capa 3) — PMT `float32[512]` normalizado [0,1] + metadata (posición, timestamp)

El handler de `captura` calcula la PSD (FFT 512 pts, Hann, Welch) reusando `calcular_psd`/`normalizar_psd` de `IA/nucleo.py`. Como no hay deadline de símbolo sobre este cómputo, usar NumPy/SciPy aquí es seguro — no compite con el scheduler de streaming.

Parámetros configurables: posiciones de barrido, ancho de sub-banda, tamaño FFT, período de ciclo.

### Capa 3 — `ChannelClassifier` + `SpectralOccupancyMap` (única implementada, en `IA/`)

- Entrada: `float32[512]` → `ChannelClassifier.classify_subbanda(psd_vector, posicion_idx)`
- Salida por sub-banda: `dict` — `prob_por_canal`, `margen_por_canal` (dB), `libres_globales`, `inference_ms`, `confidence`
- Salida agregada (`SpectralOccupancyMap.mapa_actual()`, tras las 5 sub-bandas del ciclo): `canales{prob_ocupado, margen_db, libre, antiguedad_ms}` (14-52), `libres_por_indice`, `confianza_global`

**Abierto:** no está decidido si esto debe envolverse como bloque de mensajes propio (con su propio `psd_out`→`mapa_actualizado`) o si simplemente se llama de forma síncrona dentro del handler de la Capa 2. Cualquiera de las dos es válida; falta declararlo.

Detalle de arquitectura del modelo (CNN dual-head, umbral 0.20, etc.) — no se duplica aquí, ver `IA/README.md`.

### Capa 4 — `CognitiveEngine`

- Entrada: `mapa_actual()` (de Capa 3, presumiblemente vía mensaje `mapa_actualizado`)
- Entrada: `snr_actual_db` del canal de datos activo — **sin interfaz definida todavía.** Ninguna capa calcula hoy el SNR post-ecualización del enlace RX1; es un hueco funcional real, no solo de nomenclatura.
- Salida: mensaje `orden_salto` (a Capa 5 TX) — PMT `(next_ch, t_hop, flag)`

Responsabilidades: política de selección (`lowest_free`|`max_margin`|`least_used`), umbral de degradación → protocolo de canal refugio.

Parámetros configurables: política, canal(es) de refugio, tiempo de pre-anuncio, nº de confirmaciones CRC, umbral de degradación.

### Capa 5 — Control In-Band (Opción A), dos bloques

**`InbandControlTX`** (Gateway)
- Entrada: mensaje `orden_salto` (de Capa 4) → el handler actualiza una palabra de 32 bits (`next_ch|t_hop|flag|CRC-16`) en estado interno
- Entrada/Salida streaming: `gr_complex[512]` (pre-IFFT) — pass-through, con las posiciones #254/#256/#257 sobreescritas por símbolo en `work()`
- Regla dura: CRC/empaquetado se calculan en el handler del mensaje, **nunca** en `work()`

**`InbandControlRX`** (Cliente)
- Entrada streaming: `gr_complex[512]` (post-FFT) — tap pasivo, no modifica el stream
- `work()` acumula 3 bits/símbolo × 11 símbolos; al completar, valida CRC-16
- Salida: mensaje `control_recibido` (solo si CRC válido) — PMT `(next_ch, t_hop, flag)`

**Ejecutor del salto** (suscrito a `control_recibido`): programa la retunning real de `RadioInterfaceDatos` a `t_hop * 10 ms`. Es el componente que resuelve "quién ejecuta el salto" — antes quedaba implícito entre Capa 4 y Capa 1.

Asimetría esperada (no es fallo): solo el DL lleva campo de control; el UL no (ver README §6.3).

Parámetros configurables: índices de subportadoras, modulación del campo de control, repeticiones del pre-anuncio.

### Capa 6 — `MonitoringDashboard`

- Entrada: lectura de todos los topics anteriores (solo observador, read-only)
- Salida: JSON vía WebSocket a clientes externos (laptop remota)
- Decisión de diseño: corre en **proceso separado** del flowgraph crítico (evita que I/O de red lenta hacia un cliente remoto introduzca jitter vía GIL en el hilo de decisión/control — ver README §10, P-cores aislados)
- **Abierto:** no hay puente definido entre los puertos de mensajes PMT (intra-flowgraph) y ese proceso separado (ZMQ/WebSocket). Falta un adaptador explícito PMT→ZMQ.

Paneles: espectrograma, mapa de ocupación + confianza CNN, canal activo/próximo anunciado, historial de saltos, throughput DL/UL, SNR, BER, estado del clasificador.

---

## Tabla resumen de interfaces

| Capa | Entrada | Salida | Tipo |
|---|---|---|---|
| 1 — RadioInterfaceDatos | stream `gr_complex` (TX1) | stream `gr_complex` (RX1) | streaming |
| 1 — RadioInterfaceSensado | msg `retune` (PMT idx/freq) | msg `captura` (PMT `gr_complex[N]`) | mensajes |
| 2 — SpectralSensor | msg `captura` | msg `retune` + msg `psd_out` (PMT `float32[512]`) | mensajes |
| 3 — ChannelClassifier/Map | `float32[512]` | `dict` (prob/margen/libres) → `mapa_actual()` | llamada directa (Python) |
| 4 — CognitiveEngine | `mapa_actual()` + `snr_actual_db` (falta) | msg `orden_salto` (PMT next_ch/t_hop/flag) | mensajes |
| 5 — InbandControlTX | msg `orden_salto` + stream `gr_complex[512]` | stream `gr_complex[512]` (pass-through modificado) | mixto |
| 5 — InbandControlRX | stream `gr_complex[512]` | msg `control_recibido` (PMT, si CRC OK) | mixto |
| 6 — MonitoringDashboard | lectura de todos los topics | JSON/WebSocket | observador, proceso separado |

---

## Huecos abiertos (pendientes de decidir antes de implementar)

1. **Tamaño de ráfaga IQ** entre `RadioInterfaceSensado` → `SpectralSensor` (Welch necesita > 512 muestras con solape).
2. **Capa 3**: ¿bloque de mensajes propio o librería llamada desde el handler de Capa 2? No decidido.
3. **Fuente de `snr_actual_db`** para `CognitiveEngine.evaluar_degradacion()` — ninguna capa lo calcula hoy.
4. **Puente PMT ↔ ZMQ/WebSocket** para que Capa 6 (proceso separado) escuche sin bloquear el flowgraph.
5. Reparto de código entre `GATEWAY/` y `CLIENTE/` para el protocolo de control compartido (evitar que `CLIENTE/` importe módulos de `GATEWAY/`).
6. Dependencia de `torch` si `SpectralSensor` termina importando `IA/nucleo.py` directamente en el Gateway de campo (inferencia solo necesita ONNX Runtime, no PyTorch).
7. NAT vs IP pública ruteada en el tramo Internet↔`tun0` del Gateway (depende de asignación del ISP/RNP).
8. MTU efectiva de `tun0` y política de fragmentación de paquetes IP grandes en el MAC (`seq_num` ya reservado en el header, tamaño óptimo sin calcular).
9. Un `tun0` por nodo (full-duplex) vs dos dispositivos separados TX/RX — probablemente uno basta, falta confirmar.

---

## Plan de pruebas — tramo Internet/Router → GNU Radio

Orden pensado para aislar el tipo de falla en cada fase, en vez de depurar el sistema completo a ciegas. Hay 3 fronteras que fallan distinto: **kernel↔GNU Radio** (`tun0`↔`tuntap_pdu`: permisos, rutas, MTU), **PDU↔streaming** (MAC/FEC/MOD↔Carrier Allocator: framing, longitud, tags), **streaming↔RF** (Capa 1 con SDR real: hardware, timing, calibración).

**Fases 1, 2 y 3 no requieren ningún SDR** — son 100% software, se pueden correr ya, sin esperar hardware. Fases 4 y 5 sí necesitan bladeRF físico en ambos nodos. Fase 6 (proceso único) se puede armar sin SDR sustituyendo `RadioInterfaceDatos` por una fuente/sumidero nulo o el loopback de Fase 3, aunque no valida la parte de hardware real.

### Fase 1 — Unitarias, cada bloque aislado (sin SDR)

| # | Prueba | Cómo | Qué confirma |
|---|---|---|---|
| 1 | `tun0` básico | `ip tuntap add` + `ping -I tun0` | Permisos, la interfaz existe y el kernel enruta hacia ella |
| 2 | `tuntap_pdu` lectura | Flowgraph mínimo: `tuntap_pdu` → debug/print de PDU | Paquetes que entran a `tun0` salen como PDU con el payload correcto |
| 3 | `tuntap_pdu` escritura | Inyectar PDU sintético (message strobe) → verificar con `tcpdump -i tun0` | Bytes escritos a `tun0` llegan íntegros |
| 4 | MAC encapsulado/decapsulado | Test unitario Python puro: payload → header (`seq_num`\|`next_ch`\|`mod_scheme`\|CRC) → decap → payload igual | Framing correcto; CRC detecta corrupción inyectada a propósito |
| 5 | FEC round-trip | bits → codificado → bits, con y sin errores inyectados dentro del BER de diseño | El decodificador corrige hasta el límite esperado, no antes |
| 6 | MOD/DEMOD round-trip | bits → símbolos → bits, por separado para BPSK/QPSK/16-QAM | Constelación correcta en canal ideal |
| 7 | PDU↔Tagged Stream (ambos sentidos) | Paquete de longitud fija conocida → verificar tags y reconstrucción exacta | La frontera mensajes↔streaming no corrompe ni trunca |

### Fase 2 — Integración por pares (sin SDR)

| # | Prueba | Qué confirma |
|---|---|---|
| 8 | `tun0` → `tuntap_pdu` → MAC → dump | Tráfico real (`ping`) produce frames MAC bien formados |
| 9 | MAC → FEC → MOD → PDU-to-stream → dump a archivo | Símbolos generados coinciden con lo esperado por modulación |
| 10 | TX completo hasta antes del SDR (incluye IFFT+CP) | Estructura del símbolo OFDM correcta: guardas en cero, subportadoras de control en su índice, CP de longitud correcta |
| 11 | RX completo aislado, alimentado con la salida de la prueba 10 | La cadena de recepción reconstruye el payload original sin RF de por medio |

### Fase 3 — Loopback digital completo, mismo proceso (sin SDR)

| # | Prueba | Qué confirma |
|---|---|---|
| 12 | TX→RX conectados directo (vector, sin canal), tráfico real por `tun0` (`ping`/`iperf3`) | Pipeline completo entrega tráfico íntegro; primera medición de throughput/latencia vs. §5.3 |
| 13 | Igual que 12 con `channels.channel_model` (ruido/errores de bit sintéticos) | FEC corrige hasta el BER de diseño; CRC del MAC descarta lo que no corrige, sin colar paquetes corruptos a `tun0` |
| 14 | Paquete IP más grande que el payload útil de un frame OFDM | Fragmentación/reensamblado vía `seq_num` funciona (o expone que falta implementarlo) |
| 15 | `iperf3` sostenido por cada modo de modulación/FEC | Throughput medido vs. tabla de §5.3 (ej. BPSK 1/2 ≈1.9 Mbps) |

### Fase 4 — Con SDR real, en banco, cable/atenuador (requiere hardware)

| # | Prueba | Qué confirma |
|---|---|---|
| 16 | TX→cable/atenuador→RX del mismo bladeRF (o dos bladeRF por cable) | El hardware real (DAC/ADC, up/down-conversion) no rompe lo validado en Fase 3 |
| 17 | Orden de salto simulada a mitad de transmisión | Pérdida de paquetes acotada a la ventana de guarda de 10 ms |
| 18 | bladeRF Gateway ↔ bladeRF Cliente real, por cable | Interoperabilidad de driver/calibración antes de exponerlo a la antena (mismo modelo en ambos, riesgo reducido) |

### Fase 5 — Con antena (requiere hardware, empalma con Fase 3 del cronograma del proyecto)

| # | Prueba | Qué confirma |
|---|---|---|
| 19 | Enlace corto real (misma azotea) | BER/throughput real vs. link budget de §9.1 |

### Fase 6 — Integración final en un solo proceso

| # | Prueba | Qué confirma |
|---|---|---|
| 20 | Ensamblar TX+RX+MAC+FEC+MOD+`tuntap_pdu` en un único `gateway_flowgraph.py`, con afinidad a P-cores (§10) | Sin regresión de throughput/latencia respecto a las pruebas por partes; jitter dentro del presupuesto |
| 21 | Carga sostenida (horas) sobre el proceso único | Sin fugas de memoria ni degradación progresiva — condición para dejarlo corriendo en campo |

**Prioridad si el tiempo aprieta:** 1→7 y 12→13 exponen errores de diseño (framing, CRC, fragmentación) más barato, sin tocar hardware — hacerlas primero. 16-19 dependen de que llegue el hardware SDR y no bloquean el resto del trabajo de software mientras tanto.

---

*Este documento resume decisiones de arquitectura de software para las capas 1-6, discutidas y corregidas en sesiones de diseño. Para hardware, link budget, cronograma y estado del proyecto, ver `README.md`. Para la Capa 3 ya implementada, ver `IA/README.md`.*
