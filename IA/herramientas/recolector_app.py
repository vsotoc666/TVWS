"""
recolector_app.py
==================
Interfaz (Streamlit) para recolectar el dataset real de sensado TVWS en
múltiples zonas y sesiones de horario, pensada para repetirse sesión tras
sesión en campo sin tener que recordar comandos de escanear_tvws.sh /
etiquetar_rnf.py cada vez.

No reimplementa el acceso al hardware: envuelve escanear_tvws.sh (mismos
parámetros ya justificados -- rango de banda, bin, ganancia, recorte de
bordes) vía subprocess, y reutiliza directamente las funciones de
analizar_barrido.py, etiquetar_rnf.py, rnf_web.py y nucleo.py -- un solo
lugar dueño de cada pieza de lógica, nada duplicado en un segundo idioma.

Ejecutar con:
    streamlit run IA/herramientas/recolector_app.py

Requiere streamlit/pandas/requests además de lo ya listado en
IA/requirements.txt -- ver IA/herramientas/requirements.txt.
"""

import datetime
import glob
import json
import os
import subprocess
import sys
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

HERRAMIENTAS_DIR = os.path.dirname(os.path.abspath(__file__))
IA_DIR = os.path.dirname(HERRAMIENTAS_DIR)
sys.path.insert(0, HERRAMIENTAS_DIR)
sys.path.insert(0, IA_DIR)

import rnf_web  # noqa: E402
from analizar_barrido import construir_tabla_canales, leer_rtl_power_csv  # noqa: E402
from etiquetar_rnf import _canal_a_posicion, cargar_rnf, leer_iq_uint8  # noqa: E402
from nucleo import N_CANALES_MAX, PSD_LENGTH, iq_a_psd_normalizado  # noqa: E402

DATASET_REAL_DIR = os.path.join(IA_DIR, "dataset_real")
CAPTURAS_DIR = os.environ.get("TVWS_CAPTURAS_DIR", os.path.expanduser("~/tvws_capturas"))
SCRIPT_ESCANEAR = os.path.join(HERRAMIENTAS_DIR, "escanear_tvws.sh")
CANAL_MIN, CANAL_MAX = 14, 52

SESIONES_HORARIO = ["mañana", "mediodía", "prime_time", "noche"]
# Objetivos mínimos de calidad de pipeline_dataset_v2.md -- se usan sólo
# para la barra de progreso del inventario, no bloquean nada.
META_LOCALIDADES = 2
META_SESIONES_HORARIO = 3
META_MUESTRAS = 30_000


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = texto.strip().lower().replace(" ", "_")
    return "".join(c for c in texto if c.isalnum() or c == "_")


# ─────────────────────────────────────────────────────────────────────────────
# Hardware
# ─────────────────────────────────────────────────────────────────────────────

def dispositivo_presente() -> bool:
    try:
        salida = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5).stdout
        return "0bda:2838" in salida
    except Exception:
        return False


def ejecutar_rtl_test(timeout: float = 8.0) -> str:
    try:
        r = subprocess.run(["rtl_test", "-t"], capture_output=True, text=True, timeout=timeout)
        return (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return "(rtl_test no terminó dentro del timeout -- normal, se lo corta a propósito)"
    except FileNotFoundError:
        return "rtl_test no está instalado (paquete rtl-sdr)."


def ejecutar_scan(gain: float, integ: int, crop: int, out_prefix: str) -> None:
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    r = subprocess.run(
        ["bash", SCRIPT_ESCANEAR, "scan", "-g", str(gain), "-i", str(integ),
         "-c", f"{crop}%", "-o", out_prefix, "-A"],
        capture_output=True, text=True, timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(f"escanear_tvws.sh scan falló:\n{r.stdout}\n{r.stderr}")


def ejecutar_captura_iq(canal: int, gain: float, duracion: float, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    r = subprocess.run(
        ["bash", SCRIPT_ESCANEAR, "iq", "-c", str(canal), "-g", str(gain),
         "-d", str(duracion), "-o", out_path],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"escanear_tvws.sh iq (canal {canal}) falló:\n{r.stdout}\n{r.stderr}")


# ─────────────────────────────────────────────────────────────────────────────
# RNF
# ─────────────────────────────────────────────────────────────────────────────

def rnf_csvs_existentes() -> list:
    return sorted(glob.glob(os.path.join(DATASET_REAL_DIR, "rnf_*.csv")))


# ─────────────────────────────────────────────────────────────────────────────
# Inventario
# ─────────────────────────────────────────────────────────────────────────────

def listar_sesiones() -> pd.DataFrame:
    filas = []
    for carpeta in sorted(glob.glob(os.path.join(DATASET_REAL_DIR, "etiquetado_*"))):
        meta_path = os.path.join(carpeta, "_sesion.json")
        npz_files = glob.glob(os.path.join(carpeta, "*.npz"))
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        else:
            meta = {"zona": os.path.basename(carpeta), "sesion_horario": "?", "fecha": "?"}
        ocupados = libres = 0
        for npz_path in npz_files:
            try:
                et = np.load(npz_path)["etiquetas"]
                v = et[et >= 0]
                if len(v) == 1:
                    ocupados += int(v[0] == 1)
                    libres += int(v[0] == 0)
            except Exception:
                continue
        filas.append({
            "carpeta": os.path.basename(carpeta),
            "zona": meta.get("zona", "?"),
            "distrito": meta.get("distrito", "?"),
            "sesion_horario": meta.get("sesion_horario", "?"),
            "fecha": meta.get("fecha", "?"),
            "ganancia_db": meta.get("ganancia_db", "?"),
            "lna": meta.get("lna", "?"),
            "n_muestras": len(npz_files),
            "ocupados": ocupados,
            "libres": libres,
        })
    return pd.DataFrame(filas)


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Recolector TVWS", layout="wide")
st.title("Recolector de dataset real TVWS")
st.caption(
    "Envuelve escanear_tvws.sh / etiquetar_rnf.py / rnf_web.py en una interfaz de campo. "
    "No reemplaza esas herramientas, las orquesta."
)

with st.sidebar:
    st.header("Sesión actual")

    distritos = st.session_state.setdefault("distritos_lima", rnf_web.obtener_distritos_lima())
    nombres_a_codigo = {v: k for k, v in distritos.items()}
    nombre_distrito = st.selectbox(
        "Distrito (Lima provincia)", sorted(nombres_a_codigo.keys()),
        index=sorted(nombres_a_codigo.keys()).index("LOS OLIVOS") if "LOS OLIVOS" in nombres_a_codigo else 0,
    )
    codigo_distrito = nombres_a_codigo[nombre_distrito]

    zona_label = st.text_input("Etiqueta de zona (opcional, ej. 'Parque Central')", "")
    sesion_horario = st.selectbox("Sesión de horario", SESIONES_HORARIO)

    lna_conectado = st.checkbox("LNA conectado", value=True)
    gain_default = 20.7 if lna_conectado else 40.0
    gain = st.number_input(
        "Ganancia del tuner (dB)", min_value=0.0, max_value=49.6,
        value=gain_default, step=0.1,
        help="20.7dB validado sin clipping con LaNA conectado; 40dB sin LNA (ver CLAUDE.md).",
    )

    antena_exterior = st.checkbox(
        "Confirmo que la antena está en EXTERIOR ahora mismo", value=False,
        help="pipeline_dataset_v2.md §3.2: nunca capturar en interiores, las reflexiones contaminan el espectro.",
    )

    st.divider()
    presente = dispositivo_presente()
    st.write(("🟢" if presente else "🔴") + f" Dispositivo RTL-SDR {'detectado' if presente else 'NO detectado'}")

distrito_slug = slugify(nombre_distrito)
zona_slug = slugify(zona_label) if zona_label else distrito_slug
fecha_hoy = datetime.date.today().isoformat()
sesion_slug = f"{zona_slug}_{fecha_hoy}_{slugify(sesion_horario)}"

tab_espectro, tab_rnf, tab_captura, tab_inventario, tab_hw = st.tabs(
    ["Espectro", "RNF", "Captura + etiquetado", "Inventario", "Hardware"]
)

# ── Tab: Espectro ───────────────────────────────────────────────────────────
with tab_espectro:
    st.subheader("Distribución de energía en toda la banda (470-704 MHz)")
    st.caption(
        "Barrido rtl_power de los 39 canales. Si los picos se ven achatados en vez de "
        "redondeados con roll-off, la ganancia es demasiado alta -- bajala."
    )
    if st.button("Ejecutar barrido ahora", disabled=not presente):
        out_prefix = os.path.join(CAPTURAS_DIR, f"{sesion_slug}_scan")
        try:
            with st.spinner("Barriendo 470-704MHz..."):
                ejecutar_scan(gain, integ=12, crop=20, out_prefix=out_prefix)
                frecuencias, potencia_db = leer_rtl_power_csv(out_prefix + ".csv")
                tabla, piso_ruido = construir_tabla_canales(frecuencias, potencia_db, umbral_db=7.0)
            st.session_state["ultimo_barrido"] = {"tabla": tabla, "piso_ruido": piso_ruido}
            df = pd.DataFrame(tabla).set_index("canal")
            st.line_chart(pd.DataFrame({"potencia_db": potencia_db}, index=frecuencias / 1e6))
            st.dataframe(df, width="stretch")
            st.success(f"{sum(f['candidato_ocupado'] for f in tabla)}/{len(tabla)} canales candidato-ocupado "
                       f"(piso de ruido: {piso_ruido:.2f} dB)")
        except Exception as e:
            st.error(str(e))
    elif "ultimo_barrido" in st.session_state:
        st.caption("(mostrando el último barrido de esta sesión de la app)")
        df = pd.DataFrame(st.session_state["ultimo_barrido"]["tabla"]).set_index("canal")
        st.dataframe(df, width="stretch")

# ── Tab: RNF ─────────────────────────────────────────────────────────────────
with tab_rnf:
    st.subheader(f"RNF para Lima / Lima / {nombre_distrito}")

    existentes = [os.path.basename(p) for p in rnf_csvs_existentes()]
    coincide = [n for n in existentes if distrito_slug in n]
    if coincide:
        st.info(f"Ya existe un CSV de RNF para este distrito: {', '.join(coincide)}")

    if st.button("Consultar RNF en vivo (rnf.mtc.gob.pe)"):
        try:
            with st.spinner("Consultando el RNF..."):
                filas = rnf_web.consultar_canales(codigo_distrito)
            st.session_state["rnf_filas"] = filas
            df = pd.DataFrame(filas)
            ocupados = (df["estado_raw"] == "AUTORIZADO").sum()
            st.success(f"{len(df)} canales recibidos, {ocupados} autorizados")
            st.dataframe(df, width="stretch")
        except Exception as e:
            st.error(f"No se pudo consultar el RNF: {e}. Se puede seguir con un CSV manual (ver IA/herramientas/etiquetar_rnf.py --generar-plantilla-rnf).")

    if "rnf_filas" in st.session_state:
        ruta_guardado = os.path.join(DATASET_REAL_DIR, f"rnf_{distrito_slug}_{fecha_hoy}.csv")
        if st.button(f"Guardar como {os.path.basename(ruta_guardado)}"):
            rnf_web.guardar_csv_rnf(st.session_state["rnf_filas"], ruta_guardado)
            st.success(f"Guardado: {ruta_guardado}")

    st.divider()
    st.caption("CSV a usar para el etiquetado de esta sesión:")
    todos_csv = rnf_csvs_existentes()
    if todos_csv:
        rnf_elegido = st.selectbox("Archivo RNF", todos_csv, format_func=os.path.basename)
        st.session_state["rnf_csv_activo"] = rnf_elegido
    else:
        st.warning("No hay ningún CSV de RNF guardado todavía en IA/dataset_real/.")

# ── Tab: Captura + etiquetado ───────────────────────────────────────────────
with tab_captura:
    st.subheader("Captura de los 39 canales (14-52) y etiquetado contra el RNF")

    rnf_activo = st.session_state.get("rnf_csv_activo")
    canales_a_capturar = st.multiselect(
        "Canales a capturar", list(range(CANAL_MIN, CANAL_MAX + 1)),
        default=list(range(CANAL_MIN, CANAL_MAX + 1)),
    )

    bloqueado = not (presente and antena_exterior and rnf_activo)
    if not presente:
        st.error("Dispositivo no detectado.")
    if not antena_exterior:
        st.error("Falta confirmar que la antena está en exterior (checkbox en la barra lateral).")
    if not rnf_activo:
        st.error("Falta elegir/guardar un CSV de RNF en la pestaña RNF.")

    if st.button(f"Capturar {len(canales_a_capturar)} canales y etiquetar", disabled=bloqueado):
        etiquetas_rnf = cargar_rnf(rnf_activo)
        canal_a_posicion = _canal_a_posicion()

        iq_dir = os.path.join(CAPTURAS_DIR, f"{sesion_slug}_iq")
        salida_dir = os.path.join(DATASET_REAL_DIR, f"etiquetado_{sesion_slug}")
        os.makedirs(salida_dir, exist_ok=True)

        barrido_qa = {f["canal"]: f["candidato_ocupado"] for f in st.session_state.get("ultimo_barrido", {}).get("tabla", [])}

        progreso = st.progress(0.0)
        estado_txt = st.empty()
        avisos = []
        n_escritos = n_gris = 0

        for i, canal in enumerate(canales_a_capturar):
            estado_txt.write(f"Canal {canal} ({i+1}/{len(canales_a_capturar)})...")
            iq_path = os.path.join(iq_dir, f"iq_ch{canal}.iq")
            try:
                ejecutar_captura_iq(canal, gain, duracion=1.0, out_path=iq_path)
            except Exception as e:
                avisos.append(f"Canal {canal}: fallo de captura -- {e}")
                progreso.progress((i + 1) / len(canales_a_capturar))
                continue

            label = etiquetas_rnf.get(canal, -1)
            if label == -1:
                n_gris += 1
                avisos.append(f"Canal {canal}: zona gris / sin dato RNF -- omitido")
                progreso.progress((i + 1) / len(canales_a_capturar))
                continue

            if canal in barrido_qa:
                ocupado_detectado = barrido_qa[canal]
                if label == 1 and not ocupado_detectado:
                    avisos.append(f"QA canal {canal}: autorizado por RNF pero sin energía en el barrido (¿estación apagada?)")
                elif label == 0 and ocupado_detectado:
                    avisos.append(f"QA canal {canal}: disponible por RNF pero con energía detectada (¿interferencia?)")

            posicion_idx, indice_local = canal_a_posicion[canal]
            etiquetas = np.full(N_CANALES_MAX, -1, dtype=np.float32)
            etiquetas[indice_local] = float(label)

            iq = leer_iq_uint8(iq_path)
            psd = iq_a_psd_normalizado(iq, n_fft=PSD_LENGTH)

            nombre_salida = f"muestra_real_c{canal:02d}_{n_escritos:04d}.npz"
            np.savez(
                os.path.join(salida_dir, nombre_salida),
                psd=psd.astype(np.float32), etiquetas=etiquetas,
                posicion=np.array(posicion_idx, dtype=np.int64),
            )
            n_escritos += 1
            progreso.progress((i + 1) / len(canales_a_capturar))

        with open(os.path.join(salida_dir, "_sesion.json"), "w") as f:
            json.dump({
                "zona": zona_label or nombre_distrito,
                "distrito": nombre_distrito,
                "sesion_horario": sesion_horario,
                "fecha": fecha_hoy,
                "fecha_hora_iso": datetime.datetime.now().isoformat(),
                "ganancia_db": gain,
                "lna": lna_conectado,
                "rnf_csv": os.path.basename(rnf_activo),
                "n_muestras": n_escritos,
                "n_zona_gris_omitidas": n_gris,
            }, f, indent=2, ensure_ascii=False)

        estado_txt.empty()
        st.success(f"{n_escritos} muestras escritas en {salida_dir}")
        if avisos:
            with st.expander(f"{len(avisos)} avisos"):
                for a in avisos:
                    st.write("- " + a)

# ── Tab: Inventario ──────────────────────────────────────────────────────────
with tab_inventario:
    st.subheader("Inventario del dataset real")
    df = listar_sesiones()
    if df.empty:
        st.info("Todavía no hay ninguna sesión etiquetada en IA/dataset_real/.")
    else:
        total = int(df["n_muestras"].sum())
        n_localidades = df["distrito"].nunique()
        n_sesiones_horario = df["sesion_horario"].nunique()

        c1, c2, c3 = st.columns(3)
        c1.metric("Muestras totales", total, help=f"meta pipeline_dataset_v2.md: {META_MUESTRAS}")
        c2.metric("Localidades distintas", n_localidades, help=f"meta: {META_LOCALIDADES}")
        c3.metric("Sesiones de horario distintas", n_sesiones_horario, help=f"meta: {META_SESIONES_HORARIO}")

        st.progress(min(1.0, total / META_MUESTRAS), text=f"Muestras: {total}/{META_MUESTRAS}")
        st.progress(min(1.0, n_localidades / META_LOCALIDADES), text=f"Localidades: {n_localidades}/{META_LOCALIDADES}")
        st.progress(min(1.0, n_sesiones_horario / META_SESIONES_HORARIO), text=f"Sesiones horario: {n_sesiones_horario}/{META_SESIONES_HORARIO}")

        st.dataframe(df, width="stretch")
        st.bar_chart(df.groupby("distrito")["n_muestras"].sum())
        st.bar_chart(df.groupby("sesion_horario")["n_muestras"].sum())

# ── Tab: Hardware ────────────────────────────────────────────────────────────
with tab_hw:
    st.subheader("Estado del hardware")
    st.write(("🟢 Detectado" if presente else "🔴 No detectado") + " (lsusb 0bda:2838)")
    if st.button("Correr rtl_test -t (unos segundos)"):
        with st.spinner("rtl_test..."):
            salida = ejecutar_rtl_test()
        st.code(salida)
    st.caption(
        "El mensaje '[R82XX] PLL not locked!' es cosmético en este equipo (verificado "
        "contra captura real), no indica una falla. Ver CLAUDE.md para el detalle."
    )
