"""
Calculadora oficial de link budget — Proyecto TVWS (UNI, VRI 2026)

Interfaz interactiva sobre `core.py`. Recalcula EIRP, pérdida de trayecto,
potencia recibida, cascada de ruido, sensibilidad y margen por modulación
para Downlink y Uplink, más el chequeo de autointerferencia full-duplex —
todo editable, para no tener que recalcular a mano en cada documento cuando
cambie una potencia, una antena, un LNA/PA o la modulación.

Ejecutar con:
    streamlit run app.py
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from core import (
    BACKOFF_MAX_DB,
    BACKOFF_MIN_DB,
    MODULACIONES_DEFAULT,
    PARAM_HELP,
    CadenaRX,
    CadenaTX,
    EntornoParams,
    ResultadoEnlace,
    calcular_autointerferencia,
    calcular_enlace,
)

st.set_page_config(page_title="TVWS Link Budget", page_icon="📡", layout="wide")

WIDGET_KEYS: list[str] = []  # se llena en tiempo de ejecución para poder resetear todo


# ─────────────────────────────────────────────────────────────────────────
# Helpers de widgets ligados a los dataclasses de core.py
# ─────────────────────────────────────────────────────────────────────────

def num(container, field_name: str, label: str, default: float, step: float = 0.1, key: str = "", fmt: str = "%.2f") -> float:
    k = key or field_name
    WIDGET_KEYS.append(k)
    return container.number_input(label, value=float(default), step=step, format=fmt, help=PARAM_HELP.get(field_name, ""), key=k)


def boolean(container, field_name: str, label: str, default: bool, key: str = "") -> bool:
    k = key or field_name
    WIDGET_KEYS.append(k)
    return container.checkbox(label, value=default, help=PARAM_HELP.get(field_name, ""), key=k)


def resetear_todo():
    for k in WIDGET_KEYS:
        st.session_state.pop(k, None)
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────
# Sidebar — parámetros de entorno / trayecto (comunes a DL y UL)
# ─────────────────────────────────────────────────────────────────────────

st.sidebar.title("📡 Parámetros de entorno")
st.sidebar.caption("Comunes a Downlink, Uplink y autointerferencia.")

_e = EntornoParams()
freq_mhz = num(st.sidebar, "freq_mhz", "Frecuencia de referencia (MHz)", _e.freq_mhz, step=10.0)
distancia_km = num(st.sidebar, "distancia_km", "Distancia del enlace (km)", _e.distancia_km, step=0.5)
perdida_nlos_db = num(st.sidebar, "perdida_nlos_db", "Pérdida adicional NLOS (dB)", _e.perdida_nlos_db, step=1.0)
perdida_extra_db = num(st.sidebar, "perdida_extra_db", "Otras pérdidas (lluvia/desalineación/polarización) (dB)", _e.perdida_extra_db, step=0.5)
ancho_banda_mhz = num(st.sidebar, "ancho_banda_mhz", "Ancho de canal (MHz)", _e.ancho_banda_mhz, step=1.0)
separacion_mastil_m = num(st.sidebar, "separacion_mastil_m", "Separación antenas TX/RX en mástil (m)", _e.separacion_mastil_m, step=0.1)
margen_disenio_ai_db = num(st.sidebar, "margen_disenio_autointerferencia_db", "Margen de diseño SNR autointerferencia (dB)", _e.margen_disenio_autointerferencia_db, step=1.0)

entorno = EntornoParams(
    freq_mhz=freq_mhz,
    distancia_km=distancia_km,
    perdida_nlos_db=perdida_nlos_db,
    perdida_extra_db=perdida_extra_db,
    ancho_banda_mhz=ancho_banda_mhz,
    separacion_mastil_m=separacion_mastil_m,
    margen_disenio_autointerferencia_db=margen_disenio_ai_db,
)

st.sidebar.divider()
st.sidebar.subheader("Modulación — SNR mínimo requerido")
st.sidebar.caption("BPSK/QPSK reconstruidos desde las sensibilidades documentadas en README §9.1. 16-QAM es una estimación teórica (no documentada).")
modulaciones: dict[str, float] = {}
for mod, snr_default in MODULACIONES_DEFAULT.items():
    modulaciones[mod] = num(st.sidebar, f"snr_{mod}", f"SNR req. {mod} (dB)", snr_default, step=0.5, key=f"snr_{mod}")

st.sidebar.divider()
if st.sidebar.button("↺ Restaurar todos los valores por defecto", width="stretch"):
    resetear_todo()

st.sidebar.caption("Los valores por defecto y su origen (documento + sección, o 'estimado' si el proyecto no lo documenta) están en el `help` de cada campo y en `core.py`.")


# ─────────────────────────────────────────────────────────────────────────
# Título
# ─────────────────────────────────────────────────────────────────────────

st.title("📡 Calculadora de Link Budget — TVWS (UNI, VRI 2026)")
st.caption(
    "Calculadora oficial del proyecto: recalcula el presupuesto de enlace completo (Downlink, Uplink y "
    "autointerferencia full-duplex) ante cualquier cambio de hardware, potencia, antena o modulación. "
    "Todos los valores son editables; los valores por defecto reproducen README.md §9.1 y "
    "claudedocs/requisitos_pa_lna.md al 29/07/2026."
)

tab_dl, tab_ul, tab_ai, tab_resumen, tab_ayuda = st.tabs(
    ["⬇️ Downlink", "⬆️ Uplink", "🔁 Autointerferencia", "📊 Resumen", "ℹ️ Ayuda / fórmulas"]
)


# ─────────────────────────────────────────────────────────────────────────
# Formulario de cadena TX/RX reutilizable
# ─────────────────────────────────────────────────────────────────────────

def formulario_tx(
    container,
    nodo: str,
    key_prefix: str,
    pa_habilitado_default: bool,
    pa_p1db_default: float,
    pa_backoff_default: float = 7.5,
) -> CadenaTX:
    d = CadenaTX(nodo)
    container.markdown(f"**Cadena TX — {nodo}**")
    potencia_sdr = num(container, "potencia_sdr_dbm", "Potencia SDR (dBm)", d.potencia_sdr_dbm, key=f"{key_prefix}_potencia_sdr_dbm")
    perdida_pigtail = num(container, "perdida_pigtail_db", "Pérdida pigtail SDR→PA (dB)", d.perdida_pigtail_db, key=f"{key_prefix}_perdida_pigtail_db")
    pa_on = boolean(container, "pa_habilitado", "PA instalado", pa_habilitado_default, key=f"{key_prefix}_pa_habilitado")
    if pa_on:
        pa_p1db = num(container, "pa_p1db_dbm", "P1dB nominal del PA (dBm)", pa_p1db_default, key=f"{key_prefix}_pa_p1db_dbm", fmt="%.1f")
        pa_backoff = num(container, "pa_backoff_db", "Backoff aplicado (dB)", pa_backoff_default, key=f"{key_prefix}_pa_backoff_db", step=0.5, fmt="%.1f")
    else:
        pa_p1db, pa_backoff = pa_p1db_default, pa_backoff_default
    perdida_cable = num(container, "perdida_cable_db", "Pérdida cable LMR-400 TX (dB)", d.perdida_cable_db, key=f"{key_prefix}_perdida_cable_db")
    perdida_gdt = num(container, "perdida_gdt_db", "Pérdida GDT (dB)", d.perdida_gdt_db, key=f"{key_prefix}_perdida_gdt_db")
    ganancia_antena = num(container, "ganancia_antena_dbi", "Ganancia antena TX (dBi)", d.ganancia_antena_dbi, key=f"{key_prefix}_ant_tx_dbi")
    tx = CadenaTX(
        nombre_nodo=nodo,
        potencia_sdr_dbm=potencia_sdr,
        perdida_pigtail_db=perdida_pigtail,
        pa_habilitado=pa_on,
        pa_p1db_dbm=pa_p1db,
        pa_backoff_db=pa_backoff,
        perdida_cable_db=perdida_cable,
        perdida_gdt_db=perdida_gdt,
        ganancia_antena_dbi=ganancia_antena,
    )
    if pa_on:
        container.caption(
            f"→ Salida promedio del PA: **{tx.potencia_pa_salida_dbm():.2f} dBm** "
            f"(ganancia efectiva implícita: {tx.pa_ganancia_efectiva_db():.1f} dB)"
        )
        estado = tx.backoff_estado()
        rango = f"(rango exigido: {BACKOFF_MIN_DB:.0f}-{BACKOFF_MAX_DB:.0f} dB, requisitos_pa_lna.md §3.1/§3.2 punto 5)"
        if estado == "insuficiente":
            container.error(f"⚠ Backoff: {pa_backoff:.1f} dB — INSUFICIENTE {rango}. Riesgo de compresión de picos OFDM y spectral regrowth hacia canales TV vecinos.", icon="🚨")
        elif estado == "conservador":
            container.info(f"Backoff: {pa_backoff:.1f} dB — más conservador de lo necesario {rango}. Hay margen para sacar más potencia media del PA.", icon="ℹ️")
        else:
            container.success(f"✅ Backoff: {pa_backoff:.1f} dB — dentro del rango de diseño {rango}.", icon="✅")
    return tx


def formulario_rx(container, nodo: str, key_prefix: str) -> CadenaRX:
    d = CadenaRX(nodo)
    container.markdown(f"**Cadena RX — {nodo}**")
    ganancia_antena = num(container, "ganancia_antena_dbi", "Ganancia antena RX (dBi)", d.ganancia_antena_dbi, key=f"{key_prefix}_ant_rx_dbi")
    perdida_antes_lna = num(container, "perdida_antes_lna_db", "Pérdida cable/GDT ANTES del LNA (dB)", d.perdida_antes_lna_db, key=f"{key_prefix}_perdida_antes_lna_db")
    lna_gan = num(container, "lna_ganancia_db", "Ganancia LNA (dB)", d.lna_ganancia_db, key=f"{key_prefix}_lna_ganancia_db")
    lna_nf = num(container, "lna_nf_db", "NF LNA (dB)", d.lna_nf_db, step=0.05, key=f"{key_prefix}_lna_nf_db")
    perdida_cable_post = num(container, "perdida_cable_lna_sdr_db", "Pérdida cable LNA→SDR (dB)", d.perdida_cable_lna_sdr_db, key=f"{key_prefix}_perdida_cable_lna_sdr_db")
    perdida_pigtail_post = num(container, "perdida_pigtail_lna_sdr_db", "Pérdida pigtail final →SDR (dB)", d.perdida_pigtail_lna_sdr_db, key=f"{key_prefix}_perdida_pigtail_lna_sdr_db")
    sdr_nf = num(container, "sdr_nf_nativo_db", "NF nativo SDR (dB)", d.sdr_nf_nativo_db, step=0.1, key=f"{key_prefix}_sdr_nf_nativo_db")
    if perdida_antes_lna > 0:
        container.warning(
            f"⚠ {perdida_antes_lna:.2f} dB de pérdida antes del LNA degrada el NF de sistema notablemente "
            "(con 0 dB se reproduce el ~1.04 dB documentado; con 0.3 dB ya sube a ~1.3 dB). "
            "Ver pestaña Ayuda.",
            icon="⚠️",
        )
    return CadenaRX(
        nombre_nodo=nodo,
        ganancia_antena_dbi=ganancia_antena,
        perdida_antes_lna_db=perdida_antes_lna,
        lna_ganancia_db=lna_gan,
        lna_nf_db=lna_nf,
        perdida_cable_lna_sdr_db=perdida_cable_post,
        perdida_pigtail_lna_sdr_db=perdida_pigtail_post,
        sdr_nf_nativo_db=sdr_nf,
    )


def graficar_cadena(resultado: ResultadoEnlace, titulo: str):
    etapas = resultado.cadena_potencia_tx + resultado.cadena_potencia_rx
    nombres = [e[0] for e in etapas]
    valores = [e[1] for e in etapas]

    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(nombres, valores, marker="o", color="#1f77b4", linewidth=2)
    for x, y in zip(nombres, valores):
        ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)
    for mod, sens in resultado.sensibilidades_dbm.items():
        ax.axhline(sens, linestyle="--", linewidth=1, alpha=0.5, label=f"Sensibilidad {mod} ({sens:.1f} dBm)")
    ax.set_ylabel("Potencia (dBm)")
    ax.set_title(titulo)
    ax.tick_params(axis="x", rotation=30)
    ax.legend(fontsize=7, loc="lower left")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def mostrar_resultados(resultado: ResultadoEnlace, nombre_enlace: str):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("EIRP", f"{resultado.eirp_dbm:.2f} dBm")
    c2.metric("Pérdida de trayecto", f"{resultado.perdida_trayecto_db:.2f} dB")
    c3.metric("PRx en antena", f"{resultado.prx_antena_dbm:.2f} dBm")
    c4.metric("NF de sistema", f"{resultado.nf_sistema_db:.3f} dB")

    filas = []
    for mod in resultado.margenes_db:
        margen = resultado.margenes_db[mod]
        filas.append(
            {
                "Modulación": mod,
                "Sensibilidad (dBm)": round(resultado.sensibilidades_dbm[mod], 2),
                "Margen (dB)": round(margen, 2),
                "Estado": "✅ Cierra" if margen >= 0 else "❌ No cierra",
            }
        )
    df = pd.DataFrame(filas)
    st.dataframe(df, hide_index=True, width="stretch")

    with st.expander("Ver nivel de señal en la entrada del SDR (referencia distinta a PRx en antena)"):
        st.write(
            f"Señal en la entrada del SDR tras LNA y cables: **{resultado.señal_entrada_sdr_dbm:.2f} dBm** "
            "(dato informativo/de rango dinámico; el margen se calcula referenciado en la antena, no aquí — "
            "ambas referencias dan el mismo margen si se usan de forma consistente)."
        )

    graficar_cadena(resultado, f"Cadena de potencia — {nombre_enlace}")


# ─────────────────────────────────────────────────────────────────────────
# Tab Downlink
# ─────────────────────────────────────────────────────────────────────────

with tab_dl:
    st.subheader("Downlink — Gateway (TX) → Cliente (RX)")
    col_tx, col_rx = st.columns(2)
    gw_tx = formulario_tx(col_tx, "Gateway", "dl_tx", pa_habilitado_default=True, pa_p1db_default=32.0)
    cli_rx = formulario_rx(col_rx, "Cliente", "dl_rx")
    st.divider()
    resultado_dl = calcular_enlace(gw_tx, cli_rx, entorno, modulaciones)
    mostrar_resultados(resultado_dl, "Downlink")


# ─────────────────────────────────────────────────────────────────────────
# Tab Uplink
# ─────────────────────────────────────────────────────────────────────────

with tab_ul:
    st.subheader("Uplink — Cliente (TX) → Gateway (RX)")
    col_tx, col_rx = st.columns(2)
    cli_tx = formulario_tx(col_tx, "Cliente", "ul_tx", pa_habilitado_default=True, pa_p1db_default=32.0)
    gw_rx = formulario_rx(col_rx, "Gateway", "ul_rx")
    st.divider()
    resultado_ul = calcular_enlace(cli_tx, gw_rx, entorno, modulaciones)
    mostrar_resultados(resultado_ul, "Uplink")
    if cli_tx.pa_habilitado:
        st.info(
            "El PA del Cliente está habilitado y es el mismo modelo real que el del Gateway (actualizado "
            "28/08/2026, SPECS EQUIPOS/PA.md — 'PA OEM 2W 1-900MHz', P1dB > +32 dBm, clase A) — ya no es un "
            "placeholder, ambos nodos usan el mismo componente comprado.",
            icon="ℹ️",
        )
    else:
        st.warning(
            "PA del Cliente deshabilitado manualmente — esto ya no refleja el estado real del proyecto "
            "(el Cliente tiene PA instalado desde el 30/07/2026). Sin PA, el enlace no cierra en ninguna modulación.",
            icon="⚠️",
        )


# ─────────────────────────────────────────────────────────────────────────
# Tab Autointerferencia
# ─────────────────────────────────────────────────────────────────────────

with tab_ai:
    st.subheader("Autointerferencia full-duplex (TX propio hacia RX propio, mismo nodo)")
    st.caption(
        "Riesgo #1 documentado en claudedocs/riesgos_arquitectura_transmision.md: sin duplexer ni cancelación "
        "activa (SIC), el único aislamiento entre la LPDA TX y la LPDA RX del mismo nodo es la separación física "
        "en el mástil. Esta pestaña usa las cadenas TX ya definidas arriba en Downlink/Uplink."
    )

    override_ai = st.checkbox(
        "Usar aislamiento medido/estimado manualmente en vez de la fórmula de espacio libre",
        value=False,
        help="La fórmula de espacio libre es optimista a distancias tan cortas (campo cercano). "
        "riesgos_arquitectura_transmision.md cita un rango empírico más realista de 30-50 dB.",
    )
    aislamiento_manual = None
    if override_ai:
        aislamiento_manual = st.slider("Aislamiento asumido (dB)", min_value=10.0, max_value=110.0, value=40.0, step=1.0)

    col_gw, col_cli = st.columns(2)
    with col_gw:
        st.markdown("**Gateway**")
        ai_gw = calcular_autointerferencia(gw_tx, resultado_dl.sensibilidades_dbm["BPSK"], entorno, aislamiento_manual)
        st.metric("Aislamiento asumido", f"{ai_gw.aislamiento_db:.2f} dB")
        st.metric("Autointerferencia en RX propio", f"{ai_gw.autointerferencia_dbm:.2f} dBm")
        st.metric("Déficit de aislamiento", f"{ai_gw.deficit_db:.2f} dB", delta="Problema" if ai_gw.deficit_db > 0 else "OK", delta_color="inverse")
    with col_cli:
        st.markdown("**Cliente**")
        ai_cli = calcular_autointerferencia(cli_tx, resultado_ul.sensibilidades_dbm["BPSK"], entorno, aislamiento_manual)
        st.metric("Aislamiento asumido", f"{ai_cli.aislamiento_db:.2f} dB")
        st.metric("Autointerferencia en RX propio", f"{ai_cli.autointerferencia_dbm:.2f} dBm")
        st.metric("Déficit de aislamiento", f"{ai_cli.deficit_db:.2f} dB", delta="Problema" if ai_cli.deficit_db > 0 else "OK", delta_color="inverse")

    if ai_gw.deficit_db > 0 or ai_cli.deficit_db > 0:
        st.error(
            "Déficit de aislamiento positivo = el TX propio satura/desensibiliza el RX propio con el aislamiento "
            "asumido. Esto coincide con el hallazgo de riesgos_arquitectura_transmision.md: la separación física "
            "de antenas sola (30-50 dB reales) no alcanza frente a los 90-110 dB típicamente necesarios en IBFD.",
            icon="🚨",
        )


# ─────────────────────────────────────────────────────────────────────────
# Tab Resumen
# ─────────────────────────────────────────────────────────────────────────

with tab_resumen:
    st.subheader("Resumen comparativo — Downlink vs Uplink")
    filas = []
    for etiqueta, resultado in [("Downlink", resultado_dl), ("Uplink", resultado_ul)]:
        fila = {
            "Enlace": etiqueta,
            "EIRP (dBm)": round(resultado.eirp_dbm, 2),
            "Pérdida trayecto (dB)": round(resultado.perdida_trayecto_db, 2),
            "PRx antena (dBm)": round(resultado.prx_antena_dbm, 2),
            "NF sistema (dB)": round(resultado.nf_sistema_db, 3),
        }
        for mod, margen in resultado.margenes_db.items():
            fila[f"Margen {mod} (dB)"] = round(margen, 2)
        filas.append(fila)
    df_resumen = pd.DataFrame(filas)
    st.dataframe(df_resumen, hide_index=True, width="stretch")

    st.markdown("**Backoff del PA** (rango exigido: 6-9 dB, requisitos_pa_lna.md §3.1/§3.2 punto 5 — reduce la salida promedio del PA, ver pestaña Ayuda)")
    filas_backoff = []
    for etiqueta, tx in [("Gateway (TX Downlink)", gw_tx), ("Cliente (TX Uplink)", cli_tx)]:
        estado = tx.backoff_estado()
        filas_backoff.append(
            {
                "Nodo": etiqueta,
                "PA instalado": "Sí" if tx.pa_habilitado else "No",
                "P1dB (dBm)": round(tx.pa_p1db_dbm, 2) if tx.pa_habilitado else "N/A",
                "Backoff (dB)": round(tx.pa_backoff_db, 2) if tx.pa_habilitado else "N/A",
                "Salida promedio PA (dBm)": round(tx.potencia_pa_salida_dbm(), 2) if tx.pa_habilitado else "N/A",
                "Estado": {"ok": "✅ Dentro de rango", "insuficiente": "🚨 Insuficiente", "conservador": "ℹ️ Conservador", None: "—"}[estado],
            }
        )
    st.dataframe(pd.DataFrame(filas_backoff), hide_index=True, width="stretch")

    csv = df_resumen.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar resumen (CSV)", data=csv, file_name="link_budget_resumen.csv", mime="text/csv")

    md = df_resumen.to_markdown(index=False)
    st.download_button("⬇️ Descargar resumen (tabla Markdown)", data=md, file_name="link_budget_resumen.md", mime="text/markdown")

    st.divider()
    st.caption(
        "⚠ Estos números pueden diferir por ~1-8 dB de las cifras redondeadas en README.md §9.1: esta calculadora "
        "es más granular (incluye pérdidas de cable/conector que el resumen del README omite) y, en particular, "
        "el Downlink del README arrastraba un colchón de margen no trazable a ningún parámetro documentado "
        "(~6-8 dB) desde antes de esta calculadora. Ver pestaña Ayuda."
    )


# ─────────────────────────────────────────────────────────────────────────
# Tab Ayuda
# ─────────────────────────────────────────────────────────────────────────

with tab_ayuda:
    st.subheader("Fórmulas y supuestos")
    st.markdown(
        r"""
**Potencia de salida del PA (si hay PA instalado):**
`Salida_PA_promedio = P1dB_nominal − Backoff` — el backoff limita directamente cuánta potencia promedio es
utilizable (no es solo una verificación posterior).

**EIRP (TX):**
`EIRP = Salida_PA_promedio (o Potencia_SDR − Pérdida_pigtail si no hay PA) − Pérdida_cable − Pérdida_GDT + Ganancia_antena_TX`
(Pérdida_GDT = 0 dB por defecto desde el 28/08/2026 — GDT eliminado del diseño, ver `claudedocs/estructura_fisica_instalacion.md`. El término se conserva por si se reintroduce protección de sobretensión para un despliegue permanente futuro.)

**Pérdida de espacio libre (FSPL, fórmula de Friis):**
`FSPL(dB) = 20·log10(distancia_km) + 20·log10(freq_MHz) + 32.44`

**Pérdida de trayecto total:**
`Pérdida_trayecto = FSPL + Pérdida_NLOS + Otras_pérdidas`

**Potencia recibida en la antena (referencia usada para el margen):**
`PRx = EIRP − Pérdida_trayecto + Ganancia_antena_RX`

**Cascada de ruido (Friis, referida a la antena RX):**
`F_total = F1 + (F2−1)/G1 + (F3−1)/(G1·G2) + ...`
donde cada etapa pasiva (cable/GDT) tiene `NF_dB = Pérdida_dB` y ganancia negativa igual a esa pérdida.

**Sensibilidad del receptor:**
`Sensibilidad(dBm) = −174 + 10·log10(BW_Hz) + NF_sistema + SNR_mínimo_requerido`

**Margen de enlace:**
`Margen = PRx − Sensibilidad` — positivo significa que el enlace cierra con esa modulación.

**Aislamiento antena-antena (mismo mástil, campo cercano — fórmula de espacio libre, optimista):**
`Aislamiento(dB) = 20·log10(4π·distancia_m / λ_m)`, con `λ_m = 300 / freq_MHz`.
        """
    )

    st.divider()
    st.subheader("Por qué el backoff del PA SÍ reduce el EIRP (actualizado 30/07/2026)")
    st.markdown(
        """
OFDM tiene un PAPR (Peak-to-Average Power Ratio) alto: al sumarse muchas subportadoras en fase, la señal
genera picos instantáneos varios dB por encima de la potencia promedio. Si el PA opera cerca de su punto de
compresión (P1dB), esos picos se recortan/distorsionan → intermodulación, *spectral regrowth* hacia los
canales de TV vecinos (riesgo regulatorio, no solo de calidad) y degradación del EVM de la constelación.

`requisitos_pa_lna.md` §3.1/§3.2 (punto 5) exige que ambos PA operen con **6-9 dB de backoff** respecto a su
P1dB. Los PA comerciales se especifican por su **P1dB/Psat nominal** (la potencia de la hoja técnica, p. ej.
"PA de 2W" = su rating de saturación) — no por una potencia media ya reducida. Por eso el modelo es:

```
Potencia de salida PROMEDIO utilizable = P1dB nominal − Backoff
```

Antes (hasta el 29/07/2026) la calculadora trataba la ganancia del PA como un valor libre e independiente, y
el P1dB solo como una verificación posterior — eso permitía, sin darse cuenta, fijar una salida promedio que
en la práctica ningún PA real con ese P1dB podría sostener sin comprimir. Ahora el backoff **limita
directamente** la salida promedio, y por lo tanto el EIRP: subir el backoff (más conservador) baja el EIRP;
bajar el backoff (menos colchón, más riesgo de compresión) lo sube, con el aviso 🚨 si sale de rango.

**Defaults actualizados con la hoja técnica real (28/08/2026, `SPECS EQUIPOS/PA.md` — "PA OEM 2W 1-900MHz",
mismo modelo en ambos nodos):** el datasheet da **P1dB > +32 dBm** y **+33 dBm** como potencia de salida
máxima/Psat — son dos cifras distintas, no la misma. La calculadora usa 32 dBm (el piso documentado de P1dB)
para no sobreestimar. Con 7.5 dB de backoff, la salida promedio real utilizable es **+24.5 dBm** (no +33 ni
+25.5 dBm como se asumía antes de tener el datasheet). El datasheet también da la ganancia real: **30 dB
típica a 500 MHz** (más que los ~27 dB que se asumían genéricamente) y clase **A** (no AB) — mejor linealidad,
menos eficiencia.

⚠ **Entrada máxima tolerada del PA: +3 dBm.** El bladeRF a su ganancia TX máxima entrega ~+5.7 dBm al PA (tras
el pigtail) — por ENCIMA del máximo tolerado. En la instalación real hay que bajar la ganancia TX del bladeRF
por software a un nivel mucho menor (aprox. -5 a -6 dBm de salida del SDR, dado el gain de 30 dB del PA) antes
de conectarlo — no operar el bladeRF a su ganancia máxima con este PA conectado.
        """
    )

    st.divider()
    st.subheader("✅ Resuelto (28/08/2026): posición del LNA respecto al NF de sistema")
    st.markdown(
        """
El NF de sistema documentado (~1.0-1.04 dB, README §9.1) **solo se reproduce si la pérdida de cable antes
del LNA es ~0 dB** — es decir, si el LNA está montado literalmente en el punto de alimentación de la antena,
tal como pide `requisitos_pa_lna.md` §4 punto 7 ("Montaje: cerca de la antena, antes del tramo largo de cable").

Esto ya no es una discrepancia abierta: `claudedocs/estructura_fisica_instalacion.md` §3.2 fija la instalación
física real como

```
LPDA RX → jumper corto → LNA (en el tope del mástil, junto a la antena) →
LMR-400 (tramo largo, longitud no fija) → RG-316 pigtail → bladeRF
```

es decir, el LNA va **antes** del tramo largo de cable — con eso el NF de sistema documentado (~1.04 dB) sí
se reproduce. Si en algún momento se instala distinto a esto, el NF real subiría a ~1.3-1.9 dB — usa el
campo **"Pérdida cable ANTES del LNA"** en Downlink/Uplink para explorar ese escenario.
        """
    )

    st.divider()
    st.subheader("Qué está documentado vs. qué es estimado")
    st.markdown(
        """
- **Documentado con hoja técnica real (`SPECS EQUIPOS/`, actualizado 28/08/2026):** potencia TX máxima del
  bladeRF (+6 dBm), P1dB del PA (>32 dBm) y ganancia típica (30 dB a 500 MHz, clase A), ganancia de antena LPDA
  (5 dBi a 500 MHz, WA5VJB 400-1000MHz), ganancia y NF del LNA Nooelec LaNA (20 dB / 0.9 dB a 1000 MHz), NF
  nativo del AD9361 (<2.5 dB), distancia final del enlace (4 km, decidida 28/08/2026 — antes 6 km/5-6 km, y antes de eso 10-15 km), línea de vista (LOS) confirmada por estudio de sitio
  (04-05/09/2026) — `perdida_nlos_db` en 0.0 dB por defecto, ya no el supuesto NLOS de 15 dB usado antes. La pérdida de
  inserción del GDT ya no aplica — GDT eliminado del diseño el 28/08/2026 (`perdida_gdt_db` en 0.0 dB por
  defecto).
- **Estimado por esta calculadora (no documentado tramo a tramo en el proyecto):** pérdidas individuales de
  pigtail RG-316 y de los tramos de LMR-400 (se fijaron para que la suma reproduzca el EIRP/NF documentados),
  el SNR mínimo requerido por modulación (reconstruido desde las sensibilidades documentadas para BPSK/QPSK;
  estimado por teoría para 16-QAM), y el punto exacto de la cadena donde va montado el LNA.

Cuando cambie cualquier dato "documentado" (nueva hoja técnica, componente distinto, medición de campo real),
actualiza el campo correspondiente aquí — los resultados y el resumen exportable reflejan el cambio en toda la
cadena automáticamente, en vez de tener que recalcular a mano en README.md, `requisitos_pa_lna.md` y
`bladerf_2_micro_xa4_specs.md` por separado.
        """
    )
