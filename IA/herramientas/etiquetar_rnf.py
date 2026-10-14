"""
etiquetar_rnf.py
=================
Convierte capturas I/Q reales (de `escanear_tvws.sh iq`) en muestras de
dataset etiquetadas (.npz, formato que espera `entrenamiento.TVWSDataset`),
usando el Registro Nacional de Frecuencias (RNF) del MTC como fuente
PRIMARIA de la etiqueta de ocupación -- no el detector de energía. El RNF
es un hecho regulatorio (¿está autorizada una estación en este canal en
esta localidad?), no depende de que la antena/ganancia estén calibradas;
el detector de energía (salida de `analizar_barrido.py`) es sólo un
cruce de QA opcional que señala desacuerdos, nunca los resuelve en
silencio (ver memoria de proyecto "referencia_canales_tv_peru" y
IA/pipeline_dataset_v2.md).

El RNF (https://rnf.mtc.gob.pe/Television) no tiene API -- es un
formulario interactivo por localidad. Este script NO lo consulta por vos:
tenés que consultarlo a mano para tu distrito y volcar el resultado a un
CSV con este formato (usar --generar-plantilla-rnf para crear uno vacío
con los 39 canales listos para completar):

    canal,estado
    14,disponible
    15,autorizada vigente
    16,autorizada vigente
    ...

Valores de 'estado' reconocidos (case-insensitive, con o sin tildes):
    autorizada vigente / autorizada  -> ocupado (1)
    disponible                       -> libre (0)
    reservada / en tramite / impugnada -> zona gris (-1, se enmascara)
Canal ausente del CSV: se trata como desconocido (-1) por defecto -- NO se
asume "disponible" sólo porque el RNF no lo liste, salvo que se pase
--asumir-disponible-si-ausente explícitamente.

Entrada de capturas: un directorio con archivos .iq producidos por
`escanear_tvws.sh iq` (nombre `iq_<freq_hz>_<timestamp>.iq`, el canal se
infiere de la frecuencia). Para capturas con otro origen/nombre, pasar
--manifiesto con columnas: archivo,canal[,localidad,sesion].

Salida: un .npz por captura válida en --salida, con psd (512,), etiquetas
(9,) (un solo índice válido, el resto -1) y posicion (0-4, índice en
POSICIONES_BARRIDO) -- exactamente el formato que TVWSDataset ya sabe leer
(sin margen_db, igual que el dataset real v1 legacy: no hay forma
calibrada todavía de derivar un margen en dB confiable de esta antena
genérica, así que no se inventa esa etiqueta).

Esto NO arma train/val/test ni hace el split por sesión -- eso es trabajo
de un `construir_dataset.py` todavía no implementado (ver
pipeline_dataset_v2.md). Este script sólo etiqueta capturas individuales.
"""

import argparse
import csv
import os
import re
import sys
import unicodedata

import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from nucleo import POSICIONES_BARRIDO, N_CANALES_MAX, PSD_LENGTH, iq_a_psd_normalizado  # noqa: E402

CANAL_MIN = 14
CANAL_MAX = 52

PATRON_NOMBRE_IQ = re.compile(r"iq_(\d+)_")

ESTADOS_OCUPADO = {"autorizada vigente", "autorizada"}
ESTADOS_LIBRE = {"disponible"}
ESTADOS_ZONA_GRIS = {"reservada", "en tramite", "en trámite", "impugnada"}


def _normalizar_texto(s: str) -> str:
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _canal_a_posicion():
    """Mapea canal global (14-52) -> (posicion_idx, indice_local), usando
    la misma POSICIONES_BARRIDO que inferencia.py/entrenamiento.py. En los
    canales de borde que aparecen en dos posiciones adyacentes se queda con
    la primera -- no importa para el entrenamiento, 'posicion' es sólo
    metadata (TVWSDataset no la usa en el forward pass)."""
    mapa = {}
    for idx, pos in enumerate(POSICIONES_BARRIDO):
        for i, canal in enumerate(pos["canales_globales"]):
            mapa.setdefault(canal, (idx, i))
    return mapa


def generar_plantilla_rnf(ruta: str) -> None:
    with open(ruta, "w", newline="") as f:
        escritor = csv.writer(f)
        escritor.writerow(["canal", "estado"])
        for canal in range(CANAL_MIN, CANAL_MAX + 1):
            escritor.writerow([canal, ""])
    print(f"Plantilla RNF creada: {ruta}")
    print("Completar 'estado' por canal consultando https://rnf.mtc.gob.pe/Television")


def cargar_rnf(ruta: str) -> dict:
    etiquetas = {}
    with open(ruta, newline="") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            canal = int(fila["canal"])
            estado = _normalizar_texto(fila.get("estado", ""))
            if estado in ESTADOS_OCUPADO:
                etiquetas[canal] = 1
            elif estado in ESTADOS_LIBRE:
                etiquetas[canal] = 0
            elif estado in ESTADOS_ZONA_GRIS:
                etiquetas[canal] = -1
            elif estado == "":
                continue  # fila sin completar todavía
            else:
                print(f"ADVERTENCIA: estado RNF no reconocido para canal {canal}: '{fila.get('estado','')}' -> se ignora (desconocido)")
    return etiquetas


def cargar_manifiesto(ruta: str) -> dict:
    manifiesto = {}
    with open(ruta, newline="") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            manifiesto[fila["archivo"]] = {
                "canal": int(fila["canal"]) if fila.get("canal") else None,
                "localidad": fila.get("localidad", ""),
                "sesion": fila.get("sesion", ""),
            }
    return manifiesto


def cargar_qa(ruta: str) -> dict:
    """Lee <prefijo>_canales.csv de analizar_barrido.py -> {canal: candidato_ocupado}"""
    qa = {}
    with open(ruta, newline="") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            qa[int(fila["canal"])] = fila["candidato_ocupado"].strip().lower() == "true"
    return qa


def inferir_canal_desde_nombre(nombre_archivo: str) -> int | None:
    m = PATRON_NOMBRE_IQ.search(nombre_archivo)
    if not m:
        return None
    freq_hz = int(m.group(1))
    if (freq_hz - 470_000_000 - 3_000_000) % 6_000_000 != 0:
        return None
    canal = 14 + (freq_hz - 470_000_000 - 3_000_000) // 6_000_000
    if CANAL_MIN <= canal <= CANAL_MAX:
        return canal
    return None


def leer_iq_uint8(ruta: str) -> np.ndarray:
    crudo = np.fromfile(ruta, dtype=np.uint8)
    if len(crudo) % 2 != 0:
        crudo = crudo[:-1]
    crudo = crudo.reshape(-1, 2).astype(np.float32)
    i = (crudo[:, 0] - 127.5) / 127.5
    q = (crudo[:, 1] - 127.5) / 127.5
    return i + 1j * q


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--capturas", help="Directorio con archivos .iq a etiquetar")
    parser.add_argument("--rnf", help="CSV con el export manual del RNF (canal,estado)")
    parser.add_argument("--manifiesto", help="CSV opcional archivo,canal[,localidad,sesion] para capturas con nombre no estándar")
    parser.add_argument("--qa", help="CSV opcional <prefijo>_canales.csv de analizar_barrido.py, para cruce de QA")
    parser.add_argument("--salida", default="./dataset_real/etiquetado", help="Directorio de salida de los .npz")
    parser.add_argument("--asumir-disponible-si-ausente", action="store_true",
                         help="Si un canal no aparece en el RNF, etiquetarlo libre (0) en vez de desconocido (-1). Desactivado por defecto -- ver docstring.")
    parser.add_argument("--incluir-zona-gris", action="store_true",
                         help="Igual escribir el .npz para capturas en zona gris/sin señal RNF (queda totalmente enmascarado, sin señal de entrenamiento -- sólo para inventario/auditoría)")
    parser.add_argument("--generar-plantilla-rnf", metavar="RUTA",
                         help="No etiqueta nada: crea una plantilla RNF vacía (canal,estado) en RUTA y termina")
    args = parser.parse_args()

    if args.generar_plantilla_rnf:
        generar_plantilla_rnf(args.generar_plantilla_rnf)
        return

    if not args.capturas or not args.rnf:
        parser.error("--capturas y --rnf son obligatorios (o usar --generar-plantilla-rnf)")

    etiquetas_rnf = cargar_rnf(args.rnf)
    manifiesto = cargar_manifiesto(args.manifiesto) if args.manifiesto else {}
    qa = cargar_qa(args.qa) if args.qa else {}
    canal_a_posicion = _canal_a_posicion()

    os.makedirs(args.salida, exist_ok=True)

    archivos_iq = sorted(f for f in os.listdir(args.capturas) if f.endswith(".iq"))
    if not archivos_iq:
        print(f"No hay archivos .iq en {args.capturas}")
        return

    n_escritos = n_omitidos_sin_canal = n_omitidos_sin_etiqueta = n_zona_gris = 0

    for nombre in archivos_iq:
        ruta = os.path.join(args.capturas, nombre)

        canal = None
        if nombre in manifiesto and manifiesto[nombre]["canal"] is not None:
            canal = manifiesto[nombre]["canal"]
        else:
            canal = inferir_canal_desde_nombre(nombre)

        if canal is None:
            print(f"OMITIDO (no se pudo determinar el canal): {nombre}")
            n_omitidos_sin_canal += 1
            continue

        if canal in etiquetas_rnf:
            label = etiquetas_rnf[canal]
        elif args.asumir_disponible_si_ausente:
            label = 0
        else:
            label = -1

        if label == -1:
            n_zona_gris += 1
            if not args.incluir_zona_gris:
                print(f"OMITIDO (canal {canal}: zona gris / sin dato RNF): {nombre}")
                n_omitidos_sin_etiqueta += 1
                continue
            print(f"AVISO (canal {canal}: zona gris / sin dato RNF, se incluye sin señal de entrenamiento por --incluir-zona-gris): {nombre}")

        if canal in qa:
            candidato_ocupado = qa[canal]
            if label == 1 and not candidato_ocupado:
                print(f"QA: canal {canal} autorizado por RNF pero SIN energía detectada en el barrido (¿estación apagada?) -- etiqueta RNF se mantiene")
            elif label == 0 and candidato_ocupado:
                print(f"QA: canal {canal} disponible según RNF pero CON energía detectada en el barrido (¿otra fuente/interferencia?) -- etiqueta RNF se mantiene")

        posicion_idx, indice_local = canal_a_posicion[canal]
        etiquetas = np.full(N_CANALES_MAX, -1, dtype=np.float32)
        etiquetas[indice_local] = float(label)

        iq = leer_iq_uint8(ruta)
        psd = iq_a_psd_normalizado(iq, n_fft=PSD_LENGTH)

        nombre_salida = f"muestra_real_c{canal:02d}_{n_escritos:04d}.npz"
        np.savez(
            os.path.join(args.salida, nombre_salida),
            psd=psd.astype(np.float32),
            etiquetas=etiquetas,
            posicion=np.array(posicion_idx, dtype=np.int64),
        )
        n_escritos += 1

    print(f"\n{n_escritos} muestras escritas en {args.salida}")
    print(f"{n_omitidos_sin_canal} omitidas por no poder determinar el canal")
    print(f"{n_omitidos_sin_etiqueta} omitidas por zona gris / sin dato RNF ({n_zona_gris} detectadas en total)")


if __name__ == "__main__":
    main()
