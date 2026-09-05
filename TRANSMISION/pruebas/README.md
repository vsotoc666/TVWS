# Pruebas del tramo Internet/Router → GNU Radio

Ejecución paso a paso del "Plan de pruebas" descrito en
[`claudedocs/arquitectura_transmision_datos.md`](../../claudedocs/arquitectura_transmision_datos.md#plan-de-pruebas--tramo-internetrouter--gnu-radio).
Ese documento explica el *por qué* del orden (aislar el tipo de falla en cada
fase: kernel↔GNU Radio, PDU↔streaming, streaming↔RF); esta carpeta guarda la
*evidencia* de cada prueba ejecutada: comandos, resultados y conclusión.

## Entorno usado

- Laptop Ubuntu 22.04 (`fiee-god`), sin bladeRF conectado — las
  pruebas de Fase 1 están diseñadas para no necesitar hardware.
- venv `~/envs/SDR` (Python 3.10, `include-system-site-packages=true`), que
  hereda GNU Radio 3.10.1.1 instalado vía `apt`.
- Fix aplicado al venv: `numpy` se pineó a `1.26.4` (`pip install
  "numpy<2,>=1.22"`) porque los bindings compilados de GNU Radio tienen ABI de
  NumPy 1.x y el venv traía NumPy 2.2.6 por defecto, lo cual rompía
  `from gnuradio import gr, blocks`. El numpy del sistema es 1.21.5; se eligió
  1.26.4 en vez de igualarlo porque `scikit-learn 1.7.2` (también instalado en
  este venv) exige `numpy>=1.22`.

## Estado — Fase 1 (unitarias, cada bloque aislado, sin SDR) — ✅ 7/7 completa

| # | Prueba | Carpeta | Estado |
|---|--------|---------|--------|
| 1 | `tun0` básico (`ip tuntap add` + `ping -I tun0`) | [`fase1_unitarias/prueba01_tun0_basico`](fase1_unitarias/prueba01_tun0_basico/) | ✅ Aprobada |
| 2 | `tuntap_pdu` lectura (flowgraph mínimo → debug/print de PDU) | [`fase1_unitarias/prueba02_tuntap_pdu_lectura`](fase1_unitarias/prueba02_tuntap_pdu_lectura/) | ✅ Aprobada |
| 3 | `tuntap_pdu` escritura (PDU sintético → `tcpdump -i tun0`) | [`fase1_unitarias/prueba03_tuntap_pdu_escritura`](fase1_unitarias/prueba03_tuntap_pdu_escritura/) | ✅ Aprobada |
| 4 | MAC: armado de header + CRC | [`fase1_unitarias/prueba04_mac_encap_decap`](fase1_unitarias/prueba04_mac_encap_decap/) | ✅ Aprobada |
| 5 | FEC round-trip | [`fase1_unitarias/prueba05_fec_roundtrip`](fase1_unitarias/prueba05_fec_roundtrip/) | ✅ Aprobada |
| 6 | MOD/DEMOD round-trip (BPSK/QPSK/16-QAM) | [`fase1_unitarias/prueba06_mod_demod_roundtrip`](fase1_unitarias/prueba06_mod_demod_roundtrip/) | ✅ Aprobada |
| 7 | PDU↔Tagged Stream (ambos sentidos) | [`fase1_unitarias/prueba07_pdu_tagged_stream`](fase1_unitarias/prueba07_pdu_tagged_stream/) | ✅ Aprobada |

## Estado — Fase 2 (integración por pares, sin SDR) — ✅ 4/4 completa

| # | Prueba | Carpeta | Estado |
|---|--------|---------|--------|
| 8 | `tun0` → `tuntap_pdu` → MAC → dump | [`fase2_integracion_por_pares/prueba08_tun0_tuntap_mac`](fase2_integracion_por_pares/prueba08_tun0_tuntap_mac/) | ✅ Aprobada |
| 9 | MAC → FEC → MOD → PDU-to-stream → dump a archivo | [`fase2_integracion_por_pares/prueba09_mac_fec_mod_stream`](fase2_integracion_por_pares/prueba09_mac_fec_mod_stream/) | ✅ Aprobada |
| 10 | TX completo hasta antes del SDR (incluye IFFT+CP) | [`fase2_integracion_por_pares/prueba10_ofdm_tx`](fase2_integracion_por_pares/prueba10_ofdm_tx/) | ✅ Aprobada |
| 11 | RX completo aislado, alimentado con la salida de la prueba 10 | [`fase2_integracion_por_pares/prueba11_rx_completo`](fase2_integracion_por_pares/prueba11_rx_completo/) | ✅ Aprobada |

Detalle en [`fase2_integracion_por_pares/README.md`](fase2_integracion_por_pares/README.md).

## Estado — Fase 3 (loopback digital completo, mismo proceso, sin SDR) — ✅ 4/4 completa

| # | Prueba | Carpeta | Estado |
|---|--------|---------|--------|
| 12 | TX→RX conectados directo (vector, sin canal), tráfico real por `tun0` | [`fase3_loopback_completo/prueba12_txrx_loopback_tun0`](fase3_loopback_completo/prueba12_txrx_loopback_tun0/) | ✅ Aprobada |
| 13 | Igual que 12 con canal sintético de errores de bit | [`fase3_loopback_completo/prueba13_canal_sintetico`](fase3_loopback_completo/prueba13_canal_sintetico/) | ✅ Aprobada |
| 14 | Paquete IP más grande que el payload útil de un símbolo OFDM | [`fase3_loopback_completo/prueba14_paquete_grande`](fase3_loopback_completo/prueba14_paquete_grande/) | ✅ Aprobada |
| 15 | Throughput sostenido por modo de modulación/FEC | [`fase3_loopback_completo/prueba15_throughput_sostenido`](fase3_loopback_completo/prueba15_throughput_sostenido/) | ✅ Aprobada |

Detalle, piezas reutilizadas y hallazgos de esta fase en
[`fase3_loopback_completo/README.md`](fase3_loopback_completo/README.md).

Fases 1, 2 y 3 completas (15/15). Las Fases 4+ (con hardware real:
bladeRF/SDR Cliente) están en el plan pero requieren hardware que todavía
no ha llegado — ver `claudedocs/arquitectura_transmision_datos.md` para la
tabla completa.

## Nota operativa: `tun0` no sobrevive un reboot

`ip tuntap add ... mode tun user $USER` crea una interfaz con el flag
`persist`, que solo evita que el kernel la destruya cuando se cierra el fd
que la tiene abierta *dentro de la misma sesión de arranque*. Un reinicio
del equipo arranca el kernel desde cero: `tun0` no vuelve a existir
(confirmado el 2026-07-23 — la laptop se reinició a las 19:00 entre la
Prueba 2 y la Prueba 3, `tun0` desapareció por completo, y `who -b` /
`journalctl -u NetworkManager` confirmaron el reboot, descartando que fuera
NetworkManager u otra causa).

**Antes de cada sesión de pruebas**, verificar con `ip addr show tun0` y
recrearla si hace falta con los 3 comandos de la
[Prueba 1](fase1_unitarias/prueba01_tun0_basico/):

```bash
sudo ip tuntap add dev tun0 mode tun user $USER
sudo ip addr add 10.99.0.1/30 dev tun0
sudo ip link set tun0 up
```

Para el Gateway/Cliente de campo (no esta laptop de pruebas) esto implica
que la creación de `tun0` debe automatizarse al arranque (systemd `.netdev`,
`ip-up` script, o que el propio proceso de GNU Radio la cree si no existe) —
queda como pendiente para `claudedocs/arquitectura_transmision_datos.md`,
sección "Decisiones abiertas".
