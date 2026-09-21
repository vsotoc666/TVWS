#!/usr/bin/env python3
"""
Combina un JSON de --modo calibracion y uno de --modo medicion (ambos
producidos por medir_psd_tono.py) para calcular el aislamiento intra-chip
TX1->RX1 de la Prueba 4a-1. Ver README.md de esta carpeta para la
derivación física completa; resumen:

Como la ganancia TX (`tx_gain_db`) es la MISMA en ambas corridas
(obligatorio, se verifica acá), la potencia TX conducida se cancela
algebraicamente -- no hace falta conocerla en dBm absolutos, algo que el
proyecto no puede medir de todos modos (sin instrumentación de laboratorio
RF, ver claudedocs/requisitos_pa_lna.md §3.3). Solo hace falta el valor del
atenuador de calibración (dato conocido, del kit SMA) y la diferencia de
ganancia RX entre ambas corridas (parámetro que nosotros mismos fijamos):

    Aislamiento_dB = atenuador_db
                     + (rx_gain_medicion - rx_gain_calibracion)
                     - (pico_dbfs_medicion - pico_dbfs_calibracion)

Si la medición no detectó el tono (`detectado=False` en su JSON), el pico
real está por debajo del piso de ruido -- se reporta una COTA INFERIOR del
aislamiento usando el piso de ruido de la medición en vez de su pico (el
aislamiento real es *al menos* ese valor, posiblemente mucho más).
"""

import argparse
import json
import re
import sys


def calcular(calibracion: dict, medicion: dict) -> dict:
    if calibracion["modo"] != "calibracion":
        raise ValueError("El primer JSON no es una corrida --modo calibracion")
    if medicion["modo"] != "medicion":
        raise ValueError("El segundo JSON no es una corrida --modo medicion")
    if calibracion["tx_gain_db"] != medicion["tx_gain_db"]:
        raise ValueError(
            f"tx_gain_db distinta entre calibración ({calibracion['tx_gain_db']}) y medición "
            f"({medicion['tx_gain_db']}) -- la fórmula asume la misma potencia TX conducida en "
            "ambas corridas; repetir la medición con el mismo --tx_gain_db que la calibración."
        )
    if calibracion["freq_hz"] != medicion["freq_hz"] or calibracion["offset_hz"] != medicion["offset_hz"]:
        raise ValueError("freq_hz/offset_hz distintos entre calibración y medición -- deben coincidir.")
    if calibracion["atenuador_db"] is None:
        raise ValueError("El JSON de calibración no tiene atenuador_db -- ¿es realmente una corrida de calibración?")

    delta_ganancia_rx = medicion["rx_gain_db"] - calibracion["rx_gain_db"]

    if medicion["detectado"]:
        aislamiento = (
            calibracion["atenuador_db"] + delta_ganancia_rx
            - (medicion["pico_dbfs"] - calibracion["pico_dbfs"])
        )
        return {"aislamiento_db": aislamiento, "es_cota_inferior": False}

    # No detectado: el piso de ruido de la medición sustituye (pesimistamente)
    # al pico real -- el aislamiento real es AL MENOS este valor.
    cota_inferior = (
        calibracion["atenuador_db"] + delta_ganancia_rx
        - (medicion["piso_ruido_dbfs"] - calibracion["pico_dbfs"])
    )
    return {"aislamiento_db": cota_inferior, "es_cota_inferior": True}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("calibracion_json")
    p.add_argument("medicion_json")
    args = p.parse_args()

    with open(args.calibracion_json) as f:
        calibracion = json.load(f)
    with open(args.medicion_json) as f:
        medicion = json.load(f)

    resultado = calcular(calibracion, medicion)

    if resultado["es_cota_inferior"]:
        print(f"Aislamiento TX1->RX1 intra-chip: >= {resultado['aislamiento_db']:.1f} dB (cota inferior -- "
              "el tono no fue distinguible del piso de ruido en la medición; el aislamiento real podría ser mayor)")
    else:
        print(f"Aislamiento TX1->RX1 intra-chip: {resultado['aislamiento_db']:.1f} dB")

    print(
        "\nReferencia (claudedocs/riesgos_arquitectura_transmision.md, Problema 1): el full-duplex real "
        "por antena se descartó porque el aislamiento requerido (~90-110 dB) superaba por mucho el "
        "disponible por separación de antena (~30-50 dB). Comparar el número de arriba contra ese rango "
        "de 90-110 dB para saber si la hipótesis del brief (banco cableado sí permite full-duplex real, "
        "claudedocs/brief_pruebas_banco_cableado_fullduplex.md §2) se sostiene."
    )


if __name__ == "__main__":
    main()
