# Fase 2 — Integración por pares (sin SDR)

A diferencia de la Fase 1 (cada bloque aislado), estas pruebas encadenan
piezas ya validadas por separado para confirmar que la integración entre
ellas no rompe nada. Referencia:
[`claudedocs/arquitectura_transmision_datos.md`](../../../claudedocs/arquitectura_transmision_datos.md#fase-2--integración-por-pares-sin-sdr).

| # | Prueba | Carpeta | Estado |
|---|--------|---------|--------|
| 8 | `tun0` → `tuntap_pdu` → MAC → dump | [`prueba08_tun0_tuntap_mac`](prueba08_tun0_tuntap_mac/) | ✅ Aprobada |
| 9 | MAC → FEC → MOD → PDU-to-stream → dump a archivo | [`prueba09_mac_fec_mod_stream`](prueba09_mac_fec_mod_stream/) | ✅ Aprobada |
| 10 | TX completo hasta antes del SDR (incluye IFFT+CP) | [`prueba10_ofdm_tx`](prueba10_ofdm_tx/) | ✅ Aprobada |
| 11 | RX completo aislado, alimentado con la salida de la prueba 10 | [`prueba11_rx_completo`](prueba11_rx_completo/) | ✅ Aprobada |
