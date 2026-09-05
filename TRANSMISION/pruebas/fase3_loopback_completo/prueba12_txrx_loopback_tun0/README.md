# Prueba 12 — TX→RX conectados directo (vector, sin canal), tráfico real por `tun0`

**Objetivo** (según el plan): pipeline completo entrega tráfico íntegro;
primera medición de throughput/latencia vs `README.md` §5.3. Primera
prueba de la **Fase 3** (loopback digital completo, mismo proceso, sin
SDR) — ensambla en un único flowgraph lo que las Pruebas 8-11 probaron por
partes.

Requiere `tun0` viva ([Prueba 1](../../fase1_unitarias/prueba01_tun0_basico/))
y el venv `~/envs/SDR`. No requiere `sudo`.

## Qué se ensambla

```
tun0 --tuntap_pdu--> TxRxLoopbackBlock (TX completo + RX completo, sin canal) --> tuntap_pdu --> tun0
```

`TxRxLoopbackBlock` (`loopback_block.py`) es un bloque de mensajes que, por
cada PDU que recibe, corre `procesar_payload()`: la cadena TX completa
(MAC → FEC → MOD/BPSK → OFDM, reusando Pruebas 4/5/6/10) seguida directo
de la cadena RX completa (OFDM → FEC → MOD → MAC, Prueba 11) — sin ningún
canal ni SDR entre ambas, el "cable" es literalmente una lista de Python.
Si el CRC del MAC no valida, el bloque **descarta** el paquete y no
publica nada (mismo contrato que tendría un receptor real).

## Cómo correrlo

```bash
cd TRANSMISION/pruebas/fase3_loopback_completo/prueba12_txrx_loopback_tun0
~/envs/SDR/bin/python flowgraph_prueba12.py --dev tun0 --duracion 15 --salida payloads_entregados.txt
# en otra terminal, esperar ~5-6s (los imports son mas pesados que en
# Pruebas 2/3 -- constelaciones, FEC y OFDM) y luego:
ping -I tun0 -c 4 10.99.0.2
```

### Por qué `ping` siempre va a mostrar 100% packet loss aquí (y no es un fallo)

El paquete recuperado se reinyecta a `tun0` con el mismo destino
`10.99.0.2` (no la IP local `10.99.0.1`). Como esta máquina no tiene
`ip_forward` habilitado, el kernel no reenvía ese paquete a ningún lado
(lo descarta silenciosamente) — a diferencia de la Prueba 3, donde el
destino sintético *era* la IP local y el kernel sí generaba una respuesta
ICMP real. Por eso la verificación de integridad aquí es **interna**
(el CRC del MAC) y **por archivo** (`--salida`), no por la salida de
`ping`.

### Nota de timing

Con `sleep 2` (el margen que bastaba en las Pruebas 2/3) el primer
intento **falló silenciosamente**: `tuntap.msg_connect` nunca disparó
porque los imports de este script (constelaciones, FEC, OFDM — bastante
más pesados que un `tuntap_pdu` solo) tardan más en cargar antes de que
`tb.start()` abra el fd de `tun0`. Con `sleep 6` funcionó consistente.
Esto es una particularidad del *harness de prueba* (arrancar el proceso
Python + importar todo GNU Radio), no del diseño del sistema real (que
correría persistente, no se reinicia por cada prueba).

## Resultado de la ejecución

```
[prueba12] resumen: {'n_entregados': 4, 'n_descartados': 0, 'n_total': 4, 'bytes_entregados': 336,
                      'latencia_prom_ms': 5.394038002123125, 'latencia_max_ms': 7.880582008510828}
[prueba12] throughput aprox (solo computo, sin contar espera entre paquetes): 0.125 Mbps
[prueba12] 4 payloads volcados a payloads_entregados.txt
```

Los 4 payloads volcados son los 4 ICMP echo request reales del `ping -c 4`
(verificado por inspección: `45 00 00 54` = IPv4/84 bytes, proto `01`=ICMP,
`0a 63 00 01`→`0a 63 00 02` = `10.99.0.1`→`10.99.0.2`, secuencias ICMP
0001-0004 consecutivas) — no datos sintéticos.

Salida completa: [`flowgraph_output.txt`](flowgraph_output.txt).
Payloads entregados: [`payloads_entregados.txt`](payloads_entregados.txt).

### Sobre el throughput medido (0.125 Mbps) vs. la tabla de §5.3 (~1.9 Mbps BPSK R=1/2)

**Este número no es representativo del sistema real** — es muchísimo más
bajo por una razón de implementación conocida, no de arquitectura:
`ccsds_fec.codificar()`/`decodificar()` (Prueba 5) crean, corren y
destruyen un `gr.top_block()` de GNU Radio **por cada paquete**, y ese
overhead de arranque domina la latencia medida (~5.4 ms/paquete, la
mayor parte en el setup/teardown del top_block, no en el cómputo real).
Un flowgraph de producción tendría los bloques FEC persistentes dentro de
un único flowgraph continuo (streaming real), sin ese overhead por
paquete. La Prueba 15 mide esto con más detalle y documenta la brecha
explícitamente — no se debe interpretar 0.125 Mbps como "el sistema no
alcanza el objetivo de diseño", sino como "el arnés de pruebas actual no
está optimizado para throughput, solo para corrección".

## Estado: ✅ Aprobada

Primera integración de la Fase 3: la cadena completa de software corre
como un único flowgraph persistente, con tráfico real de `tun0`, sin
perder ni corromper un solo paquete. Sigue la Prueba 13 (mismo loopback,
con un canal sintético de errores de bit).
