"""Igual que la Prueba 12 (loopback_block.procesar_payload), pero con un
canal sintetico de errores de bit inyectado ANTES de modular -- reusa
`ccsds_fec.inyectar_errores` tal cual la Prueba 5 ya la valido (voltea una
fraccion ber_canal de los bits codificados por el FEC). Para BPSK, cada
bit codificado se modula 1:1 a un simbolo (+-1), asi que voltear el bit
antes de modular es equivalente a que el canal corrompa el simbolo
recibido -- mismo mecanismo, no uno nuevo.
"""
import os
import sys

_FASE1 = os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias")
_FASE2 = os.path.join(os.path.dirname(__file__), "..", "..", "fase2_integracion_por_pares")
_FASE3 = os.path.dirname(os.path.dirname(__file__))
for _p in (
    os.path.join(_FASE1, "prueba04_mac_encap_decap"),
    os.path.join(_FASE1, "prueba05_fec_roundtrip"),
    os.path.join(_FASE1, "prueba06_mod_demod_roundtrip"),
    os.path.join(_FASE2, "prueba10_ofdm_tx"),
    os.path.join(_FASE2, "prueba11_rx_completo"),
    os.path.join(_FASE3, "prueba12_txrx_loopback_tun0"),
):
    sys.path.insert(0, os.path.abspath(_p))

from mac_frame import MOD_BPSK, encapsular  # noqa: E402  (MACFrameError se deja pasar a quien llama)
from ccsds_fec import codificar as fec_codificar  # noqa: E402
from ccsds_fec import inyectar_errores  # noqa: E402
from loopback_block import BITS_CONTROL_DEFAULT, BPSK  # noqa: E402
from ofdm_symbol import dividir_en_simbolos_ofdm, ifft_mas_cp  # noqa: E402
from rx_chain import frame_mac_a_payload, ofdm_a_frame_mac  # noqa: E402
from constelaciones import modular  # noqa: E402


def procesar_payload_con_canal(payload: bytes, seq_num: int, frag_flags: int, ber_canal: float, rng):
    """Como loopback_block.procesar_payload(), pero voltea una fraccion
    ber_canal de los bits codificados por el FEC antes de modular/OFDM.
    Devuelve (payload_recuperado, seq_num_rx, frag_flags_rx, mod_scheme_rx,
    n_bits_volteados). Lanza MACFrameError si el CRC no valida."""
    frame_mac = encapsular(payload, seq_num, frag_flags, MOD_BPSK)
    bits_codificados = fec_codificar(frame_mac)

    bits_con_errores, n_flips = inyectar_errores(bits_codificados, ber_canal, rng)

    simbolos_bpsk = modular(bits_con_errores, BPSK)
    simbolos_freq = dividir_en_simbolos_ofdm(simbolos_bpsk, BITS_CONTROL_DEFAULT)
    simbolos_tiempo = [ifft_mas_cp(v) for v in simbolos_freq]

    frame_mac_recuperado, _control = ofdm_a_frame_mac(
        simbolos_tiempo, n_simbolos_datos=len(simbolos_bpsk), n_bytes_frame_mac=len(frame_mac)
    )
    payload_recuperado, seq_num_rx, frag_flags_rx, mod_scheme_rx = frame_mac_a_payload(frame_mac_recuperado)
    return payload_recuperado, seq_num_rx, frag_flags_rx, mod_scheme_rx, n_flips
