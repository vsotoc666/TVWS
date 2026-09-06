"""Codificacion/decodificacion FEC -- codigo CCSDS ("Voyager"), K=7, tasa 1/2,
mas perforado (puncturing) a tasa 3/4 sobre el mismo codigo madre.

Decision de arquitectura (cerrada, ver `claudedocs/arquitectura_enlace_datos.md`
S4.3 y `claudedocs/riesgos_arquitectura_transmision.md` Problema 3): el
proyecto estandariza en **CCSDS K=7 convolucional como FEC base para los tres
modos de modulacion (BPSK/QPSK/16-QAM)**, con **tasa 3/4 obtenida perforando
el mismo codigo madre de tasa 1/2** (no un segundo codec). LDPC fue evaluado
y explicitamente NO adoptado, por tres razones (detalle completo en el doc
de arquitectura, no se duplica aqui):

1. LDPC es un codigo de bloque (n,k fijos por palabra) -- el umbral de
   fragmentacion ya cerrado (arquitectura_enlace_datos.md S2.4, 505 bytes/18
   simbolos) se derivo alrededor del modelo de streaming orientado a bytes,
   de longitud variable, del codigo convolucional. Migrar a LDPC exigiria
   rehacer ese umbral para framing alineado a bloque con relleno.
2. El enlace TDD es simetrico -- ambos nodos codifican Y decodifican en
   cada ciclo. El Gateway es un Intel Core Ultra 5, pero el Cliente es un
   Orange Pi 5 ARM64, mucho mas debil. El decoder iterativo de belief-
   propagation de LDPC es inherentemente mas costoso por bit que Viterbi
   (trellis de 64 estados para K=7), y ese costo real en el Orange Pi 5
   nunca se midio (ni se pregunto) en los docs previos -- este riesgo no
   verificado en el nodo mas debil es la razon principal para no adoptar
   LDPC ahora.
3. GNU Radio no trae ninguna matriz LDPC de tasa 3/4 (solo matrices de tasa
   ~0.23-0.58 empaquetadas en `/usr/share/gnuradio/fec/ldpc/`) -- construir
   una es trabajo de diseño de matrices fuera del alcance de este equipo,
   mientras que tasa 3/4 convolucional es gratis via perforado del codigo
   K=7 ya validado.

Deteccion de uso importante (documentado en el docstring del propio bloque
de GNU Radio, no inventado aqui): `decode_ccsds_27_fb` esta pensado para
streaming continuo, no para paquetes -- tiene un delay fijo de 4 bytes
(32 bits) de "flush" antes de que el dato real empiece a salir. Por eso
`codificar()`/`decodificar()` agregan y descartan ese padding.

## Arnes de pruebas: top_block persistente (fix post-Prueba 15)

Version anterior de este archivo creaba, corria y destruia un
`gr.top_block()` de GNU Radio **por cada llamada** a `codificar()`/
`decodificar()`. La Prueba 15 (fase3_loopback_completo/prueba15_throughput_
sostenido/) midio que esto hacia que ~72% del tiempo por paquete fuera puro
overhead de arranque/parada del scheduler, no computo real de FEC -- ver
`claudedocs/riesgos_arquitectura_transmision.md` Problema 3, seccion
"Hallazgo relacionado (Prueba 15...)".

Este archivo ahora usa un `gr.top_block()` **persistente y de inicializacion
diferida** (uno para encode, uno para decode), reutilizado en cada llamada:
se inyectan los datos nuevos via `set_data()`, se corre con `tb.run()`, se
lee la salida del sink, y se limpia el sink con `.reset()` antes de la
siguiente llamada. La firma publica de `codificar()`/`decodificar()` no
cambio -- son varios tests ya aprobados (Pruebas 5, 9, 12, 13, 14, 15) los
que importan estas funciones y ninguno necesito modificarse.
"""
from gnuradio import gr, fec, blocks

PAD_BYTES = 4  # delay de flush documentado por decode_ccsds_27_fb

# --- Estado persistente del encoder (inicializacion diferida) ---
_enc_tb = None
_enc_src = None
_enc_snk = None

# --- Estado persistente del decoder (inicializacion diferida) ---
_dec_tb = None
_dec_src = None
_dec_snk = None


def _get_encoder():
    global _enc_tb, _enc_src, _enc_snk
    if _enc_tb is None:
        _enc_tb = gr.top_block()
        _enc_src = blocks.vector_source_b([], False)
        enc = fec.encode_ccsds_27_bb()
        _enc_snk = blocks.vector_sink_b()
        _enc_tb.connect(_enc_src, enc, _enc_snk)
    return _enc_tb, _enc_src, _enc_snk


def _get_decoder():
    global _dec_tb, _dec_src, _dec_snk
    if _dec_tb is None:
        _dec_tb = gr.top_block()
        _dec_src = blocks.vector_source_f([], False)
        dec = fec.decode_ccsds_27_fb()
        _dec_snk = blocks.vector_sink_b()
        _dec_tb.connect(_dec_src, dec, _dec_snk)
    return _dec_tb, _dec_src, _dec_snk


def codificar(payload: bytes) -> list:
    """payload (bytes, MSB-first) -> lista de simbolos 0/1 codificados
    (rate 1/2: 16 simbolos por cada byte de entrada, incluido el padding)."""
    entrada = list(payload) + [0] * PAD_BYTES
    tb, src, snk = _get_encoder()
    src.set_data(entrada)
    tb.run()
    salida = list(snk.data())
    snk.reset()
    return salida


def simbolos_a_soft(simbolos: list) -> list:
    """Mapeo BPSK ideal (sin ruido): simbolo 0 -> -1.0, simbolo 1 -> +1.0,
    igual que documenta decode_ccsds_27_fb."""
    return [1.0 if s == 1 else -1.0 for s in simbolos]


def decodificar(simbolos_soft: list, n_payload_bytes: int) -> bytes:
    """simbolos soft (float, uno por simbolo codificado) -> payload
    decodificado de n_payload_bytes, ya sin el padding de flush."""
    tb, src, snk = _get_decoder()
    src.set_data(list(simbolos_soft))
    tb.run()
    completo = bytes(snk.data())
    snk.reset()
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


# --- Tasa 3/4 via perforado (puncturing) del mismo codigo madre 1/2 ---
#
# Patron elegido (periodo 6 -- 3 bits de entrada -> 6 bits codificados a
# tasa 1/2 -> se perforan 2 -> quedan 4 -> tasa 3/4 efectiva):
#
#   posicion en el bloque de 6 (0-indexado):   0    1    2    3    4    5
#   bit proviene de la rama:                   G1   G2   G1   G2   G1   G2
#   se mantiene (True) / se perfora (False):   M    M    M    D    M    D
#
# Es decir, PATRON_PERFORADO_3_4 = (True, True, True, False, True, False):
# se perforan las posiciones 3 y 5 de cada bloque de 6 (la segunda salida
# -G2- de los ultimos dos pares de bits de entrada del bloque). Convencion
# elegida arbitrariamente por este equipo (no es una tabla de un estandar
# copiada de memoria) -- lo unico que importa es que TX (`perforar`) y RX
# (`despuncturar`) usen exactamente el mismo patron, lo cual se prueba con
# un round-trip bit-exacto sin errores de canal antes de confiar en
# cualquier numero de BER (ver test_puncturing_r34.py).
PATRON_PERFORADO_3_4 = (True, True, True, False, True, False)


def perforar(bits_codificados: list, patron: tuple = PATRON_PERFORADO_3_4) -> list:
    """Perfora (descarta) bits de una secuencia codificada a tasa 1/2 segun
    `patron` (tuple de bool/0-1, se repite ciclicamente). Devuelve solo los
    bits "mantenidos", en orden -- lista mas corta que la entrada."""
    periodo = len(patron)
    return [b for i, b in enumerate(bits_codificados) if patron[i % periodo]]


def despuncturar(simbolos_soft: list, n_bits_codificados_original: int,
                  patron: tuple = PATRON_PERFORADO_3_4) -> list:
    """Inversa de `perforar`: reinserta 0.0 (erasure neutro, "sin
    informacion") en cada posicion que fue perforada en TX, reconstruyendo
    una lista de longitud `n_bits_codificados_original` (la longitud de la
    salida de tasa 1/2 antes de perforar) lista para pasar sin cambios a
    `decodificar()`. 0.0 es el valor correcto de relleno porque
    `decode_ccsds_27_fb` espera simbolos soft donde +1.0/-1.0 son los
    puntos BPSK ideales sin ruido (convencion ya documentada en este mismo
    archivo via `simbolos_a_soft`) -- 0.0 esta exactamente a mitad de
    camino entre ambos, es decir "misma probabilidad de 0 que de 1", la
    forma estandar de alimentar un bit perforado/desconocido a un Viterbi
    blando."""
    periodo = len(patron)
    salida = []
    it = iter(simbolos_soft)
    for i in range(n_bits_codificados_original):
        if patron[i % periodo]:
            salida.append(next(it))
        else:
            salida.append(0.0)
    return salida
