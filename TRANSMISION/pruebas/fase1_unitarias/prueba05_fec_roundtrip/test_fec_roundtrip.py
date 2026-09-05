#!/usr/bin/env python3
"""Prueba 5 - Fase 1: FEC round-trip.

bits -> codificado -> bits, con y sin errores inyectados. Criterio del
plan: "el decodificador corrige hasta el limite esperado, no antes".
Como no hay un numero de BER de diseno fijado en ningun doc todavia, esta
prueba caracteriza empiricamente la curva de correccion del codigo
CCSDS K=7 tasa 1/2 (waterfall) y fija los umbrales de aprobado/fallo sobre
esa medicion, no sobre una cifra de especificacion que no existe aun.

Requiere el venv ~/envs/SDR (gnuradio.fec). No requiere tun0 ni sudo.

Uso:
    ~/envs/SDR/bin/python test_fec_roundtrip.py
"""
import random
import sys

from ccsds_fec import codificar, decodificar, inyectar_errores, simbolos_a_soft, ber_bits

# El mismo paquete UDP/IP sintetico de la Prueba 3, reusado como payload
# realista (un frame MAC ya armado, tal como lo entregaria la Prueba 4).
PAQUETE_PRUEBA3 = bytes.fromhex(
    "4500002fc0de00004011a5170a6300020a6300019c400009001b0000"
    "505255454241332d545657532d494e42414e44"
)

SEMILLA = 123


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def test_round_trip_sin_errores():
    simbolos = codificar(PAQUETE_PRUEBA3)
    decodificado = decodificar(simbolos_a_soft(simbolos), len(PAQUETE_PRUEBA3))
    return _check("round-trip sin errores de canal (payload de la Prueba 3)", decodificado == PAQUETE_PRUEBA3)


def test_corrige_dentro_del_margen(ber_canal, payload, rng):
    simbolos = codificar(payload)
    con_errores, n_flips = inyectar_errores(simbolos, ber_canal, rng)
    decodificado = decodificar(simbolos_a_soft(con_errores), len(payload))
    ok = decodificado == payload
    return _check(
        f"corrige por completo BER de canal={ber_canal:.0%} ({n_flips} bits volteados de {len(simbolos)})",
        ok,
    )


def test_falla_fuera_del_margen(ber_canal, payload, rng):
    simbolos = codificar(payload)
    con_errores, n_flips = inyectar_errores(simbolos, ber_canal, rng)
    decodificado = decodificar(simbolos_a_soft(con_errores), len(payload))
    ber_residual = ber_bits(decodificado, payload)
    # No se espera correccion total: confirma que el codigo se satura mas
    # alla de su capacidad, en vez de "corregir" silenciosamente cualquier cosa.
    return _check(
        f"NO corrige BER de canal={ber_canal:.0%} (BER residual={ber_residual:.1%}, esperado > 20%)",
        ber_residual > 0.20,
    )


def caracterizar_waterfall(payload, rng):
    """Barrido de BER de canal -> BER post-decodificacion. Evidencia para
    el README, no es un caso pass/fail."""
    print("\n--- Caracterizacion (BER canal -> BER post-decode) ---")
    simbolos = codificar(payload)
    lineas = []
    for ber_canal in [0.0, 0.01, 0.03, 0.05, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.15, 0.20]:
        con_errores, n_flips = inyectar_errores(simbolos, ber_canal, rng)
        decodificado = decodificar(simbolos_a_soft(con_errores), len(payload))
        ber_residual = ber_bits(decodificado, payload)
        linea = (
            f"BER canal={ber_canal:5.2f} (flips={n_flips:5d}/{len(simbolos)})  "
            f"->  BER post-decode={ber_residual:.5f}"
        )
        print(linea)
        lineas.append(linea)
    return lineas


def main():
    rng_payload = random.Random(SEMILLA)
    payload_grande = bytes(rng_payload.randrange(256) for _ in range(2000))

    resultados = [test_round_trip_sin_errores()]

    rng_errores = random.Random(SEMILLA)
    resultados.append(test_corrige_dentro_del_margen(0.01, payload_grande, rng_errores))
    resultados.append(test_corrige_dentro_del_margen(0.03, payload_grande, rng_errores))
    resultados.append(test_falla_fuera_del_margen(0.20, payload_grande, rng_errores))

    rng_curva = random.Random(SEMILLA)
    caracterizar_waterfall(payload_grande, rng_curva)

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
