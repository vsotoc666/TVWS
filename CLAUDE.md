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
| IA (CNN sensado espectral) | Re-entrenado tras corregir un defecto de diseño (29/09/2026): la cabeza dual original colapsaba las 128 posiciones espaciales a un solo vector global (`AdaptiveAvgPool1d(1)`) antes de las 9 salidas, sin correspondencia canal↔logit — reemplazado por pooling posicional (`AdaptiveAvgPool1d(9)` + `Conv1d` 1x1 por posición). Métricas: AUC-ROC 1.0000, F1(β=2)@0.20=0.9871, sensibilidad 98.39%, especificidad 100.00% (antes 45.3%), latencia ONNX 0.562ms CPU. AUC/especificidad perfectos ameritan lectura crítica — ver `README.md` §8.5, probablemente reflejan que el dataset sintético (con offset de canal ahora fijo) se volvió más fácil de aprender, no que el modelo generalizará igual en campo. Sigue validando el pipeline, no desempeño en campo. Hardware real llegó (14/10/2026): NooElec NESDR SMArt v5 (RTL2832U+R820T2) + antena genérica 27cm, funcionando en esta máquina (driver kernel conflictivo ya resuelto vía blacklist de módulos). Herramientas reutilizables creadas el mismo día: `IA/herramientas/escanear_tvws.sh` (barrido rtl_power + captura I/Q rtl_sdr) + `analizar_barrido.py` (mapea el barrido a los 39 canales 14-52, QA de energía) + `etiquetar_rnf.py` (etiqueta capturas .iq contra un export del RNF -> .npz en el formato exacto de TVWSDataset; RNF es la etiqueta primaria, el detector de energía sólo cruce de QA). Consultado el RNF real para Lima/Lima/Los Olivos (`IA/dataset_real/rnf_lima_los_olivos_2026-10-14.csv`, el portal no tiene API, se replicó el postback ASP.NET directamente). Cadena RF ampliada y validada el mismo día con un NooElec LaNA (antena → pigtail RG58 1.5m → LaNA, alimentado por USB propio, sin bias-tee → LMR-400 6m → SDR): confirmado que no hay clipping con ganancia de tuner 20.7dB (antes 40dB sin LNA), y con la antena ya en exterior se capturaron y etiquetaron los 39 canales (14-52) de una sesión real: 37 muestras (25 ocupados/12 libres), QA cruzado señaló 12 canales autorizados por RNF sin energía detectada en el momento (posibles estaciones apagadas, etiqueta RNF mantenida sin resolver en silencio) — primera muestra real end-to-end del pipeline completo (`IA/dataset_real/etiquetado_losolivos_20261014/`). GUI de campo creada el mismo día (`IA/herramientas/recolector_app.py`, reescrita el mismo día de Streamlit a **tkinter** puro por preferencia del usuario — interfaz de escritorio, no web; requiere `~/envs/IA` por la dependencia de nucleo.py→torch) para repetir esto en múltiples zonas/horas del día sin correr comandos a mano: pestañas de espectro (distribución de energía en toda la banda, gráfico embebido con matplotlib), RNF (consulta en vivo vía `rnf_web.py`, generalizado a cualquier distrito de Lima provincia — antes sólo Los Olivos), captura+etiquetado (con barra de progreso y los mismos avisos de QA) e inventario (muestras por localidad/hora contra los mínimos de `pipeline_dataset_v2.md`); la barra de sesión pide una hora exacta (spinbox HH:MM, no una categoría mañana/tarde/noche) y cada sesión guarda un `_sesion.json` con metadata (hora exacta, ganancia, LNA sí/no, etc.) para trazabilidad entre sesiones con configuraciones distintas. Operaciones largas (barrido, consulta RNF, captura de 39 canales) corren en un hilo de fondo para no congelar la ventana. Verificado: arranca sin errores corrida directamente (`python3 recolector_app.py`, confirmado en pantalla real vía screenshot), y sus funciones de lógica (slug, detección de dispositivo, lectura del inventario con fallback para sesiones viejas sin `_sesion.json`) corridas directamente contra los datos reales ya commiteados. | Usar `recolector_app.py` para repetir la captura en más sesiones de horario y al menos 1 localidad adicional (mínimos de `pipeline_dataset_v2.md`: ≥2 localidades, ≥3 sesiones de horario, ≥30k muestras); implementar `construir_dataset.py` (split train/val/test por sesión, hoy sin implementar) antes de poder entrenar/fine-tune sobre datos reales | `IA/README.md` §Roadmap, §Uso rápido 5, `README.md` §8.5, `IA/pipeline_dataset_v2.md` |
| TRANSMISION (MAC/FEC/MOD/OFDM) | Fases 1-3 de software aprobadas, 15/15 pruebas (36/36 casos tras cerrar fragmentación TDD el 04/09/2026; FEC cerrado el 05/09/2026 — convolucional K=7 + puncturing para tasa 3/4, LDPC descartado; patrón de subportadoras piloto cerrado el 07/09/2026 — comb escalonado stride 8), todo sin hardware SDR. DC leakage del AD9361 cerca de #254/256/257 (Problema 2): mitad resuelta (08/09/2026) — RX LO Leakage −122dBm típico (datasheet, `SPECS EQUIPOS/SDR_ENLACE`), ~56dB de margen bajo la señal recibida. Brief de diseño abierto (13/09/2026) para la Fase 4 (banco cableado): full-duplex real sin LNA/PA, atenuadores en vez de aire, sensado real en paralelo, pruebas en UNI y Huánuco. Cálculo de atenuación ejecutado el mismo día contra el hardware PA/LNA real: distancia máxima teórica 213/151/76 km (BPSK/QPSK/16-QAM, margen 0dB) → atenuador de banco 72-87 dB. Hallazgo bloqueante: el kit de atenuadores ya comprado solo llega a 42 dB — pedido de 2 kits idénticos adicionales (Nooelec, mismo modelo, ASIN B07YYMT65T) ya armado en §6.1 del brief, listo para copiar a `PRESUPUESTO COMPLETO.xlsx`. Prueba 4a-1 (aislamiento intra-chip TX1→RX1) diseñada y auto-validada en software el mismo día — código en `TRANSMISION/pruebas/fase4a_banco_cableado_fd/prueba4a1_aislamiento_intrachip/`, pendiente de correr con bladeRF real (no hay ninguno conectado a esta máquina). Dato de seguridad agregado a `SPECS EQUIPOS/SDR_ENLACE` el 20/09/2026 (fuente externa, no de los PDF del repo): límite de entrada RX del AD9361 +2.5dBm pico (single-ended) vs +6dBm máx. de TX del bladeRF — margen negativo de 3.5dB sin atenuador, regla operativa: nunca conectar TX↔RX con el atenuador en 0dB. Plan operativo de la Prueba 4a-3 (dos bladeRF por cable, half-duplex TDD — no depende de 4a-1, que solo bloquea full-duplex) abierto el mismo día en `TRANSMISION/ESQUEMA_POR_CABLE/README.md`: decisión de host (1 laptop, 2 puertos USB3, para aislar variables en la primera corrida) y hallazgo nuevo — el kit único de 42dB ya comprado no alcanza para las 2 rutas DL/UL simultáneas, la primera corrida prueba una dirección a la vez | Resolver el checklist de verificaciones de `TRANSMISION/ESQUEMA_POR_CABLE/README.md` (conector del kit de atenuadores, puertos USB3 libres, si se corre 4a-2 antes) antes de la primera corrida real de 4a-3. En paralelo, Fase 4a full-duplex (4a-4 en adelante) sigue bloqueada por 4a-1 esperando el bladeRF del nodo Cliente; su plan detallado ya está en `claudedocs/brief_pruebas_banco_cableado_fullduplex.md`, listo para ejecutar en cuanto haya 2 bladeRF disponibles | `TRANSMISION/pruebas/README.md`, `claudedocs/brief_pruebas_banco_cableado_fullduplex.md`, `TRANSMISION/ESQUEMA_POR_CABLE/README.md` |
| RF / enlace de datos | Diseño cerrado a 4 km, LOS confirmado por estudio de sitio (05/09/2026, ya no NLOS) con datasheets reales (EIRP +28.8dBm, margen +34.5/+31.5/+25.5dB BPSK/QPSK/16-QAM) | Medir tiempo de settling del PA, medir margen de fade estadístico (justificación de la reserva de ~10dB necesita revisarse ahora que el enlace es LOS, no NLOS) | `claudedocs/arquitectura_enlace_datos.md` §8 |
| Normativa (TVWS Perú) | **Bloqueador mayor de despliegue real**: el diseño usa solo sensado CNN; el decreto exige base de datos de geolocalización (Art. 17-18) como mecanismo primario de autorización | Diseñar cómo incorporar la consulta a BD de geolocalización + reporte Art. 13 al `CognitiveEngine` (el sensado CNN queda como capa complementaria, no sustituto) | `claudedocs/cumplimiento_normativo_tvws.md` |
| Instalación física | Specs reales confirmadas (conectores SMA en toda la cadena, bias-tee integrado en el bladeRF); el mount del discone (≤35mm) no encaja en ninguna sección del mástil real (60mm/48mm) | Conseguir reductor para el discone; confirmar con el equipo si el mástil tripode ya cumple el requisito no-penetrante | `claudedocs/estructura_fisica_instalacion.md` |
| Flujo de agentes (propone/verifica) | Implementados 10 agentes en `.claude/agents/` (5 dominios × proponente/verificador), disponibles por nombre desde una sesión nueva | Usarlo en tareas reales del proyecto | `.claude/agents/` (sin doc índice separado — cada agente documenta su propio rol) |

Cuando el usuario pida "seguir con X", leer solo la fila de X en esta tabla
— no releer `README.md` completo ni reconstruir contexto con `git log`. Abrir
el doc de la columna "Detalle en" solo si la tarea concreta lo requiere.

Read these docs before making non-trivial changes:
- `SPECS EQUIPOS/` — **the only source for technical characteristics of hardware already purchased**, one file per piece of equipment (`PA.md`, `LNA.md`, `ANTENA_DIRECCIONAL`, `ANTENA_OMNIDIRECCIONAL`, `MASTILES`, `COMPUTADORA_GATEWAY`, `SDR_ENLACE`). Added 28/08/2026 — supersedes the generic RFP-language specs previously scattered through `README.md`/`claudedocs/requisitos_pa_lna.md`/`PRESUPUESTO COMPLETO.xlsx` for anything this folder actually covers. Real numbers found here materially differ from what the project assumed before: PA is Class A (not AB), P1dB >32dBm (not the 33dBm nominal used everywhere), max input +3dBm (less than the bladeRF's own max TX output — don't drive it at full SDR gain); LPDA antenna is WA5VJB 400-1000MHz at 5dBi @500MHz (not the ≥10dBi originally specified nor the 6dBi conservative placeholder); LNA/antenna/PA connectors are all SMA (not N as older docs assumed); discone connector is SO-239 confirmed, mount diameter ≤35mm (doesn't fit either mast tube section, see `claudedocs/estructura_fisica_instalacion.md`); bladeRF bias-tee is built into every RF port (no separate injector needed). **Consult this folder first for any equipment-characteristics question** — don't fall back to guessing from the RFP-generic language in `PRESUPUESTO COMPLETO.xlsx` when a file here already has the real datasheet. Equipment without a file here (cables, gabinete, attenuator kit, RTL-SDR dongle) isn't covered — treat those as still-open per whatever other doc discusses them.
- `claudedocs/arquitectura_transmision_datos.md` — condensed reference for the GNU Radio cognitive block's 6 software layers (RadioInterface split, SpectralSensor, ChannelClassifier, CognitiveEngine, InbandControlLayer, MonitoringDashboard): message-port vs streaming-port model, per-layer interfaces, and open design gaps. **Read this instead of `README.md` §2/§7 when working on cognitive-block software architecture** — it's the token-cheap version of the same content.
- `claudedocs/arquitectura_enlace_datos.md` — **the assembled, current data-link physical-layer spec** (TDD framing/slot/guard, channel plan, modulation/FEC policy, PA operating point, availability/throughput budget): closed 20-21/08/2026, PA/antenna specs and distance updated 28/08/2026, LOS confirmed by site study 05/09/2026. Slot = 20 OFDM symbols (~1.78 ms), duty cycle 50/50, 1 channel for now (non-adjacent multi-channel explicitly rejected — PA intermodulation falls in the gap between bands), adaptive BPSK/QPSK/16-QAM both directions, PA 2W both nodes at 7.5 dB backoff, **4 km final design distance** (was 6 km/5-6 km range, was 10-15 km before that), **confirmed LOS** (was a 15dB NLOS assumption until 04/09/2026). Link margin at 4 km with real hardware datasheets and confirmed LOS: +34.5/+31.5/+25.5 dB BPSK/QPSK/16-QAM. **Read this first for any link-layer/digital-twin/hardware-bring-up work** — it's the "what to build," self-contained enough to start from directly. §8 lists what's still explicitly open (PA settling time unmeasured, FEC choice, statistical fade margin unmeasured — NLOS revalidation is no longer on this list, it's resolved) — don't assume those are resolved just because the framing/channel/modulation decisions are.
- `claudedocs/riesgos_arquitectura_transmision.md` — the "why" behind the decisions in the doc above, plus risks not yet closed. Full-duplex real (antenna-isolation-only TX/RX, no SIC/duplexer) was abandoned (26/07/2026) for **software TDD** — reflected in `README.md` §3.1. Still-open risk: control subcarriers #254/256/257 sitting adjacent to the DC-leakage bin that's already being avoided (only real open item left — FEC choice, the pilot-subcarrier pattern, and max frame size are all closed, don't re-litigate them). **Read this before proposing RF/full-duplex/TDD/FEC/OFDM design changes** — some problems are decided (don't re-litigate), others are open (don't assume resolved) — the doc marks which is which.
- `TRANSMISION/pruebas/README.md` — index of the GNU Radio transmission-chain test plan (`tun0`/`tuntap_pdu`, MAC framing, FEC, MOD/DEMOD, OFDM symbol structure, etc.), with pass/fail status per test and links to each test's own README + reusable code. Several architecture decisions that were left open in the docs above (the 5-byte MAC header format, the CCSDS FEC choice) got closed *here*, during testing — check this before treating them as unresolved.
- `README.md` (root) — current, authoritative system architecture: GNU Radio cognitive block layers, RF link budgets, OFDM frame structure, in-band control protocol, hardware BOM, project timeline. This was substantially rewritten — always re-read it rather than trusting memory of an earlier version. Only needed in full for hardware/RF/link-budget/timeline questions, or if `claudedocs/arquitectura_transmision_datos.md` doesn't cover what's needed.
- `IA/README.md` — IA module overview, architecture diagram, file layout, quick-start commands. Kept in sync with the actual code in this repo.
- `IA/pipeline_dataset_v2.md` — detailed design doc for the real RTL-SDR capture/labeling pipeline (capture script, energy-threshold labeling, augmentation, dataset QA checklist) — the only doc with this content. Hardware specs and code import paths were corrected to match the current module split (below); still worth a skim before touching the real-capture dataset pipeline specifically, less relevant for the synthetic-dataset/training path.
- `LINK_BUDGET/README.md` — **the only source of truth for link-budget numbers** (EIRP, NF, sensitivity, margin, DL/UL, full-duplex self-interference). Run the Streamlit calculator (`LINK_BUDGET/app.py`) instead of hand-computing or copying a number from `README.md`/`claudedocs/requisitos_pa_lna.md`/`claudedocs/bladerf_2_micro_xa4_specs.md` — those docs cite this tool's output, they don't own the numbers. Defaults updated 28/08/2026: real datasheets from `SPECS EQUIPOS/` (PA P1dB 32dBm, was 33dBm nominal; antenna gain 5dBi, real WA5VJB spec, was 6dBi conservative placeholder; no GDT) **and** final design distance **4 km** (was 6km/5-6km range, was 10-15km before that). Updated 05/09/2026: a site study confirmed **LOS** (line-of-sight) between Gateway and Cliente at 4km — `perdida_nlos_db` default dropped from 15dB (assumed NLOS) to 0dB. Current snapshot: EIRP +28.8dBm, margin +34.5/+31.5/+25.5dB BPSK/QPSK/16-QAM at 4km LOS — up ~15dB per modulation from the prior NLOS-assumed snapshot (+19.5/+16.5/+10.5dB), exactly the removed NLOS term.
- `claudedocs/cumplimiento_normativo_tvws.md` — found 14/08/2026: the architecture in `README.md` was designed *before* anyone checked `Decreto_Supremo_024-2021-MTC_TVWS.pdf` (Peru's TVWS regulation, in repo root). Still-blocking mismatch: the law mandates a **geolocation-database** model (Art. 17-18) as the primary channel-authorization mechanism, but the project's `CognitiveEngine` uses **CNN spectrum sensing** as the sole mechanism — sensing isn't a legal substitute for the DB query, at best a complementary safety layer; and Art. 13 geolocation reporting is entirely absent from the design. **Read this before treating the CNN-sensing architecture as regulatory-final for real deployment** — this is the single biggest open item blocking anything beyond lab/TRL-4 use. (The PSD-over-limit finding from 14/08 was resolved 20/08/2026 as a side effect of the PA backoff decision, and re-confirmed 28/08/2026 with the real PA datasheet — margin actually improved, ~6.1-6.6dB below the legal limit — see the doc's Problema 4.)
- `claudedocs/requisitos_antena_sensado.md` — now a **verification report** (rewritten 28/08/2026), not a procurement brief — the discone (Tram 1411) is already bought, see `SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`. Its connector is confirmed SO-239 and VSWR ≤1.5:1 (better than the ≤2:1 target), but gain-in-band and polarization are **still undocumented even in the real datasheet** — the original 21/08/2026 concern about this discone's gain never got resolved, just confirmed as an actual gap rather than a guess. New finding: mount diameter ≤35mm doesn't fit either section of the real mast (60mm/48mm, see `SPECS EQUIPOS/MASTILES`) — needs a reducer.
- `claudedocs/brief_enlace_gemelo_digital.md` — kickoff doc (13/08/2026) for closing the remaining half-duplex/TDD implementation decisions. **Superseded 20/08/2026** — the decisions it set out to close are closed, recorded in `claudedocs/arquitectura_enlace_datos.md`. Kept as historical record of how the decisions were reached; don't treat its "Qué falta decidir" section as still open.
- `claudedocs/brief_pruebas_banco_cableado_fullduplex.md` — kickoff doc (13/09/2026, **active, not superseded**) for an alternative test track: develops in detail the Fase 4 already sketched in `claudedocs/arquitectura_transmision_datos.md` (cabled bench, tests #16-18, previously left generic) with two twists of its own — **real simultaneous full-duplex** (not the field design's half-duplex/TDD) and **no LNA/PA**, using only attenuators to simulate FSPL; the sensing chain (RX2/discone) keeps its real antenna unchanged. Does not replace the field design (still TDD, `README.md` §3.1) — it's a parallel validation track that exploits the fact that, over cable with dedicated TX/RX ports, the antenna-isolation deficit that killed real full-duplex in the field (Problema 1, `riesgos_arquitectura_transmision.md`) doesn't apply the same way. Planned to run at both UNI (Lima) and Huánuco. **Read this before touching Fase 4/the cabled bench** — it has the sub-test plan, the still-pending attenuation calculation, and open questions (AD9361 intra-chip isolation unverified, Huánuco's exact role unconfirmed).
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
pip install -r IA/requirements.txt
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
