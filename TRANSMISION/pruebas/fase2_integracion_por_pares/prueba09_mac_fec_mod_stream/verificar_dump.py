#!/usr/bin/env python3
"""Verifica simbolos_stream.txt contra lo que la cadena MAC->FEC->MOD
calcula de forma independiente (cadena.payload_a_simbolos). Criterio de la
Prueba 9: "los simbolos generados coinciden con lo esperado por
modulacion" -- se compara valor por valor, no solo la cantidad.

Uso:
    ~/envs/SDR/bin/python verificar_dump.py simbolos_stream.txt --seq-num 5 --frag-flags 0
"""
import argparse
import sys

from cadena import payload_a_simbolos
from flowgraph_prueba09 import PAQUETE_PRUEBA3


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def cargar_dump(ruta):
    datos = []
    n_tags_declarado = None
    with open(ruta) as f:
        for linea in f:
            linea = linea.strip()
            if linea.startswith("# n_tags="):
                n_tags_declarado = int(linea.split("=")[1])
            elif linea.startswith("#"):
                continue
            elif linea:
                re_str, im_str = linea.split(",")
                datos.append(complex(float(re_str), float(im_str)))
    return datos, n_tags_declarado


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archivo")
    parser.add_argument("--seq-num", type=int, default=5)
    parser.add_argument("--frag-flags", type=int, default=0)
    args = parser.parse_args()

    _, _, simbolos_esperados = payload_a_simbolos(PAQUETE_PRUEBA3, args.seq_num, args.frag_flags)
    n = len(simbolos_esperados)

    datos_stream, n_tags = cargar_dump(args.archivo)

    resultados = []
    resultados.append(_check(f"el dump tiene un numero entero de paquetes de {n} simbolos", len(datos_stream) % n == 0))
    n_paquetes = len(datos_stream) // n
    resultados.append(_check(f"al menos 1 paquete capturado (hubo {n_paquetes})", n_paquetes >= 1))
    if n_tags is not None:
        resultados.append(_check(f"cantidad de tags ({n_tags}) coincide con cantidad de paquetes ({n_paquetes})", n_tags == n_paquetes))

    todos_ok = True
    for i in range(n_paquetes):
        chunk = datos_stream[i * n:(i + 1) * n]
        coincide = chunk == simbolos_esperados
        todos_ok = todos_ok and coincide
    resultados.append(_check(f"los {n_paquetes} paquetes coinciden EXACTO (valor a valor) con los simbolos esperados", todos_ok))

    ok = all(resultados)
    print(f"\n{'TODO CORRECTO' if ok else 'HAY DIFERENCIAS'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
