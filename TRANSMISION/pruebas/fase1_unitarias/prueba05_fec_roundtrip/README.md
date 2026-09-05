# Prueba 5 — FEC round-trip

**Objetivo** (según el plan): `bits → codificado → bits`, con y sin
errores inyectados dentro del BER de diseño. Criterio: *"el decodificador
corrige hasta el límite esperado, no antes"*.

Requiere el venv `~/envs/SDR` (`gnuradio.fec`). No requiere `tun0` ni
`sudo` — corre standalone.

## Esquema FEC elegido (y por qué)

El FEC también es una **decisión abierta** en
`claudedocs/arquitectura_transmision_datos.md` (línea 259 de `README.md`:
"Tasa de código FEC 1/2 o 3/4 — convolucional o LDPC"). Para esta prueba
se usó el código convolucional estándar **CCSDS ("Voyager"), K=7, tasa
1/2** (`gnuradio.fec.encode_ccsds_27_bb` / `decode_ccsds_27_fb`), no un
esquema inventado:

1. Ya viene implementado dentro de GNU Radio — no hay que armar tablas de
   trellis a mano ni depender de la API genérica `fec.cc_encoder`/
   `cc_decoder` (más flexible pero más fácil de usar mal; ver nota abajo).
2. Es exactamente la combinación **"BPSK, tasa FEC 1/2"** que `README.md`
   §5.3 marca como el objetivo conservador ya validado del proyecto
   (~1.9 Mbps DL/UL, línea 285) — no una combinación elegida al azar para
   la prueba.

Sigue pendiente el equivalente para LDPC / tasa 3/4 cuando esa parte de la
arquitectura se cierre — esta prueba solo cubre la ruta BPSK R=1/2.

### Nota de implementación (documentada por el propio bloque, no inventada aquí)

`decode_ccsds_27_fb` está pensado para *streaming continuo*, no paquetes:
tiene un delay fijo de **4 bytes (32 bits)** de "flush" antes de que el
dato real empiece a salir, y "no hay forma de vaciarlo" al final. Por eso
`ccsds_fec.codificar()` agrega 4 bytes de padding al final del payload
antes de codificar, y `decodificar()` descarta los primeros 4 bytes de
salida (el delay) para recuperar el payload alineado.

## Archivos

- **`ccsds_fec.py`** — `codificar()`, `decodificar()`, `inyectar_errores()`
  (voltea una fracción de los símbolos codificados, simulando errores de
  canal), `ber_bits()`.
- **`test_fec_roundtrip.py`** — 4 casos + un barrido de caracterización.

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

## Estado: ✅ Aprobada

Round-trip correcto, y el decodificador corrige dentro de un margen medido
empíricamente y falla (visiblemente, sin colar errores) fuera de él. Sigue
la Prueba 6 (MOD/DEMOD round-trip: bits → símbolos → bits, por separado
para BPSK/QPSK/16-QAM).
