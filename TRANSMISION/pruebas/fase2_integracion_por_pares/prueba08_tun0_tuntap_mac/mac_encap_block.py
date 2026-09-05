"""Bloque de mensajes GNU Radio que envuelve mac_frame.encapsular().

Prueba 8 es de *integracion*: no reinventa el framing MAC, reutiliza
literalmente el modulo ya validado en la Prueba 4
(`fase1_unitarias/prueba04_mac_encap_decap/mac_frame.py`) -- por eso se
importa desde ahi en vez de copiar la logica.
"""
import os
import sys

_PRUEBA04 = os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias", "prueba04_mac_encap_decap")
sys.path.insert(0, os.path.abspath(_PRUEBA04))
from mac_frame import encapsular  # noqa: E402

import pmt
from gnuradio import gr


class MacEncapBlock(gr.basic_block):
    """PDU (payload IP crudo, de tuntap_pdu) -> PDU (frame MAC completo).

    seq_num se incrementa automaticamente (con wrap-around a 256) por cada
    PDU que pasa; frag_flags/mod_scheme son fijos para esta prueba (todavia
    no hay CognitiveEngine real que los decida, ni fragmentacion activa
    aqui -- ver Prueba 14 para el caso fragmentado)."""

    def __init__(self, frag_flags: int = 0, mod_scheme: int = 0):
        gr.basic_block.__init__(self, "mac_encap_block", in_sig=None, out_sig=None)
        self.message_port_register_in(pmt.intern("pdu_in"))
        self.message_port_register_out(pmt.intern("pdu_out"))
        self.set_msg_handler(pmt.intern("pdu_in"), self._manejar_pdu)
        self._seq_num = 0
        self._frag_flags = frag_flags
        self._mod_scheme = mod_scheme

    def _manejar_pdu(self, msg):
        payload = bytes(pmt.u8vector_elements(pmt.cdr(msg)))
        frame = encapsular(payload, self._seq_num % 256, self._frag_flags, self._mod_scheme)
        self._seq_num += 1

        pdu_salida = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(frame), list(frame)))
        self.message_port_pub(pmt.intern("pdu_out"), pdu_salida)
