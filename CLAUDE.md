# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repo hosts a larger university research project: a Cognitive Radio prototype using two identical bladeRF 2.0 micro xA4 SDRs (one per node — the earlier LimeSDR Mini 2.0 candidate for the Client node was dropped) on asymmetric compute hardware (Intel Core Ultra 5 Gateway PC vs. ARM64 Orange Pi 5 Client) and Deep Learning for dynamic access to TV White Space (TVWS) spectrum in rural Peru (UNI, VRI 2026 project). Two modules live here: `IA/` (spectral sensing CNN, production-shaped code) and `TRANSMISION/pruebas/` (a validated, self-contained software test suite — 15 tests across 3 phases — for the MAC/FEC/MOD/OFDM chain and the `tun0`↔GNU Radio boundary; see `TRANSMISION/pruebas/README.md`). Neither is the final assembled system: the production GNU Radio cognitive block (`RadioInterface`, `SpectralSensor`, `CognitiveEngine`, `InbandControlLayer`, the monitoring dashboard, a single `gateway_flowgraph.py`) described in `README.md` is not implemented yet — `TRANSMISION/pruebas/` validates the pieces it would be built from, not the assembled flowgraph itself.

The model's job: given a PSD (Power Spectral Density) vector from a 56 MHz sub-band capture, classify which of the up to 9 visible 6 MHz TVWS channels are occupied by a primary user (TV broadcaster) vs free for secondary (cognitive radio) use, plus an estimated usability margin in dB per channel.

**There is no LoRa or any other out-of-band control channel in this design** — it was eliminated for budget reasons. Channel-hop signaling is in-band only (OFDM subcarriers #254/256/257 of the data channel itself), with an autonomous pre-agreed shelter-channel protocol as the only fallback if the link degrades. Don't reintroduce LoRa/serial-control assumptions when touching this code.

## Estado actual del proyecto (leer esto primero para retomar una sesión)

Esta tabla es la fuente rápida de "¿dónde estábamos?" — se carga gratis junto
con este archivo, no hace falta abrir nada más para saber en qué punto está
cada módulo. **Actualizarla** (no crear un doc de estado aparte) cada vez que
una tarea cierre o abra un ítem — si queda desactualizada, deja de servir
para esto y volvemos al problema que ya causó desincronización en otros docs.

| Módulo | Estado / último hito | Próximo paso | Detalle en |
|---|---|---|---|
| IA (CNN sensado espectral) | Baseline sintético corrido: AUC-ROC 0.88, F1(β=2)@0.20=0.80, sensibilidad 98.5%, latencia ONNX 0.089ms CPU. Valida el pipeline, no desempeño en campo. | Re-entrenar con la arquitectura de cabeza dual completa (ocupación+margen) y medir esas métricas; luego iniciar captura real con RTL-SDR (Fase 1) | `IA/README.md` §Roadmap |
| TRANSMISION (MAC/FEC/MOD/OFDM) | Fases 1-3 de software aprobadas, 15/15 pruebas (36/36 casos tras cerrar fragmentación TDD el 04/09/2026), todo sin hardware SDR | Cerrar FEC (convolucional vs LDPC) — accionable sin hardware, ver `claudedocs/riesgos_arquitectura_transmision.md` Problema 3. Fase 4 (hardware-in-the-loop) sigue bloqueada esperando el bladeRF del nodo Cliente | `TRANSMISION/pruebas/README.md` |
| RF / enlace de datos | Diseño cerrado a 4 km con datasheets reales (EIRP +28.8dBm, margen +19.5/+16.5/+10.5dB BPSK/QPSK/16-QAM) | Medir tiempo de settling del PA, revalidar NLOS a 4km, cerrar FEC (CCSDS vs LDPC), medir margen de fade estadístico | `claudedocs/arquitectura_enlace_datos.md` §8 |
| Normativa (TVWS Perú) | **Bloqueador mayor de despliegue real**: el diseño usa solo sensado CNN; el decreto exige base de datos de geolocalización (Art. 17-18) como mecanismo primario de autorización | Diseñar cómo incorporar la consulta a BD de geolocalización + reporte Art. 13 al `CognitiveEngine` (el sensado CNN queda como capa complementaria, no sustituto) | `claudedocs/cumplimiento_normativo_tvws.md` |
| Instalación física | Specs reales confirmadas (conectores SMA en toda la cadena, bias-tee integrado en el bladeRF); el mount del discone (≤35mm) no encaja en ninguna sección del mástil real (60mm/48mm) | Conseguir reductor para el discone; confirmar con el equipo si el mástil tripode ya cumple el requisito no-penetrante | `claudedocs/estructura_fisica_instalacion.md` |
| Flujo de agentes (propone/verifica) | Implementados 10 agentes en `.claude/agents/` (5 dominios × proponente/verificador), disponibles por nombre desde una sesión nueva | Usarlo en tareas reales del proyecto | `.claude/agents/` (sin doc índice separado — cada agente documenta su propio rol) |

Cuando el usuario pida "seguir con X", leer solo la fila de X en esta tabla
— no releer `README.md` completo ni reconstruir contexto con `git log`. Abrir
el doc de la columna "Detalle en" solo si la tarea concreta lo requiere.

Read these docs before making non-trivial changes:
- `SPECS EQUIPOS/` — **the only source for technical characteristics of hardware already purchased**, one file per piece of equipment (`PA.md`, `LNA.md`, `ANTENA_DIRECCIONAL`, `ANTENA_OMNIDIRECCIONAL`, `MASTILES`, `COMPUTADORA_GATEWAY`, `SDR_ENLACE`). Added 28/08/2026 — supersedes the generic RFP-language specs previously scattered through `README.md`/`claudedocs/requisitos_pa_lna.md`/`PRESUPUESTO COMPLETO.xlsx` for anything this folder actually covers. Real numbers found here materially differ from what the project assumed before: PA is Class A (not AB), P1dB >32dBm (not the 33dBm nominal used everywhere), max input +3dBm (less than the bladeRF's own max TX output — don't drive it at full SDR gain); LPDA antenna is WA5VJB 400-1000MHz at 5dBi @500MHz (not the ≥10dBi originally specified nor the 6dBi conservative placeholder); LNA/antenna/PA connectors are all SMA (not N as older docs assumed); discone connector is SO-239 confirmed, mount diameter ≤35mm (doesn't fit either mast tube section, see `claudedocs/estructura_fisica_instalacion.md`); bladeRF bias-tee is built into every RF port (no separate injector needed). **Consult this folder first for any equipment-characteristics question** — don't fall back to guessing from the RFP-generic language in `PRESUPUESTO COMPLETO.xlsx` when a file here already has the real datasheet. Equipment without a file here (cables, gabinete, attenuator kit, RTL-SDR dongle) isn't covered — treat those as still-open per whatever other doc discusses them.
- `claudedocs/arquitectura_transmision_datos.md` — condensed reference for the GNU Radio cognitive block's 6 software layers (RadioInterface split, SpectralSensor, ChannelClassifier, CognitiveEngine, InbandControlLayer, MonitoringDashboard): message-port vs streaming-port model, per-layer interfaces, and open design gaps. **Read this instead of `README.md` §2/§7 when working on cognitive-block software architecture** — it's the token-cheap version of the same content.
- `claudedocs/arquitectura_enlace_datos.md` — **the assembled, current data-link physical-layer spec** (TDD framing/slot/guard, channel plan, modulation/FEC policy, PA operating point, availability/throughput budget): closed 20-21/08/2026, PA/antenna specs and distance updated 28/08/2026. Slot = 20 OFDM symbols (~1.78 ms), duty cycle 50/50, 1 channel for now (non-adjacent multi-channel explicitly rejected — PA intermodulation falls in the gap between bands), adaptive BPSK/QPSK/16-QAM both directions, PA 2W both nodes at 7.5 dB backoff, **4 km final design distance** (was 6 km/5-6 km range, was 10-15 km before that). Link margin at 4 km with real hardware datasheets: +19.5/+16.5/+10.5 dB BPSK/QPSK/16-QAM. **Read this first for any link-layer/digital-twin/hardware-bring-up work** — it's the "what to build," self-contained enough to start from directly. §8 lists what's still explicitly open (PA settling time unmeasured, NLOS-at-new-distance unrevalidated, FEC choice, statistical fade margin unmeasured) — don't assume those are resolved just because the framing/channel/modulation decisions are.
- `claudedocs/riesgos_arquitectura_transmision.md` — the "why" behind the decisions in the doc above, plus risks not yet closed. Full-duplex real (antenna-isolation-only TX/RX, no SIC/duplexer) was abandoned (26/07/2026) for **software TDD** — reflected in `README.md` §3.1. Still-open risks: control subcarriers #254/256/257 sitting adjacent to the DC-leakage bin that's already being avoided, the conservative CCSDS convolutional FEC vs. LDPC trade-off, the undefined pilot-subcarrier pattern, and no max frame size. **Read this before proposing RF/full-duplex/TDD/FEC/OFDM design changes** — some problems are decided (don't re-litigate), others are open (don't assume resolved) — the doc marks which is which.
- `TRANSMISION/pruebas/README.md` — index of the GNU Radio transmission-chain test plan (`tun0`/`tuntap_pdu`, MAC framing, FEC, MOD/DEMOD, OFDM symbol structure, etc.), with pass/fail status per test and links to each test's own README + reusable code. Several architecture decisions that were left open in the docs above (the 5-byte MAC header format, the CCSDS FEC choice) got closed *here*, during testing — check this before treating them as unresolved.
- `README.md` (root) — current, authoritative system architecture: GNU Radio cognitive block layers, RF link budgets, OFDM frame structure, in-band control protocol, hardware BOM, project timeline. This was substantially rewritten — always re-read it rather than trusting memory of an earlier version. Only needed in full for hardware/RF/link-budget/timeline questions, or if `claudedocs/arquitectura_transmision_datos.md` doesn't cover what's needed.
- `IA/README.md` — IA module overview, architecture diagram, file layout, quick-start commands. Kept in sync with the actual code in this repo.
- `IA/pipeline_dataset_v2.md` — detailed design doc for the real RTL-SDR capture/labeling pipeline (capture script, energy-threshold labeling, augmentation, dataset QA checklist) — the only doc with this content. Hardware specs and code import paths were corrected to match the current module split (below); still worth a skim before touching the real-capture dataset pipeline specifically, less relevant for the synthetic-dataset/training path.
- `LINK_BUDGET/README.md` — **the only source of truth for link-budget numbers** (EIRP, NF, sensitivity, margin, DL/UL, full-duplex self-interference). Run the Streamlit calculator (`LINK_BUDGET/app.py`) instead of hand-computing or copying a number from `README.md`/`claudedocs/requisitos_pa_lna.md`/`claudedocs/bladerf_2_micro_xa4_specs.md` — those docs cite this tool's output, they don't own the numbers. Defaults updated 28/08/2026: real datasheets from `SPECS EQUIPOS/` (PA P1dB 32dBm, was 33dBm nominal; antenna gain 5dBi, real WA5VJB spec, was 6dBi conservative placeholder; no GDT) **and** final design distance **4 km** (was 6km/5-6km range, was 10-15km before that). Current snapshot: EIRP +28.8dBm, margin +19.5/+16.5/+10.5dB BPSK/QPSK/16-QAM at 4km — the shorter distance recovers most of the margin the real hardware datasheets had cost at 6km (which would have been +16.0/+13.0/+7.0dB), so the link ends up with comparable or better headroom than the original 6km/generic-specs snapshot (+18.9/+15.9/+9.9dB).
- `claudedocs/cumplimiento_normativo_tvws.md` — found 14/08/2026: the architecture in `README.md` was designed *before* anyone checked `Decreto_Supremo_024-2021-MTC_TVWS.pdf` (Peru's TVWS regulation, in repo root). Still-blocking mismatch: the law mandates a **geolocation-database** model (Art. 17-18) as the primary channel-authorization mechanism, but the project's `CognitiveEngine` uses **CNN spectrum sensing** as the sole mechanism — sensing isn't a legal substitute for the DB query, at best a complementary safety layer; and Art. 13 geolocation reporting is entirely absent from the design. **Read this before treating the CNN-sensing architecture as regulatory-final for real deployment** — this is the single biggest open item blocking anything beyond lab/TRL-4 use. (The PSD-over-limit finding from 14/08 was resolved 20/08/2026 as a side effect of the PA backoff decision, and re-confirmed 28/08/2026 with the real PA datasheet — margin actually improved, ~6.1-6.6dB below the legal limit — see the doc's Problema 4.)
- `claudedocs/requisitos_antena_sensado.md` — now a **verification report** (rewritten 28/08/2026), not a procurement brief — the discone (Tram 1411) is already bought, see `SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`. Its connector is confirmed SO-239 and VSWR ≤1.5:1 (better than the ≤2:1 target), but gain-in-band and polarization are **still undocumented even in the real datasheet** — the original 21/08/2026 concern about this discone's gain never got resolved, just confirmed as an actual gap rather than a guess. New finding: mount diameter ≤35mm doesn't fit either section of the real mast (60mm/48mm, see `SPECS EQUIPOS/MASTILES`) — needs a reducer.
- `claudedocs/brief_enlace_gemelo_digital.md` — kickoff doc (13/08/2026) for closing the remaining half-duplex/TDD implementation decisions. **Superseded 20/08/2026** — the decisions it set out to close are closed, recorded in `claudedocs/arquitectura_enlace_datos.md`. Kept as historical record of how the decisions were reached; don't treat its "Qué falta decidir" section as still open.
- `claudedocs/estructura_fisica_instalacion.md` — physical installation plan, rewritten 28/08/2026 against real datasheets in `SPECS EQUIPOS/`. Key findings: **the entire RF chain (antenna, LNA, PA) turned out to be SMA connectors, not N** as earlier docs assumed; the **bladeRF's bias-tee is built into every RF port** (no separate injector hardware needed for the mast-top LNA, just a software enable); the **PA's max input rating (+3dBm) is below the bladeRF's max TX output (+6dBm)** — the SDR's TX gain must be reduced by software before connecting the PA, or risk overdriving it; the real mast is a **self-supporting tripod** (`SPECS EQUIPOS/MASTILES`) which may already satisfy the non-penetrating-mount constraint the team was still sourcing a separate base for (unconfirmed, flagged for the team to check); the sensing discone's mount (≤35mm) doesn't fit either mast tube section (60mm/48mm). Still no GDT anywhere (deliberate, 28/08/2026: validation link only runs ~3h continuous, not a permanent installation) and no fixed LMR-400 lengths (sized on-site). **Read this before any physical mount/cabling/connector work.**

## Cómo mantener esta documentación sincronizada

Cada tipo de hecho tiene **un único doc canónico**; los demás enlazan o
citan, no repiten el número/dato. Si aprendés algo que cambia uno de estos
hechos, editá el doc canónico correspondiente — no crees un doc nuevo ni
copies el valor actualizado a otro archivo (eso fue exactamente lo que
causó que la corrección de ganancia de antena del 29/07/2026 tardara en
propagarse a 4 documentos distintos, y que la decisión de TDD del
26/07/2026 nunca llegara a `README.md` hasta que alguien lo notó).

| Tipo de hecho | Vive en |
|---|---|
| Características técnicas de equipos de hardware ya comprados (PA, LNA, antenas, SDR, mástil, PC) | `SPECS EQUIPOS/` — un archivo por equipo, agregado 28/08/2026 |
| Cifras de link budget / RF (EIRP, NF, margen, sensibilidad) | `LINK_BUDGET/` (correr la calculadora, no hand-compute) |
| Especificación ensamblada y vigente del enlace de datos (framing TDD, canales, modulación/FEC, punto de operación del PA, métricas esperadas) | `claudedocs/arquitectura_enlace_datos.md` |
| Historial de decisiones de transmisión y riesgos todavía abiertos (el "por qué", no el "qué") | `claudedocs/riesgos_arquitectura_transmision.md` |
| Estado del plan de pruebas de transmisión (qué está aprobado, qué falta) | `TRANSMISION/pruebas/README.md` |
| Arquitectura completa del sistema (hardware, OFDM, timeline, BOM) | `README.md` (raíz) |
| Arquitectura/estado del módulo IA (métricas, roadmap, quick-start) | `IA/README.md` |
| Cumplimiento normativo TVWS Perú (choques contra el Decreto Supremo 024-2021-MTC) | `claudedocs/cumplimiento_normativo_tvws.md` |
| Plan de instalación física (mástiles, orden de montaje, conectores por tramo) | `claudedocs/estructura_fisica_instalacion.md` |
| Guía para Claude Code / convenciones de este repo | este archivo |

Antes de citar una cifra o decisión de un doc que no sea el canónico de su
categoría, verificar que coincide con el canónico — si no coincide, el
canónico tiene razón y el otro doc quedó desactualizado.

## Environment

**Esta sección describe el entorno para desarrollar/entrenar el módulo
`IA/` (probablemente una máquina Windows del equipo) — no es el entorno
del Gateway de despliegue (Ubuntu 22.04, ver línea de ONNX execution
provider más abajo) ni el de la laptop Linux usada para las pruebas de
`TRANSMISION/` (`TRANSMISION/pruebas/README.md`). Son tres máquinas
distintas con entornos distintos, no una contradicción entre docs.**

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
