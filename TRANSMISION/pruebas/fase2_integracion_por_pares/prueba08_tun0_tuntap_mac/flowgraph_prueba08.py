#!/usr/bin/env python3
"""Prueba 8 - Fase 2: tun0 -> tuntap_pdu -> MAC -> dump.

Primera prueba de integracion: encadena piezas ya validadas por separado
en la Fase 1 (tuntap_pdu lectura = Prueba 2, encapsulado MAC = Prueba 4)
para confirmar que trafico real de red (ping) produce frames MAC bien
formados de punta a punta.

    tun0 --(kernel)--> network.tuntap_pdu --pdus--> MacEncapBlock --pdus--> dump

Uso:
    ~/envs/SDR/bin/python flowgraph_prueba08.py --dev tun0 --duracion 15
    # en otra terminal, mientras corre:
    ping -I tun0 -c 4 10.99.0.2
"""
import argparse
import time

import pmt
from gnuradio import gr, network, blocks
from mac_encap_block import MacEncapBlock


class FlowgraphPrueba08(gr.top_block):
    def __init__(self, dev="tun0", mtu=1500, frag_flags=0, mod_scheme=1):
        gr.top_block.__init__(self, "prueba08_tun0_tuntap_mac")

        self.tuntap = network.tuntap_pdu(dev, mtu, True)
        self.mac = MacEncapBlock(frag_flags=frag_flags, mod_scheme=mod_scheme)
        self.debug = blocks.message_debug()

        self.msg_connect((self.tuntap, "pdus"), (self.mac, "pdu_in"))
        self.msg_connect((self.mac, "pdu_out"), (self.debug, "store"))


def main():
    parser = argparse.ArgumentParser(
        description="Prueba 8: trafico real (ping) por tun0 -> tuntap_pdu -> MAC -> dump."
    )
    parser.add_argument("--dev", default="tun0")
    parser.add_argument("--mtu", type=int, default=1500)
    parser.add_argument("--duracion", type=float, default=15.0)
    parser.add_argument("--salida", default="frames_mac.txt", help="archivo donde volcar los frames en hex")
    args = parser.parse_args()

    print(f"[prueba08] flowgraph arrancado, escuchando '{args.dev}' durante {args.duracion}s...")
    print(f"[prueba08] en otra terminal corre: ping -I {args.dev} -c 4 10.99.0.2")

    tb = FlowgraphPrueba08(dev=args.dev, mtu=args.mtu)
    tb.start()
    time.sleep(args.duracion)
    tb.stop()
    tb.wait()

    n = tb.debug.num_messages()
    print(f"[prueba08] {n} frames MAC capturados")
    with open(args.salida, "w") as f:
        for i in range(n):
            frame = bytes(pmt.u8vector_elements(pmt.cdr(tb.debug.get_message(i))))
            f.write(frame.hex() + "\n")
    print(f"[prueba08] volcados a {args.salida}")


if __name__ == "__main__":
    main()
