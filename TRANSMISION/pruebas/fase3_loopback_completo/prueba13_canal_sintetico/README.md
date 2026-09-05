# Prueba 13 — Igual que la Prueba 12 con canal sintético de errores de bit

**Objetivo** (según el plan): el FEC corrige hasta el BER de diseño; el
CRC del MAC descarta lo que no corrige, sin colar paquetes corruptos a
`tun0`.

No requiere `tun0` ni `sudo` (usa PDUs sintéticas para tener control total
y reproducible del BER de canal, mismo espíritu que la Prueba 5). Requiere
el venv `~/envs/SDR`.

## Qué se prueba

`canal_sintetico.py` es la misma cadena de la Prueba 12
(`loopback_block.procesar_payload`), pero le inserta un paso extra: **entre
el FEC y la modulación**, voltea una fracción `ber_canal` de los bits
codificados con `ccsds_fec.inyectar_errores()` — la misma función que la
Prueba 5 ya usó para caracterizar la curva de corrección de este FEC. Para
BPSK cada bit codificado se modula 1:1 a un símbolo (±1), así que voltear
el bit antes de modular es matemáticamente equivalente a que el canal
corrompa el símbolo recibido — no es un mecanismo nuevo, es el mismo de la
Prueba 5 reutilizado en el contexto del loopback completo.

## Casos cubiertos

Los umbrales de BER se tomaron directo de la curva ya medida en la
[Prueba 5](../../fase1_unitarias/prueba05_fec_roundtrip/) (0-3% = corrección
total, ≥15% = el código se satura) — no se inventaron de nuevo aquí:

1. BER 0%, 1%, 3% → corrección **total**, el payload recuperado es
   idéntico al original.
2. BER 20% → el FEC no puede corregir; el CRC del MAC lo detecta y
   `procesar_payload_con_canal()` lanza `MACFrameError` — **no** devuelve
   un payload (aunque sea incorrecto). Esto es lo que en un flowgraph real
   evita que un paquete corrupto llegue a escribirse en `tun0`.
3. 20 corridas a BER 25% sin ningún caso de "CRC válido pero payload
   distinto del original" — confirma que, en esta muestra, el CRC nunca
   deja pasar corrupción sin detectarla (0 falsos positivos del CRC-16).

## Resultado de la ejecución

```
[OK] BER canal=0% (flips=0): corrige por completo, payload identico
[OK] BER canal=1% (flips=9): corrige por completo, payload identico
[OK] BER canal=3% (flips=27): corrige por completo, payload identico
[OK] BER canal=20% (flips=?): NO corrige -- se descarta (MACFrameError), no cuela payload corrupto
[OK] en 20 corridas a BER=25%, ningun CRC valido escondio un payload incorrecto (0 falsos positivos)

5/5 casos aprobados
```

Salida completa: [`test_output.txt`](test_output.txt).

## Estado: ✅ Aprobada

Confirma que la combinación FEC+CRC se comporta de forma segura en ambos
extremos: corrige silenciosamente los errores que puede, y **nunca**
entrega un dato corrupto como si fuera válido cuando no puede — la
propiedad de seguridad más importante de esta capa (más importante incluso
que la ganancia de corrección en sí). Sigue la Prueba 14 (paquete IP más
grande que el payload útil de un solo símbolo OFDM).
