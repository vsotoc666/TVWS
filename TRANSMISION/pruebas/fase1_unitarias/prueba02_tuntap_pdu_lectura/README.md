# Prueba 2 — `tuntap_pdu` lectura

**Objetivo** (según el plan): flowgraph mínimo `tuntap_pdu → debug/print de
PDU`. Verifica que los paquetes que entran a `tun0` (kernel → GNU Radio)
salen como PDU con el payload correcto — la segunda frontera de fallo
aislada por el plan (kernel↔GNU Radio, ahora sí con GNU Radio en juego).

Requiere la Prueba 1 hecha (`tun0` ya creada y `up`) y el venv `~/envs/SDR`
con el fix de numpy aplicado (ver [`../../README.md`](../../README.md)).

## Qué hace `flowgraph_lectura.py`

Dos bloques conectados por **puerto de mensajes** (no streaming):

```
network.tuntap_pdu('tun0', ...) --pdus--> blocks.message_debug()
```

- **`network.tuntap_pdu`**: abre el fd de la interfaz `tun0` ya existente
  (creada en la Prueba 1) y por cada paquete IP que el kernel escriba en
  ella, emite un mensaje PDU (`(dict metadata, u8vector payload)`) por su
  puerto de salida `pdus`. Se usa `network.tuntap_pdu` en vez de
  `blocks.tuntap_pdu` porque GNU Radio 3.10 movió el bloque de `gr-blocks` a
  `gr-network` y el original imprime un deprecation warning (ambos son el
  mismo bloque C++, mismo comportamiento).
- **`blocks.message_debug`**: se suscribe a ese puerto (`msg_connect`) y
  vuelca cada PDU recibida a stdout en hexdump, para inspección visual.

El script arranca el flowgraph, espera `--duracion` segundos (tiempo para
que el usuario genere tráfico real con `ping` desde otra terminal), y lo
detiene.

## Cómo correrlo

```bash
cd TRANSMISION/pruebas/fase1_unitarias/prueba02_tuntap_pdu_lectura
~/envs/SDR/bin/python flowgraph_lectura.py --dev tun0 --duracion 12
# en otra terminal, mientras el anterior sigue corriendo:
ping -I tun0 -c 4 10.99.0.2
```

## Resultado de la ejecución

Se lanzó el flowgraph en background (12 s) y, con la interfaz ya
escuchando, se generó tráfico real: `ping -I tun0 -c 4 10.99.0.2` (el mismo
comando de la Prueba 1, que entonces no tenía receptor y ahora sí).

Las 4 PDUs de 84 bytes llegaron íntegras a `message_debug`, una por cada
echo request del ping:

```
pdu length = 84 bytes
0000: 45 00 00 54 ce 50 40 00 40 01 57 90 0a 63 00 01
0010: 0a 63 00 02 08 00 fb 7c 00 02 00 01 3f 9e 62 6a
...
```

Verificación byte a byte del primer PDU (cabecera IPv4 + ICMP):

| Bytes | Campo | Valor | Coincide con |
|---|---|---|---|
| `45 00 00 54` | IPv4, IHL=5, longitud total | 84 (0x54) | tamaño reportado por `ping` (56+28) |
| byte 9 | protocolo | `01` = ICMP | — |
| `0a 63 00 01` | IP origen | 10.99.0.1 | IP de `tun0` (Prueba 1) |
| `0a 63 00 02` | IP destino | 10.99.0.2 | destino del `ping` |
| `08 00` | tipo/código ICMP | Echo Request | comando `ping` |
| `00 02 00 01` .. `00 04` | id/seq ICMP | secuencias 1-4 | los 4 paquetes del `-c 4` |

Salida completa (incluye los warnings de arranque y el orden de impresión,
comentados abajo): `flowgraph_lectura_output.txt` en esta carpeta.

### Notas sobre la salida

- **`tuntap_pdu :error: failed to set MTU to 1500`**: esperado y ya visto en
  la Prueba 1 — cambiar el MTU vía `ioctl` necesita `CAP_NET_ADMIN`, que el
  proceso Python no tiene (corre como usuario normal, a propósito). No es
  fatal: la interfaz ya tenía MTU 1500 por defecto (Prueba 1), así que el
  valor pedido y el real coinciden igual.
- **El orden de las líneas en el log no refleja el orden real de
  ejecución**: los prints de Python (`"[prueba02] flowgraph arrancado..."`)
  aparecen en el log *después* de los primeros PDUs aunque el código los
  imprime antes de `tb.start()`. Es un artefacto de buffering — stdout de
  Python queda completamente bufferizado al redirigirse a un archivo,
  mientras que el bloque C++ de `message_debug` escribe con flush
  inmediato. No indica ningún problema de sincronización real del
  flowgraph.

## Estado: ✅ Aprobada

`tuntap_pdu` convierte correctamente tráfico IP real de `tun0` en PDUs con
payload íntegro. Queda validada la frontera kernel↔GNU Radio en lectura;
falta el sentido inverso (Prueba 3: escritura, inyectar PDU sintético y
verificar con `tcpdump -i tun0`).
