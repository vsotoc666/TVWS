#!/usr/bin/env python3
"""Prueba 12 - Fase 3: TX->RX conectados directo (vector, sin canal),
trafico real por tun0.

Criterio del plan: pipeline completo entrega trafico integro; primera
medicion de throughput/latencia vs S5.3.

    tun0 --tuntap_pdu--> TxRxLoopbackBlock (TX completo + RX completo) --> tuntap_pdu --> tun0

El paquete IP que entra por tun0 (ej. un ICMP echo request de `ping`)
atraviesa TODA la cadena de software (MAC->FEC->MOD->OFDM->OFDM->FEC->MOD->MAC)
sin canal ni SDR de por medio, y el resultado se reinyecta al mismo tun0.

Nota sobre el `ping`: como el paquete reinyectado sigue direccionado a
10.99.0.2 (no a la IP local 10.99.0.1) y esta maquina no tiene
`ip_forward` habilitado, el kernel NO genera una respuesta ICMP visible
para `ping` -- por eso el propio `ping` siempre va a reportar 100% packet
loss aqui, igual que en las Pruebas 1-3, y **no** es un indicador de
fallo. La verificacion real de integridad es interna: `TxRxLoopbackBlock`
solo publica un PDU de salida si el CRC del MAC (Prueba 4) valida, y este
script vuelca cada payload entregado a un archivo para inspeccion
independiente (ver --salida).

Uso:
    ~/envs/SDR/bin/python flowgraph_prueba12.py --dev tun0 --duracion 15 --salida payloads_entregados.txt
    # en otra terminal, mientras corre (dejar pasar ~5-6s antes de pingear,
    # los imports de este script tardan mas que los de la Prueba 2/3):
    ping -I tun0 -c 4 10.99.0.2
"""
import argparse
import time

from gnuradio import gr, network
from loopback_block import TxRxLoopbackBlock


class FlowgraphPrueba12(gr.top_block):
    def __init__(self, dev="tun0", mtu=1500, frag_flags=0):
        gr.top_block.__init__(self, "prueba12_txrx_loopback_tun0")

        self.tuntap = network.tuntap_pdu(dev, mtu, True)
        self.loopback = TxRxLoopbackBlock(frag_flags=frag_flags)

        self.msg_connect((self.tuntap, "pdus"), (self.loopback, "pdu_in"))
        self.msg_connect((self.loopback, "pdu_out"), (self.tuntap, "pdus"))


def main():
    parser = argparse.ArgumentParser(description="Prueba 12: loopback TX+RX completo sobre trafico real de tun0.")
    parser.add_argument("--dev", default="tun0")
    parser.add_argument("--mtu", type=int, default=1500)
    parser.add_argument("--duracion", type=float, default=15.0)
    parser.add_argument("--salida", default="payloads_entregados.txt")
    args = parser.parse_args()

    print(f"[prueba12] flowgraph arrancado, escuchando '{args.dev}' durante {args.duracion}s...")
    print(f"[prueba12] en otra terminal corre: ping -I {args.dev} -c 4 10.99.0.2")

    tb = FlowgraphPrueba12(dev=args.dev, mtu=args.mtu)
    tb.start()
    time.sleep(args.duracion)
    tb.stop()
    tb.wait()

    resumen = tb.loopback.resumen()
    print(f"[prueba12] resumen: {resumen}")
    if resumen["latencia_prom_ms"] is not None:
        mbps = (resumen["bytes_entregados"] * 8 / 1e6) / (sum(tb.loopback.latencias_s)) if tb.loopback.latencias_s else 0
        print(f"[prueba12] throughput aprox (solo computo, sin contar espera entre paquetes): {mbps:.3f} Mbps")

    with open(args.salida, "w") as f:
        for p in tb.loopback.payloads_entregados:
            f.write(p.hex() + "\n")
    print(f"[prueba12] {len(tb.loopback.payloads_entregados)} payloads volcados a {args.salida}")


if __name__ == "__main__":
    main()
