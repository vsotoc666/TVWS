"""
rnf_web.py
==========
Consulta en vivo al RNF (Registro Nacional de Frecuencias) del MTC para
distritos de la provincia de Lima (departamento=LIMA, provincia=LIMA).

El portal (https://rnf.mtc.gob.pe/Television) no tiene API -- es un
formulario ASP.NET WebForms con selects en cascada (Departamento ->
Provincia -> Distrito) por postback. Lima/Lima ya vienen preseleccionados
en la carga inicial de la página (verificado en sesión), así que para
cualquier distrito de la provincia de Lima alcanza con UN solo POST
reutilizando el __VIEWSTATE de esa carga inicial -- no hace falta
encadenar los postbacks intermedios de departamento->provincia.

Si en algún momento hace falta consultar otro departamento/provincia,
este módulo habría que extenderlo para encadenar esos postbacks (cada
uno necesita el __VIEWSTATE que devuelve el paso anterior) -- no
implementado porque el proyecto opera en Lima.
"""

import csv
import html as _htmllib
import re

import requests

URL = "https://rnf.mtc.gob.pe/Television"
CODIGO_DEPA_LIMA = "15"
CODIGO_PROVINCIA_LIMA = "1501"

# Fallback embebido (consultado 14/10/2026) por si la consulta en vivo al
# dropdown falla -- los distritos de Lima provincia no cambian seguido.
DISTRITOS_LIMA_FALLBACK = {
    "150102": "ANCON", "150103": "ATE", "150104": "BARRANCO",
    "150105": "BREÑA", "150106": "CARABAYLLO", "150107": "CHACLACAYO",
    "150108": "CHORRILLOS", "150109": "CIENEGUILLA", "150110": "COMAS",
    "150111": "EL AGUSTINO", "150112": "INDEPENDENCIA",
    "150113": "JESUS MARIA", "150114": "LA MOLINA", "150115": "LA VICTORIA",
    "150101": "LIMA", "150116": "LINCE", "150117": "LOS OLIVOS",
    "150118": "LURIGANCHO", "150119": "LURIN", "150120": "MAGDALENA DEL MAR",
    "150122": "MIRAFLORES", "150123": "PACHACAMAC", "150124": "PUCUSANA",
    "150121": "PUEBLO LIBRE", "150125": "PUENTE PIEDRA",
    "150126": "PUNTA HERMOSA", "150127": "PUNTA NEGRA", "150128": "RIMAC",
    "150129": "SAN BARTOLO", "150130": "SAN BORJA", "150131": "SAN ISIDRO",
    "150132": "SAN JUAN DE LURIGANCHO", "150133": "SAN JUAN DE MIRAFLORES",
    "150134": "SAN LUIS", "150135": "SAN MARTIN DE PORRES",
    "150136": "SAN MIGUEL", "150137": "SANTA ANITA",
    "150138": "SANTA MARIA DEL MAR", "150139": "SANTA ROSA",
    "150140": "SANTIAGO DE SURCO", "150141": "SURQUILLO",
    "150142": "VILLA EL SALVADOR", "150143": "VILLA MARIA DEL TRIUNFO",
}

MAPA_ESTADO = {"AUTORIZADO": "autorizada vigente", "": "disponible"}


def _extraer_campo(html_texto: str, nombre_id: str) -> str:
    m = re.search(rf'id="{nombre_id}" value="([^"]*)"', html_texto)
    return m.group(1) if m else ""


def obtener_distritos_lima(timeout: float = 15.0) -> dict:
    """Lista {codigo_ubigeo: nombre} de distritos de Lima provincia.
    Intenta refrescar en vivo; si falla (red, cambio de estructura del
    sitio), devuelve el fallback embebido sin levantar excepción."""
    try:
        r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        r.raise_for_status()
        m = re.search(
            r'<select name="ctl00\$ContentPlaceHolder1\$ddlDistrito".*?</select>',
            r.text, re.S,
        )
        opts = re.findall(r'<option(?:\s+selected="selected")?\s+value="([^"]+)">([^<]+)</option>', m.group(0))
        distritos = {v: _htmllib.unescape(n.strip()) for v, n in opts}
        return distritos if distritos else dict(DISTRITOS_LIMA_FALLBACK)
    except Exception:
        return dict(DISTRITOS_LIMA_FALLBACK)


def consultar_canales(codigo_distrito: str, banda: str = "UHF", timeout: float = 30.0) -> list[dict]:
    """Consulta el RNF para Lima/Lima/<codigo_distrito>.

    Returns:
        lista de {canal: int, estado_raw: str, razon_social: str}, una
        fila por cada canal 14-52 que el RNF devolvió para esa consulta
        (estado_raw == "" significa que no hay asignación -> disponible).
    """
    s = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0"}

    r = s.get(URL, headers=headers, timeout=timeout)
    r.raise_for_status()
    html_in = r.text

    data = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": _extraer_campo(html_in, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _extraer_campo(html_in, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _extraer_campo(html_in, "__EVENTVALIDATION"),
        "ctl00$ContentPlaceHolder1$rblBanda": banda,
        "ctl00$ContentPlaceHolder1$ddlDepa": CODIGO_DEPA_LIMA,
        "ctl00$ContentPlaceHolder1$ddlProvincia": CODIGO_PROVINCIA_LIMA,
        "ctl00$ContentPlaceHolder1$ddlDistrito": codigo_distrito,
        "ctl00$ContentPlaceHolder1$ibtnAceptar.x": "15",
        "ctl00$ContentPlaceHolder1$ibtnAceptar.y": "10",
    }
    r2 = s.post(URL, headers=headers, data=data, timeout=timeout)
    r2.raise_for_status()
    html_out = r2.text

    def extraer_todos(etiqueta):
        return dict(re.findall(rf'id="ContentPlaceHolder1_rptDetalle2_{etiqueta}_(\d+)">([^<]*)</span>', html_out))

    canal = extraer_todos("lblDepa")  # el id del control reusa "lblDepa" pero la columna es "Canal"
    razon = extraer_todos("lblRazon2")
    estado = extraer_todos("Label5")

    if not canal:
        raise RuntimeError(
            "El RNF no devolvió resultados -- la estructura de la página puede haber "
            "cambiado, o la consulta no encontró nada para este distrito/banda."
        )

    filas = []
    for i in sorted(canal.keys(), key=int):
        filas.append({
            "canal": int(canal[i]),
            "razon_social": _htmllib.unescape(razon.get(i, "")).strip(),
            "estado_raw": estado.get(i, "").strip(),
        })
    return filas


def guardar_csv_rnf(filas: list[dict], ruta: str) -> None:
    """Escribe filas en el formato canal,estado,razon_social que
    etiquetar_rnf.cargar_rnf() ya sabe leer."""
    with open(ruta, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["canal", "estado", "razon_social"])
        for fila in filas:
            estado = MAPA_ESTADO.get(fila["estado_raw"], fila["estado_raw"].lower() or "")
            w.writerow([fila["canal"], estado, fila["razon_social"]])
