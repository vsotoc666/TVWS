"""Estructura del simbolo OFDM (Carrier Allocator -> IFFT -> CP), segun
README.md S5.1/S5.2 -- valores tomados literal del documento, no
inventados: FFT de 512 puntos, CP de 1/4 (128 muestras), guardas en 0-25 y
487-511, campo de control in-band en 254-257 con #255 evitada por
DC/LO-leakage.

El vector de frecuencia usa la convencion "centrada" (indice 256 ~ DC) que
el propio README describe -- por eso antes de la IFFT hay que
"des-centrar" con ifftshift, igual que hace `output_is_shifted=True` en
`digital.ofdm_carrier_allocator_cvc` de GNU Radio.

Patron de pilotos (cerrado, ver claudedocs/riesgos_arquitectura_transmision.md
Problema 4 -- decision congelada, no re-litigar): comb-type escalonado
(staggered), stride 8, offset = indice_simbolo % 8, igual que LTE -- el
subconjunto de pilotos rota simbolo a simbolo para cubrir toda la grilla
de frecuencia en un ciclo de 8 simbolos sin overhead extra. El pool logico
"datos+pilotos" es DATOS_IDX (todo lo que no es guarda ni control, 457
posiciones); PILOTOS_POR_OFFSET[offset] = DATOS_IDX[offset::8] son las
posiciones piloto de ESE simbolo, y DATOS_IDX_POR_OFFSET[offset] es el
resto (las posiciones de datos reales de ese simbolo). Hay una
irregularidad conocida y aceptada: el espaciado del peine se ensancha de
8 a 12 alrededor del hueco de control (#254-257), porque el peine ignora
ese hueco -- no es un bug, no se corrige.

Valores piloto: BPSK fijo, alternando +1.0/-1.0 segun la posicion del
piloto DENTRO del simbolo (primer piloto del simbolo = +1.0, segundo =
-1.0, etc.), deterministico e igual en ambos nodos (enlace simetrico,
mismo firmware, sin negociacion en tiempo de ejecucion).

Como la cantidad de pilotos por simbolo no es constante (58 en offset 0,
57 en offsets 1-7), la capacidad de DATOS por simbolo tampoco lo es (399
en offset 0, 400 en offsets 1-7) -- ya no hay un N_DATOS_POR_SIMBOLO unico
fijo, ver N_DATOS_POR_SIMBOLO_POR_OFFSET.
"""
import numpy as np

FFT_LEN = 512
CP_LEN = FFT_LEN // 4  # 128, "1/4 del simbolo" (README S5.1)

GUARDA_INF = range(0, 26)     # 26 sub, README S5.2
GUARDA_SUP = range(487, 512)  # 25 sub, README S5.2
CONTROL_IDX = (254, 255, 256, 257)
CONTROL_EVITADA = 255         # DC offset / LO leakage (README S5.2)

# Pool logico "datos+pilotos": todo lo que no es guarda ni control.
DATOS_IDX = list(range(26, 254)) + list(range(258, 487))  # 228 + 229 = 457 slots
N_DATOS_POR_SIMBOLO = len(DATOS_IDX)  # 457 -- capacidad del POOL, no de datos reales (ver *_POR_OFFSET)

PILOTO_STRIDE = 8

# PILOTOS_POR_OFFSET[offset] = posiciones (indices FFT) que son piloto en
# un simbolo cuyo (indice_simbolo % 8) == offset.
# DATOS_IDX_POR_OFFSET[offset] = el resto del pool (posiciones de datos
# reales) para ese mismo offset.
PILOTOS_POR_OFFSET = {off: DATOS_IDX[off::PILOTO_STRIDE] for off in range(PILOTO_STRIDE)}
DATOS_IDX_POR_OFFSET = {
    off: [idx for idx in DATOS_IDX if idx not in set(PILOTOS_POR_OFFSET[off])]
    for off in range(PILOTO_STRIDE)
}
N_DATOS_POR_SIMBOLO_POR_OFFSET = {off: len(DATOS_IDX_POR_OFFSET[off]) for off in range(PILOTO_STRIDE)}


def _valores_piloto(n_pilotos: int) -> list:
    """BPSK alternado +1.0/-1.0 empezando en +1.0, determinista."""
    return [1.0 if i % 2 == 0 else -1.0 for i in range(n_pilotos)]


def armar_simbolo_ofdm(datos_symbols: list, bits_control: tuple, indice_simbolo: int = 0) -> np.ndarray:
    """datos_symbols: hasta N_DATOS_POR_SIMBOLO_POR_OFFSET[offset] simbolos
    I/Q (el resto se rellena con 0 si faltan), donde offset = indice_simbolo
    % 8. bits_control: 3 bits (0/1) para #254/#256/#257 (BPSK: 1->+1,
    0->-1). Las posiciones piloto de este simbolo (PILOTOS_POR_OFFSET[offset])
    se llenan con BPSK alternado +1.0/-1.0, deterministico. Devuelve el
    vector de frecuencia de 512 puntos, en la convencion centrada (256 ~
    DC) descrita en README S5.2."""
    offset = indice_simbolo % PILOTO_STRIDE
    datos_idx = DATOS_IDX_POR_OFFSET[offset]
    pilotos_idx = PILOTOS_POR_OFFSET[offset]
    n_datos = len(datos_idx)

    if len(datos_symbols) > n_datos:
        raise ValueError(
            f"{len(datos_symbols)} simbolos no caben en {n_datos} slots de datos "
            f"(simbolo OFDM #{indice_simbolo}, offset {offset})"
        )
    if len(bits_control) != 3:
        raise ValueError("bits_control debe tener exactamente 3 bits (#254, #256, #257)")

    vector = np.zeros(FFT_LEN, dtype=complex)
    for idx, val in zip(datos_idx, datos_symbols):
        vector[idx] = val

    for idx, val in zip(pilotos_idx, _valores_piloto(len(pilotos_idx))):
        vector[idx] = val

    b254, b256, b257 = bits_control
    vector[254] = 1.0 if b254 else -1.0
    vector[CONTROL_EVITADA] = 0.0
    vector[256] = 1.0 if b256 else -1.0
    vector[257] = 1.0 if b257 else -1.0
    return vector


def ifft_mas_cp(vector_frecuencia: np.ndarray) -> np.ndarray:
    """Vector de frecuencia centrado (512) -> simbolo en tiempo con CP (640)."""
    señal_tiempo = np.fft.ifft(np.fft.ifftshift(vector_frecuencia))
    cp = señal_tiempo[-CP_LEN:]
    return np.concatenate([cp, señal_tiempo])


def quitar_cp_y_fft(simbolo_con_cp: np.ndarray) -> np.ndarray:
    """Inverso de ifft_mas_cp: quita el CP y vuelve al dominio de
    frecuencia centrado (para verificar el round-trip)."""
    señal_tiempo = simbolo_con_cp[CP_LEN:]
    return np.fft.fftshift(np.fft.fft(señal_tiempo))


def dividir_en_simbolos_ofdm(datos_symbols: list, bits_control: tuple) -> list:
    """Reparte una lista larga de simbolos I/Q en varios simbolos OFDM,
    consumiendo en cada simbolo la capacidad de datos que le toca segun su
    offset dentro del ciclo de pilotos de 8 (399 en offset 0, 400 en
    offsets 1-7), rellenando el ultimo simbolo con ceros si no la
    completa. Devuelve la lista de vectores de frecuencia (uno por simbolo
    OFDM, con pilotos ya escritos), listos para ifft_mas_cp()."""
    simbolos = []
    puntero = 0
    indice_simbolo = 0
    n = len(datos_symbols)
    while puntero < n:
        offset = indice_simbolo % PILOTO_STRIDE
        n_datos = N_DATOS_POR_SIMBOLO_POR_OFFSET[offset]
        chunk = datos_symbols[puntero:puntero + n_datos]
        simbolos.append(armar_simbolo_ofdm(chunk, bits_control, indice_simbolo=indice_simbolo))
        puntero += n_datos
        indice_simbolo += 1
    return simbolos
