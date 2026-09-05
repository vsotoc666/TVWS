# Prueba 9 — MAC → FEC → MOD → PDU-to-stream → dump a archivo

**Objetivo** (según el plan): los símbolos generados coinciden con lo
esperado por la modulación. Extiende la cadena de la
[Prueba 8](../prueba08_tun0_tuntap_mac/) un paso más allá de MAC.

No requiere `tun0` ni `sudo` — el payload es estático (el mismo paquete
UDP/IP de las Pruebas 3/4/5), no viene de tráfico real (eso ya lo cubrió la
Prueba 8).

## Qué se encadena

```
payload IP → mac_frame.encapsular() → ccsds_fec.codificar() → constelaciones.modular()
    → PDU de simbolos I/Q → pdu.pdu_to_tagged_stream → dump
```

- **`cadena.py`** (nuevo): `payload_a_simbolos()` importa y encadena, sin
  reimplementar nada, los tres módulos ya validados en Fase 1:
  - `mac_frame.encapsular()` — [Prueba 4](../../fase1_unitarias/prueba04_mac_encap_decap/)
  - `ccsds_fec.codificar()` — [Prueba 5](../../fase1_unitarias/prueba05_fec_roundtrip/)
  - `constelaciones.modular()` — [Prueba 6](../../fase1_unitarias/prueba06_mod_demod_roundtrip/)
- **Esquema fijo: BPSK** — la misma combinación FEC+modulación validada en
  la Prueba 5 (CCSDS K=7 R=1/2 + BPSK, el objetivo conservador de
  `README.md` §5.3). Con BPSK, `bits_per_symbol=1`, así que cada bit que
  sale del FEC es directamente un símbolo — no hace falta agrupar bits.
- **`pdu.pdu_to_tagged_stream`** — el mismo bloque de la
  [Prueba 7](../../fase1_unitarias/prueba07_pdu_tagged_stream/), sin
  modificar, cruzando la frontera mensajes→streaming con los símbolos ya
  modulados.

## Cómo correrlo

```bash
cd TRANSMISION/pruebas/fase2_integracion_por_pares/prueba09_mac_fec_mod_stream
~/envs/SDR/bin/python flowgraph_prueba09.py --salida simbolos_stream.txt
~/envs/SDR/bin/python verificar_dump.py simbolos_stream.txt --seq-num 5 --next-ch 3
```

`flowgraph_prueba09.py` calcula los símbolos esperados con `cadena.py`,
los empaqueta en un PDU, y lo dispara varias veces por `message_strobe`
(igual patrón que la Prueba 7) hacia `pdu_to_tagged_stream`, volcando el
stream de salida + sus tags a un archivo de texto.

`verificar_dump.py` **recalcula los símbolos esperados de forma
independiente** (llamando a `cadena.payload_a_simbolos()` con los mismos
parámetros) y los compara, valor a valor, contra cada paquete capturado en
el dump — no solo la cantidad de símbolos, el contenido exacto.

## Resultado de la ejecución

```
[prueba09] frame MAC: 52 bytes
[prueba09] bits codificados (FEC): 896
[prueba09] simbolos modulados (BPSK): 896
[prueba09] stream de salida: 8064 items, 9 paquetes (tags)
[prueba09] volcado a simbolos_stream.txt
```

```
[OK] el dump tiene un numero entero de paquetes de 896 simbolos
[OK] al menos 1 paquete capturado (hubo 9)
[OK] cantidad de tags (9) coincide con cantidad de paquetes (9)
[OK] los 9 paquetes coinciden EXACTO (valor a valor) con los simbolos esperados

TODO CORRECTO
```

Trazabilidad completa de tamaños en la cadena: 47 bytes de payload IP → 52
bytes de frame MAC (+5 de header/CRC) → 896 bits codificados por el FEC
(`(52+4 padding) × 16`, rate 1/2) → 896 símbolos BPSK (1 bit = 1 símbolo).

Salida completa: [`verificacion_output.txt`](verificacion_output.txt).
Dump crudo (símbolos + tags): [`simbolos_stream.txt`](simbolos_stream.txt).

## Estado: ✅ Aprobada

Segunda integración de la Fase 2: confirma que encadenar MAC→FEC→MOD y
cruzar la frontera mensajes→streaming no introduce ninguna diferencia
entre "lo que se calculó" y "lo que salió por el stream". Sigue la Prueba
10 (TX completo hasta antes del SDR, incluye IFFT+CP) — la primera que
entra a la parte puramente streaming de la cadena (Carrier Allocator, no
solo conversión de formato).
