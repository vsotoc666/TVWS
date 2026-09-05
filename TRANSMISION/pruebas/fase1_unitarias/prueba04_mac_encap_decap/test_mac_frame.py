#!/usr/bin/env python3
"""Prueba 4 - Fase 1: MAC encapsulado/decapsulado + fragmentacion.

Test unitario Python puro (sin GNU Radio, sin tun0): payload -> header
(seq_num|frag_flags|mod_scheme|CRC) -> decap -> payload igual. Verifica
framing correcto, deteccion de corrupcion via CRC, y fragmentacion/
reensamblado de PDUs que no caben en un solo frame (`claudedocs/
arquitectura_enlace_datos.md` S2.4).

Uso:
    python3 test_mac_frame.py
"""
import sys

from mac_frame import (
    MACFrameError,
    MOD_16QAM,
    MOD_BPSK,
    MOD_QPSK,
    decapsular,
    encapsular,
    fragmentar,
    frag_flags_mf,
    frag_flags_tiene_mf,
    reensamblar,
)

# El mismo paquete UDP/IP sintetico armado en la Prueba 3, reusado aqui
# como "payload realista" (un PDU crudo tal como lo entregaria tuntap_pdu).
PAQUETE_PRUEBA3 = bytes.fromhex(
    "4500002fc0de00004011a5170a6300020a6300019c400009001b0000"
    "505255454241332d545657532d494e42414e44"
)


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def test_round_trip_payload_realista():
    frame = encapsular(PAQUETE_PRUEBA3, seq_num=7, frag_flags=0, mod_scheme=MOD_QPSK)
    payload, seq_num, frag_flags, mod_scheme = decapsular(frame)
    return _check(
        "round-trip payload realista (paquete UDP/IP de la Prueba 3)",
        payload == PAQUETE_PRUEBA3 and seq_num == 7 and frag_flags == 0 and mod_scheme == MOD_QPSK,
    )


def test_round_trip_payload_vacio():
    frame = encapsular(b"", seq_num=0, frag_flags=0, mod_scheme=MOD_BPSK)
    payload, seq_num, frag_flags, mod_scheme = decapsular(frame)
    return _check("round-trip payload vacio", payload == b"" and seq_num == 0)


def test_round_trip_seq_num_limite():
    frame = encapsular(b"x" * 50, seq_num=255, frag_flags=frag_flags_mf(True), mod_scheme=MOD_16QAM)
    payload, seq_num, frag_flags, mod_scheme = decapsular(frame)
    return _check(
        "round-trip con seq_num=255 y frag_flags=MF (limites del campo de 1 byte)",
        payload == b"x" * 50 and seq_num == 255 and frag_flags_tiene_mf(frag_flags),
    )


def test_overhead_del_header():
    payload = b"y" * 20
    frame = encapsular(payload, seq_num=1, frag_flags=0, mod_scheme=MOD_BPSK)
    return _check(
        "overhead de framing es exactamente 5 bytes (3 header + 2 CRC)",
        len(frame) == len(payload) + 5,
    )


def test_crc_detecta_corrupcion_en_payload():
    frame = bytearray(encapsular(PAQUETE_PRUEBA3, seq_num=7, frag_flags=0, mod_scheme=MOD_QPSK))
    frame[-1] ^= 0xFF  # voltea el ultimo byte del payload
    try:
        decapsular(bytes(frame))
        return _check("CRC detecta 1 byte corrupto en el payload", False)
    except MACFrameError:
        return _check("CRC detecta 1 byte corrupto en el payload", True)


def test_crc_detecta_corrupcion_en_header():
    frame = bytearray(encapsular(PAQUETE_PRUEBA3, seq_num=7, frag_flags=0, mod_scheme=MOD_QPSK))
    frame[0] ^= 0x01  # voltea 1 bit de seq_num
    try:
        decapsular(bytes(frame))
        return _check("CRC detecta 1 bit corrupto en el header (seq_num)", False)
    except MACFrameError:
        return _check("CRC detecta 1 bit corrupto en el header (seq_num)", True)


def test_frame_truncado_no_crashea():
    frame = encapsular(PAQUETE_PRUEBA3, seq_num=7, frag_flags=0, mod_scheme=MOD_QPSK)
    truncado = frame[:2]  # menos que header+CRC
    try:
        decapsular(truncado)
        return _check("frame truncado rechazado con MACFrameError (no crashea)", False)
    except MACFrameError:
        return _check("frame truncado rechazado con MACFrameError (no crashea)", True)


def test_mod_scheme_invalido_rechazado_al_encapsular():
    try:
        encapsular(b"z", seq_num=0, frag_flags=0, mod_scheme=99)
        return _check("mod_scheme invalido rechazado por encapsular() (ValueError)", False)
    except ValueError:
        return _check("mod_scheme invalido rechazado por encapsular() (ValueError)", True)


def test_frag_flags_mf_helper():
    return _check(
        "frag_flags_mf()/frag_flags_tiene_mf() codifican/leen el bit MF correctamente",
        frag_flags_mf(True) == 0b0000_0001
        and frag_flags_mf(False) == 0
        and frag_flags_tiene_mf(0b0000_0001) is True
        and frag_flags_tiene_mf(0) is False
        and frag_flags_tiene_mf(0b1111_1111) is True,  # bits reservados no deberian importar al leer
    )


def test_fragmentar_payload_que_cabe_en_uno_solo():
    payload = b"z" * 10
    frames = fragmentar(payload, seq_num=3, mod_scheme=MOD_BPSK, max_bytes_por_fragmento=100)
    if len(frames) != 1:
        return _check("payload que cabe en 1 fragmento produce 1 solo frame (MF=0)", False)
    frame_directo = encapsular(payload, seq_num=3, frag_flags=frag_flags_mf(False), mod_scheme=MOD_BPSK)
    return _check(
        "payload que cabe en 1 fragmento produce 1 solo frame (MF=0), identico a encapsular() directo",
        frames[0] == frame_directo,
    )


def test_fragmentar_y_reensamblar_payload_grande():
    payload = bytes((i * 37 + 11) % 256 for i in range(1400))
    frames = fragmentar(payload, seq_num=42, mod_scheme=MOD_BPSK, max_bytes_por_fragmento=100)

    n_esperado = -(-len(payload) // 100)  # ceil division
    ok_cantidad = _check(f"1400B con max 100B/fragmento produce {n_esperado} fragmentos", len(frames) == n_esperado)

    mf_bits = []
    for f in frames:
        _, _, frag_flags, _ = decapsular(f)
        mf_bits.append(frag_flags_tiene_mf(frag_flags))
    ok_mf = _check(
        "MF=1 en todos los fragmentos salvo el ultimo (MF=0)",
        mf_bits[:-1] == [True] * (len(mf_bits) - 1) and mf_bits[-1] is False,
    )

    reensamblado = reensamblar(frames)
    ok_roundtrip = _check(
        "reensamblar(fragmentar(payload)) == payload original, bit exacto",
        reensamblado == payload,
    )
    return ok_cantidad and ok_mf and ok_roundtrip


def test_reensamblar_fragmento_corrupto_lanza_error():
    payload = b"w" * 300
    frames = fragmentar(payload, seq_num=9, mod_scheme=MOD_QPSK, max_bytes_por_fragmento=100)
    frames = list(frames)
    corrupto = bytearray(frames[1])
    corrupto[-1] ^= 0xFF
    frames[1] = bytes(corrupto)
    try:
        reensamblar(frames)
        return _check("fragmento corrupto en reensamblar() lanza MACFrameError (descarta el PDU)", False)
    except MACFrameError:
        return _check("fragmento corrupto en reensamblar() lanza MACFrameError (descarta el PDU)", True)


def test_reensamblar_seq_num_inconsistente_lanza_error():
    frame_a = encapsular(b"parte1", seq_num=1, frag_flags=frag_flags_mf(True), mod_scheme=MOD_BPSK)
    frame_b = encapsular(b"parte2", seq_num=2, frag_flags=frag_flags_mf(False), mod_scheme=MOD_BPSK)
    try:
        reensamblar([frame_a, frame_b])
        return _check("seq_num inconsistente entre fragmentos lanza MACFrameError", False)
    except MACFrameError:
        return _check("seq_num inconsistente entre fragmentos lanza MACFrameError", True)


def test_reensamblar_payload_vacio_produce_un_fragmento():
    frames = fragmentar(b"", seq_num=0, mod_scheme=MOD_BPSK, max_bytes_por_fragmento=100)
    return _check(
        "payload vacio produce exactamente 1 fragmento (MF=0) y reensambla a vacio",
        len(frames) == 1 and reensamblar(frames) == b"",
    )


def main():
    pruebas = [
        test_round_trip_payload_realista,
        test_round_trip_payload_vacio,
        test_round_trip_seq_num_limite,
        test_overhead_del_header,
        test_crc_detecta_corrupcion_en_payload,
        test_crc_detecta_corrupcion_en_header,
        test_frame_truncado_no_crashea,
        test_mod_scheme_invalido_rechazado_al_encapsular,
        test_frag_flags_mf_helper,
        test_fragmentar_payload_que_cabe_en_uno_solo,
        test_fragmentar_y_reensamblar_payload_grande,
        test_reensamblar_fragmento_corrupto_lanza_error,
        test_reensamblar_seq_num_inconsistente_lanza_error,
        test_reensamblar_payload_vacio_produce_un_fragmento,
    ]
    resultados = [prueba() for prueba in pruebas]

    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
