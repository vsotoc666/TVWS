#!/usr/bin/env python3
"""Prueba 2 - Fase 1: tuntap_pdu lectura.

Flowgraph minimo: network.tuntap_pdu abre el fd de una interfaz TUN ya
existente (creada en la Prueba 1) y traduce cada paquete IP que el kernel
le entregue en un mensaje PDU de GNU Radio. blocks.message_debug imprime
cada PDU recibida por stdout, para verificar a simple vista que el payload
llega integro.

Uso:
    python3 flowgraph_lectura.py --dev tun0 --duracion 15
    # en otra terminal, mientras corre:
    ping -I tun0 -c 4 10.99.0.2
"""
import argparse
import time

from gnuradio import gr, network, blocks


class FlowgraphLecturaTun(gr.top_block):
    def __init__(self, dev="tun0", mtu=1500):
        gr.top_block.__init__(self, "prueba02_tuntap_pdu_lectura")

        self.tuntap = network.tuntap_pdu(dev, mtu, True)
        self.debug = blocks.message_debug()

        self.msg_connect((self.tuntap, "pdus"), (self.debug, "print_pdu"))


def main():
    parser = argparse.ArgumentParser(
        description="Prueba 2: valida que tuntap_pdu convierte paquetes IP "
        "de una interfaz TUN en PDUs de GNU Radio con el payload correcto."
    )
    parser.add_argument("--dev", default="tun0", help="interfaz TUN ya creada (Prueba 1)")
    parser.add_argument("--mtu", type=int, default=1500)
    parser.add_argument(
        "--duracion", type=float, default=15.0,
        help="segundos que el flowgraph se queda escuchando la interfaz",
    )
    args = parser.parse_args()

    tb = FlowgraphLecturaTun(dev=args.dev, mtu=args.mtu)

    print(f"[prueba02] flowgraph arrancado, escuchando '{args.dev}' durante {args.duracion}s...")
    print(f"[prueba02] en otra terminal corre: ping -I {args.dev} -c 4 10.99.0.2")

    tb.start()
    time.sleep(args.duracion)
    tb.stop()
    tb.wait()

    print("[prueba02] flowgraph detenido")


if __name__ == "__main__":
    main()
