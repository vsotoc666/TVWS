#!/usr/bin/env python3
"""Prueba 9 - Fase 2: MAC -> FEC -> MOD -> PDU-to-stream -> dump a archivo.

Extiende la cadena de la Prueba 8 un paso mas alla de MAC: toma un
paquete IP (el mismo de las Pruebas 3/4/5), lo pasa por MAC (Prueba 4),
FEC (Prueba 5) y MOD (Prueba 6) -- ver cadena.py -- y el resultado
(simbolos I/Q ya modulados) se empaqueta como PDU y se cruza la frontera
mensajes->streaming con pdu_to_tagged_stream (Prueba 7), igual que lo
haria el flowgraph real antes de entrar al Carrier Allocator/IFFT.

No requiere tun0 ni sudo -- el payload es estatico, no viene de tun0 (esa
parte ya la cubre la Prueba 8).

Uso:
    ~/envs/SDR/bin/python flowgraph_prueba09.py --salida simbolos_stream.txt
"""
import argparse
import os
import sys
import time

import pmt
from gnuradio import gr, blocks
from gnuradio import pdu as pdu_mod

sys.path.insert(0, os.path.dirname(__file__))
from cadena import payload_a_simbolos

TIPO_ITEM = gr.types.complex_t
TAGNAME = "packet_len"

PAQUETE_PRUEBA3 = bytes.fromhex(
    "4500002fc0de00004011a5170a6300020a6300019c400009001b0000"
    "505255454241332d545657532d494e42414e44"
)


def main():
    parser = argparse.ArgumentParser(description="Prueba 9: MAC -> FEC -> MOD -> PDU-to-stream -> dump")
    parser.add_argument("--seq-num", type=int, default=5)
    parser.add_argument("--frag-flags", type=int, default=0)
    parser.add_argument("--periodo-ms", type=int, default=100)
    parser.add_argument("--duracion", type=float, default=1.0)
    parser.add_argument("--salida", default="simbolos_stream.txt")
    args = parser.parse_args()

    frame_mac, bits_codificados, simbolos_esperados = payload_a_simbolos(
        PAQUETE_PRUEBA3, args.seq_num, args.frag_flags
    )
    print(f"[prueba09] frame MAC: {len(frame_mac)} bytes")
    print(f"[prueba09] bits codificados (FEC): {len(bits_codificados)}")
    print(f"[prueba09] simbolos modulados (BPSK): {len(simbolos_esperados)}")

    pdu_val = pmt.cons(pmt.make_dict(), pmt.init_c32vector(len(simbolos_esperados), simbolos_esperados))

    tb = gr.top_block()
    strobe = blocks.message_strobe(pdu_val, args.periodo_ms)
    p2ts = pdu_mod.pdu_to_tagged_stream(TIPO_ITEM, TAGNAME)
    snk = blocks.vector_sink_c()
    tb.msg_connect((strobe, "strobe"), (p2ts, "pdus"))
    tb.connect(p2ts, snk)
    tb.start()
    time.sleep(args.duracion)
    tb.stop()
    tb.wait()

    datos_stream = list(snk.data())
    tags = snk.tags()
    print(f"[prueba09] stream de salida: {len(datos_stream)} items, {len(tags)} paquetes (tags)")

    with open(args.salida, "w") as f:
        f.write(f"# frame_mac_hex={frame_mac.hex()}\n")
        f.write(f"# n_bits_codificados={len(bits_codificados)}\n")
        f.write(f"# n_simbolos_esperados={len(simbolos_esperados)}\n")
        f.write(f"# n_tags={len(tags)}\n")
        for t in tags:
            valor = pmt.to_python(t.value)
            f.write(f"# tag offset={t.offset} key={pmt.symbol_to_string(t.key)} value={valor}\n")
        for s in datos_stream:
            f.write(f"{s.real},{s.imag}\n")

    print(f"[prueba09] volcado a {args.salida}")


if __name__ == "__main__":
    main()
