#!/usr/bin/env python3
"""Prueba 3 - Fase 1: tuntap_pdu escritura.

Flowgraph minimo: blocks.message_strobe emite periodicamente un PDU
sintetico (un paquete IPv4/UDP armado a mano, con checksum de cabecera IP
valido) hacia network.tuntap_pdu, que lo escribe en el fd de tun0. La
verificacion de que "los bytes escritos a tun0 llegan integros" se hace
por fuera de este script, con `tcpdump -i tun0` en otra terminal (requiere
sudo, por eso no se automatiza aqui).

Uso:
    python3 flowgraph_escritura.py --duracion 20 --periodo-ms 2000
    # en otra terminal, mientras corre:
    sudo tcpdump -i tun0 -n -vv -X
"""
import argparse
import socket
import struct
import time

from gnuradio import gr, network, blocks
import pmt


def checksum_ip(header_sin_checksum: bytes) -> int:
    """Checksum de cabecera IPv4 (RFC 791): complemento a 1 de la suma en
    palabras de 16 bits."""
    datos = header_sin_checksum
    if len(datos) % 2:
        datos += b"\x00"
    total = sum(struct.unpack("!%dH" % (len(datos) // 2), datos))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return (~total) & 0xFFFF


def construir_paquete_udp(src: str, dst: str, sport: int, dport: int, payload: bytes) -> bytes:
    """Arma un paquete IPv4/UDP valido a mano (sin scapy). Checksum UDP se
    deja en 0 -- valido en IPv4, significa "sin checksum verificado"."""
    udp_header = struct.pack("!HHHH", sport, dport, 8 + len(payload), 0)
    udp = udp_header + payload

    ihl = 5
    ver_ihl = (4 << 4) | ihl
    total_len = 20 + len(udp)
    identificacion = 0xC0DE
    ttl = 64
    protocolo = socket.IPPROTO_UDP
    src_bytes = socket.inet_aton(src)
    dst_bytes = socket.inet_aton(dst)

    cabecera_sin_checksum = struct.pack(
        "!BBHHHBBH4s4s",
        ver_ihl, 0, total_len, identificacion, 0, ttl, protocolo, 0,
        src_bytes, dst_bytes,
    )
    checksum = checksum_ip(cabecera_sin_checksum)
    cabecera = struct.pack(
        "!BBHHHBBH4s4s",
        ver_ihl, 0, total_len, identificacion, 0, ttl, protocolo, checksum,
        src_bytes, dst_bytes,
    )
    return cabecera + udp


class FlowgraphEscrituraTun(gr.top_block):
    def __init__(self, dev: str, mtu: int, periodo_ms: int, paquete: bytes):
        gr.top_block.__init__(self, "prueba03_tuntap_pdu_escritura")

        pdu = pmt.cons(pmt.make_dict(), pmt.init_u8vector(len(paquete), list(paquete)))

        self.strobe = blocks.message_strobe(pdu, periodo_ms)
        self.tuntap = network.tuntap_pdu(dev, mtu, True)

        self.msg_connect((self.strobe, "strobe"), (self.tuntap, "pdus"))


def main():
    parser = argparse.ArgumentParser(
        description="Prueba 3: inyecta un PDU sintetico (paquete UDP/IP armado a "
        "mano) en tuntap_pdu y lo escribe en tun0. Verificar con tcpdump -i tun0."
    )
    parser.add_argument("--dev", default="tun0")
    parser.add_argument("--mtu", type=int, default=1500)
    parser.add_argument("--src", default="10.99.0.2", help="IP origen del paquete sintetico")
    parser.add_argument("--dst", default="10.99.0.1", help="IP destino (10.99.0.1 = la propia tun0)")
    parser.add_argument("--sport", type=int, default=40000)
    parser.add_argument("--dport", type=int, default=9, help="puerto UDP discard, sin listener")
    parser.add_argument("--periodo-ms", type=int, default=2000, help="cada cuanto se reenvia el mismo PDU")
    parser.add_argument("--duracion", type=float, default=20.0)
    args = parser.parse_args()

    payload = b"PRUEBA3-TVWS-INBAND"
    paquete = construir_paquete_udp(args.src, args.dst, args.sport, args.dport, payload)

    print(f"[prueba03] paquete sintetico ({len(paquete)} bytes) = {paquete.hex()}")
    print(f"[prueba03] {args.src}:{args.sport} -> {args.dst}:{args.dport}, payload={payload!r}")
    print(f"[prueba03] escribiendo a '{args.dev}' cada {args.periodo_ms} ms durante {args.duracion}s...")
    print(f"[prueba03] en otra terminal corre: sudo tcpdump -i {args.dev} -n -vv -X")

    tb = FlowgraphEscrituraTun(args.dev, args.mtu, args.periodo_ms, paquete)
    tb.start()
    time.sleep(args.duracion)
    tb.stop()
    tb.wait()

    print("[prueba03] flowgraph detenido")


if __name__ == "__main__":
    main()
