"""
recolector_app.py
==================
Interfaz de escritorio (tkinter, sin dependencias extra sobre lo que ya
pide IA/requirements.txt + requests) para recolectar el dataset real de
sensado TVWS en múltiples zonas, horas del día y sesiones, pensada para
repetirse sesión tras sesión en campo sin tener que recordar comandos de
escanear_tvws.sh / etiquetar_rnf.py cada vez.

No reimplementa el acceso al hardware: envuelve escanear_tvws.sh (mismos
parámetros ya justificados -- rango de banda, bin, ganancia, recorte de
bordes) vía subprocess, y reutiliza directamente las funciones de
analizar_barrido.py, etiquetar_rnf.py, rnf_web.py y nucleo.py -- un solo
lugar dueño de cada pieza de lógica, nada duplicado en un segundo idioma.

Las operaciones largas (barrido rtl_power, consulta RNF por red, captura
de hasta 39 canales) corren en un hilo de fondo y reportan a la UI por una
Queue -- tkinter no es thread-safe, nunca se toca un widget desde otro
hilo que no sea el principal.

Ejecutar con:
    ~/envs/IA/bin/python3 IA/herramientas/recolector_app.py

Requiere tkinter (viene con CPython; en Debian/Ubuntu puede necesitar el
paquete de sistema `python3-tk` si no está) + lo ya listado en
IA/herramientas/requirements.txt (sólo `requests`, para rnf_web.py) +
matplotlib (ya en IA/requirements.txt) para el gráfico embebido del
espectro.
"""

import datetime
import glob
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import unicodedata
from tkinter import messagebox, ttk

import matplotlib

matplotlib.use("TkAgg", force=True)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import numpy as np  # noqa: E402

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

# Objetivos mínimos de calidad de pipeline_dataset_v2.md -- se usan sólo
# para las barras de progreso del inventario, no bloquean nada.
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

def listar_sesiones() -> list:
    filas = []
    for carpeta in sorted(glob.glob(os.path.join(DATASET_REAL_DIR, "etiquetado_*"))):
        meta_path = os.path.join(carpeta, "_sesion.json")
        npz_files = glob.glob(os.path.join(carpeta, "*.npz"))
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        else:
            meta = {"zona": os.path.basename(carpeta), "fecha": "?"}
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
            # "hora_captura" es el campo nuevo (HH:MM exacto); las sesiones
            # viejas sólo tienen "sesion_horario" (categoría mañana/tarde/...).
            "hora": meta.get("hora_captura", meta.get("sesion_horario", "?")),
            "fecha": meta.get("fecha", "?"),
            "ganancia_db": meta.get("ganancia_db", "?"),
            "lna": meta.get("lna", "?"),
            "n_muestras": len(npz_files),
            "ocupados": ocupados,
            "libres": libres,
        })
    return filas


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

class RecolectorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Recolector de dataset real TVWS")
        self.geometry("1000x680")

        self._cola = queue.Queue()
        self._ultimo_barrido = None  # {"tabla": [...], "piso_ruido": float}
        self._rnf_filas = None       # último resultado de consulta en vivo
        self.distritos = rnf_web.obtener_distritos_lima()  # {codigo: nombre}

        self._construir_barra_sesion()
        self._construir_tabs()
        self._refrescar_estado_dispositivo()
        self.after(150, self._procesar_cola)

    # ── Barra de sesión (arriba, siempre visible) ──────────────────────────
    def _construir_barra_sesion(self):
        barra = ttk.LabelFrame(self, text="Sesión actual")
        barra.pack(side="top", fill="x", padx=8, pady=6)

        nombres = sorted(self.distritos.values())
        self.var_distrito = tk.StringVar(value="LOS OLIVOS" if "LOS OLIVOS" in nombres else (nombres[0] if nombres else ""))
        ttk.Label(barra, text="Distrito:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.combo_distrito = ttk.Combobox(barra, textvariable=self.var_distrito, values=nombres, state="readonly", width=22)
        self.combo_distrito.grid(row=0, column=1, padx=4, pady=3)

        ttk.Label(barra, text="Zona (opcional):").grid(row=0, column=2, sticky="w", padx=4, pady=3)
        self.var_zona = tk.StringVar()
        ttk.Entry(barra, textvariable=self.var_zona, width=22).grid(row=0, column=3, padx=4, pady=3)

        ttk.Label(barra, text="Hora de la sesión:").grid(row=0, column=4, sticky="w", padx=4, pady=3)
        ahora = datetime.datetime.now()
        frame_hora = ttk.Frame(barra)
        self.var_hora = tk.StringVar(value=f"{ahora.hour:02d}")
        self.var_minuto = tk.StringVar(value=f"{ahora.minute:02d}")
        ttk.Spinbox(frame_hora, from_=0, to=23, width=3, textvariable=self.var_hora,
                    format="%02.0f", wrap=True, justify="center").pack(side="left")
        ttk.Label(frame_hora, text=":").pack(side="left")
        ttk.Spinbox(frame_hora, from_=0, to=59, width=3, textvariable=self.var_minuto,
                    format="%02.0f", wrap=True, justify="center").pack(side="left")
        frame_hora.grid(row=0, column=5, padx=4, pady=3)

        self.var_lna = tk.BooleanVar(value=True)
        ttk.Checkbutton(barra, text="LNA conectado", variable=self.var_lna,
                        command=self._al_cambiar_lna).grid(row=1, column=0, columnspan=2, sticky="w", padx=4)

        ttk.Label(barra, text="Ganancia tuner (dB):").grid(row=1, column=2, sticky="w", padx=4)
        self.var_ganancia = tk.DoubleVar(value=20.7)
        ttk.Spinbox(barra, from_=0.0, to=49.6, increment=0.1, width=6,
                    textvariable=self.var_ganancia).grid(row=1, column=3, sticky="w", padx=4)

        self.var_antena_ext = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            barra, text="Confirmo que la antena está en EXTERIOR ahora mismo",
            variable=self.var_antena_ext, command=self._actualizar_estado_captura,
        ).grid(row=1, column=4, columnspan=2, sticky="w", padx=4)

        self.lbl_dispositivo = ttk.Label(barra, text="?")
        self.lbl_dispositivo.grid(row=2, column=0, columnspan=3, sticky="w", padx=4, pady=(3, 4))
        ttk.Button(barra, text="Actualizar estado", command=self._refrescar_estado_dispositivo).grid(
            row=2, column=3, sticky="w", padx=4, pady=(3, 4))

    def _al_cambiar_lna(self):
        self.var_ganancia.set(20.7 if self.var_lna.get() else 40.0)

    def _refrescar_estado_dispositivo(self):
        self.presente = dispositivo_presente()
        self.lbl_dispositivo.config(
            text=("🟢 Dispositivo RTL-SDR detectado" if self.presente else "🔴 Dispositivo RTL-SDR NO detectado"),
            foreground=("green" if self.presente else "red"),
        )
        self._actualizar_estado_captura()

    # ── Helpers de sesión derivados de la barra ─────────────────────────────
    def distrito_actual(self) -> str:
        return self.var_distrito.get()

    def distrito_slug(self) -> str:
        return slugify(self.distrito_actual())

    def hora_str(self) -> str:
        return f"{int(self.var_hora.get()):02d}:{int(self.var_minuto.get()):02d}"

    def sesion_slug(self) -> str:
        zona = self.var_zona.get().strip()
        zona_slug = slugify(zona) if zona else self.distrito_slug()
        fecha = datetime.date.today().isoformat()
        return f"{zona_slug}_{fecha}_{self.hora_str().replace(':', 'h')}m"

    # ── Tabs ─────────────────────────────────────────────────────────────
    def _construir_tabs(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tab_espectro = ttk.Frame(self.notebook)
        self.tab_rnf = ttk.Frame(self.notebook)
        self.tab_captura = ttk.Frame(self.notebook)
        self.tab_inventario = ttk.Frame(self.notebook)
        self.tab_hw = ttk.Frame(self.notebook)
        for frame, nombre in [
            (self.tab_espectro, "Espectro"), (self.tab_rnf, "RNF"),
            (self.tab_captura, "Captura + etiquetado"),
            (self.tab_inventario, "Inventario"), (self.tab_hw, "Hardware"),
        ]:
            self.notebook.add(frame, text=nombre)

        self._construir_tab_espectro()
        self._construir_tab_rnf()
        self._construir_tab_captura()
        self._construir_tab_inventario()
        self._construir_tab_hw()

    # ── Tab: Espectro ────────────────────────────────────────────────────
    def _construir_tab_espectro(self):
        f = self.tab_espectro
        top = ttk.Frame(f)
        top.pack(fill="x", padx=6, pady=6)
        self.btn_scan = ttk.Button(top, text="Ejecutar barrido ahora", command=self._on_scan)
        self.btn_scan.pack(side="left")
        self.lbl_scan_estado = ttk.Label(top, text="")
        self.lbl_scan_estado.pack(side="left", padx=10)
        ttk.Label(
            f, text="Distribución de energía en toda la banda (470-704 MHz). "
                    "Picos achatados en vez de redondeados con roll-off => ganancia demasiado alta.",
            wraplength=950,
        ).pack(fill="x", padx=6)

        self.fig_espectro = Figure(figsize=(9, 3.2), dpi=100)
        self.ax_espectro = self.fig_espectro.add_subplot(111)
        self.ax_espectro.set_xlabel("Frecuencia (MHz)")
        self.ax_espectro.set_ylabel("Potencia (dB, relativo)")
        self.canvas_espectro = FigureCanvasTkAgg(self.fig_espectro, master=f)
        self.canvas_espectro.get_tk_widget().pack(fill="x", padx=6, pady=4)

        cols = ("canal", "centro_mhz", "media_db", "margen_db", "dispersion_db", "candidato_ocupado")
        self.tree_espectro = ttk.Treeview(f, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (60, 100, 90, 90, 100, 130)):
            self.tree_espectro.heading(c, text=c)
            self.tree_espectro.column(c, width=w, anchor="center")
        self.tree_espectro.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def _on_scan(self):
        if not self.presente:
            messagebox.showerror("Dispositivo no detectado", "No se encontró el RTL-SDR (lsusb).")
            return
        self.btn_scan.config(state="disabled")
        self.lbl_scan_estado.config(text="Barriendo 470-704MHz... (hasta ~2 min)")
        gain = self.var_ganancia.get()
        out_prefix = os.path.join(CAPTURAS_DIR, f"{self.sesion_slug()}_scan")

        def trabajo():
            try:
                ejecutar_scan(gain, integ=12, crop=20, out_prefix=out_prefix)
                frecuencias, potencia_db = leer_rtl_power_csv(out_prefix + ".csv")
                tabla, piso_ruido = construir_tabla_canales(frecuencias, potencia_db, umbral_db=7.0)
                self._cola.put(("scan_ok", frecuencias, potencia_db, tabla, piso_ruido))
            except Exception as e:
                self._cola.put(("scan_error", str(e)))

        threading.Thread(target=trabajo, daemon=True).start()

    def _mostrar_resultado_scan(self, frecuencias, potencia_db, tabla, piso_ruido):
        self._ultimo_barrido = {"tabla": tabla, "piso_ruido": piso_ruido}
        self.ax_espectro.clear()
        self.ax_espectro.plot(frecuencias / 1e6, potencia_db, linewidth=0.5, color="steelblue")
        self.ax_espectro.axhline(piso_ruido, color="gray", linestyle="--", linewidth=1)
        self.ax_espectro.set_xlabel("Frecuencia (MHz)")
        self.ax_espectro.set_ylabel("Potencia (dB, relativo)")
        self.fig_espectro.tight_layout()
        self.canvas_espectro.draw()

        self.tree_espectro.delete(*self.tree_espectro.get_children())
        for fila in tabla:
            self.tree_espectro.insert("", "end", values=(
                fila["canal"], fila["centro_mhz"], fila["media_db"],
                fila["margen_db"], fila["dispersion_db"], fila["candidato_ocupado"],
            ))

        n_ocupados = sum(f["candidato_ocupado"] for f in tabla)
        self.lbl_scan_estado.config(
            text=f"{n_ocupados}/{len(tabla)} canales candidato-ocupado (piso de ruido: {piso_ruido:.2f} dB)")
        self.btn_scan.config(state="normal")
        self._actualizar_estado_captura()

    # ── Tab: RNF ─────────────────────────────────────────────────────────
    def _construir_tab_rnf(self):
        f = self.tab_rnf
        top = ttk.Frame(f)
        top.pack(fill="x", padx=6, pady=6)
        self.btn_rnf = ttk.Button(top, text="Consultar RNF en vivo (rnf.mtc.gob.pe)", command=self._on_consultar_rnf)
        self.btn_rnf.pack(side="left")
        self.btn_rnf_guardar = ttk.Button(top, text="Guardar CSV", command=self._on_guardar_rnf, state="disabled")
        self.btn_rnf_guardar.pack(side="left", padx=6)
        self.lbl_rnf_estado = ttk.Label(top, text="")
        self.lbl_rnf_estado.pack(side="left", padx=10)

        self.lbl_rnf_existentes = ttk.Label(f, text="", wraplength=950, foreground="#555")
        self.lbl_rnf_existentes.pack(fill="x", padx=6)

        cols = ("canal", "estado_raw", "razon_social")
        self.tree_rnf = ttk.Treeview(f, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (60, 110, 500)):
            self.tree_rnf.heading(c, text=c)
            self.tree_rnf.column(c, width=w, anchor="w" if c == "razon_social" else "center")
        self.tree_rnf.pack(fill="both", expand=True, padx=6, pady=6)

        bottom = ttk.Frame(f)
        bottom.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(bottom, text="CSV a usar para el etiquetado de esta sesión:").pack(side="left")
        self.var_rnf_activo = tk.StringVar()
        self.combo_rnf_activo = ttk.Combobox(bottom, textvariable=self.var_rnf_activo, state="readonly", width=60)
        self.combo_rnf_activo.pack(side="left", padx=6)
        self.combo_rnf_activo.bind("<<ComboboxSelected>>", lambda e: self._actualizar_estado_captura())
        ttk.Button(bottom, text="Refrescar lista", command=self._refrescar_rnf_existentes).pack(side="left")

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed())
        self._refrescar_rnf_existentes()

    def _on_tab_changed(self):
        actual = self.notebook.tab(self.notebook.select(), "text")
        if actual == "RNF":
            self.lbl_rnf_existentes.config(
                text=f"RNF para Lima / Lima / {self.distrito_actual()}. "
                     f"CSV ya guardados para este distrito: " +
                     (", ".join(n for n in (os.path.basename(p) for p in rnf_csvs_existentes())
                                if self.distrito_slug() in n) or "ninguno"))

    def _refrescar_rnf_existentes(self):
        existentes = rnf_csvs_existentes()
        self.combo_rnf_activo["values"] = existentes
        if existentes and not self.var_rnf_activo.get():
            self.var_rnf_activo.set(existentes[-1])
        self._actualizar_estado_captura()

    def _on_consultar_rnf(self):
        self.btn_rnf.config(state="disabled")
        self.lbl_rnf_estado.config(text="Consultando...")
        codigo_distrito = next((k for k, v in self.distritos.items() if v == self.distrito_actual()), None)

        def trabajo():
            try:
                filas = rnf_web.consultar_canales(codigo_distrito)
                self._cola.put(("rnf_ok", filas))
            except Exception as e:
                self._cola.put(("rnf_error", str(e)))

        threading.Thread(target=trabajo, daemon=True).start()

    def _mostrar_resultado_rnf(self, filas):
        self._rnf_filas = filas
        self.tree_rnf.delete(*self.tree_rnf.get_children())
        for fila in filas:
            self.tree_rnf.insert("", "end", values=(fila["canal"], fila["estado_raw"], fila["razon_social"]))
        ocupados = sum(1 for f in filas if f["estado_raw"] == "AUTORIZADO")
        self.lbl_rnf_estado.config(text=f"{len(filas)} canales recibidos, {ocupados} autorizados")
        self.btn_rnf.config(state="normal")
        self.btn_rnf_guardar.config(state="normal")

    def _on_guardar_rnf(self):
        if not self._rnf_filas:
            return
        fecha = datetime.date.today().isoformat()
        ruta = os.path.join(DATASET_REAL_DIR, f"rnf_{self.distrito_slug()}_{fecha}.csv")
        rnf_web.guardar_csv_rnf(self._rnf_filas, ruta)
        self.lbl_rnf_estado.config(text=f"Guardado: {os.path.basename(ruta)}")
        self._refrescar_rnf_existentes()
        self.var_rnf_activo.set(ruta)
        self._actualizar_estado_captura()

    # ── Tab: Captura + etiquetado ────────────────────────────────────────
    def _construir_tab_captura(self):
        f = self.tab_captura
        izq = ttk.Frame(f)
        izq.pack(side="left", fill="y", padx=6, pady=6)
        ttk.Label(izq, text="Canales a capturar (14-52):").pack(anchor="w")
        self.lista_canales = tk.Listbox(izq, selectmode="extended", height=20, exportselection=False)
        for c in range(CANAL_MIN, CANAL_MAX + 1):
            self.lista_canales.insert("end", str(c))
        self.lista_canales.selection_set(0, "end")
        self.lista_canales.pack(fill="y")
        btns = ttk.Frame(izq)
        btns.pack(fill="x", pady=4)
        ttk.Button(btns, text="Todos", command=lambda: self.lista_canales.selection_set(0, "end")).pack(side="left")
        ttk.Button(btns, text="Ninguno", command=lambda: self.lista_canales.selection_clear(0, "end")).pack(side="left", padx=4)

        der = ttk.Frame(f)
        der.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        self.lbl_captura_requisitos = ttk.Label(der, text="", foreground="#b00020", wraplength=650, justify="left")
        self.lbl_captura_requisitos.pack(fill="x", anchor="w")

        self.btn_capturar = ttk.Button(der, text="Capturar y etiquetar", command=self._on_capturar, state="disabled")
        self.btn_capturar.pack(anchor="w", pady=6)

        self.barra_progreso = ttk.Progressbar(der, orient="horizontal", mode="determinate", length=500)
        self.barra_progreso.pack(fill="x", pady=4)
        self.lbl_captura_estado = ttk.Label(der, text="")
        self.lbl_captura_estado.pack(anchor="w")

        ttk.Label(der, text="Avisos / QA:").pack(anchor="w", pady=(10, 0))
        self.txt_avisos = tk.Text(der, height=18, state="disabled", wrap="word")
        self.txt_avisos.pack(fill="both", expand=True)

        self._actualizar_estado_captura()

    def _actualizar_estado_captura(self):
        if not hasattr(self, "lbl_captura_requisitos"):
            return
        faltantes = []
        if not getattr(self, "presente", False):
            faltantes.append("- Dispositivo RTL-SDR no detectado.")
        if not self.var_antena_ext.get():
            faltantes.append("- Falta confirmar que la antena está en EXTERIOR (barra de sesión).")
        if not self.var_rnf_activo.get():
            faltantes.append("- Falta elegir/guardar un CSV de RNF en la pestaña RNF.")
        self.lbl_captura_requisitos.config(text="\n".join(faltantes))
        self.btn_capturar.config(state=("disabled" if faltantes else "normal"))

    def _log_aviso(self, texto):
        self.txt_avisos.config(state="normal")
        self.txt_avisos.insert("end", texto + "\n")
        self.txt_avisos.see("end")
        self.txt_avisos.config(state="disabled")

    def _on_capturar(self):
        canales = [int(self.lista_canales.get(i)) for i in self.lista_canales.curselection()]
        if not canales:
            messagebox.showwarning("Sin canales", "Elegí al menos un canal.")
            return

        self.txt_avisos.config(state="normal")
        self.txt_avisos.delete("1.0", "end")
        self.txt_avisos.config(state="disabled")
        self.barra_progreso.config(value=0, maximum=len(canales))
        self.btn_capturar.config(state="disabled")

        rnf_activo = self.var_rnf_activo.get()
        gain = self.var_ganancia.get()
        lna = self.var_lna.get()
        distrito = self.distrito_actual()
        zona = self.var_zona.get().strip() or distrito
        hora = self.hora_str()
        fecha = datetime.date.today().isoformat()
        sesion_slug = self.sesion_slug()
        barrido_qa = {f["canal"]: f["candidato_ocupado"] for f in (self._ultimo_barrido or {}).get("tabla", [])}

        def trabajo():
            try:
                etiquetas_rnf = cargar_rnf(rnf_activo)
            except Exception as e:
                self._cola.put(("captura_error", f"No se pudo leer el CSV de RNF: {e}"))
                return
            canal_a_posicion = _canal_a_posicion()
            iq_dir = os.path.join(CAPTURAS_DIR, f"{sesion_slug}_iq")
            salida_dir = os.path.join(DATASET_REAL_DIR, f"etiquetado_{sesion_slug}")
            os.makedirs(salida_dir, exist_ok=True)

            n_escritos = n_gris = 0
            for i, canal in enumerate(canales):
                self._cola.put(("captura_progreso", i, len(canales), canal))
                iq_path = os.path.join(iq_dir, f"iq_ch{canal}.iq")
                try:
                    ejecutar_captura_iq(canal, gain, duracion=1.0, out_path=iq_path)
                except Exception as e:
                    self._cola.put(("captura_aviso", f"Canal {canal}: fallo de captura -- {e}"))
                    continue

                label = etiquetas_rnf.get(canal, -1)
                if label == -1:
                    n_gris += 1
                    self._cola.put(("captura_aviso", f"Canal {canal}: zona gris / sin dato RNF -- omitido"))
                    continue

                if canal in barrido_qa:
                    ocupado_detectado = barrido_qa[canal]
                    if label == 1 and not ocupado_detectado:
                        self._cola.put(("captura_aviso", f"QA canal {canal}: autorizado por RNF pero sin energía en el barrido (¿estación apagada?)"))
                    elif label == 0 and ocupado_detectado:
                        self._cola.put(("captura_aviso", f"QA canal {canal}: disponible por RNF pero con energía detectada (¿interferencia?)"))

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

            with open(os.path.join(salida_dir, "_sesion.json"), "w") as fjson:
                json.dump({
                    "zona": zona,
                    "distrito": distrito,
                    "hora_captura": hora,
                    "fecha": fecha,
                    "fecha_hora_iso": datetime.datetime.now().isoformat(),
                    "ganancia_db": gain,
                    "lna": lna,
                    "rnf_csv": os.path.basename(rnf_activo),
                    "n_muestras": n_escritos,
                    "n_zona_gris_omitidas": n_gris,
                }, fjson, indent=2, ensure_ascii=False)

            self._cola.put(("captura_ok", n_escritos, n_gris, salida_dir))

        threading.Thread(target=trabajo, daemon=True).start()

    # ── Tab: Inventario ──────────────────────────────────────────────────
    def _construir_tab_inventario(self):
        f = self.tab_inventario
        top = ttk.Frame(f)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Refrescar", command=self._refrescar_inventario).pack(side="left")
        self.lbl_inv_resumen = ttk.Label(top, text="")
        self.lbl_inv_resumen.pack(side="left", padx=10)

        self.inv_progresos = {}
        marco_metas = ttk.Frame(f)
        marco_metas.pack(fill="x", padx=6)
        for clave, etiqueta in (("muestras", "Muestras"), ("localidades", "Localidades"), ("horas", "Sesiones de horario distintas")):
            fila = ttk.Frame(marco_metas)
            fila.pack(fill="x", pady=2)
            ttk.Label(fila, text=etiqueta, width=28).pack(side="left")
            barra = ttk.Progressbar(fila, orient="horizontal", mode="determinate", length=300, maximum=100)
            barra.pack(side="left", padx=6)
            lbl = ttk.Label(fila, text="")
            lbl.pack(side="left")
            self.inv_progresos[clave] = (barra, lbl)

        cols = ("carpeta", "zona", "distrito", "hora", "fecha", "ganancia_db", "lna", "n_muestras", "ocupados", "libres")
        self.tree_inventario = ttk.Treeview(f, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (210, 110, 110, 60, 90, 70, 50, 80, 70, 60)):
            self.tree_inventario.heading(c, text=c)
            self.tree_inventario.column(c, width=w, anchor="center")
        self.tree_inventario.pack(fill="both", expand=True, padx=6, pady=6)

        self._refrescar_inventario()

    def _refrescar_inventario(self):
        filas = listar_sesiones()
        self.tree_inventario.delete(*self.tree_inventario.get_children())
        if not filas:
            self.lbl_inv_resumen.config(text="Todavía no hay ninguna sesión etiquetada en IA/dataset_real/.")
            for barra, lbl in self.inv_progresos.values():
                barra.config(value=0)
                lbl.config(text="0")
            return

        for fila in filas:
            self.tree_inventario.insert("", "end", values=tuple(fila[c] for c in (
                "carpeta", "zona", "distrito", "hora", "fecha", "ganancia_db", "lna", "n_muestras", "ocupados", "libres")))

        total = sum(f["n_muestras"] for f in filas)
        n_localidades = len({f["distrito"] for f in filas})
        n_horas = len({f["hora"] for f in filas})
        self.lbl_inv_resumen.config(
            text=f"{total} muestras totales, {n_localidades} localidades distintas, {n_horas} sesiones de horario distintas")

        for clave, valor, meta in (
            ("muestras", total, META_MUESTRAS),
            ("localidades", n_localidades, META_LOCALIDADES),
            ("horas", n_horas, META_SESIONES_HORARIO),
        ):
            barra, lbl = self.inv_progresos[clave]
            barra.config(value=min(100, 100 * valor / meta))
            lbl.config(text=f"{valor}/{meta}")

    # ── Tab: Hardware ────────────────────────────────────────────────────
    def _construir_tab_hw(self):
        f = self.tab_hw
        top = ttk.Frame(f)
        top.pack(fill="x", padx=6, pady=6)
        self.lbl_hw_estado = ttk.Label(top, text="")
        self.lbl_hw_estado.pack(side="left")
        ttk.Button(top, text="Correr rtl_test -t (unos segundos)", command=self._on_rtl_test).pack(side="left", padx=10)

        self.txt_hw_salida = tk.Text(f, height=20, state="disabled", wrap="word")
        self.txt_hw_salida.pack(fill="both", expand=True, padx=6, pady=6)

        ttk.Label(
            f, text="El mensaje '[R82XX] PLL not locked!' es cosmético en este equipo "
                    "(verificado contra captura real), no indica una falla. Ver CLAUDE.md.",
            wraplength=950,
        ).pack(fill="x", padx=6, pady=(0, 6))

    def _on_rtl_test(self):
        self.txt_hw_salida.config(state="normal")
        self.txt_hw_salida.delete("1.0", "end")
        self.txt_hw_salida.insert("end", "Corriendo rtl_test...\n")
        self.txt_hw_salida.config(state="disabled")

        def trabajo():
            salida = ejecutar_rtl_test()
            self._cola.put(("rtl_test_ok", salida))

        threading.Thread(target=trabajo, daemon=True).start()

    # ── Cola de resultados de hilos de fondo ────────────────────────────
    def _procesar_cola(self):
        try:
            while True:
                mensaje = self._cola.get_nowait()
                tipo = mensaje[0]
                if tipo == "scan_ok":
                    self._mostrar_resultado_scan(*mensaje[1:])
                elif tipo == "scan_error":
                    self.btn_scan.config(state="normal")
                    self.lbl_scan_estado.config(text="")
                    messagebox.showerror("Error en el barrido", mensaje[1])
                elif tipo == "rnf_ok":
                    self._mostrar_resultado_rnf(mensaje[1])
                elif tipo == "rnf_error":
                    self.btn_rnf.config(state="normal")
                    self.lbl_rnf_estado.config(text="")
                    messagebox.showerror(
                        "No se pudo consultar el RNF",
                        f"{mensaje[1]}\n\nSe puede seguir con un CSV manual "
                        "(ver IA/herramientas/etiquetar_rnf.py --generar-plantilla-rnf).",
                    )
                elif tipo == "captura_progreso":
                    i, total, canal = mensaje[1], mensaje[2], mensaje[3]
                    self.barra_progreso.config(value=i + 1)
                    self.lbl_captura_estado.config(text=f"Canal {canal} ({i + 1}/{total})...")
                elif tipo == "captura_aviso":
                    self._log_aviso(mensaje[1])
                elif tipo == "captura_error":
                    self.btn_capturar.config(state="normal")
                    messagebox.showerror("Error de captura", mensaje[1])
                elif tipo == "captura_ok":
                    n_escritos, n_gris, salida_dir = mensaje[1], mensaje[2], mensaje[3]
                    self.lbl_captura_estado.config(text=f"{n_escritos} muestras escritas en {salida_dir} ({n_gris} omitidas por zona gris)")
                    self._actualizar_estado_captura()
                    self._refrescar_inventario()
                elif tipo == "rtl_test_ok":
                    self.txt_hw_salida.config(state="normal")
                    self.txt_hw_salida.delete("1.0", "end")
                    self.txt_hw_salida.insert("end", mensaje[1])
                    self.txt_hw_salida.config(state="disabled")
        except queue.Empty:
            pass
        self.after(150, self._procesar_cola)


def main():
    app = RecolectorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
