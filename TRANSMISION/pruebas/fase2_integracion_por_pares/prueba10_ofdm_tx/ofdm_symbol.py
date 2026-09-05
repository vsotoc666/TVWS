"""Estructura del simbolo OFDM (Carrier Allocator -> IFFT -> CP), segun
README.md S5.1/S5.2 -- valores tomados literal del documento, no
inventados: FFT de 512 puntos, CP de 1/4 (128 muestras), guardas en 0-25 y
487-511, campo de control in-band en 254-257 con #255 evitada por
DC/LO-leakage.

El vector de frecuencia usa la convencion "centrada" (indice 256 ~ DC) que
el propio README describe -- por eso antes de la IFFT hay que
"des-centrar" con ifftshift, igual que hace `output_is_shifted=True` en
`digital.ofdm_carrier_allocator_cvc` de GNU Radio.

Nota: la posicion exacta de los ~55 subportadoras piloto NO esta fijada en
ningun doc (README solo dice "~55 dispersas", sin indices) -- es una
decision abierta. Esta prueba usa todos los slots de "datos + pilotos"
como datos, sin reservar pilotos, hasta que esa decision se cierre. Por
eso este modulo usa numpy directo en vez de
`digital.ofdm_carrier_allocator_cvc` (que exige una tabla de pilotos
concreta) -- asi se prueba exactamente lo que el doc SI especifica (guardas,
control, CP) sin inventar el patron de pilotos.
"""
import numpy as np

FFT_LEN = 512
CP_LEN = FFT_LEN // 4  # 128, "1/4 del simbolo" (README S5.1)

GUARDA_INF = range(0, 26)     # 26 sub, README S5.2
GUARDA_SUP = range(487, 512)  # 25 sub, README S5.2
CONTROL_IDX = (254, 255, 256, 257)
CONTROL_EVITADA = 255         # DC offset / LO leakage (README S5.2)

DATOS_IDX = list(range(26, 254)) + list(range(258, 487))  # 228 + 229 = 457 slots
N_DATOS_POR_SIMBOLO = len(DATOS_IDX)


def armar_simbolo_ofdm(datos_symbols: list, bits_control: tuple) -> np.ndarray:
    """datos_symbols: hasta N_DATOS_POR_SIMBOLO simbolos I/Q (el resto se
    rellena con 0 si faltan). bits_control: 3 bits (0/1) para #254/#256/#257
    (BPSK: 1->+1, 0->-1). Devuelve el vector de frecuencia de 512 puntos,
    en la convencion centrada (256 ~ DC) descrita en README S5.2."""
    if len(datos_symbols) > N_DATOS_POR_SIMBOLO:
        raise ValueError(f"{len(datos_symbols)} simbolos no caben en {N_DATOS_POR_SIMBOLO} slots de datos")
    if len(bits_control) != 3:
        raise ValueError("bits_control debe tener exactamente 3 bits (#254, #256, #257)")

    vector = np.zeros(FFT_LEN, dtype=complex)
    for idx, val in zip(DATOS_IDX, datos_symbols):
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
    """Reparte una lista larga de simbolos I/Q en varios simbolos OFDM
    (cada uno con hasta N_DATOS_POR_SIMBOLO), rellenando el ultimo con
    ceros si no la completa. Devuelve la lista de vectores de frecuencia
    (uno por simbolo OFDM), listos para ifft_mas_cp()."""
    simbolos = []
    for i in range(0, len(datos_symbols), N_DATOS_POR_SIMBOLO):
        chunk = datos_symbols[i:i + N_DATOS_POR_SIMBOLO]
        simbolos.append(armar_simbolo_ofdm(chunk, bits_control))
    return simbolos
