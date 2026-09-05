"""Frontera mensajes<->streaming: pdu_to_tagged_stream / tagged_stream_to_pdu.

Es la frontera descrita en `claudedocs/arquitectura_transmision_datos.md`
linea 84-85: la salida de MAC/FEC/MOD (PDUs de simbolos) se convierte en un
stream `gr_complex` tageado con longitud antes de entrar al Carrier
Allocator/IFFT (streaming puro). En RX ocurre lo inverso ("Tagged Stream to
PDU", linea 88). Se usa `gnuradio.pdu` (no `gnuradio.blocks`) porque estos
dos bloques se movieron de gr-blocks a gr-pdu en GNU Radio 3.10 (mismo
patron que `network.tuntap_pdu` en la Prueba 2/3).

Tipo de item: `gr_complex` (simbolos I/Q), consistente con la Prueba 6
(BPSK/QPSK/16-QAM) -- este modulo simula justo el paso siguiente en la
cadena.
"""
import time

import pmt
from gnuradio import gr, blocks
from gnuradio import pdu as pdu_mod

TIPO_ITEM = gr.types.complex_t
TAGNAME = "packet_len"


def _pdu_de(valores: list) -> pmt.pmt_base:
    return pmt.cons(pmt.make_dict(), pmt.init_c32vector(len(valores), valores))


def pdu_a_stream_repetido(valores: list, periodo_ms: int, duracion_s: float):
    """Reenvia el mismo PDU cada periodo_ms durante duracion_s (varios
    paquetes seguidos, para poder validar que los limites entre paquetes
    consecutivos no se corrompen). Devuelve (datos, tags) del stream de
    salida de pdu_to_tagged_stream."""
    tb = gr.top_block()
    strobe = blocks.message_strobe(_pdu_de(valores), periodo_ms)
    p2ts = pdu_mod.pdu_to_tagged_stream(TIPO_ITEM, TAGNAME)
    snk = blocks.vector_sink_c()
    tb.msg_connect((strobe, "strobe"), (p2ts, "pdus"))
    tb.connect(p2ts, snk)
    tb.start()
    time.sleep(duracion_s)
    tb.stop()
    tb.wait()
    return list(snk.data()), snk.tags()


def stream_a_pdus(datos: list, longitudes: list) -> list:
    """datos concatenados + longitudes de cada paquete consecutivo (se
    calculan los offsets de los tags a partir de ellas) -> lista de PDUs
    recuperados por tagged_stream_to_pdu, en orden."""
    tags = []
    offset = 0
    for n in longitudes:
        tags.append(gr.python_to_tag((offset, pmt.intern(TAGNAME), pmt.from_long(n), pmt.intern("pdu_stream"))))
        offset += n

    tb = gr.top_block()
    src = blocks.vector_source_c(datos, False, 1, tags)
    ts2p = pdu_mod.tagged_stream_to_pdu(TIPO_ITEM, TAGNAME)
    dbg = blocks.message_debug()
    tb.connect(src, ts2p)
    tb.msg_connect((ts2p, "pdus"), (dbg, "store"))
    tb.start()
    time.sleep(max(0.5, len(datos) * 1e-4))
    tb.stop()
    tb.wait()

    return [list(pmt.c32vector_elements(pmt.cdr(dbg.get_message(i)))) for i in range(dbg.num_messages())]


def round_trip_completo(valores: list, periodo_ms: int, duracion_s: float) -> list:
    """PDU -> pdu_to_tagged_stream -> tagged_stream_to_pdu -> PDU, ambos
    bloques encadenados en el mismo top_block. Devuelve la lista de PDUs
    recuperados (uno por cada disparo del strobe)."""
    tb = gr.top_block()
    strobe = blocks.message_strobe(_pdu_de(valores), periodo_ms)
    p2ts = pdu_mod.pdu_to_tagged_stream(TIPO_ITEM, TAGNAME)
    ts2p = pdu_mod.tagged_stream_to_pdu(TIPO_ITEM, TAGNAME)
    dbg = blocks.message_debug()
    tb.msg_connect((strobe, "strobe"), (p2ts, "pdus"))
    tb.connect(p2ts, ts2p)
    tb.msg_connect((ts2p, "pdus"), (dbg, "store"))
    tb.start()
    time.sleep(duracion_s)
    tb.stop()
    tb.wait()
    return [list(pmt.c32vector_elements(pmt.cdr(dbg.get_message(i)))) for i in range(dbg.num_messages())]
