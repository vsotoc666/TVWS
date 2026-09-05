#!/usr/bin/env python3
"""Prueba 11 - Fase 2: RX completo aislado, alimentado con la salida de la
Prueba 10.

Criterio del plan: la cadena de recepcion reconstruye el payload original
sin RF de por medio. Cierra el circulo de la Fase 2: TX (Pruebas 8-10) ->
RX (esta prueba), conectados directo (sin canal, sin SDR).

Requiere el venv ~/envs/SDR. No requiere tun0 ni sudo.

Uso:
    ~/envs/SDR/bin/python test_rx_completo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rx_chain import frame_mac_a_payload, ofdm_a_frame_mac

_FASE2 = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE2, "prueba09_mac_fec_mod_stream")))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE2, "prueba10_ofdm_tx")))
from cadena import payload_a_simbolos  # noqa: E402
from flowgraph_prueba09 import PAQUETE_PRUEBA3  # noqa: E402
from ofdm_symbol import dividir_en_simbolos_ofdm, ifft_mas_cp  # noqa: E402

SEQ_NUM = 9
FRAG_FLAGS = 0
BITS_CONTROL = (1, 0, 1)


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def main():
    # --- TX: exactamente la misma cadena de las Pruebas 9 y 10 ---
    frame_mac_original, bits_codificados, simbolos_bpsk = payload_a_simbolos(
        PAQUETE_PRUEBA3, SEQ_NUM, FRAG_FLAGS
    )
    simbolos_freq = dividir_en_simbolos_ofdm(simbolos_bpsk, BITS_CONTROL)
    simbolos_tiempo = [ifft_mas_cp(v) for v in simbolos_freq]
    print(f"[prueba11] TX: {len(simbolos_tiempo)} simbolos OFDM generados (Pruebas 9-10)")

    # --- RX: alimentado DIRECTO con la salida del TX, sin canal ni SDR ---
    frame_mac_recuperado, control_por_simbolo = ofdm_a_frame_mac(
        simbolos_tiempo, n_simbolos_datos=len(simbolos_bpsk), n_bytes_frame_mac=len(frame_mac_original)
    )
    print(f"[prueba11] RX: frame MAC recuperado ({len(frame_mac_recuperado)} bytes)")

    resultados = []
    resultados.append(_check("frame MAC recuperado == frame MAC original (bit exacto)", frame_mac_recuperado == frame_mac_original))
    resultados.append(_check(
        f"control recuperado == {BITS_CONTROL} en los {len(control_por_simbolo)} simbolos OFDM",
        all(c == BITS_CONTROL for c in control_por_simbolo),
    ))

    try:
        payload_recuperado, seq_num, frag_flags, mod_scheme = frame_mac_a_payload(frame_mac_recuperado)
        resultados.append(_check("mac_frame.decapsular(): CRC valido", True))
    except Exception as e:
        resultados.append(_check(f"mac_frame.decapsular(): CRC valido ({e})", False))
        payload_recuperado, seq_num, frag_flags = None, None, None

    resultados.append(_check(f"payload recuperado == paquete original ({len(PAQUETE_PRUEBA3)} bytes)", payload_recuperado == PAQUETE_PRUEBA3))
    resultados.append(_check(f"seq_num recuperado == {SEQ_NUM}", seq_num == SEQ_NUM))
    resultados.append(_check(f"frag_flags recuperado == {FRAG_FLAGS}", frag_flags == FRAG_FLAGS))

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
