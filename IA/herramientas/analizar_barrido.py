"""
analizar_barrido.py
====================
Lee el CSV producido por `rtl_power` (invocado desde escanear_tvws.sh) y lo
mapea sobre la grilla de 39 canales TVWS del proyecto (14-52, ver
IA/nucleo.py / IA/inferencia.py), reportando para cada uno:

    - potencia media dentro del canal (dB, relativo al nivel que reporta
      rtl_power -- no es una medida absoluta calibrada, la antena genérica
      no está calibrada, ver IA/pipeline_dataset_v2.md)
    - margen sobre el piso de ruido global (percentil 10 de todo el barrido)
    - dispersión interna del canal (std de los bins dentro de su ancho)
    - candidato_ocupado: margen > umbral (default 7dB, ajustable)

Esto es una herramienta de caracterización/QA del entorno RF real, NO el
etiquetado final del dataset -- el etiquetado real usa el RNF como fuente
primaria (ver memoria de proyecto "referencia_canales_tv_peru") y este
detector de energía como cruce de QA, tal como se diseñó en la sesión que
definió el pipeline de Fase 1.

Uso:
    python3 analizar_barrido.py barrido.csv --salida /ruta/prefijo
    MPLBACKEND=Agg python3 analizar_barrido.py barrido.csv --salida prefijo --umbral-db 7
"""

import argparse
import csv
import os

import numpy as np

CANAL_MIN = 14
CANAL_MAX = 52
ANCHO_CANAL_HZ = 6_000_000


def centro_canal_hz(canal: int) -> int:
    return 470_000_000 + (canal - CANAL_MIN) * ANCHO_CANAL_HZ + ANCHO_CANAL_HZ // 2


def leer_rtl_power_csv(ruta: str):
    """
    Formato real de rtl_power: UNA fila por salto de frecuencia (no una fila
    por barrido completo) -- con un barrido de banda ancha como el de este
    proyecto (470-704 MHz en saltos de ~2.8 MHz) cada pasada ya genera ~100
    filas, cada una con su propio (freq_baja, freq_alta, paso) porque el
    paso real (Hz step) depende del recorte de bordes (-c) y puede diferir
    ligeramente entre saltos.

    Si el archivo tiene varias pasadas en el tiempo (barrido continuo con
    -n > 1 en escanear_tvws.sh), cada salto se repite con timestamps
    distintos pero el mismo (freq_baja, freq_alta) -- se agrupan por rango
    de frecuencia y se promedian en potencia lineal entre pasadas.
    Luego los saltos se concatenan en orden de frecuencia para formar el
    espectro completo de la banda.
    """
    segmentos: dict[tuple[int, int], list[np.ndarray]] = {}
    pasos: dict[tuple[int, int], float] = {}

    with open(ruta, newline="") as f:
        lector = csv.reader(f)
        for fila in lector:
            fila = [c.strip() for c in fila if c.strip() != ""]
            if len(fila) < 7:
                continue
            fb, fa, paso = int(float(fila[2])), int(float(fila[3])), float(fila[4])
            valores = np.array([float(x) for x in fila[6:]], dtype=np.float64)
            clave = (fb, fa)
            segmentos.setdefault(clave, []).append(valores)
            pasos[clave] = paso

    if not segmentos:
        raise ValueError(f"No se pudo parsear ningún dato de {ruta}")

    frecuencias_totales = []
    potencia_totales = []

    for (fb, fa) in sorted(segmentos.keys()):
        pasadas = segmentos[(fb, fa)]
        n_bins = min(len(v) for v in pasadas)
        matriz = np.stack([v[:n_bins] for v in pasadas])

        # Promedio en potencia lineal (mW relativo) entre pasadas repetidas
        lineal = 10 ** (matriz / 10.0)
        promedio_db = 10 * np.log10(lineal.mean(axis=0))

        paso = pasos[(fb, fa)]
        frecuencias_totales.append(fb + np.arange(n_bins) * paso)
        potencia_totales.append(promedio_db)

    frecuencias = np.concatenate(frecuencias_totales)
    potencia_db = np.concatenate(potencia_totales)

    orden = np.argsort(frecuencias)
    return frecuencias[orden], potencia_db[orden]


def construir_tabla_canales(frecuencias, potencia_db, umbral_db: float):
    piso_ruido = float(np.percentile(potencia_db, 10))
    tabla = []

    for canal in range(CANAL_MIN, CANAL_MAX + 1):
        f0 = 470_000_000 + (canal - CANAL_MIN) * ANCHO_CANAL_HZ
        f1 = f0 + ANCHO_CANAL_HZ
        mascara = (frecuencias >= f0) & (frecuencias < f1)

        if not mascara.any():
            continue

        valores = potencia_db[mascara]
        media = float(valores.mean())
        margen = media - piso_ruido
        dispersion = float(valores.std())

        tabla.append({
            "canal": canal,
            "centro_mhz": centro_canal_hz(canal) / 1e6,
            "media_db": round(media, 2),
            "margen_db": round(margen, 2),
            "dispersion_db": round(dispersion, 2),
            "candidato_ocupado": margen > umbral_db,
        })

    return tabla, piso_ruido


def imprimir_tabla(tabla, piso_ruido):
    print(f"Piso de ruido global (percentil 10): {piso_ruido:.2f} dB\n")
    print(f"{'Canal':>5} {'Centro(MHz)':>12} {'Media(dB)':>10} {'Margen(dB)':>11} {'Disp(dB)':>9}  Candidato")
    for fila in tabla:
        marca = "OCUPADO" if fila["candidato_ocupado"] else "-"
        print(f"{fila['canal']:>5} {fila['centro_mhz']:>12.1f} {fila['media_db']:>10.2f} "
              f"{fila['margen_db']:>11.2f} {fila['dispersion_db']:>9.2f}  {marca}")


def guardar_csv(tabla, ruta):
    with open(ruta, "w", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(tabla[0].keys()))
        escritor.writeheader()
        escritor.writerows(tabla)


def graficar(frecuencias, potencia_db, tabla, piso_ruido, ruta_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(frecuencias / 1e6, potencia_db, linewidth=0.5, color="steelblue")
    ax.axhline(piso_ruido, color="gray", linestyle="--", linewidth=1, label="piso de ruido (p10)")

    for fila in tabla:
        color = "red" if fila["candidato_ocupado"] else "green"
        f0 = fila["centro_mhz"] - 3
        ax.axvspan(f0, f0 + 6, alpha=0.08, color=color)

    ax.set_xlabel("Frecuencia (MHz)")
    ax.set_ylabel("Potencia (dB, relativo)")
    ax.set_title("Barrido TVWS (canales 14-52) -- rojo: candidato ocupado, verde: libre")
    ax.legend()
    fig.tight_layout()
    fig.savefig(ruta_png, dpi=120)
    print(f"Gráfica: {ruta_png}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_entrada", help="CSV de salida de rtl_power")
    parser.add_argument("--salida", required=True, help="Prefijo de archivos de salida")
    parser.add_argument("--umbral-db", type=float, default=7.0,
                         help="Margen sobre piso de ruido para marcar 'candidato_ocupado' (default: 7.0)")
    parser.add_argument("--sin-grafica", action="store_true", help="No generar PNG")
    args = parser.parse_args()

    frecuencias, potencia_db = leer_rtl_power_csv(args.csv_entrada)
    tabla, piso_ruido = construir_tabla_canales(frecuencias, potencia_db, args.umbral_db)

    imprimir_tabla(tabla, piso_ruido)

    os.makedirs(os.path.dirname(args.salida) or ".", exist_ok=True)
    guardar_csv(tabla, args.salida + "_canales.csv")
    print(f"\nTabla por canal: {args.salida}_canales.csv")

    if not args.sin_grafica:
        graficar(frecuencias, potencia_db, tabla, piso_ruido, args.salida + "_plot.png")


if __name__ == "__main__":
    main()
