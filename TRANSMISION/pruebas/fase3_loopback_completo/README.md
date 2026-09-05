# Fase 3 — Loopback digital completo, mismo proceso (sin SDR)

TX y RX conectados directo (sin canal, sin SDR), ensamblando en flowgraphs
únicos y persistentes lo que las Fases 1-2 ya validaron por partes.
Referencia: [`claudedocs/arquitectura_transmision_datos.md`](../../../claudedocs/arquitectura_transmision_datos.md#fase-3--loopback-digital-completo-mismo-proceso-sin-sdr).

| # | Prueba | Carpeta | Estado |
|---|--------|---------|--------|
| 12 | TX→RX conectados directo (vector, sin canal), tráfico real por `tun0` | [`prueba12_txrx_loopback_tun0`](prueba12_txrx_loopback_tun0/) | ✅ Aprobada |
| 13 | Igual que 12 con canal sintético de errores de bit | [`prueba13_canal_sintetico`](prueba13_canal_sintetico/) | ✅ Aprobada |
| 14 | Paquete IP más grande que el payload útil de un símbolo OFDM | [`prueba14_paquete_grande`](prueba14_paquete_grande/) | ✅ Aprobada |
| 15 | Throughput sostenido por modo de modulación/FEC | [`prueba15_throughput_sostenido`](prueba15_throughput_sostenido/) | ✅ Aprobada |

## Piezas reutilizadas (ninguna reimplementada en esta fase)

Cada prueba de esta fase encadena módulos ya validados en Fase 1 y Fase 2
— es el patrón consistente de todo `TRANSMISION/pruebas/`:

- `mac_frame.py` (Prueba 4) — encapsulado/decapsulado MAC + CRC-16.
- `ccsds_fec.py` (Prueba 5) — FEC CCSDS K=7 R=1/2.
- `constelaciones.py` (Prueba 6) — modulación/demodulación BPSK/QPSK/16-QAM.
- `ofdm_symbol.py` (Prueba 10) — Carrier Allocator + IFFT + CP.
- `rx_chain.py` (Prueba 11) — cadena RX completa (quitar CP+FFT → DEMOD → FEC decode → MAC decap).
- `loopback_block.py` (Prueba 12) — `procesar_payload()`, la función TX+RX
  completa que las Pruebas 13, 14 y 15 reutilizan directamente.

## Hallazgos de esta fase (con impacto fuera de `TRANSMISION/pruebas/`)

1. **Fragmentación vía `seq_num` no implementada, y no hace falta con el
   diseño actual** (Prueba 14) — un frame MAC puede extenderse a un número
   arbitrario de símbolos OFDM. Queda una pregunta abierta sobre el
   presupuesto de latencia de control in-band para frames muy grandes —
   documentada como "Problema 5" en
   [`claudedocs/riesgos_arquitectura_transmision.md`](../../../claudedocs/riesgos_arquitectura_transmision.md).
2. **El throughput medido es ~0.35x del objetivo de diseño** (Prueba 15),
   pero por una razón de implementación conocida y acotada (overhead de
   crear un `gr.top_block()` por paquete dentro de `ccsds_fec.py`), no por
   un problema de arquitectura — ver la sección "Interpretación" del
   README de la Prueba 15 para el desglose y la solución propuesta.

## Notas operativas heredadas de fases anteriores

- **`tun0` no sobrevive un reboot** — ver la nota en
  [`../README.md`](../README.md#nota-operativa-tun0-no-sobrevive-un-reboot).
  La Prueba 12 la necesita viva.
- **Los flowgraphs que importan `constelaciones`/`ccsds_fec`/`ofdm_symbol`
  necesitan más margen de arranque que los de Fase 1** (~5-6s antes de
  generar tráfico, no los ~2s que bastaban en las Pruebas 2-3) — ver la
  nota de timing en el README de la Prueba 12.
