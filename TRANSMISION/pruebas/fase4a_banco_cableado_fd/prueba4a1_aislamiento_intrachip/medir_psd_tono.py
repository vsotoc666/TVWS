#!/usr/bin/env python3
"""
Captura una ráfaga IQ de un bladeRF (TX1 transmitiendo un tono CW en banda
base a `--offset_hz` del centro, RX1 capturando) y mide la potencia de pico
del tono en el PSD, más el piso de ruido de referencia — bloque de captura
de la Prueba 4a-1 (aislamiento intra-chip TX1->RX1). Ver README.md de esta
carpeta para la metodología completa (por qué dos corridas — calibración y
medición — y cómo se combinan en `calcular_aislamiento.py`).

Modo --simular: genera IQ sintético (tono + ruido gaussiano complejo) en vez
de abrir el bladeRF real — permite validar toda la lógica de este script
(detección de pico, piso de ruido, JSON de salida) sin hardware conectado.
Usado por `test_medir_psd_tono.py`. No requiere GNU Radio ni el venv
`~/envs/SDR` — solo numpy.

Modo real (sin --simular): requiere el venv `~/envs/SDR` (gnuradio 3.10.1.1
+ numpy 1.26.4 — ver TRANSMISION/pruebas/README.md, nota de entorno; el
Python de sistema tiene un choque de ABI numpy/gnuradio ya documentado ahí)
y gr-osmosdr con el módulo bladerf habilitado (confirmado 13/09/2026 en el
entorno de desarrollo: `soapysdr0.8-module-bladerf` instalado, gr-osmosdr
funcional vía el venv — no se encontró gr-bladeRF nativo en esta máquina,
pero no hace falta: osmosdr ya envuelve libbladeRF).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from psd_welch import calcular_psd, PSD_LENGTH


def _capturar_simulado(n_muestras, samp_rate, offset_hz, snr_db, rx_gain_db, semilla=None):
    """IQ sintético: tono a `offset_hz` + ruido gaussiano complejo.

    `rx_gain_db` escala tono y ruido por igual (10**(rx_gain_db/20)) — modela
    que la ganancia RX se aplica sobre la señal completa antes del ADC, sin
    cambiar la relación señal/ruido (aproximación estándar para una cadena
    limitada por ruido referido a la entrada, no por el propio escalón de
    ganancia). `snr_db` es relativo a un piso de ruido de referencia fijo
    (amplitud 1.0) — junto con `rx_gain_db`, determina la potencia de pico
    absoluta en dBFS que el resto del pipeline (`medir`) va a leer.
    Solo para --simular (validación de la lógica sin hardware)."""
    rng = np.random.default_rng(semilla)
    t = np.arange(n_muestras) / samp_rate
    amplitud_ruido = 1.0
    amplitud_tono = amplitud_ruido * 10 ** (snr_db / 20)
    tono = amplitud_tono * np.exp(2j * np.pi * offset_hz * t)
    ruido = (rng.normal(size=n_muestras) + 1j * rng.normal(size=n_muestras)) * amplitud_ruido / np.sqrt(2)
    escala = 10 ** (rx_gain_db / 20)
    return (escala * (tono + ruido)).astype(np.complex64)


def _capturar_bladerf(n_muestras, samp_rate, freq_hz, offset_hz, tx_gain_db, rx_gain_db, device_args):
    """Captura real: TX1 transmite un tono CW a `offset_hz` de `freq_hz`
    mientras RX1 captura `n_muestras` del MISMO bladeRF físico (un solo
    `device_args`, p.ej. 'bladerf=0', usado para el source Y el sink en el
    mismo top_block — así se mide acoplamiento intra-chip real, no dos
    unidades distintas)."""
    from gnuradio import gr, blocks, analog
    import osmosdr

    tb = gr.top_block()

    # --- TX1: tono CW en banda base, offset_hz respecto al centro ---
    fuente_tono = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, offset_hz, 1.0, 0)
    tx = osmosdr.sink(args=device_args)
    tx.set_sample_rate(samp_rate)
    tx.set_center_freq(freq_hz, 0)
    tx.set_gain(tx_gain_db, 0)
    tb.connect(fuente_tono, tx)

    # --- RX1: captura de n_muestras ---
    rx = osmosdr.source(args=device_args)
    rx.set_sample_rate(samp_rate)
    rx.set_center_freq(freq_hz, 0)
    rx.set_gain(rx_gain_db, 0)
    cabeza = blocks.head(gr.sizeof_gr_complex, n_muestras)
    sumidero = blocks.vector_sink_c()
    tb.connect(rx, cabeza, sumidero)

    tb.start()
    # blocks.head no detiene la rama TX (sig_source es infinita) -> tb.run()
    # nunca retornaría solo; se para manualmente tras el tiempo esperado.
    duracion_esperada = n_muestras / samp_rate
    time.sleep(duracion_esperada + 1.0)  # margen: settling de retune + streaming USB
    tb.stop()
    tb.wait()

    datos = np.array(sumidero.data(), dtype=np.complex64)
    if len(datos) < n_muestras:
        raise RuntimeError(
            f"Solo se capturaron {len(datos)}/{n_muestras} muestras -- revisar "
            "conexión USB/alimentación del bladeRF, o subir el margen de tiempo "
            "de este script si la máquina es lenta entregando muestras."
        )
    return datos[:n_muestras]


def medir(iq, samp_rate, offset_hz, n_fft, n_segmentos, ventana_pico_bins, margen_deteccion_db):
    """A partir del IQ capturado, calcula el PSD (Welch/Hann) y ubica el pico
    esperado del tono (`offset_hz`) dentro de una ventana de búsqueda (tolera
    algo de CFO). El piso de ruido se estima con la mediana del resto del
    espectro, excluyendo la ventana del pico y una guarda alrededor de DC
    (contaminada por el LO leakage del AD9361, ver SPECS EQUIPOS/SDR_ENLACE
    — no queremos confundir esa fuga, ya conocida y de otro origen, con el
    tono de esta prueba).

    Devuelve pico_dbfs, piso_ruido_dbfs, snr_pico_db y detectado (bool,
    snr_pico_db > margen_deteccion_db)."""
    psd_db = calcular_psd(iq, n_fft=n_fft, n_segmentos=n_segmentos)  # centrado en DC (fftshift)

    bin_dc = n_fft // 2
    bin_offset = int(round(offset_hz / samp_rate * n_fft))
    bin_tono = bin_dc + bin_offset
    if not (0 <= bin_tono < n_fft):
        raise ValueError(
            f"offset_hz={offset_hz} cae fuera del ancho de banda capturado "
            f"(samp_rate={samp_rate}) -- el bin calculado ({bin_tono}) no "
            f"existe en un FFT de {n_fft} puntos. Bajar --offset_hz o subir --samp_rate."
        )

    lo = max(0, bin_tono - ventana_pico_bins)
    hi = min(n_fft, bin_tono + ventana_pico_bins + 1)
    pico_dbfs = float(np.max(psd_db[lo:hi]))

    mascara = np.ones(n_fft, dtype=bool)
    mascara[lo:hi] = False
    mascara[max(0, bin_dc - 5):min(n_fft, bin_dc + 6)] = False
    piso_ruido_dbfs = float(np.median(psd_db[mascara]))

    snr_pico_db = pico_dbfs - piso_ruido_dbfs
    return {
        "pico_dbfs": pico_dbfs,
        "piso_ruido_dbfs": piso_ruido_dbfs,
        "snr_pico_db": snr_pico_db,
        "detectado": snr_pico_db > margen_deteccion_db,
        "bin_tono": bin_tono,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modo", choices=["calibracion", "medicion"], required=True,
                   help="'calibracion': TX1->cable+atenuador conocido->RX1. "
                        "'medicion': TX1 sin cable cruzado (RX1 terminado/desconectado) -- mide solo fuga intra-chip.")
    p.add_argument("--freq_hz", type=float, default=600e6,
                   help="Frecuencia central (Hz). Default 600 MHz (referencia del proyecto, README §3.3).")
    p.add_argument("--offset_hz", type=float, default=500e3,
                   help="Offset del tono CW respecto al centro (Hz). Default 500 kHz -- lejos de la banda DC "
                        "contaminada por LO leakage del AD9361.")
    p.add_argument("--samp_rate", type=float, default=4e6,
                   help="Tasa de muestreo (Hz). Default 4 MSPS.")
    p.add_argument("--tx_gain_db", type=float, required=True,
                   help="Ganancia TX del bladeRF (dB). DEBE ser idéntica entre la corrida de calibración y la "
                        "de medición -- calcular_aislamiento.py lo verifica y rechaza si no coincide.")
    p.add_argument("--rx_gain_db", type=float, required=True,
                   help="Ganancia RX del bladeRF (dB). Puede (normalmente debe) ser distinta entre calibración "
                        "y medición -- la fuga intra-chip suele ser mucho más débil que la ruta calibrada.")
    p.add_argument("--atenuador_db", type=float, default=None,
                   help="Atenuación total (dB) del atenuador físico en el cable de calibración. "
                        "Obligatorio si --modo calibracion.")
    p.add_argument("--n_muestras", type=int, default=2_000_000, help="Muestras IQ a capturar.")
    p.add_argument("--n_fft", type=int, default=PSD_LENGTH,
                   help=f"Tamaño de FFT para el PSD (default: {PSD_LENGTH}, igual que IA/nucleo.py). Subir esto "
                        "(no --n_segmentos) es la palanca principal si el tono no se distingue del ruido -- un "
                        "bin más angosto concentra más energía relativa del tono frente al ruido de banda ancha.")
    p.add_argument("--n_segmentos", type=int, default=40,
                   help="Segmentos a promediar (Welch) -- reduce la varianza de la ESTIMACIÓN del piso de ruido, "
                        "no mejora el SNR real del tono (para eso, subir --n_fft).")
    p.add_argument("--ventana_pico_bins", type=int, default=2,
                   help="+/- bins alrededor del bin esperado del tono donde buscar el pico real (tolera algo de CFO).")
    p.add_argument("--margen_deteccion_db", type=float, default=8.0,
                   help="SNR mínimo (dB) del pico sobre el piso de ruido para considerarlo 'detectado' en vez de "
                        "reportar solo un piso de ruido (cota inferior de aislamiento).")
    p.add_argument("--device_args", default="bladerf=0",
                   help="Argumentos de dispositivo para osmosdr (default: 'bladerf=0').")
    p.add_argument("--salida", required=True, help="Ruta del JSON de salida con resultados + metadatos.")
    p.add_argument("--simular", action="store_true",
                   help="No abre hardware real -- genera IQ sintético para validar este script sin bladeRF.")
    p.add_argument("--simular_snr_db", type=float, default=20.0,
                   help="Solo con --simular: SNR del tono sintético inyectado.")
    p.add_argument("--simular_semilla", type=int, default=None,
                   help="Solo con --simular: semilla del generador aleatorio, para resultados reproducibles.")
    args = p.parse_args()

    if args.modo == "calibracion" and args.atenuador_db is None:
        p.error("--atenuador_db es obligatorio en --modo calibracion (dB del atenuador físico instalado en el cable).")

    if args.simular:
        iq = _capturar_simulado(args.n_muestras, args.samp_rate, args.offset_hz,
                                 args.simular_snr_db, args.rx_gain_db, args.simular_semilla)
    else:
        iq = _capturar_bladerf(args.n_muestras, args.samp_rate, args.freq_hz, args.offset_hz,
                                args.tx_gain_db, args.rx_gain_db, args.device_args)

    resultado = medir(iq, args.samp_rate, args.offset_hz, args.n_fft, args.n_segmentos,
                       args.ventana_pico_bins, args.margen_deteccion_db)

    salida = {
        "modo": args.modo,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "freq_hz": args.freq_hz,
        "offset_hz": args.offset_hz,
        "samp_rate": args.samp_rate,
        "tx_gain_db": args.tx_gain_db,
        "rx_gain_db": args.rx_gain_db,
        "atenuador_db": args.atenuador_db,
        "n_muestras": args.n_muestras,
        "n_fft": args.n_fft,
        "n_segmentos": args.n_segmentos,
        "simulado": args.simular,
        **resultado,
    }
    Path(args.salida).write_text(json.dumps(salida, indent=2))
    print(json.dumps(salida, indent=2))

    if not resultado["detectado"]:
        print(
            f"\n⚠ Tono NO distinguible del piso de ruido (SNR pico {resultado['snr_pico_db']:.1f} dB "
            f"<= margen {args.margen_deteccion_db} dB).\n"
            "  - En --modo medicion esto es un resultado VÁLIDO: significa que el aislamiento es al menos el "
            "que calcular_aislamiento.py derive usando el piso de ruido (cota inferior, no el valor exacto).\n"
            "  - En --modo calibracion normalmente indica que el atenuador usado es demasiado grande o la "
            "ganancia RX demasiado baja para esta corrida -- revisar antes de fiarse del resultado.\n"
            "  - Antes de asumir 'no se puede medir': subir --n_fft (más resolución = más energía del tono "
            "por bin frente al ruido) antes que subir --rx_gain_db (la ganancia no mejora el SNR real).",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
