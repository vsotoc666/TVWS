# Calculadora de Link Budget — TVWS

> **Fuente única de verdad para cifras de link budget.** Ninguna cifra de
> EIRP, NF, sensibilidad o margen (Downlink/Uplink) debe copiarse ni
> editarse a mano en otro documento — si cambia un parámetro (potencia,
> antena, LNA/PA, distancia, modulación), se corre esta herramienta y se
> re-exporta el resumen. `README.md` §9.1, `claudedocs/requisitos_pa_lna.md`
> y `claudedocs/bladerf_2_micro_xa4_specs.md` solo deben **citar/enlazar**
> aquí, no mantener su propia copia editable de estos números — eso fue lo
> que causó que la corrección de ganancia de antena (29/07/2026) tardara en
> propagarse a los 4 documentos que repetían la misma cifra.
>
> **Los parámetros de hardware (P1dB del PA, ganancia/NF del LNA, ganancia
> de antena) salen de `SPECS EQUIPOS/`** (actualizado 28/08/2026) — esa
> carpeta es la única fuente para características de equipos ya comprados,
> un archivo por equipo (`PA.md`, `LNA.md`, `ANTENA_DIRECCIONAL`, etc.). Si
> cambia una hoja técnica ahí, recalcular acá con los valores nuevos.

Calculadora oficial del presupuesto de enlace del proyecto (Downlink, Uplink y
autointerferencia full-duplex). Reemplaza el recálculo manual en README.md
§9.1, `claudedocs/requisitos_pa_lna.md` y `claudedocs/bladerf_2_micro_xa4_specs.md`
cada vez que cambia una potencia, una antena, un LNA/PA, la distancia o la
modulación — usa esta herramienta y exporta el resumen en vez de editar cifras
a mano en varios documentos.

## Uso

```bash
cd LINK_BUDGET
pip install -r requirements.txt
streamlit run app.py
```

Se abre en el navegador (por defecto `http://localhost:8501`). Todos los
parámetros son editables desde la interfaz; cada campo tiene un tooltip (ícono
`?`) con su valor por defecto y de dónde sale (documento + sección, o
"estimado" si el proyecto no lo documenta con una cifra explícita).

## Estructura

- `core.py` — motor de cálculo puro (sin dependencia de Streamlit): fórmulas
  de FSPL, cascada de ruido de Friis, EIRP, sensibilidad y margen. Reutilizable
  desde un script o notebook si se necesita fuera de la interfaz.
- `app.py` — interfaz Streamlit sobre `core.py`.

## Qué incluye

- **Downlink y Uplink completos**, con cadena TX (SDR → pigtail → PA opcional
  → cable → GDT opcional → antena, GDT en 0 dB por defecto — ver nota abajo)
  y cadena RX (antena → pérdida antes del LNA → LNA → cable → pigtail → SDR)
  totalmente editables.
- **Autointerferencia full-duplex** (TX propio hacia RX propio, mismo nodo) —
  el riesgo #1 documentado en `claudedocs/riesgos_arquitectura_transmision.md`.
- **Modulación configurable** (BPSK/QPSK/16-QAM, SNR mínimo editable) — el
  margen y la sensibilidad se recalculan para cualquier combinación.
- **Exportación** del resumen a CSV o tabla Markdown, lista para pegar en un
  documento si se decide actualizar las cifras oficiales.

## Verificado contra el proyecto (05/09/2026 — LOS confirmado por estudio de sitio)

Con los valores por defecto actuales (PA real "OEM 2W 1-900MHz" con P1dB 32
dBm en **ambos** nodos, backoff 7.5 dB, antena LPDA real 5 dBi, LNA Nooelec
LaNA real 20 dB/0.9 dB NF, distancia final del enlace **4 km**, **sin GDT**,
**pérdida NLOS 0 dB** — un estudio de sitio confirmó línea de vista (LOS)
despejada entre Gateway y Cliente a esta distancia, ya no el supuesto NLOS
de 15 dB usado hasta el 04/09/2026), el motor da (dentro de ~0.1 dB):

- EIRP Downlink = Uplink (enlace ahora simétrico): +28.8 dBm (sin cambio — LOS no afecta EIRP)
- Salida promedio del PA: +24.5 dBm (P1dB 32 dBm − backoff 7.5 dB, sin cambio)
- Pérdida de trayecto: ahora es FSPL pura, sin término NLOS — 100.0 dB a 4 km/600 MHz (antes 115.0 dB con los 15 dB de NLOS)
- NF de sistema: ~0.94 dB (sin cambio — no depende del trayecto)
- Margen a 4 km: **BPSK +34.5 dB, QPSK +31.5 dB, 16-QAM +25.5 dB** (ambas direcciones) — sube ~15 dB en cada modulación respecto al snapshot NLOS anterior (+19.5/+16.5/+10.5 dB), exactamente el término NLOS que se retiró
- Potencia conducida a la antena: ~23.8 dBm → PSD ≈ 6.0-6.5 dBm/100kHz, dentro
  del límite legal de 12.6 dBm/100kHz (Art. 8, `Decreto_Supremo_024-2021-MTC_TVWS.pdf`)
  con ~6.1-6.6 dB de margen — ver `claudedocs/cumplimiento_normativo_tvws.md`
  (este cálculo no depende de la distancia ni de NLOS/LOS, solo de la potencia conducida).

**Los tres modos cierran con margen amplio** una vez confirmado LOS —
16-QAM pasa de ser el modo "oportunista, apenas cierra" (+10.5 dB, +0.5 dB
tras reservar ~10 dB de fading) a tener +25.5 dB de margen total, con
colchón de sobra incluso reservando margen de fading estadístico (todavía
sin medir en campo, ver `claudedocs/arquitectura_enlace_datos.md` §6/§8).
No cambia qué modo es "el default operativo" per se — eso lo decide la CNN
de margen en tiempo real — pero sí elimina el riesgo de que 16-QAM no
cierre bajo fading que existía en el escenario NLOS.

> **Corrección con hojas técnicas reales (28/08/2026, histórico):** hasta
> esa fecha el PA se modelaba con P1dB nominal genérico de +33 dBm y la
> antena con 6 dBi (valor conservador sin datasheet, corregido de un spec
> de compra de ≥10 dBi nunca confirmado por el fabricante real). Con las
> hojas técnicas reales de `SPECS EQUIPOS/` (PA "OEM 2W 1-900MHz": P1dB
> real >32 dBm, no 33; antena WA5VJB 400-1000MHz: 5 dBi a 500 MHz, no 6 ni
> 10), el EIRP bajó ~2 dB y el margen bajó ~2.9 dB en cada modulación
> respecto al snapshot anterior de esa época. El LNA (Nooelec LaNA real: NF
> 0.9 dB, ganancia 20 dB) resultó prácticamente igual a lo que se asumía,
> así que el NF de sistema mejora levemente (~0.94 dB vs ~1.04 dB).
>
> **LOS confirmado por estudio de sitio (05/09/2026):** un estudio de sitio
> confirmó línea de vista despejada entre Gateway y Cliente a los 4 km de
> distancia final — no es un supuesto simplificador ni un TBD pendiente de
> validar, es un hecho de campo. `perdida_nlos_db` pasa de 15.0 dB (asumido)
> a 0.0 dB (LOS confirmado) por defecto en `core.py`; el campo se conserva
> por si alguien quiere modelar un escenario NLOS hipotético desde la
> interfaz. Esto no cambia ningún otro parámetro de hardware — solo el
> término de pérdida de trayecto.

> **GDT eliminado (28/08/2026):** el proyecto decidió no usar descargador de
> sobretensión (GDT) en ninguna rama RF — el enlace de validación opera
> continuo solo ~3 horas, no como instalación permanente expuesta a
> temporada de tormentas. `perdida_gdt_db` quedó en 0.0 dB por defecto.
> Ver `claudedocs/estructura_fisica_instalacion.md` para el razonamiento y el
> plano de instalación sin GDT.

> **Historial:** hasta el 20/08/2026 los valores por defecto reproducían un
> escenario previo (distancia de diseño 15 km, PA asimétrico Gateway 2W/Cliente
> ~26-29 dBm objetivo, sin backoff aplicado a la potencia de salida) que daba
> EIRP Downlink +37.7 dBm y dejaba el Uplink con margen muy ajustado o sin
> cerrar en QPSK/16-QAM. Se reemplazó al confirmarse PA de 2 W en ambos nodos,
> backoff real de operación, y la distancia real del enlace (5-6 km, no 10-15 km).
> **28/08/2026:** la distancia final del enlace quedó fijada en **4 km**
> (ya no el rango 5-6 km ni el extremo pesimista de 6 km usado como default).

Ver la pestaña **"ℹ️ Ayuda / fórmulas"** dentro de la app para las fórmulas
completas y qué está documentado vs. estimado.

## ✅ Resuelto (28/08/2026): posición del LNA respecto al cable largo

El NF de sistema documentado (~1.0–1.04 dB, `README.md` §9.1) **solo se
reproduce si la pérdida de cable antes del LNA es ~0 dB** — es decir, si el
LNA está montado literalmente en el punto de alimentación de la antena, tal
como pide `claudedocs/requisitos_pa_lna.md` §4 punto 7 ("Montaje: cerca de
la antena, antes del tramo largo de cable").

Esto ya no es una discrepancia abierta: `claudedocs/estructura_fisica_instalacion.md`
§3.2 fija la instalación física real como

```
LPDA RX → jumper corto → LNA (en el tope del mástil, junto a la antena) →
LMR-400 (tramo largo, longitud no fija) → RG-316 pigtail → bladeRF
```

es decir, el LNA va **antes** del tramo largo de cable, no después — con eso
el NF de sistema documentado (~1.04 dB) sí se reproduce. Si en algún momento
se instala distinto a esto (LNA después del tramo largo), el NF real subiría
a ~1.3–1.9 dB — usa el campo **"Pérdida cable ANTES del LNA"** en
Downlink/Uplink (dentro de la app) para explorar ese escenario.
