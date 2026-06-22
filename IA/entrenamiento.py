"""
entrenamiento.py
================
Dataset, bucle de entrenamiento y exportación ONNX de SpectralSenseCNN.

Uso:
  python entrenamiento.py --modo entrenar --dataset ./dataset_v2 --salida ./modelos
  python entrenamiento.py --modo exportar --checkpoint ./modelos/mejor_modelo.pt
  python entrenamiento.py --modo test
"""

import os
import sys
import time
import json
import argparse
import numpy as np

if sys.platform == "win32":
    # torch.onnx.export (exportador dynamo) imprime checkmarks Unicode que
    # rompen la consola cp1252 por defecto de Windows.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score, fbeta_score

from nucleo import (
    SpectralSenseCNN, BCEWithLogitsLossMasked, MargenLossMasked,
    normalizar_psd, N_CANALES_MAX, PSD_LENGTH,
)


# ─────────────────────────────────────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────────────────────────────────────

class TVWSDataset(Dataset):
    """
    Espera archivos .npz con:
        psd:       array (512,) float32 — PSD normalizado
        etiquetas: array (9,)  float32 — 1.0=ocupado, 0.0=libre, -1.0=desconocido
        margen_db: array (9,)  float32, OPCIONAL — margen/SNR real en dB
                   (presente en datos sintéticos v2; ausente en datos reales
                   v1 capturados antes de la cabeza de margen, que entonces
                   se entrenan solo con la cabeza de ocupación)
        posicion:  int — índice de posición de barrido (0-4)
    """

    def __init__(self, directorio: str, split: str = "train", augmentar: bool = True):
        self.directorio = os.path.join(directorio, split)
        self.augmentar  = augmentar and (split == "train")
        self.archivos   = sorted(f for f in os.listdir(self.directorio) if f.endswith(".npz"))
        if len(self.archivos) == 0:
            raise RuntimeError(f"No se encontraron archivos .npz en {self.directorio}")

    def __len__(self) -> int:
        return len(self.archivos)

    def __getitem__(self, idx: int):
        ruta = os.path.join(self.directorio, self.archivos[idx])
        data = np.load(ruta)

        psd       = data["psd"].astype(np.float32)
        etiquetas = data["etiquetas"].astype(np.float32)

        if "margen_db" in data.files:
            margen        = data["margen_db"].astype(np.float32)
            margen_valido = np.ones(N_CANALES_MAX, dtype=np.float32)
        else:
            margen        = np.zeros(N_CANALES_MAX, dtype=np.float32)
            margen_valido = np.zeros(N_CANALES_MAX, dtype=np.float32)

        if self.augmentar:
            psd = self._augmentar(psd)

        return (torch.from_numpy(psd), torch.from_numpy(etiquetas),
                torch.from_numpy(margen), torch.from_numpy(margen_valido))

    def _augmentar(self, psd: np.ndarray) -> np.ndarray:
        if np.random.rand() < 0.5:
            sigma = np.random.uniform(0.005, 0.02)
            psd   = psd + np.random.normal(0, sigma, psd.shape).astype(np.float32)
        if np.random.rand() < 0.4:
            psd = psd + np.random.uniform(-0.05, 0.05)
        if np.random.rand() < 0.3:
            psd = np.roll(psd, np.random.randint(-3, 4))
        if np.random.rand() < 0.3:
            psd = psd * np.random.uniform(0.9, 1.1)
        return np.clip(normalizar_psd(psd), 0.0, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRENAMIENTO
# ─────────────────────────────────────────────────────────────────────────────

def calcular_pos_weight(dataset_dir: str) -> torch.Tensor:
    suma_ocupado = np.zeros(N_CANALES_MAX)
    suma_libre   = np.zeros(N_CANALES_MAX)
    directorio   = os.path.join(dataset_dir, "train")

    for archivo in os.listdir(directorio):
        if not archivo.endswith(".npz"):
            continue
        etiquetas = np.load(os.path.join(directorio, archivo))["etiquetas"].astype(float)
        for i, e in enumerate(etiquetas):
            if e >= 0:
                suma_ocupado[i] += e
                suma_libre[i]   += (1.0 - e)

    if suma_ocupado.sum() == 0:
        raise RuntimeError("Dataset vacío o sin etiquetas válidas")

    pos_weight = np.clip(suma_libre / (suma_ocupado + 1e-6), 0.5, 10.0)
    print(f"pos_weight calculado: {np.round(pos_weight, 2)}")
    return torch.tensor(pos_weight, dtype=torch.float32)


def evaluar(modelo: nn.Module, loader: DataLoader,
            criterio_ocup: nn.Module, criterio_margen: nn.Module,
            device: torch.device) -> dict:
    modelo.eval()
    perdida_total = 0.0
    todas_probs, todas_etiq = [], []

    with torch.no_grad():
        for psd, etiquetas, margen, margen_valido in loader:
            psd, etiquetas = psd.to(device), etiquetas.to(device)
            margen, margen_valido = margen.to(device), margen_valido.to(device)

            logits, margen_pred = modelo(psd)
            perdida = criterio_ocup(logits, etiquetas) + 0.1 * criterio_margen(
                margen_pred, margen, etiquetas, margen_valido
            )
            perdida_total += perdida.item()
            todas_probs.append(torch.sigmoid(logits).cpu().numpy())
            todas_etiq.append(etiquetas.cpu().numpy())

    todas_probs = np.vstack(todas_probs)
    todas_etiq  = np.vstack(todas_etiq)

    aucs = []
    for canal in range(todas_etiq.shape[1]):
        etiq_c, prob_c = todas_etiq[:, canal], todas_probs[:, canal]
        mask = etiq_c >= 0
        etiq_c, prob_c = etiq_c[mask], prob_c[mask]
        if len(etiq_c) > 0 and len(np.unique(etiq_c)) == 2:
            aucs.append(roc_auc_score(etiq_c, prob_c))

    mascara      = todas_etiq.flatten() >= 0
    etiq_validas = todas_etiq.flatten()[mascara].astype(int)
    pred_validas = (todas_probs.flatten()[mascara] >= 0.5).astype(int)
    f1_beta2 = (fbeta_score(etiq_validas, pred_validas, beta=2, average="binary", zero_division=0)
                if len(np.unique(etiq_validas)) > 1 and len(np.unique(pred_validas)) > 1 else 0.0)

    return {
        "perdida":   perdida_total / len(loader),
        "auc_media": float(np.mean(aucs)) if aucs else 0.0,
        "f1_beta2":  float(f1_beta2),
    }


def entrenar(dataset_dir: str, salida_dir: str,
             epocas: int = 80, batch_size: int = 64,
             lr: float = 1e-3, dispositivo: str = "auto") -> SpectralSenseCNN:
    os.makedirs(salida_dir, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if dispositivo == "auto" \
        else torch.device(dispositivo)
    print(f"Entrenando en: {device}")

    ds_train = TVWSDataset(dataset_dir, split="train", augmentar=True)
    ds_val   = TVWSDataset(dataset_dir, split="val",   augmentar=False)
    n_workers = 0 if os.name == "nt" else 2
    pin = device.type != "cpu"
    loader_train = DataLoader(ds_train, batch_size=batch_size, shuffle=True,
                               num_workers=n_workers, pin_memory=pin)
    loader_val   = DataLoader(ds_val, batch_size=batch_size, shuffle=False,
                               num_workers=n_workers, pin_memory=pin)
    print(f"Train: {len(ds_train)} muestras | Val: {len(ds_val)} muestras")

    modelo = SpectralSenseCNN(n_canales_salida=N_CANALES_MAX).to(device)
    print(f"Parámetros entrenables: {modelo.contar_parametros():,}")

    pos_weight      = calcular_pos_weight(dataset_dir).to(device)
    criterio_ocup   = BCEWithLogitsLossMasked(pos_weight=pos_weight)
    criterio_margen = MargenLossMasked()

    optimizador = torch.optim.AdamW(modelo.parameters(), lr=lr, weight_decay=1e-4)
    scheduler   = torch.optim.lr_scheduler.CosineAnnealingLR(optimizador, T_max=epocas, eta_min=1e-5)

    mejor_auc, paciencia, epocas_sin_mejora = 0.0, 10, 0
    ruta_mejor = os.path.join(salida_dir, "mejor_modelo.pt")
    historial = []

    for epoca in range(1, epocas + 1):
        modelo.train()
        perdida_train = 0.0
        t0 = time.time()

        for psd, etiquetas, margen, margen_valido in loader_train:
            psd, etiquetas = psd.to(device), etiquetas.to(device)
            margen, margen_valido = margen.to(device), margen_valido.to(device)

            optimizador.zero_grad()
            logits, margen_pred = modelo(psd)
            perdida = criterio_ocup(logits, etiquetas) + 0.1 * criterio_margen(
                margen_pred, margen, etiquetas, margen_valido
            )
            perdida.backward()
            nn.utils.clip_grad_norm_(modelo.parameters(), max_norm=1.0)
            optimizador.step()
            perdida_train += perdida.item()

        perdida_train /= len(loader_train)
        scheduler.step()

        metricas_val = evaluar(modelo, loader_val, criterio_ocup, criterio_margen, device)
        duracion = time.time() - t0

        print(f"Época {epoca:3d}/{epocas} | Train loss: {perdida_train:.4f} | "
              f"Val loss: {metricas_val['perdida']:.4f} | AUC: {metricas_val['auc_media']:.4f} | "
              f"F1(b=2): {metricas_val['f1_beta2']:.4f} | {duracion:.1f}s")

        historial.append({"epoca": epoca, "perdida_train": perdida_train, **metricas_val})

        if metricas_val["auc_media"] > mejor_auc:
            mejor_auc = metricas_val["auc_media"]
            epocas_sin_mejora = 0
            torch.save({
                "epoca": epoca, "model_state": modelo.state_dict(),
                "optim_state": optimizador.state_dict(), "auc": mejor_auc,
                "metricas": metricas_val,
            }, ruta_mejor)
            print(f"  Mejor modelo guardado (AUC={mejor_auc:.4f})")
        else:
            epocas_sin_mejora += 1
            if epocas_sin_mejora >= paciencia:
                print(f"Early stopping en época {epoca} (sin mejora en {paciencia} épocas)")
                break

    if os.path.exists(ruta_mejor):
        checkpoint = torch.load(ruta_mejor, map_location=device, weights_only=True)
        modelo.load_state_dict(checkpoint["model_state"])
        print(f"\nEntrenamiento completado. Mejor AUC: {mejor_auc:.4f}")
    else:
        print("\nEntrenamiento completado (sin checkpoint guardado — AUC no mejoró).")

    with open(os.path.join(salida_dir, "historial.json"), "w") as f:
        json.dump(historial, f, indent=2)

    return modelo


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTACIÓN A ONNX
# ─────────────────────────────────────────────────────────────────────────────

def exportar_onnx(modelo: SpectralSenseCNN, ruta_salida: str = "spectral_sense.onnx") -> str:
    modelo.eval()
    modelo.cpu()

    dummy_input = torch.randn(1, PSD_LENGTH)

    torch.onnx.export(
        modelo, dummy_input, ruta_salida,
        export_params=True,
        input_names=["psd_input"],
        output_names=["logits_ocupacion", "margen_db"],
        opset_version=18,
        do_constant_folding=True,
    )

    tamanio_kb = os.path.getsize(ruta_salida) / 1024
    print(f"Modelo exportado: {ruta_salida} ({tamanio_kb:.1f} KB)")

    try:
        import onnxruntime as ort
        session = ort.InferenceSession(ruta_salida, providers=["CPUExecutionProvider"])
        inp = np.random.randn(1, PSD_LENGTH).astype(np.float32)
        out = session.run(["logits_ocupacion", "margen_db"], {"psd_input": inp})
        print(f"Verificación ONNX OK — shapes: {out[0].shape}, {out[1].shape}")
    except ImportError:
        print("onnxruntime no instalado — omitir verificación")

    return ruta_salida


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SpectralSense — entrenamiento y exportación")
    parser.add_argument("--modo", choices=["entrenar", "exportar", "test"], default="test")
    parser.add_argument("--dataset", default="./dataset_v2")
    parser.add_argument("--salida", default="./modelos")
    parser.add_argument("--checkpoint", default="./modelos/mejor_modelo.pt")
    parser.add_argument("--epocas", type=int, default=80)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    if args.modo == "entrenar":
        modelo = entrenar(args.dataset, args.salida, args.epocas, args.batch, args.lr)
        exportar_onnx(modelo, os.path.join(args.salida, "spectral_sense.onnx"))

    elif args.modo == "exportar":
        print(f"Cargando checkpoint: {args.checkpoint}")
        modelo = SpectralSenseCNN()
        ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
        modelo.load_state_dict(ckpt["model_state"])
        exportar_onnx(modelo, args.checkpoint.replace(".pt", ".onnx"))

    elif args.modo == "test":
        print("SpectralSense CNN — test de inferencia con datos sintéticos")
        modelo = SpectralSenseCNN()
        print(f"Parámetros: {modelo.contar_parametros():,}")

        psd_fake = torch.rand(4, PSD_LENGTH)
        logits, margen = modelo(psd_fake)
        print(f"Input shape:  {psd_fake.shape}")
        print(f"Output shapes: ocupacion={logits.shape}, margen={margen.shape}")
        print(f"Probs (batch 0): {torch.sigmoid(logits)[0].detach().numpy().round(3)}")
        print(f"Margen dB (batch 0): {margen[0].detach().numpy().round(2)}")

        os.makedirs("./modelos_test", exist_ok=True)
        ruta = exportar_onnx(modelo, "./modelos_test/spectral_sense_test.onnx")

        from inferencia import ChannelClassifier
        try:
            clasificador = ChannelClassifier(ruta)
            psd_test = np.random.rand(PSD_LENGTH).astype(np.float32)
            resultado = clasificador.classify(psd_test)
            print(f"\nTest classify(): free_local={resultado['free_local']} "
                  f"confidence={resultado['confidence']:.3f} "
                  f"latencia={resultado['inference_ms']} ms")
        except ImportError:
            print("onnxruntime no disponible — instalar con: pip install onnxruntime")

        print("\nTest completado sin errores.")


if __name__ == "__main__":
    main()
