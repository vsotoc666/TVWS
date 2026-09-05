#!/usr/bin/env python3
"""Prueba 6 - Fase 1: MOD/DEMOD round-trip.

bits -> simbolos -> bits, por separado para BPSK/QPSK/16-QAM, en canal
ideal (sin ruido). Criterio del plan: "constelacion correcta en canal
ideal".

Requiere el venv ~/envs/SDR (gnuradio.digital). No requiere tun0 ni sudo,
y no arma ningun top_block (ver constelaciones.py).

Uso:
    ~/envs/SDR/bin/python test_mod_demod_roundtrip.py
"""
import random
import sys

from constelaciones import ESQUEMAS, bits_a_chunks, chunks_a_bits, demodular, modular

SEMILLA = 123


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def test_round_trip_exhaustivo(nombre_esquema, constelacion):
    """Prueba TODOS los valores posibles de simbolo (no solo una muestra
    aleatoria) -- son pocos (2, 4 o 16), asi que se cubre el 100% de la
    tabla de mapeo bits<->punto."""
    k = constelacion.bits_per_symbol()
    todos_los_chunks = list(range(2 ** k))
    simbolos = modular(todos_los_chunks, constelacion)
    recuperados = demodular(simbolos, constelacion)
    return _check(
        f"{nombre_esquema}: round-trip exhaustivo de los {2 ** k} simbolos posibles",
        recuperados == todos_los_chunks,
    )


def test_round_trip_bitstream_aleatorio(nombre_esquema, constelacion, rng, n_bits=200):
    k = constelacion.bits_per_symbol()
    n_bits = (n_bits // k) * k  # ajustar a multiplo de k
    bits_originales = [rng.randint(0, 1) for _ in range(n_bits)]

    chunks = bits_a_chunks(bits_originales, k)
    simbolos = modular(chunks, constelacion)
    chunks_recuperados = demodular(simbolos, constelacion)
    bits_recuperados = chunks_a_bits(chunks_recuperados, k)

    return _check(
        f"{nombre_esquema}: round-trip de {n_bits} bits aleatorios (payload simulado)",
        bits_recuperados == bits_originales,
    )


def test_constelacion_bpsk(constelacion):
    puntos = constelacion.points()
    magnitudes = [abs(p) for p in puntos]
    return _check(
        "BPSK: 2 puntos, ambos de magnitud 1, en antifase (180 grados)",
        len(puntos) == 2
        and all(abs(m - 1.0) < 1e-6 for m in magnitudes)
        and abs(puntos[0] + puntos[1]) < 1e-6,
    )


def test_constelacion_qpsk(constelacion):
    puntos = constelacion.points()
    magnitudes = [abs(p) for p in puntos]
    mag_ref = magnitudes[0]
    return _check(
        "QPSK: 4 puntos, todos con la misma magnitud (modulo constante)",
        len(puntos) == 4 and all(abs(m - mag_ref) < 1e-6 for m in magnitudes),
    )


def test_constelacion_16qam(constelacion):
    puntos = constelacion.points()
    niveles_i = sorted({round(p.real, 4) for p in puntos})
    niveles_q = sorted({round(p.imag, 4) for p in puntos})
    simetrico_i = all(abs(niveles_i[i] + niveles_i[-1 - i]) < 1e-3 for i in range(len(niveles_i)))
    simetrico_q = all(abs(niveles_q[i] + niveles_q[-1 - i]) < 1e-3 for i in range(len(niveles_q)))
    return _check(
        "16-QAM: 16 puntos en grilla 4x4 (4 niveles I x 4 niveles Q), simetrica respecto al origen",
        len(puntos) == 16 and len(niveles_i) == 4 and len(niveles_q) == 4 and simetrico_i and simetrico_q,
    )


def main():
    rng = random.Random(SEMILLA)
    resultados = []

    for nombre, constelacion in ESQUEMAS.items():
        resultados.append(test_round_trip_exhaustivo(nombre, constelacion))
        resultados.append(test_round_trip_bitstream_aleatorio(nombre, constelacion, rng))

    resultados.append(test_constelacion_bpsk(ESQUEMAS["BPSK"]))
    resultados.append(test_constelacion_qpsk(ESQUEMAS["QPSK"]))
    resultados.append(test_constelacion_16qam(ESQUEMAS["16-QAM"]))

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
