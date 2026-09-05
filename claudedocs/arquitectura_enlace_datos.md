# Arquitectura detallada del enlace de datos — TDD, canales, modulación, PA

> **Qué es este documento:** la especificación ensamblada y vigente del
> enlace físico de datos (capa TDD/framing, plan de canales, política de
> modulación/FEC, punto de operación del PA, presupuesto de rendimiento
> esperado). Es el **"qué construir"**, pensado para que otra sesión de
> Claude Code (u otra persona) pueda arrancar directamente un aspecto del
> enlace — el gemelo digital, la implementación GNU Radio del framing TDD,
> la selección final de PA — sin tener que reconstruir estas decisiones
> desde cero ni releer el historial completo de cómo se llegó a ellas.
>
> **Qué NO es:** no es el registro de *por qué* se descartaron las
> alternativas (full-duplex real, FDD con filtro, etc.) ni el log de
> riesgos abiertos — eso vive en `claudedocs/riesgos_arquitectura_transmision.md`,
> que este documento no reemplaza. Tampoco cubre el modelo de IA/CNN de
> sensado (`IA/README.md`) ni la arquitectura completa de las 6 capas de
> software del bloque cognitivo (`claudedocs/arquitectura_transmision_datos.md`)
> — este doc trata **solo** la capa física/TDD del enlace de datos. Cuando
> el diseño de aquí necesita una señal que produce la CNN (el margen
> continuo por canal), se referencia como una entrada externa, sin entrar
> en cómo se calcula.
>
> **Fecha de cierre de las decisiones que registra:** 20-21/08/2026, sesión
> de seguimiento a `claudedocs/brief_enlace_gemelo_digital.md`. Si trabajás
> sobre esto en una sesión bastante posterior, verificar contra
> `LINK_BUDGET/` que los parámetros de PA/distancia siguen vigentes antes
> de asumir que las cifras de este doc no cambiaron.

---

## 1. Resumen ejecutivo (para lectura rápida)

| Parámetro | Valor decidido |
|---|---|
| Duplexado | TDD por software (sin switch RF, sin filtro) |
| Slot | 20 símbolos OFDM/dirección (~1.78 ms) |
| Guarda TDD | 25–70 µs (ver desglose §2.2) |
| Duty cycle | 50/50 simétrico DL/UL |
| Canales | 1 canal de 6 MHz (fase inicial) |
| Fragmentación | Vía `seq_num`/PDU ID + bit MF, frames que no caben en 1 slot (§2.4) |
| Modulación | Adaptativa BPSK/QPSK/16-QAM, ambas direcciones |
| FEC | CCSDS K=7 convolucional, tasa 1/2 (línea base) / 3/4 vía perforado del mismo código madre (oportunista) — **cerrado 05/09/2026, LDPC descartado**, ver §4.3 |
| PA (ambos nodos) | Real: "OEM 2W 1-900MHz" clase A, P1dB >32 dBm (`SPECS EQUIPOS/PA.md`), backoff 7.5 dB → salida promedio +24.5 dBm |
| Distancia de diseño | 4 km (final, decidida 28/08/2026 — antes 6 km/rango 5-6 km) |
| Margen de enlace (4 km, simétrico) | BPSK +19.5 dB / QPSK +16.5 dB / 16-QAM +10.5 dB (recalculado 28/08/2026 con hojas técnicas reales de PA/antena y la distancia final de 4 km) |
| Throughput esperado (planificación) | ~1.9–2.8 Mbps por dirección (QPSK) |
| Throughput piso garantizado | ~0.92 Mbps por dirección (BPSK, refugio) |
| Throughput techo oportunista | ~5.6 Mbps por dirección (16-QAM, no garantizado) |

---

## 2. Framing TDD

### 2.1 Estructura de trama

```
Ciclo completo (símbolo OFDM = 89 µs, slot = 20 símbolos ≈ 1.78 ms):

|←── slot DL (Gateway TX) ──→|←g→|←── slot UL (Cliente TX) ──→|←g→|
        ~1.78 ms              ~50µs*      ~1.78 ms              ~50µs*
                          (+ ~20µs prop.)                  (+ ~20µs prop.)

* pesimista, sin medir en banco — ver §2.2

Periodo total del ciclo ≈ 2 × 1.78 ms + 2 × ~70 µs ≈ 3.70 ms
Eficiencia de slot ≈ 2×1.78ms / 3.70ms ≈ 96.2% (con guarda pesimista)
```

Sincronización: sin canal fuera de banda (no hay LoRa en este diseño, ver
`CLAUDE.md`). Cada nodo alinea su propia ventana de TX respecto al timing
de trama que detecta en la señal entrante, usando el mismo preámbulo
Schmidl-Cox que ya sincroniza el símbolo OFDM (`README.md` §6.2) — no
requiere handshake aparte.

### 2.2 Guarda — dos componentes distintos, no confundir

| Componente | Rango | ¿Necesita medición? | Qué gobierna |
|---|---|---|---|
| Asentamiento de bias del PA al conmutar TX on/off | 5–50 µs (rango de diseño) | **Sí — pendiente, bloqueante antes de Fase 4** | Riesgo de autointerferencia residual (el nodo "se escucha a sí mismo" si el PA no se apagó de verdad) y de spectral splatter en el encendido |
| Retardo de propagación (4 km, ida) | ~13 µs, fijo | No — es física, ya calculado | Tiempo muerto de tránsito en el ciclo completo — reduce eficiencia, no es opcional ni "guarda" en sentido estricto |

**Por qué importa la distinción:** el asentamiento del PA es un riesgo de
*seguridad/correctitud* (autointerferencia, posible violación regulatoria
de emisiones espurias si el encendido no asentó) — no cerrar esa medición
antes de operar en hardware real es un riesgo real, no un detalle de
precisión. El retardo de propagación es determinístico y ya está
incorporado al presupuesto — no bloquea nada, solo se suma al cálculo de
eficiencia.

**Decisión operativa relacionada:** ganancia manual (AGC deshabilitado) en
TX/RX durante los slots, para sacar el settling de AGC de la ecuación —
deja el asentamiento del PA como la única incógnita real de guarda.

### 2.3 Tabla de sensibilidad guarda/slot/eficiencia

Eficiencia = tiempo activo / (tiempo activo + guarda):

| N símbolos/slot | duración slot | guarda 5µs | 15µs | 30µs | 50µs |
|---|---|---|---|---|---|
| 5 | 445 µs | 98.9% | 96.7% | 93.7% | 89.9% |
| 10 | 890 µs | 99.4% | 98.3% | 96.7% | 94.7% |
| **20** | **1.78 ms** | 99.7% | 99.2% | 98.3% | **97.3%** |
| 50 | 4.45 ms | 99.9% | 99.7% | 99.3% | 98.9% |

N=20 con guarda pesimista (70 µs total, incluyendo propagación) da ~96.2%
de eficiencia — el punto elegido: buen balance entre latencia de espera
por turno (~1.78 ms por dirección, ~3.7 ms peor caso de ciclo completo) y
overhead de guarda.

### 2.4 Fragmentación de frames grandes (decidido 21/08/2026)

**El hallazgo:** el slot de 20 símbolos (§2.1) es más corto de lo que un
frame grande necesita en los modos de modulación más robustos. La Prueba
14 (`TRANSMISION/pruebas/fase3_loopback_completo/prueba14_paquete_grande/`)
midió empíricamente que un payload de 1400 bytes ocupa **50 símbolos OFDM**
a BPSK R=1/2 (~28 bytes/símbolo efectivos) — y concluyó en su momento que
no hacía falta fragmentación, porque en Fase 3 (sin TDD modelado) un frame
podía extenderse a cuantos símbolos hiciera falta sin chocar con nada. Con
el slot TDD ya decidido, esa conclusión ya no aplica:

| Modo | Bytes/símbolo (escalado desde la medición de Prueba 14) | Símbolos para MTU 1500B | ¿Cabe en 1 slot (20 símbolos)? |
|---|---|---|---|
| BPSK 1/2 | ~28 | ~54 | **No — necesita ~3 slots** |
| BPSK 3/4 | ~42 | ~36 | **No — necesita ~2 slots** |
| QPSK 1/2 | ~56 | ~27 | **No — necesita ~2 slots** |
| QPSK 3/4 | ~84 | ~18 | Sí, al límite |
| 16-QAM 3/4 | ~168 | ~9 | Sí, con margen |

Justo en el escenario más adverso (enlace degradado, forzado a BPSK — el
mismo escenario del canal de refugio), un frame de tamaño MTU no cabe en
un slot. **Decisión: implementar la fragmentación vía `seq_num` que la
Prueba 14 había dejado pendiente** (reabre esa prueba).

**Diseño de fragmentación:**

- **Regla de segmentación:** el TX calcula, al momento de encolar un
  paquete IP, cuántos símbolos ocuparía a la modulación activa. Si excede
  el presupuesto de un slot (20 símbolos, con margen — el umbral exacto de
  corte, ej. 18 vs 20 símbolos, es un detalle de implementación a ajustar
  con medición real, no una decisión de arquitectura), se fragmenta en N
  trozos que sí quepan cada uno en un slot.
- **Sin reordenamiento posible** (enlace punto a punto, sin rutas
  alternativas) → los fragmentos de un mismo paquete llegan siempre en el
  orden en que se transmitieron. Esto simplifica el diseño: **no hace
  falta un índice de fragmento explícito**, solo un bit "más fragmentos"
  (MF, análogo al de IPv4) y un identificador de PDU para detectar dónde
  empieza cada paquete nuevo.
- **Modulación fija por PDU:** todos los fragmentos de un mismo paquete
  usan la modulación decidida al momento de empezar a fragmentarlo (no se
  cambia de modulación a mitad de un paquete) — simplifica la reconstrucción
  y es irrelevante en la práctica porque el margen de la CNN se actualiza
  cada 100-200 ms, mucho más lento que la transmisión de un PDU completo.
- **Cambio de header propuesto:** el campo `next_ch` de `mac_frame.py`
  (`seq_num|next_ch|mod_scheme|CRC`, `TRANSMISION/pruebas/fase1_unitarias/prueba04_mac_encap_decap/mac_frame.py`)
  resultó **vestigial** — ningún test lo liga a lógica real de salto de
  canal (siempre se pasa como valor fijo/arbitrario en las pruebas), lo
  cual tiene sentido: el salto de canal real ya lo maneja el canal de
  control in-band dedicado (Opción A, subportadoras #254/256/257,
  `README.md` §7), no el header MAC — `next_ch` en `mac_frame.py` parece
  ser un remanente de un diseño anterior a esa decisión. Se propone
  **repurpuesar ese byte como `frag_flags`**: bit 0 = MF, bits 1-7
  reservados. Costo de header: **cero bytes adicionales** (sigue siendo de
  5 bytes) — la alternativa de agregar un byte nuevo (`frag_flags` aparte,
  header de 6 bytes) queda como plan B si al revisar el código se
  encuentra que `next_ch` sí se usa en algún lado no cubierto por esta
  búsqueda.
- **Reensamblado RX:** buffer por `seq_num` (ahora interpretado como ID de
  PDU, no como contador de frame suelto); concatena payloads en orden de
  llegada hasta el fragmento con MF=0. CRC-16 se sigue verificando por
  fragmento (ya existe) — un fragmento corrupto invalida todo el PDU en
  reensamblado (no hay ARQ/retransmisión en este diseño, ver más abajo).
- **Beneficio secundario:** la pregunta que la Prueba 14 dejó abierta
  ("¿cuánto puede ocupar un frame el canal de control in-band antes de
  retrasar un salto de emergencia?") se acota solo: con fragmentación, el
  peor caso pasa de ~4.5-5.7 ms (un frame monolítico de 1500B a BPSK) a
  **un slot completo (~1.78 ms)**, porque ningún frame individual excede
  ya un slot.

**Explícitamente fuera de este diseño — no confundir con fragmentación:**
no existe (ni se diseña acá) un mecanismo de ARQ/retransmisión — la única
protección contra errores es el FEC (§4.3). Si un fragmento llega corrupto,
el PDU completo se descarda en el receptor; no hay NAK ni reenvío
automático. Si esto termina siendo un problema real de calidad de servicio,
es una decisión aparte, no una extensión trivial de este diseño.

**Estado: ✅ implementado (04/09/2026).** `mac_frame.py` repurpuso `next_ch`
como `frag_flags` (bit 0 = MF, bits 1-7 reservados y ahora validados) y
agregó `fragmentar()`/`reensamblar()`; la Prueba 14 se rehizo contra el
slot TDD real (umbral de corte elegido: 18 símbolos, ~10% de margen bajo
el presupuesto de 20 — el paquete de prueba de 1400B fragmenta en 3 piezas
de ≤505 bytes de payload cada una, todas ≤20 símbolos, reensamblado
bit-exacto). 36/36 pruebas afectadas (Pruebas 4, 10, 11, 13, 14) pasan.
Detalle en `TRANSMISION/pruebas/fase1_unitarias/prueba04_mac_encap_decap/README.md`
y `TRANSMISION/pruebas/fase3_loopback_completo/prueba14_paquete_grande/README.md`.
El umbral de 18 símbolos es un valor razonable, no una medición de campo —
ajustable si el settling real de guarda TDD (§2.2, sigue sin medir) termina
dejando menos margen del asumido.

---

## 3. Plan de canales

**Decidido para esta fase: 1 canal de 6 MHz.** No se persigue re-sintonía
multi-ventana (sin presupuesto de latencia de hop cerrado para eso) ni
bonding de canales todavía.

**Extensión futura evaluada — bonding contiguo dentro de la ventana de 56
MHz** (el AD9361 tiene ~56 MHz de ancho de banda instantáneo máximo, así
que 2 canales de 6 MHz contiguos caben sin re-sintonía, mismo LO): viable
en principio para recuperar throughput perdido por TDD, pendiente de
diseño de detalle.

**Descartado explícitamente: 2 canales NO adyacentes simultáneos**, aunque
ambos quepan dentro de los 56 MHz. Razón: un PA no lineal alimentado con
dos bloques OFDM separados en frecuencia genera productos de
intermodulación de tercer orden que caen en el hueco *entre* ambos bloques
(problema conocido de *carrier aggregation* no contigua) — el proyecto usa
un único PA compartido para toda la cadena TX (no hay un PA por portadora
componente como en sistemas comerciales que sí hacen esto), así que
controlar esa intermodulación exigiría más backoff del ya ajustado (7.5
dB), y si hay un primario de TV en ese hueco, la intermodulación podría
interferirlo aunque el canal transmisor esté correctamente autorizado.
**Si se necesita más throughput vía multicanal, preferir contiguo sobre no
adyacente.**

**Fuera de los 56 MHz (dos frecuencias muy separadas, usando TX1+TX2 del
bladeRF a la vez):** casi seguro no es posible de forma simultánea con un
solo bladeRF — el AD9361 típicamente comparte un solo sintetizador/LO de
TX entre sus dos puertos (el modo 2×2 MIMO es para diversidad/beamforming
a la *misma* frecuencia, no frecuencias independientes). **No confirmado
explícitamente en `claudedocs/bladerf_2_micro_xa4_specs.md`** — verificar
contra el datasheet del AD9361 (ya enlazado en ese doc) antes de asumirlo
como decidido.

---

## 4. Modulación y FEC

### 4.1 Política de modulación

Adaptativa, **ambas direcciones** (ya no BPSK forzado en UL — el margen
dejó de estar asimétrico, ver §5). La selección en tiempo real depende de
una señal de margen continuo por canal (cabeza `margen_db` de la CNN,
`IA/README.md` — fuera de alcance de este documento cómo se calcula). Este
documento especifica los modos disponibles y cuándo son seguros de usar,
no el mecanismo de decisión en sí.

**Umbrales de disponibilidad recomendados** (ver §6 para el razonamiento
completo de margen de fading):

| Modo | Rol |
|---|---|
| BPSK | Garantizado — canal de refugio / condiciones degradadas |
| QPSK | Línea base esperada de operación normal |
| 16-QAM | Oportunista — solo cuando el margen medido en tiempo real lo sostiene, no asumir como modo por defecto |

### 4.2 Canal de refugio (contingencia)

Sin cambios respecto a `README.md` §7.6: si el SNR del canal activo cae
bajo un umbral configurable, ambos nodos saltan de forma autónoma al canal
de refugio pre-acordado (470 MHz, mejor difracción NLOS). No requiere
coordinación explícita — destino pre-acordado en firmware de ambos nodos.

### 4.3 FEC — **✅ cerrado (05/09/2026)**

**Decisión:** CCSDS K=7 convolucional como FEC base para **los tres modos
de modulación (BPSK/QPSK/16-QAM)**, con **tasa 3/4 obtenida perforando
(puncturing) el mismo código madre de tasa 1/2** — no un segundo códec.
Implementado y probado en
`TRANSMISION/pruebas/fase1_unitarias/prueba05_fec_roundtrip/` (`perforar()`/
`despuncturar()` en `ccsds_fec.py`, `test_puncturing_r34.py`).

**LDPC fue evaluado y explícitamente NO adoptado** (no diferido, no
prototipado — no hay código LDPC en el repo), por tres razones:

1. LDPC es un código de bloque (n,k fijos por palabra) — el umbral de
   fragmentación cerrado en §2.4 (505 bytes/18 símbolos) se derivó
   alrededor del modelo de streaming orientado a bytes, de longitud
   variable, del código convolucional. Migrar a LDPC exigiría rehacer ese
   umbral para framing alineado a bloque con relleno.
2. **El enlace TDD es simétrico — ambos nodos codifican Y decodifican en
   cada ciclo.** El Gateway es un Intel Core Ultra 5, pero el Cliente es
   un Orange Pi 5 ARM64, mucho más débil. El decoder iterativo de
   belief-propagation de LDPC es inherentemente más costoso por bit que
   Viterbi (trellis de 64 estados para K=7), y ese costo real en el
   Orange Pi 5 nunca se midió ni se preguntó en los docs previos (que
   solo consideraban cómputo del lado Gateway) — este riesgo no
   verificado en el nodo más débil fue la razón principal para no
   adoptar LDPC ahora (ver también punto nuevo en §8 más abajo).
3. GNU Radio no trae ninguna matriz LDPC de tasa 3/4 (solo matrices de
   tasa ~0.23-0.58 empaquetadas en `/usr/share/gnuradio/fec/ldpc/`) —
   construir una es trabajo de diseño de matrices fuera del alcance de
   este equipo, mientras que tasa 3/4 convolucional es gratis vía
   perforado del código K=7 ya validado.

**Qué se midió al cerrar esta decisión:**

- **Fix del arnés de pruebas** (causa raíz que Prueba 15 había señalado:
  `ccsds_fec.py` creaba un `gr.top_block()` por llamada): reescrito a un
  `top_block` persistente y de inicialización diferida por dirección
  (encode/decode). Resultado: ~40-55% menos tiempo por llamada
  (`codificar()`: ~0.59→~0.3 ms; `decodificar()`: ~1.07→~0.48 ms sobre
  payload de 100B), pero **no cerró la brecha al objetivo de throughput de
  diseño** (Prueba 15 sigue midiendo ~0.35x, ~0.67 Mbps vs. 1.9 Mbps
  objetivo BPSK R=1/2) — `tb.run()` conserva overhead de scheduler no
  trivial (~0.25 ms/llamada) incluso con topología persistente, y a los
  tamaños de payload medidos el resto de la cadena (MOD/OFDM en Python
  puro) resultó ser un cuello de botella igual o mayor que el FEC. Detalle
  completo en `TRANSMISION/pruebas/fase3_loopback_completo/prueba15_
  throughput_sostenido/README.md`.
- **Curva de ganancia de codificación (coding gain) real, tasa 1/2 vs.
  3/4**: tasa 3/4 (perforada) ya muestra degradación medible a solo 1% de
  BER de canal (~0.78% residual), mientras que tasa 1/2 sigue corrigiendo
  totalmente hasta ~3% — confirma con un número real el trade-off que la
  tabla de §7.1 ya asumía en teoría. Curva completa en
  `TRANSMISION/pruebas/fase1_unitarias/prueba05_fec_roundtrip/README.md`.

**Lo que esto NO cierra:** el costo real de decodificación Viterbi K=7 en
el Orange Pi 5 (ARM64) tampoco se midió — no hay hardware Orange Pi 5
disponible en este entorno de desarrollo. Se asume, sin medir, que Viterbi
K=7 es lo bastante liviano para el Cliente (es la motivación de rechazar
LDPC en primer lugar), pero eso sigue siendo una suposición, no una
medición — ver punto nuevo en §8.

---

## 5. Punto de operación del PA

| Parámetro | Valor real (`SPECS EQUIPOS/PA.md`) | Nodo |
|---|---|---|
| P1dB | >32 dBm (Psat/salida máxima +33 dBm, cifra distinta) | Ambos (Gateway y Cliente, mismo modelo comprado) |
| Ganancia típica | 30 dB a 500 MHz (máx. 42 dB) | Ambos |
| Backoff aplicado | 7.5 dB | Ambos |
| Salida promedio | +24.5 dBm | Ambos |
| Clase | **A** (no AB — mejor linealidad, menos eficiencia) | Ambos |
| Entrada máxima tolerada | +3 dBm — ⚠ menor que el TX máximo del bladeRF (+6 dBm); operar el SDR a ganancia reducida | Ambos |

**Por qué 7.5 dB y no el mínimo (6 dB) o el valor de trabajo inicial (5
dB):** con margen de enlace abundante a la distancia final de 4 km, subir
el backoff cuesta poco margen (16-QAM queda en +10.5 dB con las hojas
técnicas reales y la distancia final) y mejora linealidad/ACPR — y de paso
deja la potencia conducida a la antena (~+23.8 dBm, no depende de la
distancia) dentro del límite legal de densidad espectral (Art. 8 del
decreto, 12.6 dBm/100kHz) con ~6.1-6.6 dB de margen, resolviendo el
excedente que tenía marcado `claudedocs/cumplimiento_normativo_tvws.md`.

**Estado de compra (actualizado 28/08/2026):** el PA ya fue comprado y
**su hoja técnica real ya está confirmada** en `SPECS EQUIPOS/PA.md`
("PA OEM 2W 1-900MHz") — este punto de operación (7.5 dB de backoff sobre
P1dB=32dBm) ya no es un placeholder sobre un P1dB nominal genérico, está
calibrado contra el datasheet real del componente comprado. Lo que sigue
sin confirmar es el ACPR/OIP3 real (no está en la hoja técnica disponible)
— ver `claudedocs/requisitos_pa_lna.md` §3 para el checklist de
verificación completo.

---

## 6. Presupuesto de disponibilidad (margen de enlace vs. margen de fading)

**Fuente de verdad de los números de RF: `LINK_BUDGET/`** — esta sección
es una instantánea, no la fuente. Con el PA real (P1dB 32dBm, `SPECS
EQUIPOS/PA.md`) ambos nodos, backoff 7.5 dB, antena real (5 dBi a 500MHz,
`SPECS EQUIPOS/ANTENA_DIRECCIONAL`), distancia final **4 km** (decidida
28/08/2026 — antes 6 km), NLOS 15 dB (sin revalidar a esta distancia, ver
§8), **sin GDT** (eliminado del diseño 28/08/2026 — enlace de validación
de solo ~3h, ver `claudedocs/estructura_fisica_instalacion.md`):

| Modo | Margen total (4 km) | Margen residual tras reservar ~10 dB para fading* | Rol |
|---|---|---|---|
| BPSK | +19.5 dB | +9.5 dB | Garantizado |
| QPSK | +16.5 dB | +6.5 dB | Línea base esperada |
| 16-QAM | +10.5 dB | +0.5 dB | Oportunista — margen residual apenas positivo, no confiable como modo garantizado |

> **Actualizado 28/08/2026:** con las hojas técnicas reales de PA/antena y
> la distancia final de 4 km, el margen residual de 16-QAM bajo la reserva
> de fading vuelve a ser positivo (+0.5 dB) — a 6 km con las mismas hojas
> técnicas había quedado claramente negativo (−3.0 dB). La reducción de
> distancia (6→4 km) recupera ~3.5 dB de FSPL, más que compensando la
> pérdida de margen de pasar de cifras genéricas a las reales de PA/antena.
> Aun así, +0.5 dB de margen residual es un colchón mínimo — no tratar
> 16-QAM como un modo confiable bajo fading sin datos de campo que lo
> respalden, aunque en el papel ya no cierre en negativo como a 6 km.

\* Los márgenes de `LINK_BUDGET/` son contra una pérdida NLOS **estática**
(15 dB fijo), no un margen de desvanecimiento estadístico (fading rápido
por multipath, típico en enlaces NLOS UHF fijos). No hay datos de campo
propios todavía — los 10 dB reservados son una regla práctica común en
enlaces NLOS UHF fijos (referencia de orden de magnitud, no cifra exacta
del proyecto), **a validar en el piloto de azotea UNI (Fase 3)**.

**Conclusión operativa:** QPSK es el modo a citar como rendimiento
"esperado", no 16-QAM — 16-QAM es techo oportunista, no línea de
planificación, mientras no haya margen de fading medido en campo.

---

## 7. Métricas de rendimiento esperadas

### 7.1 Throughput (por dirección, ya con TDD 50/50 y eficiencia de guarda ~96.2% aplicados)

| Modo | FEC | Throughput bruto | Neto (sin TDD) | **Neto con TDD 50/50** |
|---|---|---|---|---|
| BPSK | 1/2 | 6 Mbps | ~1.9 Mbps | **~0.92 Mbps** |
| BPSK | 3/4 | 6 Mbps | ~2.9 Mbps | **~1.4 Mbps** |
| QPSK | 1/2 | 12 Mbps | ~3.9 Mbps | **~1.9 Mbps** |
| QPSK | 3/4 | 12 Mbps | ~5.8 Mbps | **~2.8 Mbps** |
| 16-QAM | 3/4 | 24 Mbps | ~11.6 Mbps | **~5.6 Mbps** |

### 7.2 Latencia

| Componente | Valor |
|---|---|
| Espera de turno TDD (promedio / peor caso) | ~1.83 ms / ~3.66 ms |
| Propagación (4 km) | 0.013 ms |
| Señalización de control in-band | <1 ms transmisión + hasta ~3.66 ms espera de slot |
| Evacuación de canal (sensado + CNN + control + guarda) | <300 ms |

---

## 8. Qué NO está cerrado — no asumir resuelto

1. **Asentamiento real del bias del PA** — sin medir en banco, bloqueante
   antes de Fase 4 (§2.2).
2. **Pérdida NLOS de 15 dB sin revalidar a 4 km** — se arrastra del
   análisis hecho para 10-15 km (y luego 5-6 km); el terreno real puede
   diferir, y menos aún a la distancia final más corta.
3. **Margen de fading estadístico no medido** — la reserva de ~10 dB (§6)
   es una regla práctica, no una medición del sitio real.
4. **FEC (convolucional vs. LDPC, tasa 1/2 vs 3/4) — ✅ cerrado
   (05/09/2026)**, ver §4.3: CCSDS K=7 base para los tres modos, tasa 3/4
   vía perforado del mismo código madre, LDPC explícitamente descartado.
   **Nuevo hallazgo, sigue abierto:** el costo real de decodificación
   Viterbi K=7 en el Cliente (Orange Pi 5, ARM64) **nunca se midió** — no
   hay hardware Orange Pi 5 en este entorno de desarrollo. La decisión de
   no adoptar LDPC se apoyó en la suposición de que Viterbi es lo bastante
   liviano para el nodo débil, pero esa suposición en sí no está
   verificada; si en algún momento se reconsidera LDPC (p. ej. si el
   margen de enlace se ajusta más y se necesita más ganancia de
   codificación), este es el primer benchmark pendiente — medir
   decode_ccsds_27_fb (o el equivalente Viterbi) en el hardware ARM64 real
   antes de comparar contra el costo de un decoder LDPC.
5. **ACPR/OIP3 real del PA no documentado** — el PA ya está comprado y su
   backoff está calibrado contra su P1dB real (`SPECS EQUIPOS/PA.md`, §5),
   pero esa hoja técnica no incluye ACPR ni OIP3 — la métrica más directa
   de riesgo regulatorio (spectral regrowth hacia canales TV vecinos) sigue
   sin confirmarse experimentalmente.
6. **LO compartido del AD9361 entre TX1/TX2 asumido, no confirmado** en
   los docs del proyecto (§3).
7. **Umbrales de hysteresis para bajar/subir de modulación** — no
   definidos; es una decisión de política de control, no de esta capa
   física en sí.
8. **Fragmentación (§2.4) — ✅ implementada (04/09/2026)**, ver detalle
   arriba. Sigue sin cerrar: el umbral de 18 símbolos es una elección
   razonable, no una medición de campo — ajustar cuando se mida el
   asentamiento real de guarda TDD (punto 1 de esta lista). No hay
   ARQ/retransmisión — solo FEC — si un fragmento se corrompe se descarta
   el PDU completo; evaluar si hace falta ARQ es una decisión aparte, no
   fue evaluada acá.
9. **Regulatorio:** la norma peruana exige un modelo de base de datos de
   canales autorizados (Art. 17-18) como mecanismo primario — el sensado
   CNN no es sustituto legal. No bloquea seguir construyendo/validando
   esta arquitectura técnica, pero es el hallazgo más grande pendiente
   para cualquier despliegue real fuera de laboratorio — ver
   `claudedocs/cumplimiento_normativo_tvws.md`.

---

## 9. Dónde está cada cosa (para no duplicar)

| Tipo de hecho | Vive en |
|---|---|
| Cifras de RF/link budget (EIRP, NF, margen, sensibilidad) | `LINK_BUDGET/` |
| Historial de decisiones y riesgos abiertos de transmisión | `claudedocs/riesgos_arquitectura_transmision.md` |
| Esta especificación ensamblada (framing TDD, canales, modulación, PA) | **este documento** |
| Arquitectura de las 6 capas de software del bloque cognitivo | `claudedocs/arquitectura_transmision_datos.md` |
| Estado del plan de pruebas de transmisión | `TRANSMISION/pruebas/README.md` |
| Modelo de IA / CNN de sensado | `IA/README.md` (fuera de alcance aquí) |
| Cumplimiento normativo TVWS Perú | `claudedocs/cumplimiento_normativo_tvws.md` |
| Requisitos y evaluación de PA/LNA comerciales | `claudedocs/requisitos_pa_lna.md` |
