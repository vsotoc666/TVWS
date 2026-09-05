"""Bloque GNU Radio de mensajes que ejecuta la cadena TX+RX completa
(MAC->FEC->MOD->OFDM->OFDM->FEC->MOD->MAC) sobre cada PDU que recibe, sin
canal de por medio (el "cable" entre TX y RX es una lista de Python, no
RF). Es la Prueba 12 del plan: "TX->RX conectados directo (vector, sin
canal)".

No reimplementa nada: reutiliza literalmente los modulos ya validados
en Fase 1 (mac_frame, ccsds_fec, constelaciones) y Fase 2
(ofdm_symbol, rx_chain).

La version con canal sintetico de errores de bit (Prueba 13) vive aparte,
en `fase3_loopback_completo/prueba13_canal_sintetico/`, reusando estas
mismas piezas -- no se mezcla aqui para no complicar el caso base.
"""
import os
import sys
import time

import pmt
from gnuradio import gr

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

from mac_frame import MOD_BPSK, MACFrameError, encapsular  # noqa: E402
from ccsds_fec import codificar as fec_codificar  # noqa: E402
from constelaciones import ESQUEMAS, modular  # noqa: E402
from ofdm_symbol import dividir_en_simbolos_ofdm, ifft_mas_cp  # noqa: E402
from rx_chain import frame_mac_a_payload, ofdm_a_frame_mac  # noqa: E402

BPSK = ESQUEMAS["BPSK"]
BITS_CONTROL_DEFAULT = (0, 0, 0)  # placeholder -- InbandControlTX no implementado todavia


def procesar_payload(payload: bytes, seq_num: int, frag_flags: int, mod_scheme: int = MOD_BPSK):
    """TX completo -> RX completo, sin canal. Devuelve (payload_recuperado,
    seq_num_rx, frag_flags_rx, mod_scheme_rx). Lanza MACFrameError si el CRC
    no valida (no la esconde -- lo maneja quien llama)."""
    if mod_scheme != MOD_BPSK:
        raise NotImplementedError("el loopback solo tiene cableada la ruta BPSK (ver cadena.py, Prueba 9)")

    frame_mac = encapsular(payload, seq_num, frag_flags, mod_scheme)
    bits_codificados = fec_codificar(frame_mac)
    simbolos_bpsk = modular(bits_codificados, BPSK)
    simbolos_freq = dividir_en_simbolos_ofdm(simbolos_bpsk, BITS_CONTROL_DEFAULT)
    simbolos_tiempo = [ifft_mas_cp(v) for v in simbolos_freq]

    frame_mac_recuperado, _control = ofdm_a_frame_mac(
        simbolos_tiempo, n_simbolos_datos=len(simbolos_bpsk), n_bytes_frame_mac=len(frame_mac)
    )
    return frame_mac_a_payload(frame_mac_recuperado)


class TxRxLoopbackBlock(gr.basic_block):
    """PDU (payload IP crudo) -> procesar_payload() -> PDU (payload
    recuperado), o se descarta silenciosamente si el CRC del MAC no
    valida -- el mismo contrato que tendria el receptor real: nunca deja
    pasar un paquete corrupto a `tun0`."""

    def __init__(self, frag_flags: int = 0, mod_scheme: int = MOD_BPSK):
        gr.basic_block.__init__(self, "tx_rx_loopback_block", in_sig=None, out_sig=None)
        self.message_port_register_in(pmt.intern("pdu_in"))
        self.message_port_register_out(pmt.intern("pdu_out"))
        self.set_msg_handler(pmt.intern("pdu_in"), self._manejar_pdu)

        self._seq_num = 0
        self._frag_flags = frag_flags
        self._mod_scheme = mod_scheme

        self.n_entregados = 0
        self.n_descartados = 0
        self.bytes_entregados = 0
        self.latencias_s = []
        self.payloads_entregados = []  # copia de cada payload entregado, para verificar contenido despues

    def _manejar_pdu(self, msg):
        t0 = time.perf_counter()
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        seq_num = self._seq_num % 256
        self._seq_num += 1

        try:
            payload_recuperado, *_ = procesar_payload(payload, seq_num, self._frag_flags, self._mod_scheme)
        except MACFrameError:
            self.n_descartados += 1
            return

        self.n_entregados += 1
        self.bytes_entregados += len(payload_recuperado)
        self.latencias_s.append(time.perf_counter() - t0)
        self.payloads_entregados.append(payload_recuperado)

        pdu_salida = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(payload_recuperado), list(payload_recuperado)))
        self.message_port_pub(pmt.intern("pdu_out"), pdu_salida)

    def resumen(self) -> dict:
        total = self.n_entregados + self.n_descartados
        return {
            "n_entregados": self.n_entregados,
            "n_descartados": self.n_descartados,
            "n_total": total,
            "bytes_entregados": self.bytes_entregados,
            "latencia_prom_ms": (sum(self.latencias_s) / len(self.latencias_s) * 1000) if self.latencias_s else None,
            "latencia_max_ms": (max(self.latencias_s) * 1000) if self.latencias_s else None,
        }
