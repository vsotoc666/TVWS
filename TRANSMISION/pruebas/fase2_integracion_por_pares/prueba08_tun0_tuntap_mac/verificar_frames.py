#!/usr/bin/env python3
"""Verifica los frames MAC volcados por flowgraph_prueba08.py.

Criterio de la Prueba 8: trafico real (ping) produce frames MAC bien
formados. "Bien formado" aqui significa: CRC valido (Prueba 4), seq_num
consecutivo desde 0, y el payload decapsulado es un paquete IPv4 real
(version 4, protocolo ICMP) que va de la IP de tun0 a la IP del ping.

Uso:
    ~/envs/SDR/bin/python verificar_frames.py frames_mac.txt
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias", "prueba04_mac_encap_decap")))
from mac_frame import MACFrameError, decapsular  # noqa: E402

IP_TUN0 = "10.99.0.1"
FRAG_FLAGS_ESPERADO = 0
MOD_SCHEME_ESPERADO = 1
PROTO_ICMP = 1


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def verificar_archivo(ruta):
    with open(ruta) as f:
        lineas = [l.strip() for l in f if l.strip()]

    if not _check(f"al menos 1 frame capturado en {ruta}", len(lineas) > 0):
        return False

    resultados = []
    seq_esperado = 0
    for i, hexline in enumerate(lineas):
        frame = bytes.fromhex(hexline)
        try:
            payload, seq_num, frag_flags, mod_scheme = decapsular(frame)
        except MACFrameError as e:
            resultados.append(_check(f"frame {i}: CRC valido", False))
            print(f"    -> {e}")
            continue

        ip_version = payload[0] >> 4
        proto = payload[9]
        ip_src = ".".join(str(b) for b in payload[12:16])

        resultados.append(_check(f"frame {i}: CRC valido", True))
        resultados.append(_check(f"frame {i}: seq_num={seq_num} consecutivo (esperado {seq_esperado})", seq_num == seq_esperado))
        resultados.append(_check(f"frame {i}: frag_flags={frag_flags} (esperado {FRAG_FLAGS_ESPERADO})", frag_flags == FRAG_FLAGS_ESPERADO))
        resultados.append(_check(f"frame {i}: mod_scheme={mod_scheme} (esperado {MOD_SCHEME_ESPERADO})", mod_scheme == MOD_SCHEME_ESPERADO))
        resultados.append(_check(f"frame {i}: payload es IPv4 (version={ip_version})", ip_version == 4))
        resultados.append(_check(f"frame {i}: protocolo ICMP ({proto})", proto == PROTO_ICMP))
        resultados.append(_check(f"frame {i}: IP origen = tun0 ({ip_src})", ip_src == IP_TUN0))
        seq_esperado += 1

    return all(resultados)


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "frames_mac.txt"
    ok = verificar_archivo(ruta)
    print(f"\n{'TODOS los frames validos' if ok else 'HAY FRAMES INVALIDOS'}")
    sys.exit(0 if ok else 1)
