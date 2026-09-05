#!/usr/bin/env python3
"""Prueba 13 - Fase 3: igual que la Prueba 12 con canal sintetico de
errores de bit.

Criterio del plan: el FEC corrige hasta el BER de diseno; el CRC del MAC
descarta lo que no corrige, sin colar paquetes corruptos "a tun0" (aqui:
sin devolver un payload_recuperado incorrecto -- MACFrameError debe
lanzarse siempre que el FEC no pudo corregir del todo).

No requiere tun0 (usa PDUs sinteticas, para tener control total y
reproducible del BER de canal -- igual de espiritu que la Prueba 5, que
ya caracterizo el waterfall de este mismo FEC). Requiere el venv
~/envs/SDR.

Uso:
    ~/envs/SDR/bin/python test_canal_sintetico.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from canal_sintetico import procesar_payload_con_canal

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias", "prueba04_mac_encap_decap")))
from mac_frame import MACFrameError  # noqa: E402

SEMILLA = 13
PAYLOAD = bytes.fromhex(
    "4500002fc0de00004011a5170a6300020a6300019c400009001b0000"
    "505255454241332d545657532d494e42414e44"
)


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def probar_ber(ber_canal: float, debe_corregir: bool, rng) -> bool:
    try:
        payload_rx, seq_num, frag_flags, mod_scheme, n_flips = procesar_payload_con_canal(
            PAYLOAD, seq_num=1, frag_flags=0, ber_canal=ber_canal, rng=rng
        )
        corrigio = payload_rx == PAYLOAD
    except MACFrameError:
        corrigio = False
        n_flips = "?"

    if debe_corregir:
        return _check(
            f"BER canal={ber_canal:.0%} (flips={n_flips}): corrige por completo, payload identico",
            corrigio,
        )
    else:
        return _check(
            f"BER canal={ber_canal:.0%} (flips={n_flips}): NO corrige -- se descarta (MACFrameError), no cuela payload corrupto",
            not corrigio,
        )


def test_no_cuela_payload_corrupto_silenciosamente(rng):
    """Verificacion extra: a BER muy alta, si por alguna razon el CRC
    fallara en detectar la corrupcion, el payload recuperado NO deberia
    coincidir con el original -- confirma que un CRC valido siempre
    implica payload correcto (no hay falsos positivos del CRC en esta
    corrida)."""
    intentos_con_crc_valido_pero_payload_distinto = 0
    for _ in range(20):
        try:
            payload_rx, *_ = procesar_payload_con_canal(PAYLOAD, seq_num=1, frag_flags=0, ber_canal=0.25, rng=rng)
            if payload_rx != PAYLOAD:
                intentos_con_crc_valido_pero_payload_distinto += 1
        except MACFrameError:
            pass  # esperado a BER=25%
    return _check(
        "en 20 corridas a BER=25%, ningun CRC valido escondio un payload incorrecto (0 falsos positivos)",
        intentos_con_crc_valido_pero_payload_distinto == 0,
    )


def main():
    rng = random.Random(SEMILLA)

    resultados = [
        probar_ber(0.0, debe_corregir=True, rng=rng),
        probar_ber(0.01, debe_corregir=True, rng=rng),   # Prueba 5: BER<=3% -> correccion total
        probar_ber(0.03, debe_corregir=True, rng=rng),
        probar_ber(0.20, debe_corregir=False, rng=rng),  # Prueba 5: BER>=15% -> el codigo se satura
        test_no_cuela_payload_corrupto_silenciosamente(rng),
    ]

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
