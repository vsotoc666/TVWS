# Prueba 14 — Paquete IP más grande que el slot TDD: fragmentación real

**Objetivo** (según el plan, actualizado): un PDU que no cabe en un slot
TDD (20 símbolos OFDM, `claudedocs/arquitectura_enlace_datos.md` §2.1) se
fragmenta vía `mac_frame.fragmentar()`/`reensamblar()` (§2.4: `seq_num`
como ID de PDU + bit MF en `frag_flags`), cada fragmento cabe en su slot,
y el PDU se reensambla bit-exacto en el receptor.

No requiere `tun0` ni `sudo`. Requiere el venv `~/envs/SDR`.

## Historia de esta prueba

La primera versión (21/08/2026) midió que un payload de 1400 bytes
(tamaño típico de `ping -s 1400`) necesita **50 símbolos OFDM** a BPSK R=1/2
como un único frame MAC monolítico, y concluyó que no hacía falta
fragmentación — en ese momento no existía framing TDD, así que un frame
podía extenderse a cuantos símbolos hiciera falta sin chocar con nada.

Esa conclusión dejó de aplicar cuando se decidió el slot TDD de 20 símbolos
(`claudedocs/arquitectura_enlace_datos.md` §2.1): un frame de 50 símbolos
ocupa 2.5 slots, y sin canal fuera de banda (no hay LoRa en este diseño)
no hay forma de que un frame "se pase" al siguiente slot sin pisar la
dirección de transmisión contraria. Se decidió fragmentar (§2.4) y esta
prueba se rehizo para validar el escenario real.

## Cuánto cabe realmente en un símbolo OFDM y en un slot

```
capacidad de un simbolo OFDM: 457 bits codificados
presupuesto de slot TDD: 20 simbolos (~1.78 ms)
umbral de corte usado: 18 simbolos
max bytes de payload IP por fragmento (a 18 simbolos, BPSK R=1/2): 505
```

El máximo de bytes por fragmento se **calcula exacto** a partir de las
constantes reales de este codebase (`N_DATOS_POR_SIMBOLO` de
`ofdm_symbol.py`, `PAD_BYTES` de `ccsds_fec.py`, y el overhead de 5 bytes
del header MAC), no copiado de la tabla aproximada de
`claudedocs/arquitectura_enlace_datos.md` §2.4 (esa tabla está "escalada
desde la medición", ~28 bytes/símbolo — una aproximación, no un cálculo
exacto):

```
coded_bits = (payload_bytes + MAC_OVERHEAD_BYTES + PAD_BYTES) * 16   (FEC R=1/2)
n_simbolos = ceil(coded_bits / N_DATOS_POR_SIMBOLO)
```

**Umbral de corte elegido: 18 símbolos, no 20.** El presupuesto completo
del slot (20 símbolos) alcanzaría exactamente para 562 bytes de payload
por fragmento, sin ningún margen — el propio diseño de arquitectura deja
este umbral como "detalle de implementación a ajustar" (§2.4) y advierte
explícitamente evitar quedar justo al límite. Se eligió 18/20 (10% de
margen) para no depender de que ningún futuro ajuste (ej. un símbolo de
control adicional) empuje un fragmento calculado al límite exacto fuera
del slot.

## El hallazgo

```
[prueba14] payload de prueba: 1400 bytes
[OK] [contraste] frame monolitico de 1400B sigue ocupando 50 simbolos (>1 slot, como antes)
[OK] [contraste] frame monolitico sigue recuperando el payload bit-exacto (la capa OFDM no tiene limite propio)
[prueba14] 3 fragmentos generados para 1400B
[OK] se generó más de 1 fragmento (3)
[prueba14]   fragmento 0: 510B de frame MAC -> 18 simbolos OFDM (cabe en 20)
[prueba14]   fragmento 1: 510B de frame MAC -> 18 simbolos OFDM (cabe en 20)
[prueba14]   fragmento 2: 395B de frame MAC -> 14 simbolos OFDM (cabe en 20)
[OK] los 3 fragmentos caben cada uno en <= 20 simbolos (1 slot TDD)
[OK] reensamblar() sobre los fragmentos recuperados por TX+RX == payload original, bit exacto

5/5 casos aprobados
```

El paquete de 1400 bytes se parte en 3 fragmentos vía
`mac_frame.fragmentar()` (máximo 505 bytes de payload por fragmento),
cada fragmento pasa por la cadena TX completa (FEC → MOD BPSK → OFDM) y
RX completa (OFDM → DEMOD → FEC → decapsulado) ya validada en las Pruebas
9-11, y `mac_frame.reensamblar()` reconstruye el payload original
**bit-exacto** a partir de los 3 fragmentos recuperados. Los 3 fragmentos
comparten `seq_num=42` (el mismo ID de PDU) y llevan MF=1 en los primeros
dos, MF=0 en el último.

Se mantiene, como caso de contraste/regresión, el escenario del frame
monolítico sin fragmentar: sigue siendo cierto que la capa OFDM en sí
(`dividir_en_simbolos_ofdm`) no impone ningún límite de tamaño — 50
símbolos consecutivos siguen funcionando bit-exacto en loopback puro. Pero
ese ya no es el criterio de éxito relevante: lo que importa ahora es que
cada fragmento individual respete el presupuesto del slot TDD.

Salida completa: [`test_output.txt`](test_output.txt).

## Estado: ✅ Aprobada

El sistema soporta paquetes más grandes que un slot TDD fragmentándolos
correctamente vía `mac_frame.fragmentar()`/`reensamblar()`, con cada
fragmento respetando el presupuesto de 20 símbolos OFDM del slot
(`claudedocs/arquitectura_enlace_datos.md` §2.1/§2.4). Sigue la Prueba 15
(throughput sostenido por modo de modulación/FEC) — la fragmentación en sí
no se mide ahí (Prueba 15 usa payloads más chicos, sin fragmentar), pero
comparte la misma cadena TX/RX ya reutilizada aquí.

**Nota de alcance:** esta prueba fragmenta y reensambla en un único
proceso (sin canal ni pérdida de fragmentos) — no valida qué pasa si un
fragmento completo se pierde en tránsito (no solo se corrompe). Per
`claudedocs/arquitectura_enlace_datos.md` §2.4, no hay ARQ/retransmisión
en este diseño: un fragmento corrupto (CRC inválido) descarta el PDU
completo, comportamiento que sí cubre la Prueba 4
(`fase1_unitarias/prueba04_mac_encap_decap/`, caso "fragmento corrupto en
reensamblar() lanza MACFrameError").
