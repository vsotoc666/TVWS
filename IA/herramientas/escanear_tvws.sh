#!/usr/bin/env bash
# escanear_tvws.sh
# ================
# Herramienta reutilizable de captura/barrido para el NooElec NESDR SMArt v5
# (RTL2832U + R820T/R820T2) sobre la banda TVWS del proyecto (canales 14-52,
# 470-704 MHz, ver CLAUDE.md). Dos subcomandos:
#
#   scan  -> barrido ancho con rtl_power (caracterización de ocupación en
#            toda la banda, lo que se usa para contrastar contra el RNF).
#   iq    -> captura de I/Q crudo con rtl_sdr en una frecuencia puntual
#            (sanity-check de un canal o insumo para dataset real futuro).
#
# Justificación de los parámetros por defecto (no son arbitrarios):
#
# - Rango de frecuencia (scan): 470M:704M. Es exactamente la banda de los
#   39 canales 14-52 que modela el proyecto (ver SpectralOccupancyMap en
#   inferencia.py) — ni más ni menos, para que el barrido sea comparable
#   canal a canal contra el RNF.
# - Ancho de bin: 50k. ISDB-Tb (estándar de TDT en Perú) es OFDM con
#   13 segmentos de ~430 kHz cada uno y PSD aproximadamente plana dentro
#   del canal de 6 MHz, con flancos abruptos en los bordes. 50 kHz resuelve
#   bien esa forma (flat-top con roll-off) sin disparar el tiempo de barrido.
# - Recorte de bordes (-c 20%): rtl_power construye el barrido saltando de
#   frecuencia en frecuencia (~2.7-2.8 MHz por salto aquí); cada salto tiene
#   caída de ganancia en sus bordes por la respuesta del filtro del tuner.
#   Sin recortar, esto se ve como un diente de sierra periódico con el mismo
#   período que el ancho de salto (confirmado empíricamente en este equipo).
#   20% de recorte lo elimina sin perder resolución útil.
# - Ganancia manual -g 40 (el R820T/R820T2 de este dongle sólo acepta los
#   29 valores discretos de su tabla; rtl_power redondea al más cercano,
#   40.2 dB). Ganancia manual fija (no AGC) a propósito: para que la
#   potencia reportada sea comparable entre barridos/sesiones -- el AGC
#   cambiaría la ganancia en el tiempo y rompería esa comparabilidad, que
#   es lo que se necesita para futuro etiquetado por energía (QA cruzado
#   contra el RNF, ver IA/pipeline_dataset_v2.md). 40 dB es una ganancia
#   media-alta: deja margen sobre el piso de ruido sin acercarse a la
#   compresión del front-end si hay una estación fuerte cerca de la antena.
# - Tiempo de integración -i 15: suficiente promediado para que el piso de
#   ruido se estabilice sin alargar demasiado el barrido de banda completa.
# - Antena: con los 27 cm de la antena conectada, la resonancia aproximada
#   (media onda a ~580 MHz, centro de la banda TVWS, es ~26 cm) cae cerca
#   de lo óptimo para esta banda -- no se requiere amplificación externa
#   para el sanity-check, aunque sigue siendo una antena genérica no
#   calibrada (no usar estos niveles de potencia como medida absoluta).
#
# NOTA: el R820T de este dongle reporta "[R82XX] PLL not locked!" en cada
# sintonía durante el self-test de rtl_test. Verificado en esta sesión que
# es cosmético: rtl_sdr/rtl_power sí entregan datos reales y estructurados
# (espectro con forma, no ruido degenerado). No tratar esa línea como error
# fatal, pero si un día deja de recibir señal real, es el primer sospechoso.
#
# NOTA: 2.4 MSPS (el máximo estable documentado de este dongle) es menos
# que los 6 MHz de un canal ISDB-Tb -- una captura IQ puntual (subcomando
# `iq`) nunca ve el canal completo, sólo ~40% centrado en él. Por eso el
# barrido de banda completa (`scan`, que sintoniza salto a salto) es la
# forma correcta de caracterizar la banda, y `iq` es sólo para sanity-check
# puntual o para alimentar el pipeline de dataset real (que ya asume esta
# limitación, ver pipeline_dataset_v2.md).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
# Directorio para capturas (no versionado -- ver .gitignore). No usar /tmp:
# este script se ejecuta a mano entre sesiones y /tmp puede limpiarse en
# cualquier reinicio.
DIR_CAPTURAS="${TVWS_CAPTURAS_DIR:-$HOME/tvws_capturas}"

# Banda TVWS del proyecto: canales 14-52 (ver CLAUDE.md / inferencia.py)
DEFAULT_FREQ_RANGE="470M:704M"
DEFAULT_BIN_WIDTH="50k"
DEFAULT_GAIN="40"
DEFAULT_INTEGRACION="15"
DEFAULT_CROP="20%"
DEFAULT_SAMPLE_RATE="2400000"   # 2.4 MSPS, máximo estable documentado NESDR SMArt v5
DEFAULT_DURACION_S="1"          # 1 s = 2,400,000 muestras, igual a N_MUESTRAS del pipeline real

uso() {
    cat <<EOF
Uso:
  $(basename "$0") scan [opciones]     Barrido ancho (rtl_power) de la banda TVWS
  $(basename "$0") iq [opciones]       Captura I/Q puntual (rtl_sdr) en una frecuencia/canal

Opciones de 'scan':
  -f RANGO     Rango de frecuencia inicio:fin (default: ${DEFAULT_FREQ_RANGE})
  -b ANCHO     Ancho de bin (default: ${DEFAULT_BIN_WIDTH})
  -g GANANCIA  Ganancia manual en dB, tabla R820T (default: ${DEFAULT_GAIN})
  -i SEGUNDOS  Tiempo de integración por barrido (default: ${DEFAULT_INTEGRACION})
  -c RECORTE   Recorte de bordes de cada salto (default: ${DEFAULT_CROP})
  -o PREFIJO   Prefijo de archivos de salida (default: timestamp en scratchpad)
  -n N         Repetir el barrido N veces en lugar de una sola pasada (continuo)
  -A           No invocar automáticamente el analizador Python al terminar

Opciones de 'iq':
  -c CANAL     Canal del proyecto (14-52) -> calcula el centro automáticamente
  -F FREQ_HZ   Frecuencia central exacta en Hz (alternativa a -c)
  -s TASA      Sample rate en Hz (default: ${DEFAULT_SAMPLE_RATE})
  -d SEGUNDOS  Duración de la captura en segundos (default: ${DEFAULT_DURACION_S})
  -g GANANCIA  Ganancia manual en dB (default: ${DEFAULT_GAIN})
  -o ARCHIVO   Archivo de salida .iq (default: timestamp en scratchpad)
EOF
}

verificar_dispositivo() {
    if ! lsusb | grep -qi "0bda:2838"; then
        echo "ADVERTENCIA: no se detecta el RTL2838 (0bda:2838) por USB." >&2
        echo "Verificar que el NESDR SMArt v5 esté conectado." >&2
        return 1
    fi
    return 0
}

canal_a_frecuencia() {
    # Canal del proyecto (14-52) -> frecuencia central en Hz
    # centro = 470e6 + (n-14)*6e6 + 3e6
    local canal="$1"
    if (( canal < 14 || canal > 52 )); then
        echo "Canal fuera de rango (14-52): $canal" >&2
        exit 1
    fi
    echo $(( 470000000 + (canal - 14) * 6000000 + 3000000 ))
}

cmd_scan() {
    local freq="$DEFAULT_FREQ_RANGE"
    local bin="$DEFAULT_BIN_WIDTH"
    local gain="$DEFAULT_GAIN"
    local integ="$DEFAULT_INTEGRACION"
    local crop="$DEFAULT_CROP"
    local prefijo=""
    local repeticiones="1"
    local auto_analizar="1"

    while getopts "f:b:g:i:c:o:n:Ah" opt; do
        case "$opt" in
            f) freq="$OPTARG" ;;
            b) bin="$OPTARG" ;;
            g) gain="$OPTARG" ;;
            i) integ="$OPTARG" ;;
            c) crop="$OPTARG" ;;
            o) prefijo="$OPTARG" ;;
            n) repeticiones="$OPTARG" ;;
            A) auto_analizar="0" ;;
            h) uso; exit 0 ;;
            *) uso; exit 1 ;;
        esac
    done

    verificar_dispositivo || exit 1

    if [[ -z "$prefijo" ]]; then
        local ts
        ts="$(date +%Y%m%d_%H%M%S)"
        prefijo="${DIR_CAPTURAS}/scan_tvws_${ts}"
    fi
    mkdir -p "$(dirname "$prefijo")"

    local flags_1pasada=()
    if [[ "$repeticiones" == "1" ]]; then
        flags_1pasada=(-1)
    fi

    local csv="${prefijo}.csv"
    local rango_completo="${freq}:${bin}"
    echo "Barrido: ${rango_completo}, ganancia=${gain}dB, integracion=${integ}s, recorte=${crop}"
    echo "Salida CSV: ${csv}"

    if ! rtl_power -f "$rango_completo" -g "$gain" -i "$integ" -c "$crop" "${flags_1pasada[@]}" "$csv"; then
        echo "rtl_power falló. Si el error es 'usb_claim_interface', cerrar gqrx u otro" >&2
        echo "proceso que tenga el dispositivo abierto e intentar de nuevo." >&2
        exit 1
    fi

    if [[ "$auto_analizar" == "1" ]]; then
        "$PYTHON_BIN" "$SCRIPT_DIR/analizar_barrido.py" "$csv" --salida "${prefijo}"
    fi
}

cmd_iq() {
    local canal=""
    local freq_hz=""
    local tasa="$DEFAULT_SAMPLE_RATE"
    local duracion="$DEFAULT_DURACION_S"
    local gain="$DEFAULT_GAIN"
    local salida=""

    while getopts "c:F:s:d:g:o:h" opt; do
        case "$opt" in
            c) canal="$OPTARG" ;;
            F) freq_hz="$OPTARG" ;;
            s) tasa="$OPTARG" ;;
            d) duracion="$OPTARG" ;;
            g) gain="$OPTARG" ;;
            o) salida="$OPTARG" ;;
            h) uso; exit 0 ;;
            *) uso; exit 1 ;;
        esac
    done

    verificar_dispositivo || exit 1

    if [[ -z "$freq_hz" ]]; then
        if [[ -z "$canal" ]]; then
            echo "Especificar -c CANAL (14-52) o -F FREQ_HZ" >&2
            exit 1
        fi
        freq_hz="$(canal_a_frecuencia "$canal")"
    fi

    local n_muestras
    n_muestras=$(( ${tasa%.*} * ${duracion%.*} ))

    if [[ -z "$salida" ]]; then
        local ts
        ts="$(date +%Y%m%d_%H%M%S)"
        salida="${DIR_CAPTURAS}/iq_${freq_hz}_${ts}.iq"
    fi
    mkdir -p "$(dirname "$salida")"

    echo "Captura I/Q: freq=${freq_hz}Hz, tasa=${tasa}Sps, duracion=${duracion}s (${n_muestras} muestras), ganancia=${gain}dB"
    echo "NOTA: ${tasa}Sps < 6MHz de un canal ISDB-Tb -> esta captura sólo ve ~$(( tasa * 100 / 6000000 ))% del canal, centrado en él."
    echo "Salida: ${salida}"

    rtl_sdr -f "$freq_hz" -s "$tasa" -g "$gain" -n "$n_muestras" "$salida"
}

if [[ $# -lt 1 ]]; then
    uso
    exit 1
fi

subcomando="$1"
shift

case "$subcomando" in
    scan) cmd_scan "$@" ;;
    iq) cmd_iq "$@" ;;
    -h|--help) uso ;;
    *) echo "Subcomando desconocido: $subcomando" >&2; uso; exit 1 ;;
esac
