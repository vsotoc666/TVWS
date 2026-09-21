"""
psd_welch.py — PSD por el método de Welch (ventana Hann, segmentos solapados
promediados), numpy puro.

**Duplicado a propósito de `IA/nucleo.py::calcular_psd`, no importado.**
`IA/nucleo.py` importa `torch` a nivel de módulo (para `SpectralSenseCNN`),
y torch no está instalado en este entorno Linux de pruebas de TRANSMISION
(confirmado 13/09/2026: falla tanto con el Python de sistema como con el
venv `~/envs/SDR` que usa el resto de `TRANSMISION/pruebas/`) — CLAUDE.md ya
documenta que `IA/` y `TRANSMISION/` son máquinas/entornos distintos del
proyecto, y `claudedocs/arquitectura_transmision_datos.md` ya tenía esto
listado como decisión abierta #6 ("Dependencia de torch si SpectralSensor
termina importando IA/nucleo.py directamente en el Gateway de campo —
inferencia solo necesita ONNX Runtime, no PyTorch"). Esta prueba topa con
la misma fricción un nivel más abajo (un script de banco, no el bloque de
producción) — importar `IA/nucleo.py` solo para esta función arrastraría
una dependencia pesada e innecesaria a un entorno que no la tiene ni la
necesita.

El algoritmo es idéntico al de `calcular_psd` (mismo método, misma
ventana, mismo criterio de segmentación) — si `IA/nucleo.py::calcular_psd`
cambia alguna vez, replicar el cambio acá también.
"""

import numpy as np

PSD_LENGTH = 512  # mismo default que IA/nucleo.py — no es un valor libre de esta prueba


def calcular_psd(iq: np.ndarray, n_fft: int = PSD_LENGTH, n_segmentos: int = 20) -> np.ndarray:
    """
    PSD de un vector I/Q por el método de Welch simplificado (ventana Hann,
    segmentos solapados promediados). Ver docstring del módulo: copia
    deliberada de `IA/nucleo.py::calcular_psd`, no una reimplementación
    distinta.

    Args:
        iq:          array complejo (N,) o real (N, 2) con columnas [I, Q]
        n_fft:       puntos de la FFT
        n_segmentos: segmentos a promediar (más = menos varianza)

    Returns:
        psd_db: array (n_fft,) en dB, centrado en DC (fftshift aplicado)
    """
    if iq.ndim == 2:
        iq = iq[:, 0] + 1j * iq[:, 1]

    ventana = np.hanning(n_fft)
    paso = max(1, (len(iq) - n_fft) // n_segmentos)
    acumulado = np.zeros(n_fft)
    n_validos = 0

    for k in range(n_segmentos):
        inicio = k * paso
        fin = inicio + n_fft
        if fin > len(iq):
            break
        segmento = iq[inicio:fin] * ventana
        espectro = np.fft.fftshift(np.fft.fft(segmento))
        acumulado += np.abs(espectro) ** 2
        n_validos += 1

    if n_validos == 0:
        raise ValueError(f"Vector I/Q demasiado corto: {len(iq)} muestras para n_fft={n_fft}")

    psd_lineal = acumulado / n_validos
    return 10 * np.log10(psd_lineal + 1e-12)
