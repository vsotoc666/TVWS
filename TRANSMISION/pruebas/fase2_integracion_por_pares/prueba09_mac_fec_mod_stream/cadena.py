"""Cadena MAC -> FEC -> MOD, reutilizando literalmente los modulos ya
validados en Fase 1 (Pruebas 4, 5 y 6). Prueba 9 es integracion: no
reimplementa nada de esto, solo los encadena.

    payload (IP crudo) -> mac_frame.encapsular() -> ccsds_fec.codificar()
        -> constelaciones.modular() -> lista de simbolos I/Q (gr_complex)

Esquema fijo para esta prueba: BPSK (mod_scheme=MOD_BPSK), la misma
combinacion FEC+modulacion que ya se valido en la Prueba 5 (CCSDS K=7 R=1/2
+ BPSK = el objetivo conservador de README.md S5.3). bits_per_symbol=1 en
BPSK hace que cada bit codificado por el FEC sea directamente un simbolo,
sin necesidad de agrupar bits.
"""
import os
import sys

_FASE1 = os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias")
sys.path.insert(0, os.path.abspath(os.path.join(_FASE1, "prueba04_mac_encap_decap")))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE1, "prueba05_fec_roundtrip")))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE1, "prueba06_mod_demod_roundtrip")))

from mac_frame import MOD_BPSK, encapsular  # noqa: E402
from ccsds_fec import codificar  # noqa: E402
from constelaciones import ESQUEMAS, modular  # noqa: E402


def payload_a_simbolos(payload: bytes, seq_num: int, frag_flags: int, mod_scheme: int = MOD_BPSK):
    """Devuelve (frame_mac, bits_codificados, simbolos) -- los tres pasos
    intermedios, para poder verificar cada frontera por separado."""
    if mod_scheme != MOD_BPSK:
        raise NotImplementedError("Prueba 9 solo cablea la ruta BPSK (la validada en la Prueba 5)")

    frame_mac = encapsular(payload, seq_num, frag_flags, mod_scheme)
    bits_codificados = codificar(frame_mac)  # 0/1 por bit, ya con el padding de flush del FEC
    simbolos = modular(bits_codificados, ESQUEMAS["BPSK"])  # bits_per_symbol=1: cada bit es 1 simbolo
    return frame_mac, bits_codificados, simbolos
