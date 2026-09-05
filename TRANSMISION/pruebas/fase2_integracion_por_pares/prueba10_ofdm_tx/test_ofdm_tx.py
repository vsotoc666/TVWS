#!/usr/bin/env python3
"""Prueba 10 - Fase 2: TX completo hasta antes del SDR (incluye IFFT+CP).

Criterio del plan: estructura del simbolo OFDM correcta -- guardas en
cero, subportadoras de control en su indice, CP de longitud correcta.

Encadena la salida de la Prueba 9 (simbolos BPSK ya moduladados, via
MAC->FEC->MOD) con el Carrier Allocator + IFFT + CP de esta prueba.

Requiere el venv ~/envs/SDR (numpy + la cadena de la Prueba 9). No
requiere tun0 ni sudo.

Uso:
    ~/envs/SDR/bin/python test_ofdm_tx.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from ofdm_symbol import (
    CONTROL_EVITADA,
    CONTROL_IDX,
    CP_LEN,
    DATOS_IDX,
    FFT_LEN,
    GUARDA_INF,
    GUARDA_SUP,
    N_DATOS_POR_SIMBOLO,
    armar_simbolo_ofdm,
    dividir_en_simbolos_ofdm,
    ifft_mas_cp,
    quitar_cp_y_fft,
)

_PRUEBA09 = os.path.join(os.path.dirname(__file__), "..", "prueba09_mac_fec_mod_stream")
sys.path.insert(0, os.path.abspath(_PRUEBA09))
from cadena import payload_a_simbolos  # noqa: E402
from flowgraph_prueba09 import PAQUETE_PRUEBA3  # noqa: E402

BITS_CONTROL = (1, 0, 1)  # placeholder fijo -- InbandControlTX no esta implementado todavia


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def test_guardas_en_cero(simbolos_freq):
    ok = True
    for i, vec in enumerate(simbolos_freq):
        for idx in list(GUARDA_INF) + list(GUARDA_SUP):
            ok = ok and vec[idx] == 0j
    return _check(
        f"guardas (indices 0-25 y 487-511) en cero en los {len(simbolos_freq)} simbolos OFDM",
        ok,
    )


def test_control_en_indice_correcto(simbolos_freq):
    b254, b256, b257 = BITS_CONTROL
    esperado = {254: (1.0 if b254 else -1.0), 255: 0.0, 256: (1.0 if b256 else -1.0), 257: (1.0 if b257 else -1.0)}
    ok = True
    for vec in simbolos_freq:
        for idx in CONTROL_IDX:
            ok = ok and vec[idx] == esperado[idx]
    return _check(
        f"subportadoras de control (#254/#256/#257=BPSK del mensaje, #{CONTROL_EVITADA} evitada=0) en su indice",
        ok,
    )


def test_datos_no_tocan_guardas_ni_control(simbolos_freq, simbolos_esperados):
    """Los simbolos de datos deben caer EXACTO en DATOS_IDX, ni uno mas
    ni uno menos, sin pisar guardas ni control."""
    ok = True
    puntero = 0
    for vec in simbolos_freq:
        chunk = simbolos_esperados[puntero:puntero + N_DATOS_POR_SIMBOLO]
        for pos, idx in enumerate(DATOS_IDX):
            esperado = chunk[pos] if pos < len(chunk) else 0j
            ok = ok and vec[idx] == esperado
        puntero += N_DATOS_POR_SIMBOLO
    return _check(
        "simbolos de datos ubicados exacto en los slots de datos (sin pisar guardas/control)",
        ok,
    )


def test_longitud_simbolo_y_cp(simbolos_tiempo):
    ok = all(len(s) == FFT_LEN + CP_LEN for s in simbolos_tiempo)
    return _check(f"cada simbolo OFDM con CP mide {FFT_LEN}+{CP_LEN}={FFT_LEN + CP_LEN} muestras", ok)


def test_cp_es_copia_de_la_cola(simbolos_tiempo):
    """El prefijo ciclico, por definicion, es una copia exacta de las
    ultimas CP_LEN muestras del simbolo IFFT -- no basta con que mida
    128 muestras, tienen que ser las correctas."""
    ok = True
    for s in simbolos_tiempo:
        cp = s[:CP_LEN]
        cola = s[CP_LEN:][-CP_LEN:]
        ok = ok and np.allclose(cp, cola)
    return _check("el CP es copia exacta de la cola del simbolo IFFT (no solo la longitud)", ok)


def test_round_trip_quitar_cp_y_fft(simbolos_tiempo, simbolos_freq):
    ok = True
    for s_tiempo, s_freq in zip(simbolos_tiempo, simbolos_freq):
        recuperado = quitar_cp_y_fft(s_tiempo)
        ok = ok and np.allclose(recuperado, s_freq, atol=1e-9)
    return _check("round-trip (quitar CP + FFT) recupera el vector de frecuencia original", ok)


def main():
    _, _, simbolos_bpsk = payload_a_simbolos(PAQUETE_PRUEBA3, seq_num=9, frag_flags=0)
    print(f"[prueba10] {len(simbolos_bpsk)} simbolos BPSK de entrada (Prueba 9)")

    simbolos_freq = dividir_en_simbolos_ofdm(simbolos_bpsk, BITS_CONTROL)
    print(f"[prueba10] repartidos en {len(simbolos_freq)} simbolos OFDM ({N_DATOS_POR_SIMBOLO} datos c/u)")

    simbolos_tiempo = [ifft_mas_cp(v) for v in simbolos_freq]

    resultados = [
        test_guardas_en_cero(simbolos_freq),
        test_control_en_indice_correcto(simbolos_freq),
        test_datos_no_tocan_guardas_ni_control(simbolos_freq, simbolos_bpsk),
        test_longitud_simbolo_y_cp(simbolos_tiempo),
        test_cp_es_copia_de_la_cola(simbolos_tiempo),
        test_round_trip_quitar_cp_y_fft(simbolos_tiempo, simbolos_freq),
    ]

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
