# Prueba 6 — MOD/DEMOD round-trip

**Objetivo** (según el plan): `bits → símbolos → bits`, por separado para
BPSK/QPSK/16-QAM. Criterio: *"constelación correcta en canal ideal"*.

Requiere el venv `~/envs/SDR` (`gnuradio.digital`). No requiere `tun0` ni
`sudo`, y —a diferencia de las Pruebas 2/3/5— **no arma ningún
`gr.top_block`**: los objetos `constellation` de `gnuradio.digital` son
invocables directo desde Python puro.

Los tres esquemas (BPSK/QPSK/16-QAM) no son una elección hecha para esta
prueba — ya están fijados en `README.md` §5.3 (tabla de throughput por
modo). A diferencia de la Prueba 4 (header MAC) y la Prueba 5 (esquema
FEC), aquí no hubo que tomar ninguna decisión de arquitectura nueva.

## Qué hace `constelaciones.py`

- `ESQUEMAS`: los tres objetos de constelación de GNU Radio
  (`digital.constellation_bpsk/qpsk/16qam()`).
- `bits_a_chunks(bits, k)` / `chunks_a_bits(chunks, k)`: empaquetan una
  lista de bits en enteros de `k = bits_per_symbol()` bits (1 para BPSK, 2
  para QPSK, 4 para 16-QAM) y viceversa.
- `modular(chunks, constelacion)`: cada entero → su punto I/Q en el plano
  complejo, vía `constelacion.map_to_points_v(chunk)`.
- `demodular(simbolos, constelacion)`: cada punto I/Q → el entero más
  cercano en la tabla de la constelación, vía
  `constelacion.decision_maker_v([simbolo])`. En canal ideal (sin ruido,
  que es lo que exige el criterio de esta prueba) el símbolo recibido es
  exactamente el punto de la tabla, así que la decisión siempre acierta.

## Qué hace `test_mod_demod_roundtrip.py`

Para cada uno de los 3 esquemas:

1. **Round-trip exhaustivo**: en vez de probar con una muestra aleatoria,
   se recorren *todos* los símbolos posibles (2 para BPSK, 4 para QPSK, 16
   para 16-QAM — son pocos, cubrir el 100% de la tabla es barato) y se
   verifica que `demodular(modular(x)) == x` para cada uno.
2. **Round-trip con un bitstream aleatorio de 200 bits** (simulando un
   payload), para validar también el empaquetado/desempaquetado de bits en
   símbolos, no solo la tabla de mapeo símbolo↔entero.

Y 3 chequeos de geometría de la constelación en sí (el criterio "constelación
correcta"):

- **BPSK**: 2 puntos, ambos de magnitud 1, en antifase (180°).
- **QPSK**: 4 puntos, todos con el mismo módulo (constante — típico de PSK).
- **16-QAM**: 16 puntos en una grilla 4×4 (4 niveles en I, 4 en Q),
  simétrica respecto al origen.

## Resultado de la ejecución

```
[OK] BPSK: round-trip exhaustivo de los 2 simbolos posibles
[OK] BPSK: round-trip de 200 bits aleatorios (payload simulado)
[OK] QPSK: round-trip exhaustivo de los 4 simbolos posibles
[OK] QPSK: round-trip de 200 bits aleatorios (payload simulado)
[OK] 16-QAM: round-trip exhaustivo de los 16 simbolos posibles
[OK] 16-QAM: round-trip de 200 bits aleatorios (payload simulado)
[OK] BPSK: 2 puntos, ambos de magnitud 1, en antifase (180 grados)
[OK] QPSK: 4 puntos, todos con la misma magnitud (modulo constante)
[OK] 16-QAM: 16 puntos en grilla 4x4 (4 niveles I x 4 niveles Q), simetrica respecto al origen

9/9 casos aprobados
```

Salida completa: [`test_output.txt`](test_output.txt).

## Estado: ✅ Aprobada

Con esto quedan validados, de forma aislada, todos los bloques de
procesamiento de datos de la Fase 1 salvo uno: `tun0`/`tuntap_pdu`
(Pruebas 1-3), MAC (Prueba 4), FEC (Prueba 5) y MOD/DEMOD (Prueba 6). Sigue
la Prueba 7 (PDU↔Tagged Stream, ambos sentidos) — la última de la Fase 1,
que valida específicamente la frontera mensajes↔streaming antes de pasar a
la Fase 2 (integración por pares).
