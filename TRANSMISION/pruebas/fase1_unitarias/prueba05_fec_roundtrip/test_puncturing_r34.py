#!/usr/bin/env python3
"""Prueba 5 (extension) - Fase 1: tasa 3/4 via perforado (puncturing) del
mismo codigo madre K=7 tasa 1/2.

Decision de arquitectura (cerrada): CCSDS K=7 convolucional es la base
para BPSK/QPSK/16-QAM, con tasa 3/4 obtenida perforando la misma tasa 1/2
-- ver `claudedocs/arquitectura_enlace_datos.md` S4.3 y
`claudedocs/riesgos_arquitectura_transmision.md` Problema 3. Esta prueba:

1. Confirma round-trip perforado bit-exacto con CERO errores de canal
   inyectados -- puerta obligatoria antes de confiar en cualquier numero
   de BER (si esto no pasa, el patron de perforado o el relleno de
   erasure tiene un bug).
2. Construye una curva BER de canal -> BER post-decodificacion para tasa
   3/4 (perforada) y la compara con la curva ya medida en
   test_fec_roundtrip.py para tasa 1/2 (sin perforar). Resultado esperado
   y correcto: tasa 3/4 deja de corregir completamente a un BER de canal
   MENOR que tasa 1/2 (menos redundancia = menos capacidad de correccion)
   -- esto no es un bug, es el trade-off real de ganancia de codificacion
   vs. throughput que la tabla de S7.1 del doc de arquitectura ya asume
   que existe; el punto de esta prueba es poner un numero real en vez de
   uno teorico.

Requiere el venv ~/envs/SDR (gnuradio.fec). No requiere tun0 ni sudo.

Uso:
    ~/envs/SDR/bin/python test_puncturing_r34.py
"""
import random
import sys

from ccsds_fec import (
    codificar,
    decodificar,
    inyectar_errores,
    simbolos_a_soft,
    ber_bits,
    perforar,
    despuncturar,
    PATRON_PERFORADO_3_4,
)

# Mismo paquete UDP/IP sintetico de la Prueba 3, reusado como en
# test_fec_roundtrip.py.
PAQUETE_PRUEBA3 = bytes.fromhex(
    "4500002fc0de00004011a5170a6300020a6300019c400009001b0000"
    "505255454241332d545657532d494e42414e44"
)

SEMILLA = 123


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def _tx_r34(payload):
    """payload -> bits codificados (1/2) -> perforados (3/4)."""
    bits = codificar(payload)
    return bits, perforar(bits, PATRON_PERFORADO_3_4)


def _rx_r34(simbolos_punct_soft, n_bits_original, n_payload_bytes):
    """simbolos perforados (soft) -> despuncturados (relleno erasure=0.0)
    -> decodificados -> payload."""
    completo = despuncturar(simbolos_punct_soft, n_bits_original, PATRON_PERFORADO_3_4)
    return decodificar(completo, n_payload_bytes)


def test_patron_reduce_a_3_4():
    """El patron perfora exactamente 2 de cada 6 bits -> 4/6 = 2/3 de los
    bits de tasa 1/2 sobreviven. Relativo al payload original (que ya
    duplica bits en tasa 1/2), la tasa efectiva final es 3/4:
    k bits payload -> 2k bits (tasa 1/2) -> perforado a (2k * 2/3) bits.
    Para que esa cantidad final sea (4/3)k (= k / (3/4)), hace falta que
    el patron mantenga 4 de cada 6 bits (2/3), lo cual el patron elegido
    cumple: (True, True, True, False, True, False) mantiene posiciones
    0,1,2,4 (4 de 6) y perfora 3,5 (2 de 6)."""
    mantenidos = sum(1 for b in PATRON_PERFORADO_3_4 if b)
    perforados = len(PATRON_PERFORADO_3_4) - mantenidos
    ok = mantenidos == 4 and perforados == 2 and len(PATRON_PERFORADO_3_4) == 6
    return _check(
        f"patron perfora 2 de cada 6 bits (mantiene {mantenidos}/6) -> tasa 3/4",
        ok,
    )


def test_round_trip_bit_exacto_sin_errores():
    """Puerta obligatoria: sin esto, no se confia en ningun numero de BER
    de mas abajo."""
    bits, punct = _tx_r34(PAQUETE_PRUEBA3)
    soft_punct = simbolos_a_soft(punct)
    decodificado = _rx_r34(soft_punct, len(bits), len(PAQUETE_PRUEBA3))
    return _check(
        "round-trip perforado (3/4) bit-exacto sin errores de canal (payload de la Prueba 3)",
        decodificado == PAQUETE_PRUEBA3,
    )


def test_round_trip_bit_exacto_payload_grande(payload):
    bits, punct = _tx_r34(payload)
    soft_punct = simbolos_a_soft(punct)
    decodificado = _rx_r34(soft_punct, len(bits), len(payload))
    return _check(
        f"round-trip perforado (3/4) bit-exacto sin errores de canal (payload grande, {len(payload)}B)",
        decodificado == payload,
    )


def curva_ber_r12_vs_r34(payload, rng):
    """Barrido BER de canal -> BER post-decodificacion, tasa 1/2 (sin
    perforar) vs tasa 3/4 (perforada), sobre el MISMO patron de BER de
    canal para que la comparacion sea directa. Nota metodologica: el BER
    de canal se aplica sobre los simbolos ya perforados en el caso 3/4
    (es decir, es un BER de canal post-perforado, no pre-perforado) --
    modela el canal actuando sobre lo que realmente se transmite."""
    print("\n--- Curva BER de canal -> BER post-decode: tasa 1/2 vs tasa 3/4 ---")
    bits, punct = _tx_r34(payload)

    bers_canal = [0.0, 0.01, 0.03, 0.05, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.15, 0.20]
    filas = []
    for ber_canal in bers_canal:
        # Tasa 1/2 (sin perforar) -- mismo codigo de test_fec_roundtrip.py.
        con_errores_12, n_flips_12 = inyectar_errores(bits, ber_canal, rng)
        dec_12 = decodificar(simbolos_a_soft(con_errores_12), len(payload))
        ber_post_12 = ber_bits(dec_12, payload)

        # Tasa 3/4 (perforada) -- BER de canal sobre los bits YA perforados.
        con_errores_34, n_flips_34 = inyectar_errores(punct, ber_canal, rng)
        soft_34 = despuncturar(simbolos_a_soft(con_errores_34), len(bits), PATRON_PERFORADO_3_4)
        dec_34 = decodificar(soft_34, len(payload))
        ber_post_34 = ber_bits(dec_34, payload)

        linea = (
            f"BER canal={ber_canal:5.2f}  "
            f"R=1/2: flips={n_flips_12:5d}/{len(bits):5d} -> post-decode={ber_post_12:.5f}  |  "
            f"R=3/4: flips={n_flips_34:5d}/{len(punct):5d} -> post-decode={ber_post_34:.5f}"
        )
        print(linea)
        filas.append((ber_canal, ber_post_12, ber_post_34))

    return filas


def test_r34_falla_antes_que_r12(filas):
    """Confirma el trade-off esperado: al BER de canal donde R=1/2 sigue
    corrigiendo totalmente, R=3/4 ya deberia mostrar degradacion medible
    (o al reves nunca deberia pasar: R=3/4 nunca deberia corregir MEJOR
    que R=1/2 al mismo BER de canal, dado que tiene menos redundancia)."""
    ok = True
    peor_r34_en_algun_punto = False
    for ber_canal, post_12, post_34 in filas:
        if post_34 < post_12 - 1e-9:
            ok = False  # R=3/4 nunca deberia corregir mejor que R=1/2
        if post_34 > post_12 + 1e-9:
            peor_r34_en_algun_punto = True
    ok = ok and peor_r34_en_algun_punto
    return _check(
        "R=3/4 nunca corrige mejor que R=1/2, y es mediblemente peor en al menos un punto de la curva (coding-gain trade-off esperado)",
        ok,
    )


def main():
    rng_payload = random.Random(SEMILLA)
    payload_grande = bytes(rng_payload.randrange(256) for _ in range(2000))

    resultados = [test_patron_reduce_a_3_4()]
    resultados.append(test_round_trip_bit_exacto_sin_errores())
    resultados.append(test_round_trip_bit_exacto_payload_grande(payload_grande))

    rng_curva = random.Random(SEMILLA)
    filas = curva_ber_r12_vs_r34(payload_grande, rng_curva)
    resultados.append(test_r34_falla_antes_que_r12(filas))

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
