"""Modulacion/demodulacion -- BPSK, QPSK, 16-QAM via gnuradio.digital.

A diferencia de las Pruebas 2/3/5, los objetos `constellation` de
`gnuradio.digital` son invocables directo desde Python puro
(`map_to_points_v` / `decision_maker_v`), sin necesidad de armar un
`top_block` con bloques de streaming -- por eso este modulo no depende de
`gr.top_block`.

README.md linea 259 fija el set de esquemas que el proyecto usa
(BPSK/QPSK/16-QAM), consistente con la tabla de throughput de S5.3 -- no
es una eleccion inventada aqui, a diferencia del header MAC (Prueba 4) o
el esquema FEC (Prueba 5), que si eran decisiones abiertas.
"""
from gnuradio import digital

ESQUEMAS = {
    "BPSK": digital.constellation_bpsk(),
    "QPSK": digital.constellation_qpsk(),
    "16-QAM": digital.constellation_16qam(),
}


def bits_a_chunks(bits: list, k: int) -> list:
    """Empaqueta una lista de bits (0/1) en enteros de k bits, MSB primero."""
    assert len(bits) % k == 0, f"{len(bits)} bits no es multiplo de {k}"
    chunks = []
    for i in range(0, len(bits), k):
        valor = 0
        for b in bits[i:i + k]:
            valor = (valor << 1) | b
        chunks.append(valor)
    return chunks


def chunks_a_bits(chunks: list, k: int) -> list:
    """Inverso de bits_a_chunks."""
    bits = []
    for c in chunks:
        for shift in range(k - 1, -1, -1):
            bits.append((c >> shift) & 1)
    return bits


def modular(chunks: list, constelacion) -> list:
    return [constelacion.map_to_points_v(c)[0] for c in chunks]


def demodular(simbolos: list, constelacion) -> list:
    """Canal ideal: decide el punto de constelacion mas cercano a cada
    simbolo recibido (aqui, sin ruido, el simbolo recibido es exacto)."""
    return [constelacion.decision_maker_v([s]) for s in simbolos]
