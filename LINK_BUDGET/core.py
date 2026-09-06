"""
Motor de cálculo del link budget TVWS — sin dependencias de interfaz.

Reconstruye desde cero (potencia TX, pérdidas de cable/conector, ganancias de
antena, cascada de ruido RX) los mismos números que aparecen en README.md §9.1,
claudedocs/bladerf_2_micro_xa4_specs.md y claudedocs/requisitos_pa_lna.md, para
que cualquier cambio futuro (modulación, hardware, potencias) se recalcule
automáticamente en vez de editarse a mano en varios documentos.

Todos los valores por defecto están comentados con su origen: el documento y
sección de donde salen, o "estimado" si el proyecto no lo documenta con una
cifra explícita (p. ej. pérdidas de conectores individuales — el proyecto solo
documenta el EIRP/NF resultante, no cada tramo de cable por separado). Los
valores "estimados" se calibraron para reproducir los totales documentados
(ver comentarios en `EntornoParams`/`CadenaTX`/`CadenaRX`).

⚠ Nota importante encontrada al reconstruir la cascada de ruido (ver función
`nf_cascada_db`): el NF de sistema documentado (~1.0–1.04 dB, README §9.1)
solo se reproduce si la pérdida de cable antes del LNA es ~0 dB, es decir,
si el LNA está montado literalmente en el punto de alimentación de la antena
(tal como exige requisitos_pa_lna.md §4 punto 7 y confirma
claudedocs/estructura_fisica_instalacion.md §3.2). Esta calculadora expone
esa pérdida como parámetro independiente (`perdida_antes_lna_db`) para poder
explorar el escenario en que hay cable de por medio antes del LNA.

**GDT eliminado del diseño (28/08/2026):** el proyecto decidió no usar
descargador de sobretensión (GDT) en ninguna rama RF — el enlace de
validación opera de forma continua solo ~3 horas, no como instalación
permanente expuesta a temporada de tormentas, así que el riesgo de
sobretensión atmosférica que el GDT mitigaría no aplica a esta ventana de
uso. Ver `claudedocs/estructura_fisica_instalacion.md` para el razonamiento
completo. `perdida_gdt_db` (cadena TX) queda en 0.0 dB por defecto — el
campo se conserva por si el proyecto reintroduce protección de sobretensión
para una instalación permanente futura.
"""

from dataclasses import dataclass, field
from math import log10, pi
from typing import Optional

# ─────────────────────────────────────────────────────────────────────────
# Constantes físicas
# ─────────────────────────────────────────────────────────────────────────

RUIDO_TERMICO_DBM_HZ = -174.0  # kTB a temperatura ambiente (290K), constante física estándar

BACKOFF_MIN_DB = 6.0  # Backoff mínimo exigido del PA respecto a su P1dB (requisitos_pa_lna.md §3.1/§3.2 punto 5)
BACKOFF_MAX_DB = 9.0  # Backoff máximo del rango recomendado — más que esto es sobredimensionar el P1dB sin necesidad


# ─────────────────────────────────────────────────────────────────────────
# Parámetros de entorno / trayecto (comunes a downlink y uplink)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class EntornoParams:
    freq_mhz: float = 600.0                        # Frecuencia de referencia (README §3.3, §9.1)
    distancia_km: float = 4.0                      # Distancia final del enlace (actualizada 28/08/2026 — decisión del
                                                    # proyecto: 4 km, ya no 6 km / rango 5-6 km. Antes de eso: 10-15 km,
                                                    # rango de diseño previo a tener ubicación real de los nodos).
    perdida_nlos_db: float = 0.0                   # Pérdida adicional por NLOS. Default 0 dB: estudio de sitio confirmó
                                                    # LOS (línea de vista despejada) entre Gateway y Cliente a la
                                                    # distancia final de 4 km — no es un supuesto simplificador ni un
                                                    # TBD, es un hecho validado en campo (04/09/2026). Campo conservado
                                                    # (no borrado) para poder modelar un escenario NLOS hipotético desde
                                                    # la interfaz si hiciera falta a futuro.
    perdida_extra_db: float = 0.0                  # Margen libre: lluvia, desalineación de antena, polarización, o para
                                                    # modelar el ~5-6 dB de colchón no trazable que tenía el Downlink
                                                    # original antes de esta calculadora (ver claudedocs si se investiga)
    ancho_banda_mhz: float = 6.0                   # Ancho de canal TVWS estándar (README §5.1)
    separacion_mastil_m: float = 1.5               # Separación TX/RX en el mismo mástil (claudedocs/presupuesto_enlace_sin_filtro.xlsx)
    margen_disenio_autointerferencia_db: float = 10.0  # Colchón de SNR exigido sobre la sensibilidad al evaluar autointerferencia (xlsx)


# ─────────────────────────────────────────────────────────────────────────
# Cadena de transmisión de un nodo
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CadenaTX:
    nombre_nodo: str
    potencia_sdr_dbm: float = 6.0                  # bladeRF TX máx. real (ganancia 66 dB ≈ +6 dBm) — bladerf_2_micro_xa4_specs.md
    perdida_pigtail_db: float = 0.3                # RG-316 pigtail SDR→PA/antena — estimado (no documentado tramo a tramo)
    pa_habilitado: bool = True                     # Ambos nodos tienen PA instalado (actualizado 30/07/2026 — antes el
                                                    # Cliente transmitía sin PA).
    pa_p1db_dbm: float = 32.0                      # P1dB del PA REAL comprado (SPECS EQUIPOS/PA.md, "PA OEM 2W 1-900MHz",
                                                    # ambos nodos, actualizado 28/08/2026): hoja técnica da "P1dB > +32 dBm"
                                                    # y "potencia de salida máxima +33 dBm (2W)" como cifras separadas —
                                                    # se usa 32 dBm (el piso documentado de P1dB) en vez de 33 (que es
                                                    # Psat, no P1dB) para no sobreestimar la salida utilizable. Antes de
                                                    # tener esta hoja técnica se usaba 33 dBm como P1dB nominal genérico.
                                                    # Es el dato PRIMARIO: junto con el backoff, DETERMINA la salida
                                                    # promedio. Clase real: A (no AB) — mejor linealidad, menos eficiencia.
    pa_backoff_db: float = 7.5                     # Backoff de diseño aplicado (dentro del rango 6-9 dB exigido para
                                                    # OFDM por su PAPR alto — requisitos_pa_lna.md §3.1/§3.2 punto 5).
                                                    # Default: 7.5 dB, punto medio del rango. Esto SÍ reduce la potencia
                                                    # de salida promedio utilizable: Potencia_salida = P1dB − backoff.
                                                    # Nota (20/08/2026): el valor de trabajo mencionado inicialmente para
                                                    # el hardware real era 5 dB — insuficiente contra el mínimo de 6 dB
                                                    # de esta misma tabla. Con el margen de enlace disponible a la
                                                    # distancia final de 4 km (10.5 dB incluso en 16-QAM con specs
                                                    # reales, actualizado 28/08/2026), se decidió operar con más
                                                    # backoff en vez del mínimo posible — ver "Problema 1" en
                                                    # claudedocs/riesgos_arquitectura_transmision.md.
    perdida_cable_db: float = 0.7                  # LMR-400 hasta la antena — estimado (~0.2 dB/m @600MHz); longitud no
                                                    # fija, dimensionada en sitio (claudedocs/estructura_fisica_instalacion.md)
    perdida_gdt_db: float = 0.0                    # GDT eliminado del diseño (28/08/2026) — enlace de validación de solo
                                                    # ~3h, no instalación permanente; ver claudedocs/estructura_fisica_instalacion.md.
                                                    # Campo conservado (no borrado) por si se reintroduce protección de
                                                    # sobretensión para un despliegue permanente futuro.
    ganancia_antena_dbi: float = 5.0               # LPDA TX (WA5VJB 400-1000MHz) — hoja técnica real da "5 dBi a 500 MHz"
                                                    # (SPECS EQUIPOS/ANTENA_DIRECCIONAL, actualizado 28/08/2026). Antes
                                                    # 6 dBi (valor conservador sin hoja técnica) y antes de eso 10 dBi
                                                    # (spec de compra objetivo, nunca confirmado por el fabricante real).

    def potencia_entrada_pa_dbm(self) -> float:
        """Potencia que llega a la entrada del PA (o del conector de antena si no hay PA).
        ⚠ Con `potencia_sdr_dbm` en su default (6 dBm, máximo del bladeRF), este método da
        ~+5.7 dBm — por ENCIMA de la entrada máxima tolerada del PA real (+3 dBm, SPECS
        EQUIPOS/PA.md). No es un dato para operar así: en la instalación real, el bladeRF
        debe correr a una ganancia TX mucho menor (la necesaria para llegar al punto de
        operación de `potencia_pa_salida_dbm()` dada la ganancia típica del PA, ~30 dB) —
        este valor por defecto solo describe el máximo teórico del SDR solo, no el punto de
        trabajo real con el PA conectado."""
        return self.potencia_sdr_dbm - self.perdida_pigtail_db

    def potencia_pa_salida_dbm(self) -> float:
        """Potencia de salida PROMEDIO (no de pico) a la salida del PA, o del SDR si no hay PA.
        Con PA, se DERIVA de P1dB − backoff (30/07/2026) — antes era una ganancia libre
        independiente del P1dB; ahora el backoff limita directamente cuánta potencia
        promedio es utilizable, en vez de ser solo una verificación posterior."""
        if not self.pa_habilitado:
            return self.potencia_entrada_pa_dbm()
        return self.pa_p1db_dbm - self.pa_backoff_db

    def pa_ganancia_efectiva_db(self) -> Optional[float]:
        """Ganancia implícita del PA en este punto de operación (informativa, para comparar
        contra el rango de ganancia típico de un PA real de esa clase)."""
        if not self.pa_habilitado:
            return None
        return self.potencia_pa_salida_dbm() - self.potencia_entrada_pa_dbm()

    def eirp_dbm(self) -> float:
        return self.potencia_pa_salida_dbm() - self.perdida_cable_db - self.perdida_gdt_db + self.ganancia_antena_dbi

    def backoff_estado(self) -> Optional[str]:
        """'insuficiente' (<6dB, riesgo de compresión/spectral regrowth), 'ok' (6-9dB,
        dentro del rango documentado) o 'conservador' (>9dB, deja potencia sin usar)."""
        if not self.pa_habilitado:
            return None
        if self.pa_backoff_db < BACKOFF_MIN_DB:
            return "insuficiente"
        if self.pa_backoff_db > BACKOFF_MAX_DB:
            return "conservador"
        return "ok"

    def cadena_potencia(self) -> list[tuple[str, float]]:
        """Nivel de potencia (dBm) en cada punto de la cadena TX, para graficar."""
        etapas = [("SDR TX", self.potencia_sdr_dbm)]
        etapas.append(("Post pigtail", self.potencia_entrada_pa_dbm()))
        if self.pa_habilitado:
            etapas.append(("Post PA (P1dB−backoff)", self.potencia_pa_salida_dbm()))
        etapas.append(("Post cable" + (" +GDT" if self.perdida_gdt_db > 0 else ""), self.potencia_pa_salida_dbm() - self.perdida_cable_db - self.perdida_gdt_db))
        etapas.append(("EIRP (post antena)", etapas[-1][1] + self.ganancia_antena_dbi))
        return etapas


# ─────────────────────────────────────────────────────────────────────────
# Cadena de recepción de un nodo
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CadenaRX:
    nombre_nodo: str
    ganancia_antena_dbi: float = 5.0               # LPDA RX (WA5VJB 400-1000MHz) — "5 dBi a 500 MHz" real
                                                    # (SPECS EQUIPOS/ANTENA_DIRECCIONAL, actualizado 28/08/2026)
    perdida_antes_lna_db: float = 0.0              # Cable ENTRE la antena y el LNA. 0 dB por defecto: asume LNA
                                                    # montado en el punto de alimentación de la antena (requisitos_pa_lna.md
                                                    # §4 punto 7), necesario para reproducir el NF de sistema documentado.
                                                    # ⚠ Si en la instalación real hay cable antes del LNA, subir este
                                                    # valor degrada el NF de sistema notablemente — ver docstring del módulo.
    lna_ganancia_db: float = 20.0                  # LNA Nooelec LaNA real: "Ganancia a 1000 MHz (S21): +20 dB"
                                                    # (SPECS EQUIPOS/LNA.md, actualizado 28/08/2026 — coincide con el
                                                    # rango de diseño 15-25 dB que se usaba antes de tener la hoja técnica)
    lna_nf_db: float = 0.9                         # LNA Nooelec LaNA real: "NF a 1000 MHz: 0.8-1.0 dB (0.9 dB típico)"
                                                    # (SPECS EQUIPOS/LNA.md) — cifra a 1000 MHz, la más cercana
                                                    # disponible a la banda TVWS (470-698 MHz); antes se usaba 1.0 dB
                                                    # como spec de proyecto genérica ("≤1dB").
    perdida_cable_lna_sdr_db: float = 0.7          # LMR-400 entre LNA y el SDR (tramo largo, después del LNA) — estimado, longitud no fija
    perdida_pigtail_lna_sdr_db: float = 0.3        # RG-316 pigtail final hacia el SDR — estimado
    sdr_nf_nativo_db: float = 2.5                  # NF nativo del AD9361 sin LNA externo (<2.5 dB, hoja técnica Analog Devices)

    def etapas_cascada(self) -> list[tuple[float, float]]:
        """Lista de (ganancia_db, nf_db) en orden desde la antena hasta el SDR, para Friis."""
        etapas = []
        if self.perdida_antes_lna_db > 0:
            etapas.append((-self.perdida_antes_lna_db, self.perdida_antes_lna_db))  # tramo pasivo: NF = pérdida
        etapas.append((self.lna_ganancia_db, self.lna_nf_db))
        perdida_post_lna = self.perdida_cable_lna_sdr_db + self.perdida_pigtail_lna_sdr_db
        if perdida_post_lna > 0:
            etapas.append((-perdida_post_lna, perdida_post_lna))
        etapas.append((0.0, self.sdr_nf_nativo_db))
        return etapas

    def nf_sistema_db(self) -> float:
        return nf_cascada_db(self.etapas_cascada())

    def cadena_potencia(self, prx_antena_dbm: float) -> list[tuple[str, float]]:
        """Nivel de potencia (dBm) en cada punto de la cadena RX, para graficar."""
        etapas = [("En antena RX", prx_antena_dbm)]
        if self.perdida_antes_lna_db > 0:
            etapas.append(("Pre-LNA", etapas[-1][1] - self.perdida_antes_lna_db))
        etapas.append(("Post LNA", etapas[-1][1] + self.lna_ganancia_db))
        etapas.append(("Entrada SDR", etapas[-1][1] - self.perdida_cable_lna_sdr_db - self.perdida_pigtail_lna_sdr_db))
        return etapas


# ─────────────────────────────────────────────────────────────────────────
# Modulaciones — requisito de SNR reconstruido desde las sensibilidades
# documentadas en README §9.1 (-100.7 dBm BPSK / -97.7 dBm QPSK) usando
# NF≈1.04 dB y BW=6MHz: SNR_req = Sensibilidad - RuidoTermico - NF.
# 16-QAM no está documentado con una cifra propia — valor estimado por
# teoría estándar de modulación (~+6 dB sobre QPSK para BER equivalente).
# ─────────────────────────────────────────────────────────────────────────

MODULACIONES_DEFAULT: dict[str, float] = {
    "BPSK": 4.5,     # Reconstruido desde sensibilidad documentada -100.7 dBm (README §9.1)
    "QPSK": 7.5,     # Reconstruido desde sensibilidad documentada -97.7 dBm (README §9.1)
    "16-QAM": 13.5,  # No documentado — estimado (QPSK + ~6 dB, teoría estándar de constelación)
}


# ─────────────────────────────────────────────────────────────────────────
# Texto de ayuda por parámetro — misma fuente que los comentarios de arriba,
# centralizado aquí para que la interfaz (app.py) muestre el mismo criterio
# sin duplicar redacciones que puedan desincronizarse.
# ─────────────────────────────────────────────────────────────────────────

PARAM_HELP: dict[str, str] = {
    "freq_mhz": "Frecuencia de referencia. Default: 600 MHz (README §3.3, §9.1).",
    "distancia_km": "Distancia del enlace. Default: 4 km (decisión final del proyecto, actualizada 28/08/2026; antes 6 km/rango 5-6 km, y antes de eso 15 km, valor de diseño previo a tener la ubicación real de los nodos).",
    "perdida_nlos_db": "Pérdida adicional por obstrucción NLOS sobre la FSPL. Default: 0 dB — estudio de sitio confirmó línea de vista (LOS) despejada entre Gateway y Cliente a 4 km (04-05/09/2026), no un supuesto NLOS. Campo conservado para modelar un escenario NLOS hipotético si hiciera falta.",
    "perdida_extra_db": "Margen libre para lluvia, desalineación de antena, polarización, u otro factor no modelado explícitamente. Default: 0 dB.",
    "ancho_banda_mhz": "Ancho del canal TVWS. Default: 6 MHz (README §5.1).",
    "separacion_mastil_m": "Separación física entre la LPDA TX y la LPDA RX del mismo nodo, en el mástil. Default: 1.5 m (claudedocs/presupuesto_enlace_sin_filtro.xlsx).",
    "margen_disenio_autointerferencia_db": "Colchón de SNR exigido sobre la sensibilidad al evaluar si la autointerferencia es tolerable. Default: 10 dB (xlsx).",
    "potencia_sdr_dbm": "Potencia TX del bladeRF antes de cualquier PA, AL MÁXIMO de ganancia del SDR. Default: 6 dBm (claudedocs/bladerf_2_micro_xa4_specs.md — SPECS EQUIPOS/SDR_ENLACE no lista este número explícitamente). ⚠ No representa la potencia real que se le entrega al PA: con el PA real (SPECS EQUIPOS/PA.md, ganancia típica 30 dB @500MHz, entrada máxima tolerada +3 dBm), operar el bladeRF a su ganancia máxima sobrecargaría la entrada del PA — en la práctica hay que BAJAR la ganancia TX del bladeRF por software (a ~-5 a -6 dBm de salida) para no exceder ni el nivel de entrada del PA ni el punto de operación de backoff objetivo. Este campo modela el máximo teórico del SDR, no el punto de operación real con PA — ver `potencia_entrada_pa_dbm()`.",
    "perdida_pigtail_db": "Pérdida del pigtail RG-316 entre el SDR y la siguiente etapa (PA o cable). Default: 0.3 dB — estimado, el proyecto no documenta esta pérdida tramo a tramo.",
    "pa_habilitado": "Si el nodo tiene amplificador de potencia (PA) instalado. Default: sí en ambos nodos (actualizado 30/07/2026 — el Cliente ahora también tiene PA; antes transmitía sin PA, ver requisitos_pa_lna.md).",
    "pa_p1db_dbm": "P1dB del PA, de su hoja técnica. Junto con el backoff, DETERMINA la potencia de salida promedio (Salida = P1dB − backoff). Default (ambos nodos, actualizado 28/08/2026, SPECS EQUIPOS/PA.md — 'PA OEM 2W 1-900MHz'): 32 dBm — la hoja técnica real da 'P1dB > +32 dBm' y '+33 dBm' como Psat/potencia máxima (cifras distintas); se usa el piso de P1dB (32) para no sobreestimar. Ganancia típica documentada: 30 dB a 500 MHz, clase A.",
    "pa_backoff_db": "Backoff de diseño aplicado, dentro del rango 6-9 dB exigido para OFDM por su PAPR alto (requisitos_pa_lna.md §3.1/§3.2 punto 5) — si el PA opera cerca de su P1dB, los picos OFDM se comprimen y generan spectral regrowth hacia canales TV vecinos. Default: 7.5 dB (punto medio). Este valor SÍ reduce la potencia de salida promedio utilizable (a diferencia de antes del 30/07/2026, cuando era solo una verificación posterior).",
    "perdida_cable_db": "Pérdida del cable LMR-400 entre el PA/SDR y la antena. Default: 0.7 dB — estimado (~0.2 dB/m a 600 MHz, longitud real no fija, ver claudedocs/estructura_fisica_instalacion.md).",
    "perdida_gdt_db": "Pérdida de inserción del GDT (protección de sobretensión). Default: 0.0 dB — GDT eliminado del diseño el 28/08/2026 (enlace de validación de solo ~3h, no instalación permanente). Campo conservado por si se reintroduce para un despliegue permanente futuro.",
    "ganancia_antena_dbi": "Ganancia de la antena LPDA (WA5VJB 400-1000MHz). Default: 5 dBi — hoja técnica real da '5 dBi a 500 MHz' (SPECS EQUIPOS/ANTENA_DIRECCIONAL, actualizado 28/08/2026). Antes 6 dBi (conservador sin datasheet) y antes de eso 10 dBi (spec de compra objetivo, nunca confirmado por el fabricante).",
    "perdida_antes_lna_db": "Pérdida de cable ENTRE la antena y el LNA. Default: 0 dB, asumiendo LNA montado en el punto de alimentación de la antena (requisitos_pa_lna.md §4 punto 7, confirmado en claudedocs/estructura_fisica_instalacion.md §3.2). ⚠ Si en la instalación real hay cable antes del LNA, subir este valor degrada notablemente el NF de sistema.",
    "lna_ganancia_db": "Ganancia del LNA Nooelec LaNA. Default: 20 dB — 'Ganancia a 1000 MHz (S21): +20 dB' (SPECS EQUIPOS/LNA.md, actualizado 28/08/2026).",
    "lna_nf_db": "Figura de ruido del LNA Nooelec LaNA. Default: 0.9 dB — 'NF a 1000 MHz: 0.8-1.0 dB (0.9 dB típico)' (SPECS EQUIPOS/LNA.md, actualizado 28/08/2026; cifra a 1000 MHz, la más cercana disponible a la banda TVWS).",
    "perdida_cable_lna_sdr_db": "Pérdida del cable LMR-400 entre el LNA y el SDR (tramo largo, después del LNA). Default: 0.7 dB — estimado, longitud real no fija.",
    "perdida_pigtail_lna_sdr_db": "Pérdida del pigtail final entre el LNA/cable y el SDR. Default: 0.3 dB — estimado.",
    "sdr_nf_nativo_db": "NF nativo del RFIC AD9361 sin LNA externo. Default: 2.5 dB — spec <2.5 dB (hoja técnica Analog Devices). Casi no pesa en el NF de sistema porque el LNA lo antecede con suficiente ganancia.",
}


# ─────────────────────────────────────────────────────────────────────────
# Fórmulas físicas
# ─────────────────────────────────────────────────────────────────────────

def fspl_db(distancia_km: float, freq_mhz: float) -> float:
    """Pérdida de espacio libre estándar (Friis), distancia en km, frecuencia en MHz."""
    if distancia_km <= 0 or freq_mhz <= 0:
        return 0.0
    return 20 * log10(distancia_km) + 20 * log10(freq_mhz) + 32.44


def aislamiento_espacio_libre_db(freq_mhz: float, distancia_m: float) -> float:
    """Aislamiento entre dos antenas separadas `distancia_m`, misma fórmula que
    claudedocs/presupuesto_enlace_sin_filtro.xlsx. ⚠ A distancias tan cortas
    (mismo mástil) las antenas están en campo cercano/reactivo, donde Friis de
    espacio libre es optimista — riesgos_arquitectura_transmision.md cita un
    rango empírico más realista de 30-50 dB para separación física únicamente.
    Tratar el resultado de esta fórmula como cota superior, no como garantía."""
    if distancia_m <= 0 or freq_mhz <= 0:
        return 0.0
    lambda_m = 300.0 / freq_mhz
    return 20 * log10(4 * pi * distancia_m / lambda_m)


def nf_cascada_db(etapas: list[tuple[float, float]]) -> float:
    """Fórmula de cascada de Friis. `etapas` = [(ganancia_db, nf_db), ...] en
    orden desde la entrada (antena) hasta la salida. Una etapa pasiva (cable,
    conector) se modela con ganancia negativa y NF == pérdida en dB."""
    if not etapas:
        return 0.0
    f_total = 0.0
    ganancia_acumulada = 1.0
    for i, (g_db, nf_db) in enumerate(etapas):
        f = 10 ** (nf_db / 10)
        if i == 0:
            f_total = f
        else:
            f_total += (f - 1) / ganancia_acumulada
        ganancia_acumulada *= 10 ** (g_db / 10)
    return 10 * log10(f_total)


def sensibilidad_dbm(nf_sistema_db: float, ancho_banda_mhz: float, snr_requerido_db: float) -> float:
    ancho_banda_hz = ancho_banda_mhz * 1e6
    return RUIDO_TERMICO_DBM_HZ + 10 * log10(ancho_banda_hz) + nf_sistema_db + snr_requerido_db


# ─────────────────────────────────────────────────────────────────────────
# Resultado de un enlace (downlink o uplink) completo
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoEnlace:
    eirp_dbm: float
    perdida_trayecto_db: float
    prx_antena_dbm: float
    nf_sistema_db: float
    señal_entrada_sdr_dbm: float
    sensibilidades_dbm: dict[str, float]
    margenes_db: dict[str, float]
    cadena_potencia_tx: list[tuple[str, float]]
    cadena_potencia_rx: list[tuple[str, float]]


def calcular_enlace(
    tx: CadenaTX,
    rx: CadenaRX,
    entorno: EntornoParams,
    modulaciones: Optional[dict[str, float]] = None,
) -> ResultadoEnlace:
    modulaciones = modulaciones or MODULACIONES_DEFAULT

    eirp = tx.eirp_dbm()
    perdida_trayecto = fspl_db(entorno.distancia_km, entorno.freq_mhz) + entorno.perdida_nlos_db + entorno.perdida_extra_db
    prx_antena = eirp - perdida_trayecto + rx.ganancia_antena_dbi

    nf_sistema = rx.nf_sistema_db()
    cadena_rx_potencia = rx.cadena_potencia(prx_antena)
    señal_sdr = cadena_rx_potencia[-1][1]

    sensibilidades = {mod: sensibilidad_dbm(nf_sistema, entorno.ancho_banda_mhz, snr) for mod, snr in modulaciones.items()}
    margenes = {mod: prx_antena - sens for mod, sens in sensibilidades.items()}

    return ResultadoEnlace(
        eirp_dbm=eirp,
        perdida_trayecto_db=perdida_trayecto,
        prx_antena_dbm=prx_antena,
        nf_sistema_db=nf_sistema,
        señal_entrada_sdr_dbm=señal_sdr,
        sensibilidades_dbm=sensibilidades,
        margenes_db=margenes,
        cadena_potencia_tx=tx.cadena_potencia(),
        cadena_potencia_rx=cadena_rx_potencia,
    )


# ─────────────────────────────────────────────────────────────────────────
# Autointerferencia full-duplex (mismo nodo, antena TX vs antena RX propia)
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoAutointerferencia:
    aislamiento_db: float
    potencia_conducida_dbm: float
    autointerferencia_dbm: float
    nivel_requerido_dbm: float
    deficit_db: float


def calcular_autointerferencia(
    tx: CadenaTX,
    sensibilidad_referencia_dbm: float,
    entorno: EntornoParams,
    aislamiento_override_db: Optional[float] = None,
) -> ResultadoAutointerferencia:
    aislamiento = (
        aislamiento_override_db
        if aislamiento_override_db is not None
        else aislamiento_espacio_libre_db(entorno.freq_mhz, entorno.separacion_mastil_m)
    )
    # Potencia conducida en el puerto de la antena TX propia (EIRP sin la ganancia de antena,
    # porque lo que "escapa" hacia la antena RX vecina es la potencia conducida, no el EIRP irradiado
    # en la dirección del enlace lejano).
    potencia_conducida = tx.eirp_dbm() - tx.ganancia_antena_dbi
    autointerferencia = potencia_conducida - aislamiento
    nivel_requerido = sensibilidad_referencia_dbm - entorno.margen_disenio_autointerferencia_db
    deficit = autointerferencia - nivel_requerido
    return ResultadoAutointerferencia(
        aislamiento_db=aislamiento,
        potencia_conducida_dbm=potencia_conducida,
        autointerferencia_dbm=autointerferencia,
        nivel_requerido_dbm=nivel_requerido,
        deficit_db=deficit,
    )
