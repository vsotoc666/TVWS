# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repo is the IA (artificial intelligence) module of a larger university research project: a Cognitive Radio prototype using asymmetric SDR hardware (bladeRF + LimeSDR) and Deep Learning for dynamic access to TV White Space (TVWS) spectrum in rural Peru (UNI, VRI 2026 project). Only the `IA/` module — spectral sensing CNN — lives in this repo currently; the GNU Radio cognitive block (`RadioInterface`, `SpectralSensor`, `CognitiveEngine`, `InbandControlLayer`, the monitoring dashboard) described in `README.md` is not yet implemented here.

The model's job: given a PSD (Power Spectral Density) vector from a 56 MHz sub-band capture, classify which of the up to 9 visible 6 MHz TVWS channels are occupied by a primary user (TV broadcaster) vs free for secondary (cognitive radio) use, plus an estimated usability margin in dB per channel.

**There is no LoRa or any other out-of-band control channel in this design** — it was eliminated for budget reasons. Channel-hop signaling is in-band only (OFDM subcarriers #254/256/257 of the data channel itself), with an autonomous pre-agreed shelter-channel protocol as the only fallback if the link degrades. Don't reintroduce LoRa/serial-control assumptions when touching this code.

Read these docs before making non-trivial changes:
- `README.md` (root) — current, authoritative system architecture: GNU Radio cognitive block layers, RF link budgets, OFDM frame structure, in-band control protocol, hardware BOM, project timeline. This was substantially rewritten — always re-read it rather than trusting memory of an earlier version.
- `IA/README.md` — IA module overview, architecture diagram, file layout, quick-start commands. Kept in sync with the actual code in this repo (unlike the two docs below).
- `IA/arquitectura_ia_tvws.md` / `IA/pipeline_dataset_v2.md` — older, more detailed design docs. Still valid for the 3-conv-block kernel-size reasoning and the real RTL-SDR capture/labeling pipeline, but **predate the dual-head model and the module split below** — don't trust their code snippets or file names over the actual code.

## Environment

Windows, Python 3.11/3.12, CPU-only (no CUDA/ROCm available locally). A `venv/` virtualenv lives at the repo root (gitignored).

```bash
pip install -r requirements.txt
```

On Windows, `torch.onnx.export`'s dynamo exporter prints Unicode checkmarks that crash the default cp1252 console — `entrenamiento.py` reconfigures `sys.stdout` to UTF-8 at import time to avoid this; if you invoke torch.onnx export from a new entry point, do the same.

When running any script that calls `matplotlib`'s `plt.show()` (`evaluar_modelo.py`, `analizar_entrenamiento.py`) non-interactively (e.g. from an agent/CI shell), set `MPLBACKEND=Agg` first — otherwise it blocks waiting for a GUI window that will never appear.

Config is read from `.env` at the repo root (paths, RTL-SDR params, model thresholds, training hyperparameters, thread counts). Not committed for secrets reasons but tracked in this repo — check it for current `TVWS_*`, `MODEL_*`, `TRAIN_*` values before assuming defaults from code.

## Commands

All commands below are run from `IA/`.

```bash
# Quick smoke test: builds model, runs forward pass, exports ONNX, verifies via onnxruntime + ChannelClassifier
python entrenamiento.py --modo test

# Generate a synthetic dataset (full sub-band format, includes margen_db labels)
python generar_dataset_sintetico.py --n_muestras 6000 --ocupacion_media 0.32 --salida ./dataset_v2

# Train (also auto-exports to ONNX on completion)
python entrenamiento.py --modo entrenar --dataset ./dataset_v2 --salida ./modelos --epocas 80 --batch 64 --lr 1e-3

# Export an existing checkpoint to ONNX
python entrenamiento.py --modo exportar --checkpoint ./modelos/mejor_modelo.pt

# Post-training diagnostics (reads modelos/historial.json -> plots to ./graficas)
MPLBACKEND=Agg python analizar_entrenamiento.py --historial ./modelos/historial.json --salida ./graficas

# Full test-set evaluation: per-channel AUC/F1, ROC curves, confusion matrices, ONNX latency benchmark
MPLBACKEND=Agg python evaluar_modelo.py --dataset ./dataset_v2 --checkpoint ./modelos/mejor_modelo.pt --onnx ./modelos/spectral_sense.onnx
```

There is no automated test suite (no pytest/unittest files) — `--modo test` in `entrenamiento.py` is the closest thing to a smoke test, and `evaluar_modelo.py` is the closest thing to a correctness/quality check against held-out data.

## Architecture

### Module split

The old monolithic `spectral_sense.py` was split into three files — don't recreate it:

- **`IA/nucleo.py`** — constants (`POSICIONES_BARRIDO`, `PSD_LENGTH=512`, `UMBRAL_LIBRE=0.20`), preprocessing (`calcular_psd`, `corregir_dc_offset`, `normalizar_psd`, `iq_a_psd_normalizado`), the model (`SpectralSenseCNN`), and the masked losses (`BCEWithLogitsLossMasked`, `MargenLossMasked`). This is the only place that should define these — other files import from here.
- **`IA/inferencia.py`** — field inference: `ChannelClassifier` (ONNX Runtime wrapper, classifies **one sub-band per call**) and `SpectralOccupancyMap` (aggregates the 5 sweep-position results into the global 39-channel map, tracking a per-channel timestamp since the 5 sub-bands are captured sequentially, not simultaneously).
- **`IA/entrenamiento.py`** — `TVWSDataset`, the training loop (`entrenar`), evaluation helper (`evaluar`), ONNX export (`exportar_onnx`), and the CLI entry point (`--modo test|entrenar|exportar`).

### Why the model classifies one sub-band at a time, not all 39 channels at once

The bladeRF (AD9361) has a ~56 MHz max instantaneous bandwidth — physically incapable of capturing the full 470–698 MHz (228 MHz) TVWS range in a single FFT. So the model takes a 512-point PSD from **one** of 5 fixed sweep positions (`POSICIONES_BARRIDO`, each covering 7-9 channels) and `SpectralOccupancyMap` does the aggregation into the global channel map in plain Python, outside the ONNX graph. Don't try to feed a wider composite PSD into the model expecting it to output all 39 channels directly — that would require redesigning the conv kernel sizes (tuned for 56 MHz/512 bins ≈ 109 kHz/bin) and hasn't been validated.

### Dual-head model: occupancy + margin

`SpectralSenseCNN.forward()` returns a **tuple** `(logits_ocupacion, margen_db)`, both shape `(batch, 9)`, sharing the same conv backbone + GAP + one dense trunk layer. The margin head (linear regression, dB) exists because the downstream `CognitiveEngine`'s `max_margin` selection policy needs a continuous quality signal between free channels — P(occupied) alone saturates near 0 for all of them and can't rank "cleaner" vs "less clean." `MargenLossMasked` reuses the *same* validity mask as the occupancy labels (`etiquetas >= 0`) rather than a separate sentinel — there's no such thing as a channel with a known margin but unknown occupancy.

**Backward compatibility with the real v1 dataset:** `IA/dataset/` (committed, captured before the margin head existed) has no `margen_db` key in its `.npz` files. `TVWSDataset.__getitem__` checks `"margen_db" in data.files` and falls back to an all-zero array with a `margen_valido=0` mask, so those legacy samples still train the occupancy head normally while the margin loss silently ignores them. Don't regenerate or break this fallback when touching `TVWSDataset`.

### `IA/dataset/` (real, v1, per-channel) vs synthetic v2 (sub-band-complete)

`IA/dataset/` was captured per the real RTL-SDR pipeline in `pipeline_dataset_v2.md`: each `.npz` has exactly one valid occupancy label among 9 (the other 8 are `-1`/masked), because each real capture only covers one 6 MHz channel at 2.4 MHz RTL-SDR bandwidth — a materially different frequency content/resolution than the 56 MHz-wide, 9-channel-at-once sub-band the model sees in production. `generar_dataset_sintetico.py` instead simulates the production-shaped input directly: a full 56 MHz sub-band with all visible channels labeled (occupancy + `margen_db`, both physically motivated — see the module docstring). **Prefer the synthetic generator's output for training** until/unless the real capture pipeline is redesigned to produce sub-band-shaped data.

### Decision threshold asymmetry

`UMBRAL_LIBRE = 0.20` (not 0.5) is the operational threshold for declaring a channel free, chosen because a false negative (declaring an occupied channel free) means interfering with a licensed TV broadcaster — a regulatory violation — while a false positive just costs spectral efficiency. Training/evaluation metrics (F1, AUC) still use threshold 0.5 internally for model-quality assessment; 0.20 is applied only at the field-inference decision layer.

### ONNX execution provider

The Gateway runs Ubuntu 22.04 LTS (Linux) on an Intel Core Ultra 5 225 — **not Windows**, so `DirectML` is never an option there. `ChannelClassifier` prefers `OpenVINOExecutionProvider` (accelerates on the Intel iGPU) and falls back to `CPUExecutionProvider`. The model is small enough (~108K params, <1 ms/sub-band measured) that CPU alone meets the latency budget — don't add a DirectML/Radeon code path back in.

### Output artifacts

- `IA/modelos/` — `mejor_modelo.pt` (PyTorch checkpoint), `spectral_sense.onnx` (+ `.onnx.data` for external weights), `historial.json` (per-epoch metrics, consumed by `analizar_entrenamiento.py`). ONNX graph has two named outputs: `logits_ocupacion` and `margen_db`.
- `IA/graficas/` — training diagnostic plots.
