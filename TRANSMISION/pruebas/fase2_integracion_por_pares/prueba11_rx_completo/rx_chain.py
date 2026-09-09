"""Cadena RX completa: OFDM (quitar CP+FFT) -> DEMOD -> FEC decode -> MAC
decap, alimentada directo con la salida de la Prueba 10 (sin RF, sin SDR,
sin canal). Es el espejo exacto de la cadena TX de las Pruebas 9-10, y
reutiliza literalmente los mismos modulos -- no reimplementa nada.

En un receptor real, la cantidad de simbolos de datos validos (sin el
relleno de ceros del ultimo simbolo OFDM) y el largo del frame MAC se
conocen por el framing (tags de longitud, Prueba 7) o por un campo de
longitud en el propio protocolo -- no adivinandolo de la estructura OFDM.
Esta prueba recibe esos dos tamanos como parametro (n_simbolos_datos,
n_bytes_frame_mac), igual que lo haria un `packet_len` tag real.

Extrae datos usando DATOS_IDX_POR_OFFSET[indice_simbolo % 8] (patron de
pilotos escalonado, ver ofdm_symbol.py) -- cada simbolo OFDM del ciclo de
8 tiene un subconjunto distinto de posiciones piloto, asi que hay que
excluir las posiciones correctas segun el offset real de CADA simbolo, no
un DATOS_IDX fijo. No implementa ecualizacion con los pilotos todavia
(fuera de alcance, trabajo de Fase 4) -- solo evita tratar pilotos como
datos.
"""
import os
import sys

_FASE1 = os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias")
_FASE2 = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE1, "prueba04_mac_encap_decap")))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE1, "prueba05_fec_roundtrip")))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE1, "prueba06_mod_demod_roundtrip")))
sys.path.insert(0, os.path.abspath(os.path.join(_FASE2, "prueba10_ofdm_tx")))

from mac_frame import MACFrameError, decapsular  # noqa: E402
from ccsds_fec import decodificar  # noqa: E402
from constelaciones import ESQUEMAS  # noqa: E402
from ofdm_symbol import CONTROL_IDX, CONTROL_EVITADA, DATOS_IDX_POR_OFFSET, PILOTO_STRIDE, quitar_cp_y_fft  # noqa: E402

_BPSK = ESQUEMAS["BPSK"]


def extraer_control(vector_freq) -> tuple:
    """#254/#256/#257 -> 3 bits (BPSK). #255 se ignora (evitada, ver Prueba 10)."""
    bits = []
    for idx in CONTROL_IDX:
        if idx == CONTROL_EVITADA:
            continue
        bits.append(_BPSK.decision_maker_v([vector_freq[idx]]))
    return tuple(bits)


def ofdm_a_frame_mac(simbolos_tiempo: list, n_simbolos_datos: int, n_bytes_frame_mac: int):
    """simbolos OFDM en tiempo (con CP) -> (frame_mac recuperado, lista de
    tuplas de control por simbolo OFDM)."""
    datos_recuperados = []
    control_por_simbolo = []

    for indice_simbolo, simbolo in enumerate(simbolos_tiempo):
        vector_freq = quitar_cp_y_fft(simbolo)
        control_por_simbolo.append(extraer_control(vector_freq))
        offset = indice_simbolo % PILOTO_STRIDE
        for idx in DATOS_IDX_POR_OFFSET[offset]:
            datos_recuperados.append(vector_freq[idx])

    datos_recuperados = datos_recuperados[:n_simbolos_datos]  # descarta el relleno de ceros

    # OJO: NO se demodula a bits duros aqui. decode_ccsds_27_fb (Prueba 5)
    # espera los simbolos "blandos" (float, +-1.0) tal como los definio la
    # propia Prueba 9 al modular los bits codificados del FEC con BPSK --
    # para BPSK, "demodular" y "extraer el simbolo blando para el FEC" son
    # el mismo numero. Pasarlos por un demodulador duro (0/1) primero y
    # reinterpretarlos como floats corrompe la convencion de signo que
    # espera el decodificador Viterbi (ver docstring de decode_ccsds_27_fb
    # en ccsds_fec.py: simbolo 0 -> -1.0, simbolo 1 -> +1.0).
    simbolos_soft = [s.real for s in datos_recuperados]

    frame_mac = decodificar(simbolos_soft, n_bytes_frame_mac)
    return frame_mac, control_por_simbolo


def frame_mac_a_payload(frame_mac: bytes):
    """Reusa mac_frame.decapsular() de la Prueba 4. Deja pasar
    MACFrameError si el CRC no valida (no la esconde)."""
    return decapsular(frame_mac)
