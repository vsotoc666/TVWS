# Prueba 11 — RX completo aislado, alimentado con la salida de la Prueba 10

**Objetivo** (según el plan): la cadena de recepción reconstruye el
payload original **sin RF de por medio**. Última prueba de la Fase 2 —
cierra el círculo TX (Pruebas 8-10) → RX (esta prueba), conectados
directo, sin canal ni SDR.

No requiere `tun0` ni `sudo`. Requiere el venv `~/envs/SDR`.

## Qué se encadena

```
TX (Pruebas 9-10):  payload → MAC → FEC → MOD(BPSK) → OFDM(IFFT+CP)
RX (esta prueba):   OFDM(quitar CP+FFT) → DEMOD → FEC decode → MAC decap → payload
```

`rx_chain.py` es el espejo exacto de la cadena TX, reutilizando **los
mismos módulos** de las Pruebas 4, 5, 6 y 10 — no hay una segunda
implementación paralela de MAC/FEC/OFDM para el lado RX.

## El bug que apareció al construirla (y por qué importa)

La primera versión demodulaba los símbolos BPSK a bits duros (0/1, con
`constelaciones.demodular()` de la Prueba 6) **antes** de pasarlos al
decodificador FEC (`ccsds_fec.decodificar()`, Prueba 5) — resultado: CRC
inválido, payload irrecuperable.

La causa: `decode_ccsds_27_fb` (el bloque Viterbi de la Prueba 5) espera
símbolos **blandos** (float, convención −1.0/+1.0), no bits ya decididos.
Para BPSK, "demodular" y "extraer el símbolo blando que necesita el FEC"
son **el mismo número** — por eso la Prueba 9 pudo usar
`constelaciones.modular()` directamente sobre los bits codificados del FEC
sin un paso intermedio. Pasar esos símbolos por un demodulador duro
primero y reinterpretar el resultado (0/1) como si fuera el float
±1.0 esperado corrompe la convención de signo (0 termina interpretado como
símbolo "erasure" en 0.0, no como bit 0 en −1.0). La corrección fue quitar
el paso de demodulación dura y tomar directo la parte real del símbolo
recibido (`s.real`) como entrada al decodificador FEC.

Esto es un ejemplo concreto de por qué la Fase 2 (integración) encuentra
errores que las pruebas unitarias de Fase 1 no pueden ver: `constelaciones.py`
y `ccsds_fec.py` funcionan perfecto cada uno por separado (Pruebas 5 y 6
en verde), pero conectarlos en el orden equivocado rompe la cadena
completa.

## Qué hace `rx_chain.py`

- **`extraer_control(vector_freq)`**: lee #254/#256/#257 (decisión BPSK
  dura — el control sí se demodula duro, porque no pasa por FEC) y
  descarta #255 (evitada, Prueba 10).
- **`ofdm_a_frame_mac(simbolos_tiempo, n_simbolos_datos, n_bytes_frame_mac)`**:
  para cada símbolo OFDM, quita el CP y hace FFT (`ofdm_symbol.quitar_cp_y_fft`,
  Prueba 10), extrae los símbolos de datos en `DATOS_IDX`, descarta el
  relleno de ceros del último símbolo, y pasa los símbolos blandos
  directo al decodificador FEC de la Prueba 5.
- **`frame_mac_a_payload(frame_mac)`**: reusa `mac_frame.decapsular()`
  (Prueba 4) tal cual.

Igual que en la Prueba 9, la cantidad de símbolos de datos válidos y el
largo del frame MAC se pasan como parámetro — en el sistema real vendrían
de un tag de longitud (Prueba 7) o un campo del protocolo, no se
adivinarían de la estructura OFDM.

## Resultado de la ejecución

```
[prueba11] TX: 2 simbolos OFDM generados (Pruebas 9-10)
[prueba11] RX: frame MAC recuperado (52 bytes)
[OK] frame MAC recuperado == frame MAC original (bit exacto)
[OK] control recuperado == (1, 0, 1) en los 2 simbolos OFDM
[OK] mac_frame.decapsular(): CRC valido
[OK] payload recuperado == paquete original (47 bytes)
[OK] seq_num recuperado == 9
[OK] frag_flags recuperado == 0

6/6 casos aprobados
```

Salida completa: [`test_output.txt`](test_output.txt).

## Estado: ✅ Aprobada

**Fase 2 completa: 4/4.** Toda la cadena de software (sin SDR) queda
validada de punta a punta: `tun0` → MAC → FEC → MOD → OFDM (TX) → OFDM →
DEMOD → FEC → MAC → payload (RX), con el payload IP original recuperado
bit-exacto. Sigue la Fase 3 (loopback digital completo, mismo proceso, sin
SDR) — el mismo TX+RX pero ensamblado en un único flowgraph continuo en
vez de pasos separados como aquí.
