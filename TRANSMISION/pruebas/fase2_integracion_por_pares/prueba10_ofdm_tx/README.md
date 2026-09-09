# Prueba 10 — TX completo hasta antes del SDR (incluye IFFT+CP)

**Objetivo** (según el plan): estructura del símbolo OFDM correcta —
guardas en cero, subportadoras de control en su índice, CP de longitud
correcta. Extiende la [Prueba 9](../prueba09_mac_fec_mod_stream/) hasta el
borde mismo del SDR (todo lo que hay antes del hardware de radio).

No requiere `tun0` ni `sudo`. Requiere el venv `~/envs/SDR` (numpy +
reutiliza la cadena de la Prueba 9).

## Parámetros usados (todos del `README.md` §5.1/§5.2, no inventados)

| Parámetro | Valor |
|---|---|
| FFT | 512 puntos |
| CP | 128 muestras (1/4 del símbolo) |
| Guarda inferior | índices 0-25 (26 sub) → 0 |
| Guarda superior | índices 487-511 (25 sub) → 0 |
| Control in-band | #254, #256, #257 = bits BPSK; **#255 evitada** (DC/LO leakage) → 0 |
| Pilotos (✅ cerrado 07/09/2026) | comb escalonado stride 8, `offset = indice_simbolo % 8` — 57-58 slots según offset |
| Datos | pool de 457 (índices 26-253 y 258-486) menos los pilotos de ese offset — 399 u 400 según offset |

El vector de frecuencia usa la convención **centrada** que el propio
`README.md` describe (índice ~256 ≈ DC, por eso el campo de control está
ahí pegado y por eso se evita #255) — la misma convención que
`digital.ofdm_carrier_allocator_cvc` usa con `output_is_shifted=True`.

### Por qué sigue en `numpy` directo y no `digital.ofdm_carrier_allocator_cvc`

El patrón de pilotos **ya está cerrado** (07/09/2026, Problema 4 de
`claudedocs/riesgos_arquitectura_transmision.md`) y documentado en detalle
en `README.md` §5.1/§5.2 — ya no es una decisión abierta. Lo que sigue
pendiente, y es la razón real por la que este módulo no usa todavía el
bloque nativo de GNU Radio, es la **migración** en sí: `ofdm_carrier_allocator_cvc`
exige que la tabla de pilotos se le pase como parámetro de construcción, y
esa migración (reemplazar el `numpy` a mano de `ofdm_symbol.py` por el
bloque real) quedó explícitamente diferida como trabajo futuro al cerrar
el patrón — no cambia el criterio de esta prueba, solo la implementación
interna del módulo que prueba.

## Qué hace `ofdm_symbol.py`

- **`armar_simbolo_ofdm(datos, bits_control, indice_simbolo=0)`**: arma un
  vector de frecuencia de 512 puntos con los símbolos de datos en los
  slots de datos del offset correspondiente (`indice_simbolo % 8`), los
  pilotos BPSK alternados (+1.0/-1.0) en las posiciones de ese offset, los
  3 bits de control mapeados a BPSK en #254/#256/#257, #255 en cero, y el
  resto (guardas) en cero.
- **`ifft_mas_cp(vector)`**: `ifftshift` (pasar de la convención centrada
  a la nativa de FFT) → `ifft` → antepone las últimas 128 muestras como
  prefijo cíclico. Da el símbolo de 640 muestras listo para "streaming
  continuo a 7.68 MSPS" (README).
- **`quitar_cp_y_fft(simbolo)`**: el inverso, para el chequeo de
  round-trip.
- **`dividir_en_simbolos_ofdm(...)`**: reparte una lista larga de símbolos
  modulados (la salida de la Prueba 9) en tantos símbolos OFDM como haga
  falta, consumiendo en cada símbolo la capacidad de datos que le toca
  según su offset dentro del ciclo de 8 (399 u 400), rellenando con ceros
  el último si no lo completa.

## Qué encadena `test_ofdm_tx.py`

Reutiliza `payload_a_simbolos()` de la Prueba 9 (que a su vez reutiliza
MAC/FEC/MOD de las Pruebas 4-6) para obtener los 896 símbolos BPSK reales,
y los reparte en símbolos OFDM. Los 3 bits de control son un valor fijo
`(1, 0, 1)` de relleno — `InbandControlTX` (la capa que los calcularía de
verdad) todavía no está implementada; esta prueba solo valida que, sean
cuales sean, **caen en el índice correcto**.

## Casos cubiertos

1. Guardas (0-25, 487-511) en cero en todos los símbolos OFDM generados.
2. Control (#254/#256/#257 = BPSK del mensaje, #255 = 0) en su índice.
3. Los símbolos de datos caen exacto en los slots de datos del offset
   correspondiente, sin pisar guardas, control ni pilotos (ni un símbolo
   de más ni de menos).
4. Cada símbolo con CP mide exactamente 640 muestras (512+128).
5. El CP es una **copia exacta** de la cola del símbolo IFFT — no basta
   con que mida 128 muestras, tienen que ser las muestras correctas (la
   definición real de un prefijo cíclico).
6. Round-trip completo (quitar CP + FFT) recupera el vector de frecuencia
   original exacto — confirma que la estructura no solo "se ve bien", es
   matemáticamente invertible y consistente.
7. Posiciones piloto correctas (índices y valores BPSK) para varios
   offsets del ciclo de 8.
8. Valores piloto alternan +1.0/-1.0 empezando en +1.0, en todos los
   offsets.
9. Pilotos + datos suman exactamente 457 (el pool completo, sin solape)
   en los 8 offsets — confirma cobertura exacta del patrón escalonado.

## Resultado de la ejecución

```
[prueba10] 896 simbolos BPSK de entrada (Prueba 9)
[prueba10] repartidos en 3 simbolos OFDM (datos por-offset: offset0=399, offset1=400, offset2=400, offset3=400, offset4=400, offset5=400, offset6=400, offset7=400)
[OK] guardas (indices 0-25 y 487-511) en cero en los 3 simbolos OFDM
[OK] subportadoras de control (#254/#256/#257=BPSK del mensaje, #255 evitada=0) en su indice
[OK] simbolos de datos ubicados exacto en los slots de datos por-offset (sin pisar guardas/control/pilotos)
[OK] cada simbolo OFDM con CP mide 512+128=640 muestras
[OK] el CP es copia exacta de la cola del simbolo IFFT (no solo la longitud)
[OK] round-trip (quitar CP + FFT) recupera el vector de frecuencia original
[OK] posiciones piloto correctas (valores BPSK) para offsets (0, 1, 3, 7)
[OK] valores piloto BPSK alternan +1.0/-1.0 empezando en +1.0, en todos los offsets
[OK] pilotos + datos suman exactamente 457 (pool completo, sin solape) en los 8 offsets

9/9 casos aprobados
```

Salida completa: [`test_output.txt`](test_output.txt) (regenerar con
`python test_ofdm_tx.py > test_output.txt` si se vuelve a modificar el
módulo).

## Estado: ✅ Aprobada

Con esto, toda la cadena TX de software (sin SDR) queda encadenada de
punta a punta: `tun0` → MAC → FEC → MOD → OFDM (Carrier Allocator + IFFT +
CP). Sigue la Prueba 11 (RX completo aislado, alimentado con la salida de
esta prueba) — cierra el círculo demostrando que la cadena de recepción
reconstruye el payload original sin RF de por medio.
