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
| Datos | el resto: índices 26-253 y 258-486 (457 slots) |

El vector de frecuencia usa la convención **centrada** que el propio
`README.md` describe (índice ~256 ≈ DC, por eso el campo de control está
ahí pegado y por eso se evita #255) — la misma convención que
`digital.ofdm_carrier_allocator_cvc` usa con `output_is_shifted=True`.

### Por qué `numpy` directo y no `digital.ofdm_carrier_allocator_cvc`

La posición exacta de las ~55 subportadoras piloto **no está fijada en
ningún doc** (`README.md` solo dice "~55 dispersas", sin tabla de índices
— otra decisión abierta, como el header MAC de la Prueba 4). El bloque
`ofdm_carrier_allocator_cvc` de GNU Radio exige una tabla de pilotos
concreta para construirse; en vez de inventar una, esta prueba usa `numpy`
directo para armar el vector de 512 puntos exactamente como lo describe el
documento (guardas, control, CP) sin necesitar decidir pilotos. Cuando esa
decisión se cierre, se puede migrar a usar el bloque real de GNU Radio sin
cambiar el criterio de la prueba.

## Qué hace `ofdm_symbol.py`

- **`armar_simbolo_ofdm(datos, bits_control)`**: arma un vector de
  frecuencia de 512 puntos con los símbolos de datos en sus 457 slots, los
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
  falta, 457 a la vez, rellenando con ceros el último si no lo completa.

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
3. Los símbolos de datos caen exacto en los 457 slots de datos, sin pisar
   guardas ni control (ni un símbolo de más ni de menos).
4. Cada símbolo con CP mide exactamente 640 muestras (512+128).
5. El CP es una **copia exacta** de la cola del símbolo IFFT — no basta
   con que mida 128 muestras, tienen que ser las muestras correctas (la
   definición real de un prefijo cíclico).
6. Round-trip completo (quitar CP + FFT) recupera el vector de frecuencia
   original exacto — confirma que la estructura no solo "se ve bien", es
   matemáticamente invertible y consistente.

## Resultado de la ejecución

```
[prueba10] 896 simbolos BPSK de entrada (Prueba 9)
[prueba10] repartidos en 2 simbolos OFDM (457 datos c/u)
[OK] guardas (indices 0-25 y 487-511) en cero en los 2 simbolos OFDM
[OK] subportadoras de control (#254/#256/#257=BPSK del mensaje, #255 evitada=0) en su indice
[OK] simbolos de datos ubicados exacto en los slots de datos (sin pisar guardas/control)
[OK] cada simbolo OFDM con CP mide 512+128=640 muestras
[OK] el CP es copia exacta de la cola del simbolo IFFT (no solo la longitud)
[OK] round-trip (quitar CP + FFT) recupera el vector de frecuencia original

6/6 casos aprobados
```

Salida completa: [`test_output.txt`](test_output.txt).

## Estado: ✅ Aprobada

Con esto, toda la cadena TX de software (sin SDR) queda encadenada de
punta a punta: `tun0` → MAC → FEC → MOD → OFDM (Carrier Allocator + IFFT +
CP). Sigue la Prueba 11 (RX completo aislado, alimentado con la salida de
esta prueba) — cierra el círculo demostrando que la cadena de recepción
reconstruye el payload original sin RF de por medio.
