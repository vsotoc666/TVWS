# Prueba 3 — `tuntap_pdu` escritura

**Objetivo** (según el plan): inyectar un PDU sintético (message strobe) por
el sentido inverso al de la Prueba 2 y verificar con `tcpdump -i tun0` que
los bytes escritos a `tun0` llegan íntegros. Tercera y última frontera de
Fase 1 relacionada con `tun0`/`tuntap_pdu` (kernel↔GNU Radio, ahora en
sentido GNU Radio → kernel).

Requiere `tun0` viva (Prueba 1) y el venv `~/envs/SDR` con el fix de numpy
(ver [`../../README.md`](../../README.md)).

## Qué hace `flowgraph_escritura.py`

```
blocks.message_strobe(pdu, periodo_ms) --strobe--> network.tuntap_pdu('tun0')
```

- El script arma a mano (sin `scapy`) un paquete IPv4/UDP válido —cabecera
  IP con checksum calculado según RFC 791, `10.99.0.2:40000 → 10.99.0.1:9`,
  payload `b"PRUEBA3-TVWS-INBAND"`— y lo envuelve como PDU PMT
  (`pmt.cons(metadata, u8vector)`).
- **`blocks.message_strobe`** reenvía ese mismo PDU cada `--periodo-ms`
  milisegundos por su puerto `strobe`, simulando el rol que en producción
  cumple el bloque MAC/FEC entregando frames ya armados.
- **`network.tuntap_pdu`** recibe el PDU por su puerto de entrada `pdus` y
  escribe el payload crudo en el fd de `tun0` — el sentido inverso de la
  Prueba 2.

La verificación ("¿llegó íntegro?") se hace con `tcpdump -i tun0` en una
terminal aparte, porque capturar paquetes crudos requiere `sudo`
(`cap_net_raw`), que no se puede automatizar sin pedirle la contraseña al
usuario de forma interactiva.

## Cómo correrlo

Terminal A (deja escuchando primero, para no perder los primeros paquetes):
```bash
sudo tcpdump -i tun0 -n -vv -X -c 5
```

Terminal B:
```bash
cd TRANSMISION/pruebas/fase1_unitarias/prueba03_tuntap_pdu_escritura
~/envs/SDR/bin/python flowgraph_escritura.py --duracion 20 --periodo-ms 3000
```

## Resultado de la ejecución

`tcpdump` capturó el paquete sintético repetido, íntegro, cada 3 segundos.
Comparación byte a byte contra lo que imprimió el propio script al arrancar:

```
[prueba03] paquete sintetico (47 bytes) = 4500002fc0de00004011a5170a6300020a6300019c400009001b0000505255454241332d545657532d494e42414e44
```

```
0x0000:  4500 002f c0de 0000 4011 a517 0a63 0002
0x0010:  0a63 0001 9c40 0009 001b 0000 5052 5545
0x0020:  4241 332d 5456 5753 2d49 4e42 414e 44
```

Coinciden exactamente — cabecera IP (`45 00 002f ...`, checksum `a517`),
cabecera UDP (`9c40 0009`, puerto origen 40000 → destino 9) y el payload
`PRUEBA3-TVWS-INBAND` en ASCII.

**Hallazgo extra (no buscado, pero informativo):** como el paquete iba
dirigido a `10.99.0.1` (la propia IP de `tun0`) y no había ningún proceso
escuchando en el puerto UDP 9, el kernel generó una respuesta real
`ICMP ... port 9 unreachable` y la enrutó de vuelta por `tun0` hacia
`10.99.0.2`, visible también en la captura. Esto confirma que el kernel no
solo recibió los bytes tal cual se escribieron, sino que los procesó como
un paquete IP genuino (parseó cabecera, intentó entrega local, generó la
respuesta ICMP estándar) — evidencia más fuerte que un simple "los bytes
llegaron" para validar la frontera `tuntap_pdu` → kernel.

Salida completa de `tcpdump`: [`tcpdump_output.txt`](tcpdump_output.txt) en
esta carpeta.

### Nota

La primera corrida de esta prueba falló con
`RuntimeError: gr::tuntap_pdu::make: tun_alloc failed` porque `tun0` había
dejado de existir (la laptop se reinició entre la Prueba 2 y la Prueba 3;
ver la nota operativa en [`../../README.md`](../../README.md)). Tras
recrear `tun0` con los comandos de la Prueba 1, la prueba corrió sin
errores.

## Estado: ✅ Aprobada

Quedan validadas ambas direcciones de `tuntap_pdu` (Prueba 2: lectura,
Prueba 3: escritura). Sigue la Prueba 4 (MAC: armado de header + CRC), que
ya no depende de `tun0` sino de los bloques MAC/FEC del propio flowgraph.
