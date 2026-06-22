"""
nucleo.py
=========
Núcleo de SpectralSense: constantes del sistema, preprocesamiento I/Q -> PSD,
arquitectura del modelo (SpectralSenseCNN) y funciones de pérdida.

Reemplaza la parte "core" de spectral_sense.py (ahora dividido en nucleo.py,
inferencia.py y entrenamiento.py). Sin canal LoRa: el control es exclusivamente
in-band (subportadoras OFDM #254/256/257), por lo que este módulo no asume
ningún transporte de control — solo produce el mapa de ocupación que consume
el CognitiveEngine.

CRÍTICO: calcular_psd() y normalizar_psd() deben ser IDÉNTICAS en
entrenamiento e inferencia. Mitigan el domain mismatch RTL-SDR (8 bits,
captura) -> bladeRF (12 bits, campo).
"""

import numpy as np
import torch
import torch.nn as nn


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES DEL SISTEMA
# ─────────────────────────────────────────────────────────────────────────────

# Plan de atribución TVWS peruano: canales 14-52, 6 MHz cada uno
CANALES_TVWS_PE = list(range(14, 53))  # 39 canales en total

# El bladeRF (AD9361) tiene ~56 MHz de ancho de banda instantáneo máximo:
# es físicamente imposible capturar los 228 MHz (470-698 MHz) en una sola
# FFT. El sensado se hace en 5 posiciones de barrido fijas; cada una expone
# entre 7 y 9 canales TVWS en su zona plana. El modelo clasifica UNA
# sub-banda por inferencia; SpectralOccupancyMap (en inferencia.py) agrega
# las 5 sub-bandas en el mapa global de 39 canales.
POSICIONES_BARRIDO = [
    {"centro_mhz": 498, "canales_globales": list(range(14, 23))},  # 9 canales
    {"centro_mhz": 536, "canales_globales": list(range(22, 31))},  # 9 canales
    {"centro_mhz": 578, "canales_globales": list(range(30, 39))},  # 9 canales
    {"centro_mhz": 626, "canales_globales": list(range(38, 47))},  # 9 canales
    {"centro_mhz": 670, "canales_globales": list(range(46, 53))},  # 7 canales
]

N_CANALES_MAX      = 9      # máximo de canales visibles en una sub-banda
PSD_LENGTH         = 512    # puntos del vector PSD de entrada (109 kHz/bin sobre 56 MHz)
UMBRAL_LIBRE       = 0.20   # prob_ocupado < 0.20 -> canal libre (conservador, asimetría regulatoria)
UMBRAL_SOSPECHOSO  = 0.65
UMBRAL_EMERGENCIA  = 0.95


# ─────────────────────────────────────────────────────────────────────────────
# PREPROCESAMIENTO — idéntico en entrenamiento e inferencia
# ─────────────────────────────────────────────────────────────────────────────

def calcular_psd(iq: np.ndarray, n_fft: int = PSD_LENGTH, n_segmentos: int = 20) -> np.ndarray:
    """
    PSD de un vector I/Q por el método de Welch simplificado (ventana Hann,
    segmentos solapados promediados).

    Args:
        iq:          array complejo (N,) o real (N, 2) con columnas [I, Q]
        n_fft:       puntos de la FFT
        n_segmentos: segmentos a promediar (más = menos varianza)

    Returns:
        psd_db: array (n_fft,) en dB, centrado en DC (fftshift aplicado)
    """
    if iq.ndim == 2:
        iq = iq[:, 0] + 1j * iq[:, 1]

    ventana   = np.hanning(n_fft)
    paso      = max(1, (len(iq) - n_fft) // n_segmentos)
    acumulado = np.zeros(n_fft)
    n_validos = 0

    for k in range(n_segmentos):
        inicio = k * paso
        fin    = inicio + n_fft
        if fin > len(iq):
            break
        segmento   = iq[inicio:fin] * ventana
        espectro   = np.fft.fftshift(np.fft.fft(segmento))
        acumulado += np.abs(espectro) ** 2
        n_validos += 1

    if n_validos == 0:
        raise ValueError(f"Vector I/Q demasiado corto: {len(iq)} muestras para n_fft={n_fft}")

    psd_lineal = acumulado / n_validos
    return 10 * np.log10(psd_lineal + 1e-12)


def corregir_dc_offset(psd: np.ndarray, n_bins_mascara: int = 3) -> np.ndarray:
    """Enmascara el bin central de DC (LO leakage del SDR) interpolando linealmente."""
    psd_c  = psd.copy()
    centro = len(psd) // 2
    inicio = max(0, centro - n_bins_mascara)
    fin    = min(len(psd), centro + n_bins_mascara + 1)
    izq    = psd[max(0, inicio - 1)]
    der    = psd[min(len(psd) - 1, fin)]
    psd_c[inicio:fin] = np.linspace(izq, der, fin - inicio)
    return psd_c


def normalizar_psd(psd_raw: np.ndarray) -> np.ndarray:
    """
    Normaliza al rango [0, 1] usando percentiles robustos (5/95).

    CRÍTICO: idéntica en entrenamiento e inferencia. Mitiga el domain
    mismatch RTL-SDR (8 bits, ~48 dB) -> bladeRF (12 bits, ~72 dB).
    """
    psd_min  = np.percentile(psd_raw, 5)
    psd_max  = np.percentile(psd_raw, 95)
    psd_norm = (psd_raw - psd_min) / (psd_max - psd_min + 1e-9)
    return np.clip(psd_norm, 0.0, 1.0).astype(np.float32)


def iq_a_psd_normalizado(iq: np.ndarray, n_fft: int = PSD_LENGTH) -> np.ndarray:
    """Pipeline completo: I/Q crudo -> PSD normalizado listo para la CNN."""
    psd_db = calcular_psd(iq, n_fft=n_fft)
    psd_db = corregir_dc_offset(psd_db)
    return normalizar_psd(psd_db)


# ─────────────────────────────────────────────────────────────────────────────
# MODELO — SpectralSenseCNN con cabeza dual (ocupación + margen)
# ─────────────────────────────────────────────────────────────────────────────

class SpectralSenseCNN(nn.Module):
    """
    1D-CNN para sensado espectral TVWS, con dos cabezas sobre un backbone
    compartido:

      - cabeza_ocupacion: P(ocupado) por canal (logits, sigmoid en inferencia)
      - cabeza_margen:    margen/SNR estimado en dB por canal (regresión)

    La cabeza de margen existe porque el CognitiveEngine soporta una política
    `max_margin`: P(ocupado) cerca de 0 no distingue cuál de varios canales
    libres está más limpio (todos saturan cerca de 0 por igual). El margen
    estimado sí da un número continuo comparable entre canales libres.

    Input:  (batch, 512)  — PSD normalizado [0, 1]
    Output: (logits_ocupacion (batch, 9), margen_db (batch, 9))
    """

    def __init__(self, n_canales_salida: int = N_CANALES_MAX, dropout: float = 0.3):
        super().__init__()
        self.n_canales_salida = n_canales_salida

        # Bloque 1: silueta espectral gruesa (~4.9 MHz de campo receptivo)
        self.bloque1 = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=45, padding=22),
            nn.BatchNorm1d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2)       # 512 -> 256
        )

        # Bloque 2: textura intra-canal (~1 MHz)
        self.bloque2 = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=9, padding=4),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.Conv1d(64, 64, kernel_size=9, padding=4),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2, stride=2)       # 256 -> 128
        )

        # Bloque 3: correlación inter-canal (~2.2 MHz)
        self.bloque3 = nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=5, padding=2),
            nn.BatchNorm1d(128),
            nn.ReLU(inplace=True)
            # Sin MaxPool: conserva resolución para GlobalAveragePool
        )

        self.gap = nn.AdaptiveAvgPool1d(1)   # 128 x 128 -> (128,)

        # Tronco compartido entre ambas cabezas
        self.tronco = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(inplace=True),
            nn.Dropout(p=dropout),
        )

        self.cabeza_ocupacion = nn.Linear(64, n_canales_salida)   # logits, sin Sigmoid
        self.cabeza_margen    = nn.Linear(64, n_canales_salida)   # regresión lineal, dB

        self._inicializar_pesos()

    def _inicializar_pesos(self):
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor):
        """
        Args:
            x: tensor (batch, 512) — PSD normalizado

        Returns:
            (logits_ocupacion, margen_db): cada uno (batch, n_canales_salida)
        """
        x = x.unsqueeze(1)          # (batch, 512) -> (batch, 1, 512)
        x = self.bloque1(x)
        x = self.bloque2(x)
        x = self.bloque3(x)
        x = self.gap(x).squeeze(-1)
        x = self.tronco(x)
        return self.cabeza_ocupacion(x), self.cabeza_margen(x)

    def predecir(self, x: torch.Tensor, umbral: float = UMBRAL_LIBRE) -> dict:
        """
        Inferencia con decisión de canal libre/ocupado y margen estimado.

        Args:
            x:      tensor (512,) o (1, 512) — PSD normalizado
            umbral: prob_ocupado < umbral -> libre

        Returns:
            dict con prob_ocupado, margen_db, libres (índices), ocupados (índices)
        """
        self.eval()
        if x.dim() == 1:
            x = x.unsqueeze(0)
        with torch.no_grad():
            logits, margen = self.forward(x)
            probs  = torch.sigmoid(logits).squeeze().cpu().numpy()
            margen = margen.squeeze().cpu().numpy()

        return {
            "prob_ocupado": probs,
            "margen_db":    margen,
            "libres":       [i for i, p in enumerate(probs) if p < umbral],
            "ocupados":     [i for i, p in enumerate(probs) if p >= umbral]
        }

    def contar_parametros(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ─────────────────────────────────────────────────────────────────────────────
# PÉRDIDAS — enmascaran posiciones con etiqueta desconocida (-1)
# ─────────────────────────────────────────────────────────────────────────────

class BCEWithLogitsLossMasked(nn.Module):
    """
    BCEWithLogitsLoss que ignora posiciones con etiqueta = -1.0 (desconocido).

    nn.BCEWithLogitsLoss estándar con target=-1 produce pérdidas inválidas
    que pueden divergir; el optimizador las explota empujando esos logits a
    valores extremos y desestabiliza TODO el entrenamiento. Esta clase
    filtra esas posiciones ANTES de calcular la pérdida.
    """
    def __init__(self, pos_weight: torch.Tensor = None):
        super().__init__()
        self.pos_weight = pos_weight

    def forward(self, logits: torch.Tensor, etiquetas: torch.Tensor) -> torch.Tensor:
        mascara = etiquetas >= 0
        if mascara.sum() == 0:
            return torch.tensor(0.0, device=logits.device, requires_grad=True)

        logits_m = logits[mascara]
        etiq_m   = etiquetas[mascara]

        pw = None
        if self.pos_weight is not None:
            pw_full = self.pos_weight.unsqueeze(0).expand_as(etiquetas)
            pw = pw_full[mascara]

        return nn.functional.binary_cross_entropy_with_logits(logits_m, etiq_m, pos_weight=pw)


class MargenLossMasked(nn.Module):
    """
    MSE del margen estimado, enmascarado por la MISMA validez que la
    ocupación: si el canal en esa posición no tiene etiqueta de ocupación
    válida (-1), tampoco hay margen real conocido para esa posición — no
    hace falta un segundo sentinel de "desconocido" para el margen.

    Los datasets reales capturados antes de esta cabeza (IA/dataset/, v1)
    no tienen margen_db: TVWSDataset les asigna margen_valido=0 en todas
    las posiciones y esta pérdida los ignora automáticamente, sin romper
    el entrenamiento de la cabeza de ocupación con esos datos.
    """
    def forward(self, margen_pred: torch.Tensor, margen_real: torch.Tensor,
                etiquetas: torch.Tensor, margen_valido: torch.Tensor) -> torch.Tensor:
        mascara = (etiquetas >= 0) & (margen_valido > 0)
        if mascara.sum() == 0:
            return torch.tensor(0.0, device=margen_pred.device, requires_grad=True)
        return nn.functional.mse_loss(margen_pred[mascara], margen_real[mascara])
