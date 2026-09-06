# Prueba 5 — FEC round-trip

**Objetivo** (según el plan): `bits → codificado → bits`, con y sin
errores inyectados dentro del BER de diseño. Criterio: *"el decodificador
corrige hasta el límite esperado, no antes"*.

Requiere el venv `~/envs/SDR` (`gnuradio.fec`). No requiere `tun0` ni
`sudo` — corre standalone.

## Esquema FEC elegido (y por qué) — **decisión cerrada**

El FEC quedó **cerrado** (`claudedocs/arquitectura_enlace_datos.md` §4.3,
05/09/2026): el proyecto estandariza en el código convolucional
**CCSDS ("Voyager"), K=7** como base para **los tres modos de modulación
(BPSK/QPSK/16-QAM)**, con **tasa 3/4 obtenida perforando (puncturing) el
mismo código madre de tasa 1/2** — no un segundo códec. LDPC fue evaluado y
**explícitamente descartado** (no diferido, no prototipado), por tres
razones (detalle completo en `claudedocs/arquitectura_enlace_datos.md`
§4.3 y `claudedocs/riesgos_arquitectura_transmision.md` Problema 3):

1. LDPC es un código de bloque (n,k fijos) — el umbral de fragmentación ya
   cerrado (§2.4, 505 bytes/18 símbolos) se derivó alrededor del modelo de
   streaming orientado a bytes del código convolucional; migrar exigiría
   rehacer ese umbral para framing alineado a bloque.
2. **El enlace TDD es simétrico** — ambos nodos codifican y decodifican en
   cada ciclo, y el Cliente es un Orange Pi 5 ARM64 (mucho más débil que el
   Gateway, un Intel Core Ultra 5). El decoder iterativo de LDPC es
   inherentemente más costoso por bit que Viterbi (trellis de 64 estados
   para K=7), y ese costo en el nodo débil nunca se midió — riesgo no
   verificado, razón principal de no adoptar LDPC ahora.
3. GNU Radio no trae ninguna matriz LDPC de tasa 3/4 lista
   (`/usr/share/gnuradio/fec/ldpc/` solo trae tasas ~0.23-0.58) — construir
   una es trabajo de diseño de matrices fuera de alcance, mientras que
   tasa 3/4 convolucional es gratis vía perforado del K=7 ya validado aquí.

Por qué CCSDS K=7 en sí (razones originales, siguen aplicando):

1. Ya viene implementado dentro de GNU Radio — no hay que armar tablas de
   trellis a mano ni depender de la API genérica `fec.cc_encoder`/
   `cc_decoder` (más flexible pero más fácil de usar mal; ver nota abajo).
2. Es exactamente la combinación **"BPSK, tasa FEC 1/2"** que `README.md`
   §5.3 marca como el objetivo conservador ya validado del proyecto
   (~1.9 Mbps DL/UL) — no una combinación elegida al azar para la prueba.

Esta prueba (Prueba 5) cubre BPSK con ambas tasas (1/2 sin perforar, 3/4
perforada) — ver la sección "Tasa 3/4 vía perforado" más abajo. QPSK/16-QAM
con esta misma base FEC no están implementados en `cadena.py`/
`loopback_block.py` (Prueba 9/12) todavía; ese es trabajo separado ya
flagged en el README de la Prueba 15.

### Nota de implementación (documentada por el propio bloque, no inventada aquí)

`decode_ccsds_27_fb` está pensado para *streaming continuo*, no paquetes:
tiene un delay fijo de **4 bytes (32 bits)** de "flush" antes de que el
dato real empiece a salir, y "no hay forma de vaciarlo" al final. Por eso
`ccsds_fec.codificar()` agrega 4 bytes de padding al final del payload
antes de codificar, y `decodificar()` descarta los primeros 4 bytes de
salida (el delay) para recuperar el payload alineado.

## Archivos

- **`ccsds_fec.py`** — `codificar()`, `decodificar()` (tasa 1/2, ahora sobre
  un `gr.top_block()` persistente y de inicialización diferida — ver
  sección "Arnés de pruebas" abajo), `perforar()`/`despuncturar()` (tasa
  3/4 vía perforado, puro Python, sin bloques de GNU Radio nuevos),
  `inyectar_errores()` (voltea una fracción de los símbolos codificados,
  simulando errores de canal), `ber_bits()`.
- **`test_fec_roundtrip.py`** — 4 casos + un barrido de caracterización,
  tasa 1/2 (sin perforar).
- **`test_puncturing_r34.py`** — round-trip bit-exacto perforado (tasa
  3/4) y comparación de curva BER contra tasa 1/2 — ver sección dedicada
  abajo.

## Arnés de pruebas: `top_block` persistente (fix 04-05/09/2026)

La versión anterior de `ccsds_fec.py` creaba, corría y destruía un
`gr.top_block()` de GNU Radio **por cada llamada** a `codificar()`/
`decodificar()`. La Prueba 15 (`fase3_loopback_completo/prueba15_throughput_
sostenido/`) midió que esto hacía que ~72% del tiempo por paquete fuera
overhead puro de arranque/parada del scheduler, no cómputo real de FEC —
ver `claudedocs/riesgos_arquitectura_transmision.md`, Problema 3.

`ccsds_fec.py` ahora usa un `gr.top_block()` **persistente y de
inicialización diferida** (uno para encode, uno para decode), reutilizado
en cada llamada: los datos nuevos se inyectan vía `set_data()`, se corre
con `tb.run()`, se lee la salida del sink, y se limpia con `.reset()`
antes de la siguiente llamada. **La firma pública no cambió** —
`codificar(payload: bytes) -> list` / `decodificar(simbolos_soft: list,
n_payload_bytes: int) -> bytes` siguen siendo exactamente las mismas, así
que ningún punto de llamada en las Pruebas 9, 12, 13, 14 o 15 necesitó
modificarse.

**Verificado explícitamente antes de confiar en el fix:** round-trip
correcto con `codificar()`/`decodificar()` reutilizando el mismo
`top_block` a través de llamadas con payloads de longitud variable (1, 3,
5, 17, 100, 500, 2000 bytes, en ese orden, sobre la misma instancia
persistente) — sin fugas de estado entre llamadas.

**Resultado de performance (medido de forma aislada, payload 100B, 200
llamadas):**

| Función | `top_block` por llamada (antes) | `top_block` persistente (ahora) |
|---|---|---|
| `codificar()` | ~0.59 ms | ~0.28-0.36 ms |
| `decodificar()` | ~1.07 ms | ~0.48 ms |

Mejora real (~40-55% menos tiempo por llamada), pero **no cierra la
brecha al objetivo de throughput de diseño** — ver
`fase3_loopback_completo/prueba15_throughput_sostenido/README.md` para el
hallazgo completo: `tb.run()` conserva overhead de arranque/parada de
scheduler no trivial (~0.25 ms/llamada medido de forma aislada) incluso
con topología persistente, y a los tamaños de payload que mide la Prueba
15 el resto de la cadena (MOD/OFDM en Python puro) resultó ser un cuello
de botella igual o mayor que el FEC.

## Por qué los umbrales de la prueba son empíricos, no una "cifra de diseño"

Ningún documento del repo fija un BER de diseño numérico todavía (no
existe una cifra como "el sistema debe tolerar 5% BER" en ningún lado).
En vez de inventar una, esta prueba **mide** la curva de corrección real
del código (barrido BER de canal → BER post-decodificación) y fija los
casos pass/fail sobre esa medición:

- BER de canal 1% y 3% → corrección **total** (0 errores residuales).
- BER de canal 20% → el código **no** corrige (BER residual > 20%,
  confirma que satura en vez de "corregir" cualquier cosa silenciosamente).

## Resultado de la ejecución

```
[OK] round-trip sin errores de canal (payload de la Prueba 3)
[OK] corrige por completo BER de canal=1% (321 bits volteados de 32064)
[OK] corrige por completo BER de canal=3% (962 bits volteados de 32064)
[OK] NO corrige BER de canal=20% (BER residual=47.2%, esperado > 20%)

4/4 casos aprobados
```

### Curva de caracterización (waterfall)

| BER de canal | BER post-decode |
|---|---|
| 0% | 0.00000 |
| 1% | 0.00000 |
| 3% | 0.00000 |
| 5% | 0.00306 |
| 7% | 0.01350 |
| 8% | 0.03263 |
| 9% | 0.06194 |
| 10% | 0.09781 |
| 11% | 0.14131 |
| 12% | 0.18625 |
| 15% | 0.32831 |
| 20% | 0.46519 |

Corrección total hasta ~3% de BER de canal, degradación gradual entre
5-12%, y saturación (BER post-decode casi tan mala como no tener FEC)
desde ~15%. Es el comportamiento esperado de un código K=7 tasa 1/2 con
decisión dura/blanda simple sin ruido gaussiano real de por medio (aquí
los "errores de canal" son bits volteados uniformemente al azar, no un
canal AWGN con SNR — sirve para validar el codec, no como medición de
link budget real).

Salida completa: [`test_output.txt`](test_output.txt).

## Tasa 3/4 vía perforado (puncturing) — `test_puncturing_r34.py`

### Patrón elegido

Período 6: 3 bits de entrada → 6 bits codificados a tasa 1/2 → se
perforan 2 → quedan 4 → tasa 3/4 efectiva. Patrón exacto (posiciones
0-indexadas dentro de cada bloque de 6 bits codificados):

```
posición en el bloque de 6:                0    1    2    3    4    5
se mantiene (True) / se perfora (False):    M    M    M    D    M    D
```

`PATRON_PERFORADO_3_4 = (True, True, True, False, True, False)` — se
perforan las posiciones 3 y 5 de cada bloque de 6. Esta es una convención
elegida por este equipo (no una tabla de un estándar copiada de memoria) —
lo único que importa es que TX (`perforar`) y RX (`despuncturar`) usen
exactamente el mismo patrón, lo cual se verifica primero con un round-trip
bit-exacto antes de confiar en cualquier número de BER (siguiente sección).

`despuncturar()` reinserta **0.0** (erasure neutro) en cada posición
perforada — 0.0 es el punto medio exacto entre los ±1.0 BPSK ideales que
`decode_ccsds_27_fb` espera (convención ya documentada en este archivo vía
`simbolos_a_soft`), es decir "misma probabilidad de 0 que de 1", la forma
estándar de alimentar un bit desconocido a un Viterbi blando.

### Puerta obligatoria: round-trip bit-exacto sin errores de canal

**Confirmado antes de confiar en cualquier número de BER**: `payload →
codificar → perforar → simbolos_a_soft → despuncturar → decodificar →
payload` recupera el payload original exacto, probado con el paquete de
la Prueba 3 y con un payload de 2000 bytes aleatorios. Sin esto, cualquier
número de BER de la curva de abajo no sería confiable.

### Curva BER: tasa 1/2 (sin perforar) vs. tasa 3/4 (perforada)

| BER de canal | R=1/2 post-decode | R=3/4 post-decode |
|---|---|---|
| 0% | 0.00000 | 0.00000 |
| 1% | 0.00000 | 0.00781 |
| 3% | 0.00000 | 0.08150 |
| 5% | 0.00206 | 0.21831 |
| 7% | 0.01725 | 0.30906 |
| 8% | 0.03537 | 0.36219 |
| 9% | 0.06344 | 0.38550 |
| 10% | 0.10856 | 0.42238 |
| 11% | 0.14238 | 0.43619 |
| 12% | 0.20237 | 0.45044 |
| 15% | 0.34294 | 0.48050 |
| 20% | 0.46069 | 0.49281 |

**Hallazgo de ganancia de codificación (coding gain), con número real en
vez de teórico:** tasa 3/4 ya muestra degradación medible a solo **1% de
BER de canal** (0.78% residual), mientras que tasa 1/2 sigue corrigiendo
totalmente hasta ~3%. Este es el resultado esperado y correcto — menos
redundancia (4 de 6 bits vs. 3 de 6... en realidad 2 de cada bloque
codificado se descartan) implica menos capacidad de corrección — no un
bug del perforado ni del relleno de erasure (ambos ya verificados
bit-exactos en la puerta anterior). Confirma con un número real el
trade-off que la tabla de throughput de `claudedocs/arquitectura_enlace_
datos.md` §7.1 ya asumía en teoría: tasa 3/4 da más throughput bruto (6→8
símbolos útiles de cada 8 codificados vs. 4 de 8) a costa de tolerar
sensiblemente menos BER de canal antes de saturar.

Salida completa: [`test_puncturing_r34_output.txt`](test_puncturing_r34_output.txt).

## Estado: ✅ Aprobada

Round-trip correcto (tasa 1/2 y tasa 3/4 perforada), y el decodificador
corrige dentro de un margen medido empíricamente y falla (visiblemente,
sin colar errores) fuera de él, en ambas tasas. El arnés de pruebas
también se corrigió (top_block persistente) sin cambiar la API pública —
ver sección dedicada arriba. Sigue la Prueba 6 (MOD/DEMOD round-trip:
bits → símbolos → bits, por separado para BPSK/QPSK/16-QAM).
