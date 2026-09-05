"""Codificacion/decodificacion FEC -- codigo CCSDS ("Voyager"), K=7, tasa 1/2.

`claudedocs/arquitectura_transmision_datos.md` deja el esquema FEC como
decision abierta ("convolucional o LDPC", tasa "1/2 o 3/4" -- README.md
linea 259). Para esta prueba se eligio el codigo convolucional CCSDS
estandar (K=7, tasa 1/2, polinomios "Voyager" 0o171/0o133) porque:

1. Ya viene implementado en GNU Radio (`gnuradio.fec.encode_ccsds_27_bb` /
   `decode_ccsds_27_fb`) -- no hay que armar tablas de trellis a mano.
2. Es exactamente la combinacion "BPSK, tasa FEC 1/2" que README.md S5.3
   marca como el objetivo conservador ya validado (~1.9 Mbps DL/UL,
   linea 285) -- no una combinacion inventada para la prueba.

Sigue pendiente escribir el equivalente para LDPC / tasa 3/4 cuando esa
decision de arquitectura se cierre.

Detalle de uso importante (documentado en el docstring del propio bloque
de GNU Radio, no inventado aqui): `decode_ccsds_27_fb` esta pensado para
streaming continuo, no para paquetes -- tiene un delay fijo de 4 bytes
(32 bits) de "flush" antes de que el dato real empiece a salir. Por eso
`codificar()`/`decodificar()` agregan y descartan ese padding.
"""
from gnuradio import gr, fec, blocks

PAD_BYTES = 4  # delay de flush documentado por decode_ccsds_27_fb


def codificar(payload: bytes) -> list:
    """payload (bytes, MSB-first) -> lista de simbolos 0/1 codificados
    (rate 1/2: 16 simbolos por cada byte de entrada, incluido el padding)."""
    entrada = payload + bytes(PAD_BYTES)
    tb = gr.top_block()
    src = blocks.vector_source_b(list(entrada), False)
    enc = fec.encode_ccsds_27_bb()
    snk = blocks.vector_sink_b()
    tb.connect(src, enc, snk)
    tb.run()
    return list(snk.data())


def simbolos_a_soft(simbolos: list) -> list:
    """Mapeo BPSK ideal (sin ruido): simbolo 0 -> -1.0, simbolo 1 -> +1.0,
    igual que documenta decode_ccsds_27_fb."""
    return [1.0 if s == 1 else -1.0 for s in simbolos]


def decodificar(simbolos_soft: list, n_payload_bytes: int) -> bytes:
    """simbolos soft (float, uno por simbolo codificado) -> payload
    decodificado de n_payload_bytes, ya sin el padding de flush."""
    tb = gr.top_block()
    src = blocks.vector_source_f(simbolos_soft, False)
    dec = fec.decode_ccsds_27_fb()
    snk = blocks.vector_sink_b()
    tb.connect(src, dec, snk)
    tb.run()
    completo = bytes(snk.data())
    return completo[PAD_BYTES:PAD_BYTES + n_payload_bytes]


def inyectar_errores(simbolos: list, ber_canal: float, rng) -> tuple:
    """Voltea una fraccion ber_canal de los simbolos codificados (simula
    errores de bit del canal). Devuelve (simbolos_con_errores, n_flips)."""
    salida = list(simbolos)
    n_flips = int(round(len(salida) * ber_canal))
    for i in rng.sample(range(len(salida)), n_flips):
        salida[i] ^= 1
    return salida, n_flips


def ber_bits(a: bytes, b: bytes) -> float:
    """Fraccion de bits distintos entre dos bytes-strings de igual longitud."""
    errores = sum(bin(x ^ y).count("1") for x, y in zip(a, b))
    return errores / (len(a) * 8)
