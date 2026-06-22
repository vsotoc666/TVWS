"""
inferencia.py
=============
Inferencia en campo (Gateway): ChannelClassifier (wrapper ONNX, una
sub-banda por llamada) y SpectralOccupancyMap (agrega las 5 sub-bandas
en el mapa global de 39 canales que consume el CognitiveEngine).

Sin LoRa: este módulo no transporta nada, solo mide. La decisión y la
señalización in-band (subportadoras OFDM #254/256/257) son responsabilidad
del CognitiveEngine, fuera de este repo.

Proveedor ONNX Runtime: el Gateway corre Ubuntu 22.04 LTS (Linux) sobre un
Intel Core Ultra 5 225 — DirectML NO está disponible ahí (es exclusivo de
Windows). Se prioriza OpenVINOExecutionProvider (acelera en el iGPU Intel)
con fallback automático a CPU; el modelo es lo bastante liviano (~90K
parámetros, <1 ms/sub-banda) que CPU sola ya cumple el presupuesto.
"""

import time
import numpy as np

from nucleo import iq_a_psd_normalizado, PSD_LENGTH, UMBRAL_LIBRE, POSICIONES_BARRIDO


class ChannelClassifier:
    """
    Wrapper de ONNX Runtime para inferencia en campo. Clasifica UNA
    sub-banda de 56 MHz por llamada (ver nucleo.SpectralSenseCNN — el
    modelo no intenta cubrir los 228 MHz completos en una sola FFT,
    porque el bladeRF no puede capturarlos de una sola vez).

    Uso:
        clasificador = ChannelClassifier("spectral_sense.onnx")
        resultado = clasificador.classify(psd_normalizado)
    """

    def __init__(self, model_path: str, threshold: float = UMBRAL_LIBRE):
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("Instalar onnxruntime: pip install onnxruntime")

        disponibles = ort.get_available_providers()
        if "OpenVINOExecutionProvider" in disponibles:
            proveedores = ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
            print("ONNX Runtime: usando OpenVINO (iGPU Intel)")
        else:
            proveedores = ["CPUExecutionProvider"]
            print("ONNX Runtime: usando CPU")

        self.session   = ort.InferenceSession(model_path, providers=proveedores)
        self.threshold = threshold

    def classify(self, psd_vector: np.ndarray) -> dict:
        """
        Args:
            psd_vector: array (512,) float32, PSD ya normalizado [0,1]
                        (ver nucleo.iq_a_psd_normalizado)

        Returns:
            {
                'occupancy':  np.ndarray (9,)  — P(ocupado) por canal local
                'margen_db':  np.ndarray (9,)  — margen estimado por canal local
                'free_local': list[int]        — índices locales libres
                'inference_ms': float,
                'confidence': float             — mean(|p-0.5|*2), margen real
                                                   a la decisión (no mean(occupancy))
            }
        """
        t0 = time.perf_counter()

        inp = psd_vector[np.newaxis, :].astype(np.float32)
        logits, margen = self.session.run(["logits_ocupacion", "margen_db"], {"psd_input": inp})
        probs = 1.0 / (1.0 + np.exp(-logits[0]))

        inference_ms = (time.perf_counter() - t0) * 1000

        return {
            "occupancy":    probs,
            "margen_db":    margen[0],
            "free_local":   [i for i, p in enumerate(probs) if p < self.threshold],
            "inference_ms": round(inference_ms, 3),
            "confidence":   float(np.mean(np.abs(probs - 0.5) * 2)),
        }

    def classify_subbanda(self, iq: np.ndarray, posicion_idx: int) -> dict:
        """
        Conveniencia: I/Q crudo de una sub-banda -> resultado mapeado a
        canales globales (14-52) según la posición de barrido.
        """
        psd = iq_a_psd_normalizado(iq, n_fft=PSD_LENGTH)
        r   = self.classify(psd)

        canales = POSICIONES_BARRIDO[posicion_idx]["canales_globales"]
        n_vis   = len(canales)

        return {
            "prob_por_canal":  {canales[i]: float(r["occupancy"][i]) for i in range(n_vis)},
            "margen_por_canal": {canales[i]: float(r["margen_db"][i]) for i in range(n_vis)},
            "libres_globales": [canales[i] for i in r["free_local"] if i < n_vis],
            "inference_ms":    r["inference_ms"],
            "confidence":      r["confidence"],
        }


class SpectralOccupancyMap:
    """
    Agrega las 5 sub-bandas del barrido en el mapa global de 39 canales
    (14-52) que consume el CognitiveEngine.

    Las 5 sub-bandas NO se capturan simultáneamente — se barren
    secuencialmente a lo largo de un ciclo de ~100-200 ms. Por eso cada
    canal del mapa lleva su propio timestamp de última actualización en
    vez de tratarse como una foto instantánea: el CognitiveEngine puede
    así aplicar su umbral de degradación sabiendo qué tan reciente es
    cada lectura, no asumiendo que todo el mapa es igual de fresco.

    Uso:
        mapa = SpectralOccupancyMap()
        for posicion_idx, iq in enumerate(capturas_de_un_ciclo):
            resultado = clasificador.classify_subbanda(iq, posicion_idx)
            mapa.actualizar(posicion_idx, resultado, timestamp=time.time())
        print(mapa.mapa_actual())
    """

    def __init__(self):
        self._canales: dict[int, dict] = {}

    def actualizar(self, posicion_idx: int, resultado_subbanda: dict, timestamp: float) -> None:
        for canal, prob in resultado_subbanda["prob_por_canal"].items():
            self._canales[canal] = {
                "prob_ocupado":  prob,
                "margen_db":     resultado_subbanda["margen_por_canal"][canal],
                "libre":         prob < UMBRAL_LIBRE,
                "actualizado_en": timestamp,
            }

    def mapa_actual(self, ahora: float = None) -> dict:
        """
        Returns:
            {
              "canales": {14: {prob_ocupado, margen_db, libre, antiguedad_ms}, ...},
              "libres_por_indice": [...],          # orden de canal, sin preordenar por política
              "confianza_global": float,           # mean(|p-0.5|*2) sobre todos los canales conocidos
            }
        El ranking por política (lowest_free/max_margin/least_used) es
        responsabilidad del CognitiveEngine, no de este módulo.
        """
        if ahora is None:
            ahora = time.time()

        canales = {}
        probs   = []
        for canal, v in sorted(self._canales.items()):
            antiguedad_ms = (ahora - v["actualizado_en"]) * 1000
            canales[canal] = {
                "prob_ocupado":  v["prob_ocupado"],
                "margen_db":     v["margen_db"],
                "libre":         v["libre"],
                "antiguedad_ms": round(antiguedad_ms, 1),
            }
            probs.append(v["prob_ocupado"])

        confianza = float(np.mean([abs(p - 0.5) * 2 for p in probs])) if probs else 0.0

        return {
            "canales":            canales,
            "libres_por_indice":  sorted(c for c, v in canales.items() if v["libre"]),
            "confianza_global":   confianza,
        }
