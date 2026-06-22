"""
generar_dataset_sintetico_v2.py
================================
Generador de dataset sintético v2 — sub-bandas completas de 56 MHz.

DIFERENCIA CLAVE CON v1:
  v1 (generar_dataset_sintetico.py) simulaba capturas de UN canal individual
  con RTL-SDR (2.4 MHz de BW), como en el dataset real de Fase 1. Cada muestra
  tenía 1 de 9 etiquetas válidas y 8 marcadas como -1 (desconocido).

  v2 simula el formato de OPERACIÓN EN CAMPO: una sub-banda completa de 56 MHz
  (512 puntos PSD) capturada de una sola vez por el bladeRF RX2, con los 9
  canales TVWS visibles y TODOS etiquetados. Este es exactamente el formato
  que espera SpectralSenseInferencia.clasificar_subbanda() en producción.

  Esto resuelve el problema de F1=0 observado con v1 (donde el 89% de las
  etiquetas eran -1) y permite evaluar la capacidad REAL del modelo en la
  tarea multi-etiqueta para la que fue diseñado.

Características simuladas por sub-banda:
  - Múltiples canales ocupados/libres simultáneamente (independientes)
  - Fuga espectral entre canales adyacentes (adjacent channel leakage)
  - Variación de piso de ruido por captura (RF ambiente distinto)
  - Respuesta en frecuencia no plana del bladeRF (más suave que RTL-SDR)
  - Variabilidad de SNR, offset de frecuencia y nivel por canal

Uso:
  python generar_dataset_sintetico_v2.py
  python generar_dataset_sintetico_v2.py --n_muestras 8000 --salida ./dataset_v2
  python generar_dataset_sintetico_v2.py --n_muestras 4000 --ocupacion_media 0.35 --visualizar

Salida:
  dataset_v2/
    train/   muestra_XXXXXX.npz   (psd(512,), etiquetas(9,), posicion)
    val/
    test/
    metadata.json
"""

import os
import json
import argparse
import numpy as np
from tqdm import tqdm


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DEL SISTEMA (deben coincidir con nucleo.py)
# ─────────────────────────────────────────────────────────────────────────────

N_FFT       = 512
N_CANALES   = 9
BW_SUBBANDA_MHZ = 56.0
BINS_POR_CANAL  = 55          # ~6 MHz / (56 MHz / 512) ≈ 54.9 → 55

POSICIONES_BARRIDO = [
    {"centro_mhz": 498, "canales_globales": list(range(14, 23))},  # 9 canales
    {"centro_mhz": 536, "canales_globales": list(range(22, 31))},  # 9 canales
    {"centro_mhz": 578, "canales_globales": list(range(30, 39))},  # 9 canales
    {"centro_mhz": 626, "canales_globales": list(range(38, 47))},  # 9 canales
    {"centro_mhz": 670, "canales_globales": list(range(46, 53))},  # 7 canales
]


# ─────────────────────────────────────────────────────────────────────────────
# COMPONENTES ESPECTRALES POR CANAL
# ─────────────────────────────────────────────────────────────────────────────

def envolvente_canal_ocupado(ancho_bins: int, snr_db: float,
                              offset_bins: int, rng: np.random.Generator) -> np.ndarray:
    """
    Envolvente de un canal ocupado con señal ISDB-Tb dentro de su segmento
    de `ancho_bins` (en dB, relativa al piso de ruido = 0).

    Estructura: lóbulo plano (~82% del ancho) + flancos de coseno alzado
    + pilotos OFDM periódicos + ruido de fase cerca de los bordes.
    """
    env = np.zeros(ancho_bins)

    ancho_plano  = int(ancho_bins * 0.82)
    ancho_flanco = (ancho_bins - ancho_plano) // 2
    centro       = ancho_bins // 2 + offset_bins

    inicio_plano = np.clip(centro - ancho_plano // 2, 0, ancho_bins)
    fin_plano    = np.clip(centro + ancho_plano // 2, 0, ancho_bins)
    env[inicio_plano:fin_plano] = snr_db

    # Flancos de coseno alzado
    for k in range(ancho_flanco):
        fase = np.pi * k / max(ancho_flanco, 1)
        peso = 0.5 * (1 + np.cos(fase + np.pi))
        idx_izq = inicio_plano - ancho_flanco + k
        idx_der = fin_plano - 1 + ancho_flanco - k
        if 0 <= idx_izq < ancho_bins:
            env[idx_izq] = snr_db * peso
        if 0 <= idx_der < ancho_bins:
            env[idx_der] = snr_db * peso

    # Pilotos OFDM periódicos
    if fin_plano > inicio_plano:
        paso = max(1, (fin_plano - inicio_plano) // 8)
        for k in range(inicio_plano, fin_plano, paso):
            env[k] += rng.uniform(1.5, 3.0)

    # Ruido de fase cerca de los bordes del canal
    radio = ancho_bins * 0.8
    amp_fase = rng.uniform(0.5, 2.0)
    for i in range(ancho_bins):
        dist = abs(i - centro)
        if 0 < dist < radio:
            env[i] += amp_fase / (1 + (dist / (radio * 0.1)) ** 2)

    return env


def respuesta_frecuencia_bladerf(n_bins: int, rng: np.random.Generator) -> np.ndarray:
    """
    Respuesta en frecuencia del bladeRF sobre la sub-banda completa: más
    plana que el RTL-SDR pero con leve curvatura y ripple residual del
    filtro anti-aliasing del AD9361.
    """
    x = np.linspace(-1, 1, n_bins)
    amplitud  = rng.uniform(0.8, 2.0)     # dB de variación total (menor que RTL-SDR)
    curvatura = rng.uniform(0.4, 0.8)
    rolloff   = -amplitud * (np.abs(x) ** curvatura)

    # Ripple suave (ondulación periódica de baja frecuencia)
    ripple_amp  = rng.uniform(0.1, 0.4)
    ripple_freq = rng.uniform(1.5, 3.5)
    ripple      = ripple_amp * np.sin(2 * np.pi * ripple_freq * x + rng.uniform(0, 2*np.pi))

    return rolloff + ripple


def artefacto_dc_bladerf(psd_db: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    LO leakage del bladeRF: presente pero menos intenso que en RTL-SDR
    (zero-IF con mejor cancelación de DC, aún así no perfecta).
    """
    psd_r  = psd_db.copy()
    centro = len(psd_db) // 2
    intensidad = rng.uniform(3, 10)   # dB — menor que RTL-SDR (8-20 dB)
    n_af   = rng.integers(1, 3)

    for k in range(-n_af, n_af + 1):
        idx = centro + k
        if 0 <= idx < len(psd_db):
            factor = 1.0 - abs(k) / (n_af + 1)
            psd_r[idx] += intensidad * factor

    return psd_r


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZACIÓN Y CORRECCIÓN (idénticas a nucleo.py)
# ─────────────────────────────────────────────────────────────────────────────

def normalizar_psd(psd_raw: np.ndarray) -> np.ndarray:
    psd_min  = np.percentile(psd_raw, 5)
    psd_max  = np.percentile(psd_raw, 95)
    psd_norm = (psd_raw - psd_min) / (psd_max - psd_min + 1e-9)
    return np.clip(psd_norm, 0.0, 1.0).astype(np.float32)


def corregir_dc_offset(psd: np.ndarray, n_bins_mascara: int = 3) -> np.ndarray:
    psd_c  = psd.copy()
    centro = len(psd) // 2
    inicio = max(0, centro - n_bins_mascara)
    fin    = min(len(psd), centro + n_bins_mascara + 1)
    izq    = psd[max(0, inicio - 1)]
    der    = psd[min(len(psd) - 1, fin)]
    psd_c[inicio:fin] = np.linspace(izq, der, fin - inicio)
    return psd_c


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE UNA SUB-BANDA COMPLETA
# ─────────────────────────────────────────────────────────────────────────────

def generar_estados_ocupacion(n_canales: int, ocupacion_media: float,
                              rng: np.random.Generator) -> np.ndarray:
    """
    Genera el vector de ocupación (0/1) para los n_canales de una sub-banda.

    La probabilidad de ocupación de ESTA captura se sortea de una Beta
    centrada en `ocupacion_media`, simulando que distintas sesiones de
    captura (hora del día, ubicación) tienen distinta actividad de
    primarios. Luego cada canal se sortea independientemente con esa
    probabilidad — esto da variedad real entre "sesiones tranquilas"
    y "sesiones con varios primarios activos".
    """
    # Beta con media = ocupacion_media y concentración moderada
    a = ocupacion_media * 6
    b = (1 - ocupacion_media) * 6
    p_sesion = rng.beta(max(a, 0.5), max(b, 0.5))
    return (rng.random(n_canales) < p_sesion).astype(int)


def generar_subbanda(estados: np.ndarray, rng: np.random.Generator,
                     nivel_ruido_db: float = None) -> tuple:
    """
    Construye el vector PSD completo (512,) de una sub-banda de 56 MHz
    a partir del vector de estados de ocupación de cada canal visible.

    Args:
        estados:        array (n_canales,) con 0=libre, 1=ocupado
        rng:            generador de números aleatorios
        nivel_ruido_db: piso de ruido de la captura (si None, aleatorio)

    Returns:
        (psd_db, margen_db): psd_db (512,) en dB sin normalizar, y
        margen_db (n_canales,) — margen real de uso del canal para un
        secundario: negativo si hay primario (peor cuanto más fuerte la
        señal), positivo si está libre (mejor cuanto más alto el piso
        de ruido relativo). Es la etiqueta de entrenamiento de la
        cabeza de margen de SpectralSenseCNN.
    """
    n_canales = len(estados)
    if nivel_ruido_db is None:
        nivel_ruido_db = rng.uniform(-85, -75)

    # 1. Piso de ruido térmico para los 512 bins
    potencia_lineal = rng.exponential(scale=1.0, size=N_FFT)
    psd_db = 10 * np.log10(potencia_lineal + 1e-12) + nivel_ruido_db

    # 2. Calcular márgenes: centrar los n_canales*BINS_POR_CANAL bins en 512
    total_bins_senal = n_canales * BINS_POR_CANAL
    margen           = max(0, (N_FFT - total_bins_senal) // 2)

    # 3. Generar y colocar la envolvente de cada canal
    snrs = np.zeros(n_canales)
    for i, ocupado in enumerate(estados):
        inicio = margen + i * BINS_POR_CANAL
        fin    = min(inicio + BINS_POR_CANAL, N_FFT)
        ancho  = fin - inicio
        if ancho <= 0:
            continue

        if ocupado:
            snr_db      = rng.uniform(10, 35)
            offset_bins = int(rng.integers(-3, 4))
            env = envolvente_canal_ocupado(ancho, snr_db, offset_bins, rng)
            snrs[i] = snr_db
        else:
            env = np.zeros(ancho)
            snrs[i] = -rng.uniform(5, 25)   # margen positivo simbólico: ver margen_db abajo

        psd_db[inicio:fin] += env

    # 4. Fuga espectral entre canales adyacentes (adjacent channel leakage)
    #    Si un canal ocupado tiene alta SNR, sus bins de borde "sangran"
    #    hacia el canal vecino libre.
    n_bleed = max(2, BINS_POR_CANAL // 12)   # ~4-5 bins de fuga
    for i, ocupado in enumerate(estados):
        if not ocupado or snrs[i] < 15:
            continue
        inicio = margen + i * BINS_POR_CANAL
        fin    = inicio + BINS_POR_CANAL

        # Fuga hacia el canal anterior (si existe y está libre)
        if i > 0 and estados[i - 1] == 0:
            fuga = np.linspace(snrs[i] * 0.35, 0, n_bleed)
            idx0 = max(0, inicio - n_bleed)
            psd_db[idx0:inicio] += fuga[:inicio - idx0]

        # Fuga hacia el canal siguiente (si existe y está libre)
        if i < n_canales - 1 and estados[i + 1] == 0:
            fuga = np.linspace(0, snrs[i] * 0.35, n_bleed)
            idx1 = min(N_FFT, fin + n_bleed)
            psd_db[fin:idx1] += fuga[:idx1 - fin]

    # 5. Respuesta en frecuencia del bladeRF + artefacto DC
    psd_db += respuesta_frecuencia_bladerf(N_FFT, rng)
    psd_db  = artefacto_dc_bladerf(psd_db, rng)

    margen_db = -snrs   # ocupado (snr>0) -> margen negativo; libre (snr<0) -> margen positivo
    return psd_db, margen_db


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN DE MUESTRAS COMPLETAS
# ─────────────────────────────────────────────────────────────────────────────

def generar_muestra(posicion_idx: int, ocupacion_media: float,
                    rng: np.random.Generator) -> dict:
    """
    Genera una muestra completa: sub-banda + etiquetas de los 9 canales
    (con -1 de relleno en posiciones fuera de rango, solo posición 4).
    """
    canales_pos = POSICIONES_BARRIDO[posicion_idx]["canales_globales"]
    n_visibles  = len(canales_pos)   # 9 o 7

    estados = generar_estados_ocupacion(n_visibles, ocupacion_media, rng)

    psd_db, margen_local = generar_subbanda(estados, rng)
    psd_db   = corregir_dc_offset(psd_db)
    psd_norm = normalizar_psd(psd_db)

    etiquetas = np.full(N_CANALES, -1.0, dtype=np.float32)
    etiquetas[:n_visibles] = estados.astype(np.float32)

    margen_db = np.zeros(N_CANALES, dtype=np.float32)
    margen_db[:n_visibles] = margen_local.astype(np.float32)

    return {
        "psd":       psd_norm,
        "etiquetas": etiquetas,
        "margen_db": margen_db,
        "posicion":  posicion_idx
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL DATASET
# ─────────────────────────────────────────────────────────────────────────────

def construir_dataset(n_muestras: int = 6000,
                      ocupacion_media: float = 0.32,
                      salida: str = "./dataset_v2",
                      semilla: int = 42) -> dict:
    rng = np.random.default_rng(semilla)

    splits     = {"train": 0.70, "val": 0.15, "test": 0.15}
    contadores = {s: 0 for s in splits}
    for split in splits:
        os.makedirs(os.path.join(salida, split), exist_ok=True)

    # Asignar splits
    n_train = int(n_muestras * splits["train"])
    n_val   = int(n_muestras * splits["val"])
    n_test  = n_muestras - n_train - n_val
    plan = (["train"] * n_train) + (["val"] * n_val) + (["test"] * n_test)
    rng.shuffle(plan)

    # Estadísticas
    total_etiquetas_validas = 0
    total_ocupado = 0
    conteo_por_canal_ocup = np.zeros(N_CANALES)
    conteo_por_canal_tot  = np.zeros(N_CANALES)

    print(f"\nGenerando {n_muestras} sub-bandas sintéticas TVWS (formato de campo)...")
    print(f"  Ocupación media objetivo: {ocupacion_media:.0%}")
    print(f"  Splits: train={n_train} val={n_val} test={n_test}")
    print()

    for split in tqdm(plan, desc="Generando sub-bandas"):
        posicion_idx = int(rng.integers(0, 5))
        muestra = generar_muestra(posicion_idx, ocupacion_media, rng)

        idx      = contadores[split]
        ruta_npz = os.path.join(salida, split, f"muestra_{idx:06d}.npz")
        np.savez_compressed(
            ruta_npz,
            psd       = muestra["psd"],
            etiquetas = muestra["etiquetas"],
            margen_db = muestra["margen_db"],
            posicion  = np.array(muestra["posicion"], dtype=np.int8)
        )
        contadores[split] += 1

        for c, e in enumerate(muestra["etiquetas"]):
            if e >= 0:
                total_etiquetas_validas += 1
                conteo_por_canal_tot[c] += 1
                if e == 1:
                    total_ocupado += 1
                    conteo_por_canal_ocup[c] += 1

    balance_global = total_ocupado / max(total_etiquetas_validas, 1)
    balance_por_canal = {
        f"canal_local_{c}": round(conteo_por_canal_ocup[c] / max(conteo_por_canal_tot[c], 1), 3)
        for c in range(N_CANALES)
    }

    metadata = {
        "tipo":            "sintetico_v2_subbanda_completa",
        "formato":         "igual al de SpectralSenseInferencia (512 pts, 9 etiquetas/sub-banda)",
        "n_muestras":      contadores,
        "n_fft":           N_FFT,
        "n_canales":       N_CANALES,
        "bins_por_canal":  BINS_POR_CANAL,
        "ocupacion_media_objetivo": ocupacion_media,
        "balance_global_ocupado":   round(balance_global, 3),
        "balance_por_posicion_local": balance_por_canal,
        "total_etiquetas_validas": int(total_etiquetas_validas),
        "semilla":         semilla,
        "normalizacion":   "percentil_5_95",
        "dc_offset_corr":  True,
        "señales_sim":     ["ISDB-Tb (lóbulo plano + flancos coseno alzado + pilotos)",
                            "ruido térmico por sub-banda (nivel variable)",
                            "fuga espectral entre canales adyacentes",
                            "respuesta en frecuencia bladeRF (rolloff + ripple)",
                            "LO leakage / DC offset bladeRF",
                            "ruido de fase cerca de bordes de canal"]
    }
    with open(os.path.join(salida, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    return metadata


# ─────────────────────────────────────────────────────────────────────────────
# VERIFICACIÓN VISUAL
# ─────────────────────────────────────────────────────────────────────────────

def verificar_muestras(salida: str, n: int = 4):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib no disponible — omitir verificación visual")
        return

    directorio = os.path.join(salida, "train")
    archivos   = [f for f in os.listdir(directorio) if f.endswith(".npz")]
    elegidos   = np.random.choice(archivos, size=min(n, len(archivos)), replace=False)

    fig, axes = plt.subplots(2, 2, figsize=(13, 7))
    axes      = axes.flatten()
    freqs     = np.linspace(0, BW_SUBBANDA_MHZ, N_FFT)

    for ax, archivo in zip(axes, elegidos):
        data      = np.load(os.path.join(directorio, archivo))
        psd       = data["psd"]
        etiquetas = data["etiquetas"]
        posicion  = int(data["posicion"])
        canales_pos = POSICIONES_BARRIDO[posicion]["canales_globales"]
        n_vis = len(canales_pos)

        ax.plot(freqs, psd, linewidth=0.8, color="#378ADD")

        # Sombrear cada canal según su etiqueta
        margen = max(0, (N_FFT - n_vis * BINS_POR_CANAL) // 2)
        for i in range(n_vis):
            inicio_bin = margen + i * BINS_POR_CANAL
            fin_bin    = inicio_bin + BINS_POR_CANAL
            f0 = freqs[min(inicio_bin, N_FFT - 1)]
            f1 = freqs[min(fin_bin, N_FFT - 1)]
            color = "#D85A30" if etiquetas[i] == 1 else "#1D9E75"
            ax.axvspan(f0, f1, alpha=0.12, color=color)
            ax.text((f0 + f1) / 2, 1.03,
                    f"{canales_pos[i]}\n{'OCU' if etiquetas[i]==1 else 'LIB'}",
                    ha="center", va="bottom", fontsize=6.5,
                    transform=ax.get_xaxis_transform())

        ax.set_title(f"Posición {posicion} — centro {POSICIONES_BARRIDO[posicion]['centro_mhz']} MHz",
                     fontsize=9)
        ax.set_xlabel("Frecuencia relativa en sub-banda (MHz)", fontsize=8)
        ax.set_ylabel("PSD normalizada [0,1]", fontsize=8)
        ax.set_ylim(-0.05, 1.25)
        ax.grid(True, alpha=0.3)

    plt.suptitle("Muestras sintéticas v2 — sub-banda completa (formato de campo)", fontsize=11)
    plt.tight_layout()
    ruta = os.path.join(salida, "verificacion_visual_v2.png")
    plt.savefig(ruta, dpi=120, bbox_inches="tight")
    plt.show()
    print(f"Gráfica guardada en {ruta}")


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Genera dataset sintético v2 (sub-banda completa) para SpectralSenseCNN"
    )
    parser.add_argument("--n_muestras", type=int, default=6000,
                        help="Total de sub-bandas a generar (default: 6000)")
    parser.add_argument("--ocupacion_media", type=float, default=0.32,
                        help="Ocupación media objetivo por canal (default: 0.32)")
    parser.add_argument("--salida", type=str, default="./dataset_v2")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--visualizar", action="store_true")
    args = parser.parse_args()

    if not (0.05 <= args.ocupacion_media <= 0.95):
        print("ERROR: --ocupacion_media debe estar entre 0.05 y 0.95")
        return

    metadata = construir_dataset(
        n_muestras      = args.n_muestras,
        ocupacion_media = args.ocupacion_media,
        salida          = args.salida,
        semilla         = args.semilla
    )

    print("\nDataset v2 generado:")
    for split, n in metadata["n_muestras"].items():
        print(f"  {split:6s}: {n:5d} sub-bandas")
    print(f"  Total etiquetas válidas: {metadata['total_etiquetas_validas']:,}")
    print(f"  Balance global ocupado:  {metadata['balance_global_ocupado']:.1%}")
    print(f"  Guardado en: {args.salida}/")
    print(f"\nPróximo paso:")
    print(f"  python entrenamiento.py --modo entrenar --dataset {args.salida}")

    if args.visualizar:
        verificar_muestras(args.salida)


if __name__ == "__main__":
    main()