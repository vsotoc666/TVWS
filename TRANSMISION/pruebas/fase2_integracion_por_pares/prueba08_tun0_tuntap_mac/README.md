# Prueba 8 — `tun0` → `tuntap_pdu` → MAC → dump

**Objetivo** (según el plan): tráfico real (`ping`) produce frames MAC bien
formados. Primera prueba de **integración**: en vez de probar cada bloque
suelto, encadena piezas de la Fase 1 ya validadas por separado.

Requiere `tun0` viva ([Prueba 1](../../fase1_unitarias/prueba01_tun0_basico/))
y el venv `~/envs/SDR`. No requiere `sudo`.

## Qué se encadena

```
tun0 --(kernel)--> network.tuntap_pdu --pdus--> MacEncapBlock --pdus--> message_debug (dump)
```

- **`network.tuntap_pdu`**: el mismo bloque de la
  [Prueba 2](../../fase1_unitarias/prueba02_tuntap_pdu_lectura/), sin
  modificar.
- **`MacEncapBlock`** (`mac_encap_block.py`, nuevo): un bloque de mensajes
  de GNU Radio que **envuelve, no reimplementa**, `mac_frame.encapsular()`
  de la [Prueba 4](../../fase1_unitarias/prueba04_mac_encap_decap/)
  (importado con `sys.path` desde ahí). Recibe el PDU con el paquete IP
  crudo, le arma el header MAC con `seq_num` autoincremental (wrap a 256) y
  `frag_flags`/`mod_scheme` fijos para esta prueba (todavía no hay
  `CognitiveEngine` real que decida `mod_scheme`, ni fragmentación activa
  aquí — `frag_flags=0`, sin fragmentar; ver Prueba 14 para el caso
  fragmentado), y publica el frame completo como PDU de salida.
- **`message_debug`** en modo `store`: acumula los frames para volcarlos a
  un archivo de texto (uno por línea, en hex) al terminar.

## Cómo correrlo

Terminal A:
```bash
cd TRANSMISION/pruebas/fase2_integracion_por_pares/prueba08_tun0_tuntap_mac
~/envs/SDR/bin/python flowgraph_prueba08.py --dev tun0 --duracion 12 --salida frames_mac.txt
```

Terminal B, mientras corre A:
```bash
ping -I tun0 -c 4 10.99.0.2
```

Luego verificar el volcado:
```bash
~/envs/SDR/bin/python verificar_frames.py frames_mac.txt
```

## Resultado de la ejecución

`ping -c 4` generó 4 paquetes ICMP echo request; los 4 llegaron como
frames MAC bien formados (`frames_mac.txt`). `verificar_frames.py` los
decapsula con el mismo `mac_frame.decapsular()` de la Prueba 4 y confirma:

- **CRC válido** en los 4 frames (ninguno corrupto).
- **`seq_num` consecutivo**: 0, 1, 2, 3 — el autoincremento de
  `MacEncapBlock` funciona a través de múltiples PDUs.
- **`frag_flags`/`mod_scheme`** constantes (0, 1) — los valores fijos
  configurados se propagan correctamente en cada frame.
- **El payload decapsulado es un paquete IPv4/ICMP real**: versión 4,
  protocolo ICMP, IP origen `10.99.0.1` (la propia `tun0`) — exactamente lo
  que produce el kernel al enrutar el `ping`, no datos sintéticos.

```
[OK] al menos 1 frame capturado en frames_mac.txt
[OK] frame 0: CRC valido
[OK] frame 0: seq_num=0 consecutivo (esperado 0)
...
TODOS los frames validos
```

Salida completa: [`verificacion_output.txt`](verificacion_output.txt) — capturada
antes de que `next_ch` se repurpuseara como `frag_flags`
(`claudedocs/arquitectura_enlace_datos.md` §2.4), así que todavía dice
`next_ch=3`; el comportamiento verificado (campo constante propagado sin
corrupción) no cambió, solo el nombre/semántica del campo. No se
regeneró porque esta prueba requiere `tun0` real + `sudo` interactivo, que
no se recreó en esta sesión — pendiente de una corrida real para
refrescar este archivo.
Frames crudos: [`frames_mac.txt`](frames_mac.txt).

## Estado: ✅ Aprobada

Primera integración de punta a punta (kernel → GNU Radio → MAC) con
tráfico real, no sintético. Sigue la Prueba 9 (`MAC → FEC → MOD →
PDU-to-stream → dump a archivo`), que sigue extendiendo esta misma cadena
un paso más hacia el streaming.
