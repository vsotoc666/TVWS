#!/usr/bin/env python3
"""
Autoprueba de medir_psd_tono.py / calcular_aislamiento.py usando --simular
(sin hardware, sin GNU Radio -- solo numpy). No es la Prueba 4a-1 en sí
(esa requiere el bladeRF real) sino la validación de que la lógica de
captura/detección/fórmula está bien antes de gastar tiempo de banco con
hardware real.

Casos cubiertos:
  1. "Detectado": SNR alto en ambas corridas -> el aislamiento calculado
     recupera el valor conocido que se usó para construir el escenario
     sintético (dentro de una tolerancia que viene de la varianza de
     estimación del PSD, no de la fórmula).
  2. "No detectado": SNR bajo en la medición -> se reporta una cota
     inferior explícita, nunca un valor puntual disfrazado de exacto.
  3. Guardrail: tx_gain_db distinta entre calibración y medición -> error,
     no un número silenciosamente incorrecto.

Correr con: python3 test_medir_psd_tono.py
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).parent
MEDIR = AQUI / "medir_psd_tono.py"
AISLAR = AQUI / "calcular_aislamiento.py"


def _correr_medicion(tmpdir, nombre, modo, snr_db, rx_gain_db, tx_gain_db=10.0,
                      atenuador_db=None, semilla=1):
    salida = Path(tmpdir) / f"{nombre}.json"
    cmd = [
        sys.executable, str(MEDIR),
        "--modo", modo, "--simular",
        "--simular_snr_db", str(snr_db),
        "--simular_semilla", str(semilla),
        "--tx_gain_db", str(tx_gain_db),
        "--rx_gain_db", str(rx_gain_db),
        "--salida", str(salida),
    ]
    if atenuador_db is not None:
        cmd += ["--atenuador_db", str(atenuador_db)]
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    assert resultado.returncode == 0, f"medir_psd_tono.py falló:\n{resultado.stderr}"
    return json.loads(salida.read_text())


def _extraer_aislamiento_db(texto: str) -> float:
    m = re.search(r"Aislamiento TX1->RX1 intra-chip:\s*(?:>=\s*)?(-?\d+(?:\.\d+)?)\s*dB", texto)
    assert m, f"No se pudo extraer el valor de aislamiento de la salida:\n{texto}"
    return float(m.group(1))


def probar_caso_detectado():
    # Escenario construido para que el aislamiento "verdadero" sea 55 dB:
    #   atenuador_cal=40dB, rx_gain: 20->60 (delta=+40dB), snr: 30->15dB (delta=-15dB)
    #   pico_med - pico_cal = delta_rx_gain + delta_snr = 40 + (-15) = 25 dB
    #   aislamiento = atenuador(40) + delta_rx_gain(40) - 25 = 55 dB
    with tempfile.TemporaryDirectory() as tmp:
        cal = _correr_medicion(tmp, "cal", "calibracion", snr_db=30, rx_gain_db=20, atenuador_db=40, semilla=1)
        med = _correr_medicion(tmp, "med", "medicion", snr_db=15, rx_gain_db=60, semilla=2)
        assert cal["detectado"], f"Calibración debería detectar el tono (SNR pico {cal['snr_pico_db']:.1f} dB)"
        assert med["detectado"], f"Medición debería detectar el tono (SNR pico {med['snr_pico_db']:.1f} dB)"

        resultado = subprocess.run(
            [sys.executable, str(AISLAR), str(Path(tmp) / "cal.json"), str(Path(tmp) / "med.json")],
            capture_output=True, text=True,
        )
        assert resultado.returncode == 0, resultado.stderr
        print(resultado.stdout)

        valor = _extraer_aislamiento_db(resultado.stdout)
        assert abs(valor - 55.0) < 3.0, (
            f"Aislamiento calculado ({valor:.1f} dB) se aleja demasiado del valor esperado (~55 dB) -- "
            "revisar la fórmula en calcular_aislamiento.py o el modelo sintético en _capturar_simulado()"
        )
    print(f"✅ Caso 'detectado': OK (aislamiento recuperado {valor:.1f} dB, esperado ~55 dB)")


def probar_caso_no_detectado():
    # snr_db aquí es una relación de AMPLITUD en el dominio del tiempo (ver
    # docstring de _capturar_simulado), no la SNR por bin que finalmente mide
    # `medir()` -- el FFT (n_fft=512 default) aporta una ganancia de proceso
    # de ~10*log10(512) ≈ 27 dB sobre esa cifra (verificado empíricamente:
    # snr_db=-25 -> snr_pico_db medido ≈ 2.7 dB), porque el tono se suma
    # coherentemente en un bin mientras el ruido de banda ancha no. Por eso
    # -25 dB (no -5) es el valor que efectivamente cae bajo el margen de
    # detección de 8 dB -- ver también la guía de --n_fft en medir_psd_tono.py.
    with tempfile.TemporaryDirectory() as tmp:
        _correr_medicion(tmp, "cal", "calibracion", snr_db=30, rx_gain_db=20, atenuador_db=40, semilla=1)
        med = _correr_medicion(tmp, "med", "medicion", snr_db=-25, rx_gain_db=30, semilla=3)
        assert not med["detectado"], (
            f"Con SNR inyectado de -25 dB no debería superar el margen de detección "
            f"(8 dB default) -- SNR medido: {med['snr_pico_db']:.1f} dB"
        )

        resultado = subprocess.run(
            [sys.executable, str(AISLAR), str(Path(tmp) / "cal.json"), str(Path(tmp) / "med.json")],
            capture_output=True, text=True,
        )
        assert resultado.returncode == 0, resultado.stderr
        assert "cota inferior" in resultado.stdout, "Debe reportarse explícitamente como cota inferior, no como valor exacto"
        assert ">=" in resultado.stdout, "El formato de cota inferior debe usar '>=' para que no se confunda con un valor puntual"
    print("✅ Caso 'no detectado' (cota inferior): OK")


def probar_guardrail_tx_gain():
    with tempfile.TemporaryDirectory() as tmp:
        _correr_medicion(tmp, "cal", "calibracion", snr_db=30, rx_gain_db=20, tx_gain_db=10.0, atenuador_db=40, semilla=1)
        _correr_medicion(tmp, "med", "medicion", snr_db=15, rx_gain_db=60, tx_gain_db=12.0, semilla=2)  # tx_gain distinta a propósito

        resultado = subprocess.run(
            [sys.executable, str(AISLAR), str(Path(tmp) / "cal.json"), str(Path(tmp) / "med.json")],
            capture_output=True, text=True,
        )
        assert resultado.returncode != 0, "Debe fallar si tx_gain_db difiere entre calibración y medición"
        assert "tx_gain_db distinta" in (resultado.stdout + resultado.stderr)
    print("✅ Guardrail tx_gain_db distinta: OK (rechazado correctamente)")


if __name__ == "__main__":
    probar_caso_detectado()
    probar_caso_no_detectado()
    probar_guardrail_tx_gain()
    print("\nTodas las autopruebas (modo --simular, sin hardware) pasaron.")
