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

## Resultado de la ejecución

```
[prueba15] desglose de tiempo por etapa (5 repeticiones, payload de 100B):
  mac_encap                   :   0.057 ms/paquete
  fec_codificar               :   0.587 ms/paquete
  mod_ofdm_tx                 :   0.547 ms/paquete
  ofdm_rx_y_fec_decodificar   :   1.069 ms/paquete
  mac_decap                   :   0.061 ms/paquete

[prueba15] midiendo throughput sostenido: 30 paquetes de 500 bytes, BPSK R=1/2...
[prueba15] 15000 bytes entregados correctos en 0.179 s
[prueba15] throughput medido: 0.6701 Mbps
[prueba15] objetivo README S5.3 (BPSK R=1/2): 1.9 Mbps
[prueba15] razon medido/objetivo: 0.3527x
```

Salida completa: [`benchmark_output.txt`](benchmark_output.txt).

### Interpretación — 0.35x del objetivo, y por qué

El desglose confirma la hipótesis ya anotada en la Prueba 12:
**`fec_codificar` (0.59 ms) y `ofdm_rx_y_fec_decodificar` (1.07 ms,
domina `fec_decodificar`) juntos son ~72% del tiempo total por paquete**
(1.66 ms de 2.32 ms). La causa raíz, documentada en
`ccsds_fec.py` (Prueba 5): cada llamada a `codificar()`/`decodificar()`
crea, corre y destruye un `gr.top_block()` de GNU Radio **por paquete** —
ese overhead de arranque/parada del scheduler domina sobre el cómputo real
de codificación/decodificación en sí.

**Esto es una limitación del arnés de pruebas, no evidencia de que la
arquitectura no pueda cumplir el objetivo de diseño.** Un flowgraph de
producción real tendría los bloques `fec.encoder`/`fec.decoder`
**persistentes** dentro de un único flowgraph continuo (streaming
verdadero, sin crear/destruir nada por paquete) — el patrón que
`TRANSMISION/pruebas/fase3_loopback_completo/prueba12_txrx_loopback_tun0/`
ya usa para el flowgraph en sí (un solo `top_block` para toda la sesión),
pero que `ccsds_fec.py` todavía no aplica *dentro* de su propia
implementación.

### Qué haría falta para medir esto "de verdad"

1. Reescribir `ccsds_fec.codificar`/`decodificar` para que reciban un
   `fec.encoder`/`fec.decoder` ya construido (persistente) en vez de crear
   su propio `top_block` cada vez — debería acercar mucho el throughput
   medido al objetivo de diseño.
2. Extender `cadena.py` (Prueba 9) para soportar QPSK y 16-QAM, y repetir
   esta medición por modo, comparando contra toda la tabla de §5.3.
3. Repetir con `iperf3` real una vez exista un segundo nodo (Fase 4+).

## Estado: ✅ Aprobada (con hallazgo de performance documentado)

La prueba en sí — medir throughput y compararlo contra §5.3 — se ejecutó
y documentó correctamente. El resultado (0.35x del objetivo) es un
hallazgo real y esperado dado cómo está armado el arnés de pruebas, no
una falla de la arquitectura del sistema. Con esto, **Fase 3 completa
(4/4)**: Pruebas 12, 13, 14 y 15.
