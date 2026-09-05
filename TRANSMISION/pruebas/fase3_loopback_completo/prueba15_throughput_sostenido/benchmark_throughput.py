#!/usr/bin/env python3
"""Prueba 15 - Fase 3: throughput sostenido por modo de modulacion/FEC.

Criterio del plan: throughput medido vs tabla de README.md S5.3
(ej. BPSK 1/2 ~= 1.9 Mbps).

Desviacion honesta respecto al plan: el plan pide "iperf3 sostenido", lo
cual necesita un segundo nodo real escuchando en el otro extremo de tun0
-- no existe en este banco de pruebas de un solo proceso/maquina (eso es
Fase 4+, con hardware). En su lugar, esta prueba mide throughput
directamente sobre la cadena TX+RX completa (reusando
loopback_block.procesar_payload de la Prueba 12), que es la misma cadena
que alimentaria a `iperf3` si estuviera conectada a traves de tun0 -- el
numero medido es comparable, aunque no identico (no incluye overhead de
UDP/TCP/kernel).

Tambien es honesto sobre el alcance: solo BPSK esta implementado en la
cadena reusada (cadena.py / loopback_block.py, Prueba 9) -- QPSK/16-QAM
no se miden aqui porque requieren extender esos modulos primero (ver
seccion "Alcance" del README de esta prueba).

Requiere el venv ~/envs/SDR. No requiere tun0 ni sudo.

Uso:
    ~/envs/SDR/bin/python benchmark_throughput.py --n-paquetes 30 --tam-payload 500
"""
import argparse
import os
import sys
import time

_FASE1 = os.path.join(os.path.dirname(__file__), "..", "..", "fase1_unitarias")
_FASE2 = os.path.join(os.path.dirname(__file__), "..", "..", "fase2_integracion_por_pares")
_FASE3 = os.path.dirname(os.path.dirname(__file__))
for _p in (
    os.path.join(_FASE1, "prueba04_mac_encap_decap"),
    os.path.join(_FASE1, "prueba05_fec_roundtrip"),
    os.path.join(_FASE1, "prueba06_mod_demod_roundtrip"),
    os.path.join(_FASE2, "prueba10_ofdm_tx"),
    os.path.join(_FASE2, "prueba11_rx_completo"),
    os.path.join(_FASE3, "prueba12_txrx_loopback_tun0"),
):
    sys.path.insert(0, os.path.abspath(_p))

from mac_frame import MOD_BPSK, encapsular  # noqa: E402
from ccsds_fec import codificar as fec_codificar  # noqa: E402
from ccsds_fec import decodificar as fec_decodificar  # noqa: E402
from constelaciones import ESQUEMAS, modular  # noqa: E402
from loopback_block import procesar_payload  # noqa: E402
from ofdm_symbol import dividir_en_simbolos_ofdm, ifft_mas_cp  # noqa: E402
from rx_chain import ofdm_a_frame_mac  # noqa: E402

BPSK = ESQUEMAS["BPSK"]

# throughput de referencia (README.md S5.3), solo para el modo medido aqui
OBJETIVO_BPSK_R12_MBPS = 1.9


def desglose_de_tiempo(payload: bytes, n_repeticiones: int) -> dict:
    """Mide por separado cuanto tarda cada etapa, para diagnosticar donde
    se va el tiempo (hipotesis: los top_block por-paquete de ccsds_fec)."""
    tiempos = {"mac_encap": 0.0, "fec_codificar": 0.0, "mod_ofdm_tx": 0.0, "ofdm_rx_y_fec_decodificar": 0.0, "mac_decap": 0.0}

    for i in range(n_repeticiones):
        t0 = time.perf_counter()
        frame_mac = encapsular(payload, i % 256, 0, MOD_BPSK)  # frag_flags=0 (sin fragmentar)
        t1 = time.perf_counter()
        bits_codificados = fec_codificar(frame_mac)
        t2 = time.perf_counter()
        simbolos = modular(bits_codificados, BPSK)
        simbolos_freq = dividir_en_simbolos_ofdm(simbolos, (0, 0, 0))
        simbolos_tiempo = [ifft_mas_cp(v) for v in simbolos_freq]
        t3 = time.perf_counter()
        frame_mac_rx, _ = ofdm_a_frame_mac(simbolos_tiempo, len(simbolos), len(frame_mac))
        t4 = time.perf_counter()
        from mac_frame import decapsular
        decapsular(frame_mac_rx)
        t5 = time.perf_counter()

        tiempos["mac_encap"] += t1 - t0
        tiempos["fec_codificar"] += t2 - t1
        tiempos["mod_ofdm_tx"] += t3 - t2
        tiempos["ofdm_rx_y_fec_decodificar"] += t4 - t3
        tiempos["mac_decap"] += t5 - t4

    return {k: v / n_repeticiones * 1000 for k, v in tiempos.items()}  # ms promedio por paquete


def medir_throughput(tam_payload: int, n_paquetes: int) -> dict:
    payload = bytes((i * 13 + 7) % 256 for i in range(tam_payload))

    t_inicio = time.perf_counter()
    bytes_ok = 0
    for i in range(n_paquetes):
        payload_rx, *_ = procesar_payload(payload, i % 256, 0)
        if payload_rx == payload:
            bytes_ok += len(payload_rx)
    duracion_s = time.perf_counter() - t_inicio

    mbps = (bytes_ok * 8 / 1e6) / duracion_s
    return {
        "n_paquetes": n_paquetes,
        "tam_payload": tam_payload,
        "bytes_ok": bytes_ok,
        "duracion_s": duracion_s,
        "mbps": mbps,
    }


def main():
    parser = argparse.ArgumentParser(description="Prueba 15: throughput sostenido BPSK R=1/2 (unico modo implementado).")
    parser.add_argument("--n-paquetes", type=int, default=30)
    parser.add_argument("--tam-payload", type=int, default=500)
    args = parser.parse_args()

    print("[prueba15] desglose de tiempo por etapa (5 repeticiones, payload de 100B):")
    desglose = desglose_de_tiempo(bytes(range(100)), 5)
    for etapa, ms in desglose.items():
        print(f"  {etapa:28s}: {ms:7.3f} ms/paquete")

    print(f"\n[prueba15] midiendo throughput sostenido: {args.n_paquetes} paquetes de {args.tam_payload} bytes, BPSK R=1/2...")
    resultado = medir_throughput(args.tam_payload, args.n_paquetes)
    print(f"[prueba15] {resultado['bytes_ok']} bytes entregados correctos en {resultado['duracion_s']:.3f} s")
    print(f"[prueba15] throughput medido: {resultado['mbps']:.4f} Mbps")
    print(f"[prueba15] objetivo README S5.3 (BPSK R=1/2): {OBJETIVO_BPSK_R12_MBPS} Mbps")
    print(f"[prueba15] razon medido/objetivo: {resultado['mbps'] / OBJETIVO_BPSK_R12_MBPS:.4f}x")


if __name__ == "__main__":
    main()
