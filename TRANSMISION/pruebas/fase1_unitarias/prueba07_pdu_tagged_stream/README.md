# Prueba 7 — PDU↔Tagged Stream (ambos sentidos)

**Objetivo** (según el plan): paquete de longitud fija conocida →
verificar tags y reconstrucción exacta. Criterio: *"la frontera
mensajes↔streaming no corrompe ni trunca"*. Última prueba de la Fase 1.

Requiere el venv `~/envs/SDR` (`gnuradio.pdu`). No requiere `tun0` ni
`sudo`.

## Qué se prueba y por qué

Es la frontera descrita en `claudedocs/arquitectura_transmision_datos.md`
(línea 84-85): la salida de MAC/FEC/MOD (PDUs de símbolos I/Q) se convierte
en un stream `gr_complex` "tageado" con longitud antes de entrar al
Carrier Allocator/IFFT (streaming puro). En recepción ocurre lo inverso
("Tagged Stream to PDU", línea 88). Se usan `pdu_to_tagged_stream` y
`tagged_stream_to_pdu` de `gnuradio.pdu` (no `gnuradio.blocks`, que los
tiene deprecados — mismo patrón que `network.tuntap_pdu` en las Pruebas
2-3). Tipo de item: `gr_complex`, consistente con la Prueba 6.

## Qué hace `pdu_stream.py`

- **`pdu_a_stream_repetido`**: sentido TX. Reenvía el mismo PDU cada
  `periodo_ms` durante `duracion_s` (varios paquetes seguidos, no solo
  uno) y captura el stream de salida completo + sus tags de
  `pdu_to_tagged_stream`.
- **`stream_a_pdus`**: sentido RX. Dado un stream concatenado y las
  longitudes de cada paquete consecutivo, arma los tags a los offsets
  correctos y devuelve la lista de PDUs que `tagged_stream_to_pdu`
  reconstruye.
- **`round_trip_completo`**: ambos bloques encadenados en un mismo
  flowgraph (PDU → stream → PDU), el caso más parecido al uso real.

### Nota sobre `message_strobe` y el tiempo de espera

En un intento inicial, con `periodo_ms=5000` y una espera de solo 0.3-1s,
el `vector_sink_c` no capturó nada — `message_strobe` no dispara
inmediatamente al arrancar el flowgraph si el período es largo respecto a
la ventana de captura. Se resolvió usando un período corto (150 ms) y una
ventana de ~1.2 s, lo que además tiene la ventaja de disparar el PDU
**varias veces seguidas**, permitiendo validar de paso que los límites
entre paquetes consecutivos (offsets de los tags) no se pisan ni se
corrompen.

## Casos cubiertos por `test_pdu_tagged_stream.py`

1. **PDU→stream**, con el mismo paquete disparado repetidas veces: cada
   tag `packet_len` aparece en el offset correcto y el bloque de datos
   entre un tag y el siguiente coincide exactamente con el original.
2. **stream→PDU**, un solo paquete de longitud conocida: reconstrucción
   exacta.
3. **stream→PDU con 3 paquetes de longitudes *distintas* concatenados**
   en el mismo stream — el caso que más estresa el manejo de límites
   (offsets no uniformes).
4. **Round-trip completo PDU→stream→PDU**, ambos bloques encadenados en
   un solo flowgraph, disparado varias veces.

## Resultado de la ejecución

```
[OK] PDU->stream: 7 paquetes consecutivos, tags y datos correctos en cada limite
[OK] stream->PDU: un paquete de longitud conocida reconstruido exacto
[OK] stream->PDU: 3 paquetes de longitud variable reconstruidos exactos, sin mezclar limites
[OK] round-trip completo PDU->stream->PDU: 7 paquetes, todos exactos

4/4 casos aprobados
```

Salida completa: [`test_output.txt`](test_output.txt).

## Estado: ✅ Aprobada

**Fase 1 completa: 7/7 pruebas aprobadas.** Las tres fronteras de fallo
identificadas al inicio del plan quedan validadas de forma aislada:
kernel↔GNU Radio (Pruebas 1-3), PDU↔streaming (Pruebas 4-7 cubren MAC, FEC,
MOD/DEMOD y la frontera de tags en sí). Sigue la Fase 2 (integración por
pares, Pruebas 8-11 — por ejemplo `tun0 → tuntap_pdu → MAC → dump` con
tráfico real de `ping`), que empieza a encadenar estas piezas ya
verificadas individualmente en vez de probarlas sueltas.
