# Prueba 15 — Throughput sostenido por modo de modulación/FEC

**Objetivo** (según el plan): `iperf3` sostenido por cada modo de
modulación/FEC → throughput medido vs. tabla de `README.md` §5.3 (ej.
BPSK 1/2 ≈1.9 Mbps). Última prueba de la Fase 3.

No requiere `tun0` ni `sudo`. Requiere el venv `~/envs/SDR`.

## Desviación honesta respecto al plan — por qué no es `iperf3` literal

`iperf3` necesita un **segundo nodo real** escuchando en el otro extremo
de `tun0` (un Cliente de verdad, con su propia IP y su propio proceso
`iperf3 -s`). Este banco de pruebas es un solo proceso en una sola
máquina (loopback digital, Fase 3 del plan — "mismo proceso, sin SDR"), no
hay un segundo nodo hasta la Fase 4 (hardware real). Levantar `iperf3`
contra un peer que no existe no mide nada real.

En su lugar, esta prueba mide el throughput **directamente sobre la
cadena TX+RX completa** (`loopback_block.procesar_payload`, la misma
función que la Prueba 12 conecta a `tun0`) — es la misma cadena de cómputo
por la que pasaría el tráfico si `iperf3` estuviera corriendo a través de
`tun0`, solo que sin el overhead adicional de UDP/TCP/kernel de por
medio. El número es comparable al objetivo de §5.3, no idéntico.

## Alcance — solo BPSK R=1/2

`cadena.py`/`loopback_block.py` (Pruebas 9 y 12) solo tienen cableada la
ruta **BPSK** — `NotImplementedError` si se pide QPSK o 16-QAM. Medir esos
modos requiere primero extender esos módulos para soportarlos (no es
trabajo de esta prueba, que solo mide lo que ya existe). El objetivo de
comparación es entonces únicamente **BPSK R=1/2 ≈1.9 Mbps**
(`README.md` línea 279).

## Qué hace `benchmark_throughput.py`

1. **Desglose de tiempo por etapa**: mide por separado cuánto tarda cada
   paso (`mac_encap`, `fec_codificar`, `mod_ofdm_tx`,
   `ofdm_rx_y_fec_decodificar`, `mac_decap`) sobre un payload pequeño, para
   diagnosticar dónde se va el tiempo — no solo reportar un número final.
2. **Throughput sostenido**: procesa `--n-paquetes` payloads de
   `--tam-payload` bytes de punta a punta (TX completo → RX completo, sin
   canal), mide el tiempo total de pared, y calcula Mbps = bits
   entregados correctos / tiempo total.

## Resultado de la ejecución (post-fix del arnés `ccsds_fec.py`, 05/09/2026)

```
[prueba15] desglose de tiempo por etapa (5 repeticiones, payload de 100B):
  mac_encap                   :   0.091 ms/paquete
  fec_codificar               :   0.589 ms/paquete
  mod_ofdm_tx                 :   0.938 ms/paquete
  ofdm_rx_y_fec_decodificar   :   1.218 ms/paquete
  mac_decap                   :   0.107 ms/paquete

[prueba15] midiendo throughput sostenido: 30 paquetes de 500 bytes, BPSK R=1/2...
[prueba15] 15000 bytes entregados correctos en 0.179 s
[prueba15] throughput medido: 0.6700 Mbps
[prueba15] objetivo README S5.3 (BPSK R=1/2): 1.9 Mbps
[prueba15] razon medido/objetivo: 0.3527x
```

Salida completa: [`benchmark_output.txt`](benchmark_output.txt).

### El arnés de `ccsds_fec.py` se arregló — el throughput medido casi no cambió, y eso también es un hallazgo real

`ccsds_fec.py` (Prueba 5) fue reescrito (04-05/09/2026) para usar un
`gr.top_block()` **persistente y de inicialización diferida** por
dirección (uno para encode, uno para decode) en vez de crear/correr/destruir
uno por llamada — exactamente el fix que esta misma sección pedía
anteriormente. Medido de forma aislada (fuera de este benchmark, ver
`TRANSMISION/pruebas/fase1_unitarias/prueba05_fec_roundtrip/README.md`),
el fix sí reduce el costo por llamada de forma medible:

| Etapa (payload 100B) | `top_block` por llamada (antes) | `top_block` persistente (ahora) |
|---|---|---|
| `codificar()` | ~0.59 ms | ~0.28 ms |
| `decodificar()` | ~1.07 ms | ~0.48 ms |

Pero **el throughput sostenido de este benchmark (0.67 Mbps, razón 0.35x)
prácticamente no cambió** respecto a la medición anterior (0.6701 Mbps,
también 0.3527x). Dos razones, confirmadas con mediciones adicionales:

1. **`tb.run()` en sí mismo sigue teniendo overhead de arranque/parada de
   scheduler no trivial incluso con topología persistente** — medido de
   forma aislada (fuera de este benchmark): ~0.25 ms por llamada a
   `tb.run()` sobre un `top_block` de 3 bloques ya conectado, sin
   reconstruir nada. GNU Radio no expone una API de "alimentar un bloque
   ya corriendo y leer su salida sin parar el scheduler" tan simple como
   la que este arnés necesitaría — `tb.run()` arranca y detiene los hilos
   del scheduler en cada invocación, se reutilice o no la topología.
2. **A los tamaños de payload que mide este benchmark (500B), el desglose
   por etapa cambia de forma reveladora**: con el arnés viejo, FEC
   dominaba (~72% del tiempo). Con el arnés nuevo, medido directamente
   sobre un payload de 500B (no los 100B del desglose de arriba,
   reproducido igual que antes por continuidad con la Prueba 12):
   `fec_codificar` baja a ~0.44 ms, pero **`mod_ofdm_tx` (~2.4 ms) y la
   FFT+FEC-decode combinados de `ofdm_rx_y_fec_decodificar` (~2.7 ms,
   de los cuales `fec_decodificar` solo son ~1.8 ms y la FFT ~0.9 ms)
   ahora dominan el total** (~6.2 ms/paquete). El cuello de botella se
   movió de "overhead de arranque de scheduler por paquete en FEC" a
   "cómputo real de modulación/OFDM/FEC proporcional al tamaño del
   payload" — la fracción de tiempo que antes era puro overhead
   artificial del arnés de pruebas ahora es trabajo real, pero la cadena
   completa (MOD+OFDM+FEC, todo en Python puro sin vectorización numpy
   por símbolo) sigue sin acercarse al objetivo de diseño.

**Conclusión honesta: el fix cierra la causa raíz que Prueba 15 había
identificado (el overhead de arranque de `top_block` por paquete en FEC),
pero no cierra la brecha al objetivo de 1.9 Mbps**, porque a estos tamaños
de payload esa causa nunca fue el único cuello de botella — el resto de la
cadena (`ofdm_symbol.py`/`constelaciones.py`, implementados en Python puro,
símbolo por símbolo, sin vectorización) tiene su propio costo por paquete
que ahora queda expuesto. Esto **no es evidencia de que la arquitectura no
pueda cumplir el objetivo** (un flowgraph de producción real con streaming
de GNU Radio de punta a punta, no una cadena Python con conversiones
list↔GNU Radio por etapa, es un problema de implementación distinto), pero
sí corrige la narrativa anterior de que "arreglar el `top_block` de FEC
alcanza para acercar el número al objetivo" — no alcanza, por sí solo.

### Qué haría falta para medir esto "de verdad"

1. ~~Reescribir `ccsds_fec.codificar`/`decodificar` para que usen un
   `top_block` persistente~~ — **hecho (04-05/09/2026)**, ver arriba. No
   cerró la brecha al objetivo por sí solo (ver hallazgo arriba).
2. Perfilar y, si hace falta, vectorizar `ofdm_symbol.py`/
   `constelaciones.py` (actualmente Python símbolo-por-símbolo) — ahora es
   el cuello de botella más grande medido, no el FEC.
3. Extender `cadena.py` (Prueba 9) para soportar QPSK y 16-QAM, y repetir
   esta medición por modo, comparando contra toda la tabla de §7.1 de
   `claudedocs/arquitectura_enlace_datos.md`.
4. Repetir con `iperf3` real una vez exista un segundo nodo (Fase 4+).

## Estado: ✅ Aprobada (con hallazgo de performance actualizado)

La prueba en sí — medir throughput y compararlo contra §5.3 — se ejecutó
y documentó correctamente, ahora con el arnés de FEC corregido. El
resultado (todavía ~0.35x del objetivo, prácticamente sin cambio numérico
pese al fix) es un hallazgo real: la causa raíz que se sospechaba
(overhead de `top_block` por paquete en FEC) era real y se corrigió, pero
no era el único cuello de botella a estos tamaños de payload — no una
falla de la arquitectura del sistema, sino de dónde está el costo real en
esta implementación Python de referencia. Con esto, **Fase 3 sigue
completa (4/4)**: Pruebas 12, 13, 14 y 15, todas ✅.
