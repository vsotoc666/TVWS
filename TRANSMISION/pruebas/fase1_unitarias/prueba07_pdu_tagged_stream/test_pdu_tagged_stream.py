#!/usr/bin/env python3
"""Prueba 7 - Fase 1: PDU<->Tagged Stream (ambos sentidos).

Paquete de longitud fija conocida -> verificar tags y reconstruccion
exacta. Criterio del plan: "la frontera mensajes<->streaming no corrompe
ni trunca".

Requiere el venv ~/envs/SDR (gnuradio.pdu). No requiere tun0 ni sudo.

Uso:
    ~/envs/SDR/bin/python test_pdu_tagged_stream.py
"""
import sys

from pdu_stream import pdu_a_stream_repetido, round_trip_completo, stream_a_pdus

N = 40
PAQUETE = [complex(i, -i) for i in range(N)]
PERIODO_MS = 150
DURACION_S = 1.2


def _check(nombre, condicion):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}")
    return condicion


def test_pdu_a_stream_tags_y_datos():
    """Sentido TX: PDU -> pdu_to_tagged_stream. Se dispara el mismo PDU
    varias veces seguidas para validar tambien que los limites entre
    paquetes consecutivos (offsets de los tags) quedan bien puestos."""
    datos, tags = pdu_a_stream_repetido(PAQUETE, PERIODO_MS, DURACION_S)

    ok_cantidad = len(datos) % N == 0 and len(tags) == len(datos) // N and len(tags) >= 2
    ok_tags = True
    for i, t in enumerate(tags):
        import pmt
        offset_esperado = i * N
        chunk = datos[offset_esperado:offset_esperado + N]
        ok_tags = (
            ok_tags
            and t.offset == offset_esperado
            and pmt.symbol_to_string(t.key) == "packet_len"
            and pmt.to_python(t.value) == N
            and chunk == PAQUETE
        )
    return _check(
        f"PDU->stream: {len(tags)} paquetes consecutivos, tags y datos correctos en cada limite",
        ok_cantidad and ok_tags,
    )


def test_stream_a_pdu_un_paquete():
    """Sentido RX: un stream tageado de longitud conocida -> tagged_stream_to_pdu."""
    recuperados = stream_a_pdus(PAQUETE, [N])
    return _check(
        "stream->PDU: un paquete de longitud conocida reconstruido exacto",
        len(recuperados) == 1 and recuperados[0] == PAQUETE,
    )


def test_stream_a_pdu_longitudes_variables():
    """Sentido RX con 3 paquetes de longitudes DISTINTAS concatenados en el
    mismo stream -- valida que la longitud variable no corrompe ni trunca
    los limites entre paquetes."""
    paquetes = [
        [complex(i, 0) for i in range(5)],
        [complex(0, i) for i in range(12)],
        [complex(i, i) for i in range(3)],
    ]
    datos_concatenados = [v for p in paquetes for v in p]
    recuperados = stream_a_pdus(datos_concatenados, [len(p) for p in paquetes])
    return _check(
        "stream->PDU: 3 paquetes de longitud variable reconstruidos exactos, sin mezclar limites",
        recuperados == paquetes,
    )


def test_round_trip_completo():
    """PDU -> stream -> PDU, ambos bloques encadenados: el caso mas
    parecido a como se van a usar en el flowgraph real."""
    recuperados = round_trip_completo(PAQUETE, PERIODO_MS, DURACION_S)
    todos_ok = len(recuperados) >= 2 and all(r == PAQUETE for r in recuperados)
    return _check(
        f"round-trip completo PDU->stream->PDU: {len(recuperados)} paquetes, todos exactos",
        todos_ok,
    )


def main():
    resultados = [
        test_pdu_a_stream_tags_y_datos(),
        test_stream_a_pdu_un_paquete(),
        test_stream_a_pdu_longitudes_variables(),
        test_round_trip_completo(),
    ]
    total = len(resultados)
    aprobadas = sum(resultados)
    print(f"\n{aprobadas}/{total} casos aprobados")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
