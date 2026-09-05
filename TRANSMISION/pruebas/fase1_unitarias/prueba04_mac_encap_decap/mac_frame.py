"""Encapsulado/decapsulado MAC + fragmentacion, formato de header CERRADO.

Formato de header (5 bytes de overhead, todo byte-aligned), decision
cerrada en `claudedocs/arquitectura_enlace_datos.md` S2.4 (21/08/2026):

    | seq_num (1B) | frag_flags (1B) | mod_scheme (1B) | crc16 (2B) | payload |

- seq_num: 0-255, con wrap-around. Semantica: **ID de PDU** -- todos los
  fragmentos de un mismo PDU comparten el mismo seq_num. Como este es un
  enlace punto a punto sin rutas alternativas, los fragmentos de un PDU
  siempre llegan en el mismo orden en que se transmitieron, asi que no
  hace falta un indice de fragmento explicito ademas del bit MF.
- frag_flags: bit 0 = MF ("more fragments", analogo al de IPv4: 1 si
  vienen mas fragmentos de este mismo PDU, 0 si este es el ultimo/unico).
  Bits 1-7 reservados, deben ser 0. Este campo reemplaza al `next_ch`
  provisional de versiones anteriores de este modulo -- `next_ch` resulto
  vestigial (ningun test lo ligaba a logica real de salto de canal: el
  salto de canal real lo maneja el canal de control in-band dedicado,
  subportadoras #254/256/257, no el header MAC). Repurpuesar ese byte
  evita agregar overhead nuevo al header (sigue siendo 5 bytes).
- mod_scheme: enum MOD_BPSK/MOD_QPSK/MOD_16QAM.
- crc16: CRC-16-CCITT (poly 0x1021, init 0xFFFF) sobre header[:3] + payload,
  mismo polinomio que ya usa InbandControlLayer (README.md S7) por
  consistencia dentro del proyecto.

Fragmentacion (`fragmentar`/`reensamblar`): un PDU que no cabe en un slot
TDD (20 simbolos OFDM, `claudedocs/arquitectura_enlace_datos.md` S2.1) se
parte en varios frames MAC que comparten seq_num, con MF=1 en todos menos
el ultimo (MF=0). No hay ARQ/retransmision en este diseno -- un fragmento
corrupto descarta el PDU completo en el receptor, no hay NAK ni reenvio
automatico (S2.4, "Explicitamente fuera de este diseno").
"""
import struct

MOD_BPSK = 0
MOD_QPSK = 1
MOD_16QAM = 2
_MOD_VALIDOS = (MOD_BPSK, MOD_QPSK, MOD_16QAM)

_HEADER_FMT = "!BBB"
_HEADER_LEN = struct.calcsize(_HEADER_FMT)  # 3
_CRC_FMT = "!H"
_CRC_LEN = struct.calcsize(_CRC_FMT)  # 2

_MF_BIT = 0b0000_0001
_FRAG_FLAGS_RESERVADOS = ~_MF_BIT & 0xFF  # bits 1-7, deben ser 0


class MACFrameError(Exception):
    """CRC invalido, frame demasiado corto, o inconsistencia de reensamblado
    (seq_num distinto entre fragmentos de un mismo PDU)."""


def crc16_ccitt(data: bytes, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def frag_flags_mf(valor: bool) -> int:
    """Codifica el bit MF ("more fragments") en un byte frag_flags valido
    (bits 1-7 en 0). valor=True -> vienen mas fragmentos de este PDU;
    valor=False -> este es el ultimo (o unico) fragmento."""
    return _MF_BIT if valor else 0


def frag_flags_tiene_mf(frag_flags: int) -> bool:
    """Lee el bit MF de un byte frag_flags ya decodificado."""
    return bool(frag_flags & _MF_BIT)


def encapsular(payload: bytes, seq_num: int, frag_flags: int, mod_scheme: int) -> bytes:
    if not (0 <= seq_num <= 255):
        raise ValueError(f"seq_num fuera de rango: {seq_num}")
    if not (0 <= frag_flags <= 255):
        raise ValueError(f"frag_flags fuera de rango: {frag_flags}")
    if frag_flags & _FRAG_FLAGS_RESERVADOS:
        raise ValueError(f"frag_flags tiene bits reservados (1-7) en 1: {frag_flags:#04x}")
    if mod_scheme not in _MOD_VALIDOS:
        raise ValueError(f"mod_scheme invalido: {mod_scheme}")

    header = struct.pack(_HEADER_FMT, seq_num, frag_flags, mod_scheme)
    crc = crc16_ccitt(header + payload)
    return header + struct.pack(_CRC_FMT, crc) + payload


def decapsular(frame: bytes):
    """Devuelve (payload, seq_num, frag_flags, mod_scheme). Lanza
    MACFrameError si el frame es muy corto o el CRC no coincide (corrupcion
    detectada)."""
    if len(frame) < _HEADER_LEN + _CRC_LEN:
        raise MACFrameError(f"frame de {len(frame)} bytes, minimo {_HEADER_LEN + _CRC_LEN}")

    header = frame[:_HEADER_LEN]
    (crc_recibido,) = struct.unpack(_CRC_FMT, frame[_HEADER_LEN:_HEADER_LEN + _CRC_LEN])
    payload = frame[_HEADER_LEN + _CRC_LEN:]

    crc_calculado = crc16_ccitt(header + payload)
    if crc_calculado != crc_recibido:
        raise MACFrameError(
            f"CRC invalido: recibido {crc_recibido:#06x}, calculado {crc_calculado:#06x}"
        )

    seq_num, frag_flags, mod_scheme = struct.unpack(_HEADER_FMT, header)
    return payload, seq_num, frag_flags, mod_scheme


def fragmentar(payload: bytes, seq_num: int, mod_scheme: int, max_bytes_por_fragmento: int) -> list:
    """Parte `payload` en fragmentos de a lo sumo `max_bytes_por_fragmento`
    bytes de payload cada uno, encapsulando cada uno con el mismo `seq_num`
    (== ID de PDU) y MF=1 en todos menos el ultimo (MF=0). Devuelve la
    lista de frames MAC ya listos para transmitir, en orden.

    Si `payload` cabe en un solo fragmento, devuelve una lista de un solo
    elemento con MF=0 -- identico a una llamada directa a encapsular()."""
    if max_bytes_por_fragmento <= 0:
        raise ValueError(f"max_bytes_por_fragmento debe ser > 0: {max_bytes_por_fragmento}")

    if len(payload) == 0:
        # Caso borde: un PDU vacio sigue siendo 1 fragmento (MF=0), no 0
        # fragmentos -- mantiene el invariante "reensamblar ve al menos 1 frame".
        return [encapsular(payload, seq_num, frag_flags_mf(False), mod_scheme)]

    trozos = [
        payload[i:i + max_bytes_por_fragmento]
        for i in range(0, len(payload), max_bytes_por_fragmento)
    ]

    frames = []
    ultimo = len(trozos) - 1
    for i, trozo in enumerate(trozos):
        mf = i != ultimo
        frames.append(encapsular(trozo, seq_num, frag_flags_mf(mf), mod_scheme))
    return frames


def reensamblar(frames: list) -> bytes:
    """Toma una lista ordenada de frames MAC crudos (bytes, tal como los
    entregaria la capa RX antes de decapsular), los decapsula uno a uno y
    reconstruye el payload original concatenando en orden hasta ver el
    fragmento con MF=0.

    Lanza MACFrameError si:
    - `frames` esta vacio.
    - el CRC de cualquier fragmento no valida (frame corrupto -> se
      descarta el PDU completo, no hay recuperacion parcial ni ARQ).
    - el seq_num no es el mismo en todos los fragmentos (PDU inconsistente).
    - no se encuentra un fragmento con MF=0 (PDU incompleto)."""
    if not frames:
        raise MACFrameError("reensamblar() recibio una lista vacia de frames")

    payload_acumulado = bytearray()
    seq_num_pdu = None

    for i, frame in enumerate(frames):
        payload, seq_num, frag_flags, _mod_scheme = decapsular(frame)

        if seq_num_pdu is None:
            seq_num_pdu = seq_num
        elif seq_num != seq_num_pdu:
            raise MACFrameError(
                f"seq_num inconsistente en fragmento {i}: esperado {seq_num_pdu}, recibido {seq_num}"
            )

        payload_acumulado += payload

        if not frag_flags_tiene_mf(frag_flags):
            return bytes(payload_acumulado)

    raise MACFrameError(
        f"PDU incompleto: {len(frames)} fragmento(s) recibidos, ninguno con MF=0"
    )
