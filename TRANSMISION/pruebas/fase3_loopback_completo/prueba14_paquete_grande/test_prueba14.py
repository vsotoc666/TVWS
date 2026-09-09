#!/usr/bin/env python3
"""Prueba 14 - Fase 3: paquete IP mas grande que el payload util de un
slot TDD -- fragmentacion/reensamblado real.

Rehecha per `claudedocs/arquitectura_enlace_datos.md` S2.4: la version
anterior de esta prueba confirmo que un frame MAC monolitico de 1400B
necesita 50 simbolos OFDM a BPSK R=1/2, y que eso no era un problema
mientras no existiera framing TDD (un frame podia extenderse a cuantos
simbolos hiciera falta). Con el slot TDD ya decidido (20 simbolos OFDM,
~1.78 ms, S2.1), 50 simbolos no caben en un slot -- hace falta
fragmentar. Esta version valida el escenario real: fragmentar el payload
de 1400B en trozos que si quepan cada uno en un slot, transmitir/recibir
cada fragmento por la cadena TX/RX ya validada, y reensamblar via
mac_frame.reensamblar().

No requiere tun0 ni sudo. Requiere el venv ~/envs/SDR.

Uso:
    ~/envs/SDR/bin/python test_prueba14.py
"""
import math
import os
import sys

_FASE1 = os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias")
_FASE2 = os.path.join(os.path.dirname(__file__), "..", "..", "fase2_integracion_por_pares")
for _p in (
    os.path.join(_FASE1, "prueba04_mac_encap_decap"),
    os.path.join(_FASE1, "prueba05_fec_roundtrip"),
    os.path.join(_FASE1, "prueba06_mod_demod_roundtrip"),
    os.path.join(_FASE2, "prueba10_ofdm_tx"),
    os.path.join(_FASE2, "prueba11_rx_completo"),
):
    sys.path.insert(0, os.path.abspath(_p))

from mac_frame import MOD_BPSK, encapsular, fragmentar, reensamblar  # noqa: E402
from ccsds_fec import codificar as fec_codificar, PAD_BYTES  # noqa: E402
from constelaciones import ESQUEMAS, modular  # noqa: E402
from ofdm_symbol import N_DATOS_POR_SIMBOLO_POR_OFFSET, dividir_en_simbolos_ofdm, ifft_mas_cp  # noqa: E402
from rx_chain import frame_mac_a_payload, ofdm_a_frame_mac  # noqa: E402

BPSK = ESQUEMAS["BPSK"]
BITS_CONTROL = (1, 1, 0)

MAC_OVERHEAD_BYTES = 5  # seq_num(1) + frag_flags(1) + mod_scheme(1) + crc16(2), ver mac_frame.py

# --- Presupuesto de slot TDD (claudedocs/arquitectura_enlace_datos.md S2.1/S2.4) ---
SIMBOLOS_POR_SLOT = 20

# El umbral exacto de corte (18 vs 20 simbolos) queda explicitamente como
# "detalle de implementacion" en S2.4. Se elige 18/20 (10% de margen bajo
# el presupuesto completo del slot) para no quedar al limite exacto del
# slot -- evita que un fragmento que calza justo en el peor caso teorico
# termine, por redondeo o por un simbolo de control adicional en el
# futuro, empujando al fragmento fuera del slot. 18 sigue siendo un
# numero "redondo" simple de justificar, no una optimizacion fina.
MARGEN_SIMBOLOS = 18

# Patron de pilotos escalonado (stride 8, ver ofdm_symbol.py): la capacidad
# de datos por simbolo OFDM ya no es constante (399 en offset 0, 400 en
# offsets 1-7). Para el calculo conservador de max_frame_bytes se usa el
# PEOR caso (offset 0, 399) -- así el limite de frame nunca sobreestima el
# espacio real disponible, sin importar en que offset del ciclo de 8
# empiece a transmitirse el frame.
N_DATOS_PEOR_CASO = min(N_DATOS_POR_SIMBOLO_POR_OFFSET.values())


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def max_payload_por_fragmento(presupuesto_simbolos: int) -> int:
    """Bytes de payload IP (antes del header MAC) que caben en
    `presupuesto_simbolos` simbolos OFDM, a BPSK R=1/2, calculado con las
    constantes reales de este codebase (no la aproximacion ~28 bytes/
    simbolo de la tabla del doc de arquitectura, que esta "escalada desde
    la medicion", no calculada exacta):

        coded_bits = (frame_mac_bytes + PAD_BYTES) * 16   (FEC R=1/2, 8 bits/byte * 2)
        frame_mac_bytes = payload_bytes + MAC_OVERHEAD_BYTES
        n_simbolos = ceil(coded_bits / N_DATOS_POR_SIMBOLO)

    Se despeja el maximo payload_bytes tal que n_simbolos <= presupuesto_simbolos.

    Usa N_DATOS_PEOR_CASO (399, offset 0 del patron de pilotos escalonado)
    en vez de una capacidad fija -- ver comentario junto a N_DATOS_PEOR_CASO
    mas arriba."""
    max_frame_bytes = (presupuesto_simbolos * N_DATOS_PEOR_CASO) // 16 - PAD_BYTES
    return max_frame_bytes - MAC_OVERHEAD_BYTES


def procesar_frame(frame_mac: bytes):
    """TX (FEC->modula->OFDM) + RX (OFDM->demod->FEC) de un frame MAC ya
    encapsulado. Devuelve (frame_mac_recuperado, n_simbolos_ofdm)."""
    bits_codificados = fec_codificar(frame_mac)
    simbolos_bpsk = modular(bits_codificados, BPSK)
    simbolos_freq = dividir_en_simbolos_ofdm(simbolos_bpsk, BITS_CONTROL)
    simbolos_tiempo = [ifft_mas_cp(v) for v in simbolos_freq]

    frame_mac_recuperado, _control = ofdm_a_frame_mac(
        simbolos_tiempo, n_simbolos_datos=len(simbolos_bpsk), n_bytes_frame_mac=len(frame_mac)
    )
    return frame_mac_recuperado, len(simbolos_freq)


# Payload deterministico de 1400 bytes (tamano tipico de "paquete grande",
# ej. el default de muchas pruebas de MTU/`ping -s 1400`). Determinístico
# (no random) para que la prueba sea reproducible byte a byte.
PAYLOAD_GRANDE = bytes((i * 37 + 11) % 256 for i in range(1400))


def main():
    print(f"[prueba14] payload de prueba: {len(PAYLOAD_GRANDE)} bytes")
    print(f"[prueba14] capacidad de un simbolo OFDM (peor caso, offset 0): {N_DATOS_PEOR_CASO} bits codificados")
    print(f"[prueba14] presupuesto de slot TDD: {SIMBOLOS_POR_SLOT} simbolos (~1.78 ms), umbral de corte usado: {MARGEN_SIMBOLOS} simbolos")

    max_payload = max_payload_por_fragmento(MARGEN_SIMBOLOS)
    print(f"[prueba14] max bytes de payload IP por fragmento (a {MARGEN_SIMBOLOS} simbolos, BPSK R=1/2): {max_payload}")

    resultados = []

    # --- Escenario 1 (contraste/regresion): frame monolitico sin fragmentar ---
    # Sigue siendo cierto que la capa OFDM en si no impone limite -- se
    # mantiene como caso de regresion, pero ya no es el criterio de exito.
    frame_monolitico = encapsular(PAYLOAD_GRANDE, seq_num=42, frag_flags=0, mod_scheme=MOD_BPSK)
    frame_mono_recuperado, n_simbolos_mono = procesar_frame(frame_monolitico)
    payload_mono_recuperado, seq_num_mono, _frag_flags, _mod = frame_mac_a_payload(frame_mono_recuperado)
    resultados.append(_check(
        f"[contraste] frame monolitico de {len(PAYLOAD_GRANDE)}B sigue ocupando {n_simbolos_mono} simbolos (>1 slot, como antes)",
        n_simbolos_mono > SIMBOLOS_POR_SLOT,
    ))
    resultados.append(_check(
        "[contraste] frame monolitico sigue recuperando el payload bit-exacto (la capa OFDM no tiene limite propio)",
        payload_mono_recuperado == PAYLOAD_GRANDE,
    ))

    # --- Escenario 2 (el que importa): fragmentado, cada trozo cabe en 1 slot ---
    fragmentos = fragmentar(PAYLOAD_GRANDE, seq_num=42, mod_scheme=MOD_BPSK, max_bytes_por_fragmento=max_payload)
    print(f"[prueba14] {len(fragmentos)} fragmentos generados para {len(PAYLOAD_GRANDE)}B")

    resultados.append(_check(f"se generó más de 1 fragmento ({len(fragmentos)})", len(fragmentos) > 1))

    frames_recuperados = []
    todos_caben = True
    for i, frag in enumerate(fragmentos):
        frame_recuperado, n_simbolos = procesar_frame(frag)
        frames_recuperados.append(frame_recuperado)
        cabe = n_simbolos <= SIMBOLOS_POR_SLOT
        todos_caben = todos_caben and cabe
        print(f"[prueba14]   fragmento {i}: {len(frag)}B de frame MAC -> {n_simbolos} simbolos OFDM ({'cabe' if cabe else 'NO CABE'} en {SIMBOLOS_POR_SLOT})")

    resultados.append(_check(f"los {len(fragmentos)} fragmentos caben cada uno en <= {SIMBOLOS_POR_SLOT} simbolos (1 slot TDD)", todos_caben))

    payload_reensamblado = reensamblar(frames_recuperados)
    resultados.append(_check(
        "reensamblar() sobre los fragmentos recuperados por TX+RX == payload original, bit exacto",
        payload_reensamblado == PAYLOAD_GRANDE,
    ))

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")

    print(
        "\n[hallazgo] Con el framing TDD decidido (slot de 20 simbolos OFDM, "
        "claudedocs/arquitectura_enlace_datos.md S2.1), un frame MAC monolitico "
        "de 1400B (50 simbolos) YA NO cabe en un slot. La fragmentacion via "
        "mac_frame.fragmentar()/reensamblar() (S2.4: seq_num como ID de PDU + "
        "bit MF en frag_flags) resuelve esto: fragmentando a un maximo de "
        f"{max_payload} bytes de payload por fragmento (umbral de {MARGEN_SIMBOLOS} "
        "simbolos, con margen bajo el presupuesto completo del slot), cada "
        "fragmento del paquete de 1400B cabe en su slot y el PDU se reensambla "
        "bit-exacto en el receptor."
    )

    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
