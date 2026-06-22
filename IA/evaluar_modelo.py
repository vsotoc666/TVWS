"""
evaluar_modelo.py
==================
Evaluación exhaustiva de SpectralSenseCNN sobre el split de test.

Genera:
  - Métricas globales (AUC, F1, accuracy) y por canal local (0-8)
  - Curvas ROC por canal
  - Matriz de confusión agregada (umbral de campo UMBRAL_LIBRE=0.20)
  - Benchmark de latencia de inferencia (ONNX Runtime)
  - Comparación de umbrales (0.20 vs 0.50) y su efecto en falsos negativos

Uso:
  python evaluar_modelo.py --dataset ./dataset_v2 --checkpoint ./modelos/mejor_modelo.pt
  python evaluar_modelo.py --dataset ./dataset_v2 --onnx ./modelos/spectral_sense.onnx
"""

import os
import argparse
import numpy as np
import torch
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score, roc_curve, confusion_matrix, fbeta_score

from nucleo import SpectralSenseCNN, N_CANALES_MAX, UMBRAL_LIBRE, POSICIONES_BARRIDO
from entrenamiento import TVWSDataset


# ─── Estilo visual (consistente con analizar_entrenamiento.py) ───────────────
plt.rcParams.update({
    "figure.facecolor":  "#0f1117",
    "axes.facecolor":    "#1a1d27",
    "axes.edgecolor":    "#3a3d4f",
    "axes.labelcolor":   "#c8cad4",
    "axes.titlecolor":   "#e8eaf0",
    "xtick.color":       "#8890a8",
    "ytick.color":       "#8890a8",
    "grid.color":        "#2a2d3f",
    "grid.linewidth":    0.6,
    "text.color":        "#c8cad4",
    "legend.facecolor":  "#1a1d27",
    "legend.edgecolor":  "#3a3d4f",
    "font.family":       "monospace",
})

AZUL, VERDE, NARANJA, MORADO, ROJO, GRIS = \
    "#4f9cf9", "#4fc97e", "#f9844f", "#a78bfa", "#f97070", "#8890a8"


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DEL MODELO Y DATOS DE TEST
# ─────────────────────────────────────────────────────────────────────────────

def cargar_modelo_pytorch(ruta_checkpoint: str) -> SpectralSenseCNN:
    modelo = SpectralSenseCNN(n_canales_salida=N_CANALES_MAX)
    ckpt   = torch.load(ruta_checkpoint, map_location="cpu", weights_only=True)
    modelo.load_state_dict(ckpt["model_state"])
    modelo.eval()
    return modelo


def obtener_predicciones(modelo: SpectralSenseCNN, dataset_dir: str) -> dict:
    """
    Corre el modelo sobre todo el split de test y devuelve arrays
    de probabilidades, etiquetas y posiciones.
    """
    ds = TVWSDataset(dataset_dir, split="test", augmentar=False)

    todas_probs = []
    todas_etiq  = []
    todas_pos   = []

    with torch.no_grad():
        for i in range(len(ds)):
            psd, etiq, _margen, _margen_valido = ds[i]
            logits, _margen_pred = modelo(psd.unsqueeze(0))
            probs     = torch.sigmoid(logits).squeeze().numpy()
            todas_probs.append(probs)
            todas_etiq.append(etiq.numpy())
            # posicion no la expone TVWSDataset directamente; releer del npz
            ruta = os.path.join(dataset_dir, "test", ds.archivos[i])
            todas_pos.append(int(np.load(ruta)["posicion"]))

    return {
        "probs":     np.array(todas_probs),     # (N, 9)
        "etiquetas": np.array(todas_etiq),       # (N, 9)
        "posicion":  np.array(todas_pos),        # (N,)
        "n":         len(ds)
    }


# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS POR CANAL
# ─────────────────────────────────────────────────────────────────────────────

def metricas_por_canal(probs: np.ndarray, etiq: np.ndarray,
                       umbral: float) -> list[dict]:
    """Calcula AUC, F1(β=2) y matriz de confusión por posición local (0-8)."""
    resultados = []
    for c in range(N_CANALES_MAX):
        p = probs[:, c]
        e = etiq[:, c]
        mask = e >= 0
        p, e = p[mask], e[mask].astype(int)

        if len(np.unique(e)) < 2:
            resultados.append({
                "canal": c, "n": len(e), "auc": None, "f1": None,
                "tn": None, "fp": None, "fn": None, "tp": None
            })
            continue

        auc  = roc_auc_score(e, p)
        pred = (p >= umbral).astype(int)
        f1   = fbeta_score(e, pred, beta=2, zero_division=0)
        tn, fp, fn, tp = confusion_matrix(e, pred, labels=[0, 1]).ravel()

        resultados.append({
            "canal": c, "n": len(e), "auc": auc, "f1": f1,
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
        })
    return resultados


def resumen_consola(probs: np.ndarray, etiq: np.ndarray):
    """Imprime resumen global y por canal en consola."""
    mask_global = etiq.flatten() >= 0
    e_flat = etiq.flatten()[mask_global].astype(int)
    p_flat = probs.flatten()[mask_global]

    auc_global = roc_auc_score(e_flat, p_flat)

    print(f"\n{'═'*64}")
    print("  EVALUACIÓN EN TEST — RESUMEN GLOBAL")
    print(f"{'═'*64}")
    print(f"  Muestras de test         : {len(probs)}")
    print(f"  Etiquetas válidas        : {mask_global.sum():,}")
    print(f"  Balance ocupado/libre    : {e_flat.mean():.1%} / {1-e_flat.mean():.1%}")
    print(f"  AUC-ROC global           : {auc_global:.4f}")

    for umbral, nombre in [(0.20, "UMBRAL_LIBRE (campo, conservador)"),
                            (0.50, "umbral 0.5 (referencia)")]:
        pred = (p_flat >= umbral).astype(int)
        f1   = fbeta_score(e_flat, pred, beta=2, zero_division=0)
        tn, fp, fn, tp = confusion_matrix(e_flat, pred, labels=[0, 1]).ravel()
        sens = tp / (tp + fn) if (tp + fn) > 0 else 0
        espec= tn / (tn + fp) if (tn + fp) > 0 else 0
        print(f"\n  --- Umbral {umbral:.2f} ({nombre}) ---")
        print(f"    F1(β=2)              : {f1:.4f}")
        print(f"    Sensibilidad (TPR)   : {sens:.4f}  (detección de primarios)")
        print(f"    Especificidad        : {espec:.4f}  (canales libres bien detectados)")
        print(f"    Falsos negativos     : {fn:4d}  ← CRÍTICO: primario no detectado")
        print(f"    Falsos positivos     : {fp:4d}  (canal libre declarado ocupado)")

    print(f"\n{'─'*64}")
    print("  MÉTRICAS POR POSICIÓN LOCAL (0-8 dentro de la sub-banda)")
    print(f"{'─'*64}")
    print(f"  {'Canal':>5} {'N':>6} {'AUC':>7} {'F1(β2)':>7} {'TN':>5} {'FP':>5} {'FN':>5} {'TP':>5}")

    for r in metricas_por_canal(probs, etiq, UMBRAL_LIBRE):
        if r["auc"] is None:
            print(f"  {r['canal']:>5} {r['n']:>6} {'--':>7} {'--':>7} "
                  f"{'--':>5} {'--':>5} {'--':>5} {'--':>5}  (una sola clase)")
        else:
            print(f"  {r['canal']:>5} {r['n']:>6} {r['auc']:>7.4f} {r['f1']:>7.4f} "
                  f"{r['tn']:>5} {r['fp']:>5} {r['fn']:>5} {r['tp']:>5}")

    print(f"{'═'*64}\n")

    # Diagnóstico final
    if auc_global >= 0.92:
        print("  ✓ AUC excelente — modelo listo para validar con datos reales")
    elif auc_global >= 0.85:
        print("  ✓ AUC aceptable — válido para Fase 1, ampliar dataset real ayudará")
    else:
        print("  ⚠ AUC por debajo de la meta (0.85) — revisar arquitectura o dataset")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# GRÁFICAS
# ─────────────────────────────────────────────────────────────────────────────

def graficar_roc_por_canal(probs: np.ndarray, etiq: np.ndarray, salida: str):
    """ROC de cada una de las 9 posiciones locales en una sola figura."""
    fig, ax = plt.subplots(figsize=(7, 7))
    cmap = plt.cm.plasma(np.linspace(0.15, 0.9, N_CANALES_MAX))

    for c in range(N_CANALES_MAX):
        p, e = probs[:, c], etiq[:, c]
        mask = e >= 0
        p, e = p[mask], e[mask].astype(int)
        if len(np.unique(e)) < 2:
            continue
        fpr, tpr, _ = roc_curve(e, p)
        auc = roc_auc_score(e, p)
        ax.plot(fpr, tpr, color=cmap[c], linewidth=1.6,
                label=f"Canal local {c} (AUC={auc:.3f})")

    ax.plot([0, 1], [0, 1], color=GRIS, linewidth=0.8, linestyle="--",
            label="Azar (AUC=0.5)")
    ax.set_xlabel("Tasa de falsos positivos (FPR)")
    ax.set_ylabel("Tasa de verdaderos positivos (TPR)")
    ax.set_title("Curvas ROC por posición local en la sub-banda")
    ax.legend(fontsize=7, loc="lower right")
    ax.grid(True)
    _estilo_ax(ax)
    plt.tight_layout()
    ruta = os.path.join(salida, "roc_por_canal.png")
    plt.savefig(ruta, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Gráfica guardada: {ruta}")
    plt.show()


def graficar_matriz_confusion(probs: np.ndarray, etiq: np.ndarray, salida: str):
    """Matrices de confusión globales para umbral 0.20 y 0.50, lado a lado."""
    mask = etiq.flatten() >= 0
    e = etiq.flatten()[mask].astype(int)
    p = probs.flatten()[mask]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    for ax, umbral, titulo in [(axes[0], 0.20, "Umbral 0.20 (campo, conservador)"),
                                (axes[1], 0.50, "Umbral 0.50 (referencia)")]:
        pred = (p >= umbral).astype(int)
        cm   = confusion_matrix(e, pred, labels=[0, 1])

        im = ax.imshow(cm, cmap="Blues", aspect="auto")
        for i in range(2):
            for j in range(2):
                color_txt = "#0c447c" if cm[i, j] < cm.max() * 0.5 else "white"
                ax.text(j, i, f"{cm[i,j]:,}", ha="center", va="center",
                        fontsize=13, color=color_txt, fontweight="bold")

        ax.set_xticks([0, 1]); ax.set_xticklabels(["Libre (pred)", "Ocupado (pred)"], fontsize=8)
        ax.set_yticks([0, 1]); ax.set_yticklabels(["Libre (real)", "Ocupado (real)"], fontsize=8)
        ax.set_title(titulo, fontsize=10)
        _estilo_ax(ax)

    plt.suptitle("Matriz de confusión global — split de test", fontsize=11)
    plt.tight_layout()
    ruta = os.path.join(salida, "matriz_confusion.png")
    plt.savefig(ruta, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Gráfica guardada: {ruta}")
    plt.show()


def graficar_distribucion_probabilidades(probs: np.ndarray, etiq: np.ndarray, salida: str):
    """Histograma de P(ocupado) separado por clase real — mide separabilidad."""
    mask = etiq.flatten() >= 0
    e = etiq.flatten()[mask].astype(int)
    p = probs.flatten()[mask]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(p[e == 0], bins=30, alpha=0.55, color=VERDE, label="Libre (real)", density=True)
    ax.hist(p[e == 1], bins=30, alpha=0.55, color=NARANJA, label="Ocupado (real)", density=True)
    ax.axvline(UMBRAL_LIBRE, color=ROJO, linestyle="--", linewidth=1.3,
               label=f"UMBRAL_LIBRE={UMBRAL_LIBRE}")
    ax.axvline(0.50, color=GRIS, linestyle=":", linewidth=1.0, label="umbral 0.50")
    ax.set_xlabel("P(ocupado) predicha")
    ax.set_ylabel("Densidad")
    ax.set_title("Distribución de probabilidades por clase real")
    ax.legend(fontsize=9)
    ax.grid(True)
    _estilo_ax(ax)
    plt.tight_layout()
    ruta = os.path.join(salida, "distribucion_probabilidades.png")
    plt.savefig(ruta, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"Gráfica guardada: {ruta}")
    plt.show()


def _estilo_ax(ax):
    ax.tick_params(colors="#8890a8", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#3a3d4f")


# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK DE LATENCIA (ONNX)
# ─────────────────────────────────────────────────────────────────────────────

def benchmark_latencia(ruta_onnx: str, n_iter: int = 200):
    try:
        import onnxruntime as ort
    except ImportError:
        print("onnxruntime no disponible — omitir benchmark de latencia")
        return

    import time
    session = ort.InferenceSession(ruta_onnx, providers=["CPUExecutionProvider"])
    entrada = np.random.rand(1, 512).astype(np.float32)

    # Warm-up
    for _ in range(10):
        session.run(["logits_ocupacion"], {"psd_input": entrada})

    tiempos = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        session.run(["logits_ocupacion"], {"psd_input": entrada})
        tiempos.append((time.perf_counter() - t0) * 1000)

    tiempos = np.array(tiempos)
    print(f"\n{'─'*64}")
    print("  BENCHMARK DE LATENCIA (ONNX Runtime, CPU)")
    print(f"{'─'*64}")
    print(f"  Media   : {tiempos.mean():.3f} ms")
    print(f"  P50     : {np.percentile(tiempos, 50):.3f} ms")
    print(f"  P95     : {np.percentile(tiempos, 95):.3f} ms")
    print(f"  P99     : {np.percentile(tiempos, 99):.3f} ms")
    print(f"  Máximo  : {tiempos.max():.3f} ms")
    print(f"  Presupuesto de ciclo: ~137 ms (5 sub-bandas)")
    print(f"  Margen disponible para 5 inferencias: "
          f"{137 - 5*tiempos.mean():.1f} ms")
    print(f"{'─'*64}\n")


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluación detallada de SpectralSenseCNN")
    parser.add_argument("--dataset",    default="./dataset_v2")
    parser.add_argument("--checkpoint", default="./modelos/mejor_modelo.pt")
    parser.add_argument("--onnx",       default="./modelos/spectral_sense.onnx")
    parser.add_argument("--salida",     default="./graficas_eval")
    args = parser.parse_args()

    os.makedirs(args.salida, exist_ok=True)

    print(f"Cargando modelo: {args.checkpoint}")
    modelo = cargar_modelo_pytorch(args.checkpoint)

    print(f"Evaluando sobre: {args.dataset}/test")
    datos = obtener_predicciones(modelo, args.dataset)
    print(f"  {datos['n']} muestras de test cargadas")

    resumen_consola(datos["probs"], datos["etiquetas"])

    graficar_roc_por_canal(datos["probs"], datos["etiquetas"], args.salida)
    graficar_matriz_confusion(datos["probs"], datos["etiquetas"], args.salida)
    graficar_distribucion_probabilidades(datos["probs"], datos["etiquetas"], args.salida)

    if os.path.exists(args.onnx):
        benchmark_latencia(args.onnx)
    else:
        print(f"\n(omitido benchmark: {args.onnx} no existe — exportar primero con "
              f"--modo exportar)")

    print(f"\nGráficas guardadas en: {args.salida}/")


if __name__ == "__main__":
    main()
