# Requisitos de PA, LNA y otros elementos RF — verificación contra hoja técnica real

> **Propósito de este documento (actualizado 28/08/2026):** hasta el
> 28/08/2026 este documento era una guía para **buscar** candidatos
> comerciales de PA/LNA. Ya no lo es — el PA y el LNA están comprados, y
> `SPECS EQUIPOS/` tiene su hoja técnica real (`PA.md`, `LNA.md`). Este
> documento ahora es un **checklist de verificación**: compara los
> requisitos que el proyecto necesita contra lo que el componente
> realmente comprado cumple, punto por punto. Si en el futuro se evalúa un
> componente de repuesto o un modelo alternativo, la lista de requisitos
> (§3, §4) sigue sirviendo para eso también.
>
> **Fuente de las especificaciones reales: `SPECS EQUIPOS/`** — no este
> documento ni `PRESUPUESTO COMPLETO.xlsx`. Si una hoja técnica cambia,
> corregir ahí primero.

---

## 1. Contexto del proyecto (lo mínimo necesario para entender el "por qué")

Proyecto universitario (UNI, Perú, VRI 2026): radio cognitiva TVWS
(TV White Space, UHF 470–698 MHz) que da Internet a una comunidad rural sin
fibra, vía enlace punto a punto de 4 km (distancia final, 28/08/2026) con
dos nodos:

- **Gateway** (localidad con fibra): PC de especificación genérica (10-20
  núcleos, ver `SPECS EQUIPOS/COMPUTADORA_GATEWAY` — marca/modelo real sin
  confirmar), bladeRF 2.0 micro xA4. Corre toda la lógica cognitiva (CNN de
  sensado espectral + decisión de canal).
- **Cliente** (comunidad rural, sin red eléctrica confiable — batería/solar
  sin presupuestar todavía, ver `claudedocs/estructura_fisica_instalacion.md`
  §6.2): Orange Pi 5, **el mismo bladeRF 2.0 micro xA4** (mismo modelo que
  el Gateway). Solo demodula y ejecuta órdenes de salto de canal recibidas
  por control in-band.

Ambos nodos usan **OFDM** (512 subportadoras, 6 MHz de canal, modulación
adaptativa BPSK/QPSK/16-QAM, FEC convolucional o LDPC) y transmiten en la
**misma banda donde operan transmisores de TV licenciados (primarios)** —
por lo que cualquier distorsión que genere emisiones fuera de canal
(spectral regrowth) es un riesgo regulatorio real, no solo un problema de
calidad de señal. Esto es exactamente lo que la hoja técnica real del PA
**no** documenta (ACPR/OIP3 — ver §3.3), así que sigue siendo el gap más
importante de este checklist.

Presupuesto ajustado (algunos rubros del proyecto tienen tope ≤S/1000),
equipo de estudiantes sin instrumentación de laboratorio RF de precisión, y
**no existe distribuidor local en Perú para SDR/RF de nicho** (verificado —
ver `claudedocs/research_proveedores_bladerf_peru_20260702.md`).

---

## 2. Presupuesto de enlace actual (fuente: `LINK_BUDGET/`)

> Snapshot regenerado 05/09/2026, con las hojas técnicas reales de
> `SPECS EQUIPOS/PA.md` y `SPECS EQUIPOS/ANTENA_DIRECCIONAL`, la
> distancia final del enlace (4 km), y LOS confirmado por estudio de sitio
> — **no** recalcular a mano en este documento, correr `LINK_BUDGET/`.

| Parámetro | Downlink y Uplink (simétrico, mismo PA real ambos nodos) |
|---|---|
| TX SDR (a ganancia máxima) | +6 dBm — **no es el punto de operación real con PA conectado, ver §3.4** |
| Ganancia de antena (TX y RX) | 5 dBi a 500 MHz (real, WA5VJB — antes 6 dBi conservador, antes de eso 10 dBi de spec de compra nunca confirmado) |
| PA | "OEM 2W 1-900MHz" real, P1dB >32 dBm, clase A, backoff 7.5 dB → salida promedio +24.5 dBm |
| EIRP | +28.8 dBm (sin GDT) |
| Distancia de diseño | 4 km (final, 28/08/2026 — antes 6 km/rango 5-6 km) |
| Línea de vista | LOS confirmado por estudio de sitio (05/09/2026) — ya no se asume NLOS |
| Potencia recibida | ~-66.2 dBm (FSPL pura, sin término NLOS) |
| Margen BPSK / QPSK / 16-QAM | +34.5 / +31.5 / +25.5 dB |

**Conclusión:** el enlace cierra en las tres modulaciones con margen
amplio. Con LOS confirmado por estudio de sitio (05/09/2026, ya no NLOS),
incluso 16-QAM, bajo la reserva de fading estadístico (~10 dB,
`claudedocs/arquitectura_enlace_datos.md` §6), queda con margen residual
de **+15.5 dB** — un colchón amplio, no ajustado como en el snapshot
NLOS anterior (que dejaba solo +0.5 dB). Aun así, la reserva de ~10 dB en
sí sigue siendo una regla práctica sin medición de campo propia — su
justificación original (multipath NLOS) ya no aplica bajo LOS y necesita
revisarse cuando haya datos reales (`claudedocs/arquitectura_enlace_datos.md`
§8).

---

## 3. Verificación del PA contra `SPECS EQUIPOS/PA.md`

El componente real es **"PA OEM 2W 1-900MHz"**, mismo modelo en ambos
nodos (Gateway y Cliente) — ya no aplica la distinción "PA Gateway más
potente / PA Cliente a medida" que este documento tenía hasta el
20/08/2026 (ambos nodos confirmaron PA de 2W simétrico esa fecha).

### 3.1 Checklist punto por punto

| # | Requisito | Valor objetivo del proyecto | Valor real (`SPECS EQUIPOS/PA.md`) | ¿Cumple? |
|---|---|---|---|---|
| 1 | Rango de frecuencia | Cubre 470–698 MHz con margen | **1–900 MHz** | ✅ Cumple con amplio margen |
| 2 | Ganancia | ~27 dB | **30 dB típica a 500 MHz** (máx. 42 dB) | ✅ Cumple, algo más de lo esperado |
| 3 | Potencia de salida | 2 W (+33 dBm) P1dB nominal | **P1dB >32 dBm; +33 dBm es la potencia de salida máxima/Psat, no P1dB** — son cifras distintas en el datasheet real | ⚠ Cumple aproximadamente — el proyecto usaba "P1dB" y "Psat" como sinónimos; no lo son. `LINK_BUDGET/` ya usa 32 dBm (el piso documentado) |
| 4 | Clase de operación | Lineal — Clase AB (ver §3.2) | **Clase A** | ⚠ Excede el requisito (mejor linealidad) a costa de eficiencia — ver §3.2 |
| 5 | Backoff / P1dB | ≥6–9 dB de backoff | 7.5 dB sobre P1dB=32dBm → salida +24.5 dBm | ✅ Cumple, dentro del rango |
| 6 | ACPR o spec de linealidad equivalente | Documentado en hoja técnica | **No documentado** | ❌ Gap real — no hay forma de confirmar spectral regrowth sin medición propia |
| 7 | Entrada máxima tolerada | No se había pedido explícitamente antes | **+3 dBm** — el bladeRF a ganancia máxima entrega ~+5.7 dBm (por encima del límite) | ⚠ Requiere reducir la ganancia TX del bladeRF por software antes de conectar — ver §3.4, riesgo real si se opera mal |
| 8 | Eficiencia | Deseable, más crítico en el Cliente (batería/solar) | No documentada explícitamente; Clase A es la topología menos eficiente (15-35% típico) | ❌ Punto débil para el Cliente — agrava el vacío de alimentación ya señalado en `claudedocs/estructura_fisica_instalacion.md` §6.2 |
| 9 | Conectores | SMA en la entrada (pigtail desde bladeRF); salida hacia el resto de la cadena | **SMA-hembra ambos lados** | ✅ Cumple — y de hecho toda la cadena (antena, LNA) resultó ser SMA, no N como se documentaba antes (ver `claudedocs/estructura_fisica_instalacion.md`) |
| 10 | Alimentación DC | Verificar consumo | **12V DC, 300-400mA** (3.6-4.8W) | ✅ Dato confirmado — usar para dimensionar la batería del Cliente (§6.2 del doc de estructura física) |
| 11 | Térmico | Verificar si necesita disipador/ventilación | **PCB sobre disipador pasivo de aluminio estriado** — sin ventilador | ⚠ Sin ventilación activa; Clase A genera más calor que AB para la misma salida RF — vigilar temperatura en operación continua, sobre todo en el gabinete IP65 del Cliente sin refrigeración |
| 12 | Precio y disponibilidad | Verificar contra presupuesto | Ya comprado, S/165 c/u (`PRESUPUESTO COMPLETO.xlsx` #15) | ✅ Resuelto |
| 13 | Dimensiones físicas | No especificado antes | **55×40×30mm, 56g** | Informativo — cabe holgadamente en el gabinete IP65 (300×250×150mm) |

### 3.2 ¿El hecho de ser Clase A (no AB) es un problema?

**No es un defecto, es sobre-cumplimiento con una contrapartida.** Clase A
da la mejor linealidad posible (favorable para ACPR/spectral regrowth,
aunque no esté medido — punto 6 de la tabla), pero es la topología menos
eficiente (15–35% típico, consumo de reposo constante incluso sin
transmitir). Esto **no cambia el punto de operación de backoff** (7.5 dB
sigue siendo válido, calculado desde P1dB real) pero sí:

- **Agrava el problema de alimentación del Cliente** (`claudedocs/estructura_fisica_instalacion.md`
  §6.2) — un PA Clase A consume más DC por vatio de RF que uno Clase AB,
  y el presupuesto de energía del Cliente ya era un vacío antes de este
  dato.
- **Genera más calor** para la misma salida RF — relevante para el
  disipador pasivo sin ventilador (punto 11 de la tabla).

### 3.3 Gap real: ACPR no documentado

El único requisito que el datasheet real **no cubre** es la métrica más
directamente ligada al riesgo regulatorio (punto 6). El proyecto no tiene
instrumentación de laboratorio RF de precisión (§1) para medir esto de
forma independiente. Mientras no se mida:

- Operar dentro del rango de backoff decidido (7.5 dB, §2) es la única
  mitigación disponible — más backoff reduce distorsión, aunque no hay
  cifra de ACPR confirmada que diga cuánto exactamente.
- Tratar el cumplimiento normativo de PSD (`claudedocs/cumplimiento_normativo_tvws.md`)
  como válido para potencia media, no como garantía de que no hay
  spectral regrowth hacia canales TV adyacentes.

### 3.4 ⚠ Punto de operación del SDR — no conectar el PA a la ganancia máxima del bladeRF

Hallazgo nuevo (28/08/2026, al tener el datasheet real): el bladeRF a su
ganancia TX máxima entrega ~+6 dBm (~+5.7 dBm tras el pigtail) — **por
encima** de la entrada máxima tolerada del PA (+3 dBm). Con la ganancia
típica real del PA (30 dB a 500 MHz), el nivel de entrada necesario para
llegar al punto de operación decidido (+24.5 dBm de salida, backoff 7.5 dB)
es de aproximadamente **-5 a -6 dBm** — muy por debajo tanto del máximo del
bladeRF como del máximo tolerado por el PA. **Antes de conectar el PA**, hay
que bajar la ganancia TX del bladeRF por software (parámetro de
`gr-bladeRF`/`libbladeRF`, no un atenuador físico adicional — aunque el
kit de atenuadores SMA ya comprado, `PRESUPUESTO COMPLETO.xlsx` #2, sirve
como verificación de banco si se quiere confirmar el nivel antes de
conectar el PA real). No hacerlo arriesga sobrecargar la entrada del PA.

---

## 4. Verificación del LNA contra `SPECS EQUIPOS/LNA.md`

El componente real es **Nooelec LaNA**, mismo modelo para las 3 unidades
compradas (Gateway RX1, Cliente RX1, Gateway RX2/sensado).

| # | Requisito | Valor objetivo del proyecto | Valor real (`SPECS EQUIPOS/LNA.md`) | ¿Cumple? |
|---|---|---|---|---|
| 1 | Rango de frecuencia | 400–1000 MHz (cubre 470–698 MHz) | **20 MHz–4000 MHz** | ✅ Cumple con mucho margen |
| 2 | Figura de ruido (NF) | ≤1 dB | **0.8-1.0 dB (0.9 típico) a 1000 MHz** | ✅ Cumple — cifra a 1000 MHz, la más cercana disponible a la banda TVWS (no hay cifra específica a 470-698 MHz) |
| 3 | Ganancia | 15–25 dB | **+20 dB a 1000 MHz (S21)** | ✅ Cumple, dentro del rango |
| 4 | Manejo de señal grande (IIP3 / P1dB) | Alto, no solo mirar NF | **OP1dB 13-20 dBm (18 típico); entrada máxima 0 dBm** | ⚠ Dato de salida a compresión sí está, pero conviene no exceder los 0 dBm de entrada máxima — relevante si un primario de TV muy cercano/fuerte satura el LNA |
| 5 | Conectores | Compatibles con el resto de la cadena | **SMA-hembra ambos lados (RF Input, RF Output)** | ✅ Cumple — coincide con el PA y la antena, toda la cadena es SMA |
| 6 | Alimentación DC | Verificar consumo, especialmente Cliente | **3.3-5.5V (5V típico), 70-100mA (85 típico) — USB, bias-tee o pines** | ✅ Bajo consumo (~0.4-0.5W); bias-tee es alimentado por el propio bladeRF (circuito integrado en sus puertos RF, sin inyector externo — ver `claudedocs/estructura_fisica_instalacion.md` §6.1) |
| 7 | Montaje | Cerca de la antena, antes del tramo largo de cable | Dimensiones 80×30×20mm, 52g — módulo pequeño, encapsulado | ✅ Apto para montaje en el tope del mástil, ver plano en `claudedocs/estructura_fisica_instalacion.md` §3.2 |
| 8 | Precio y disponibilidad | Verificar presupuesto | Ya comprado (`PRESUPUESTO COMPLETO.xlsx` #4 y "Gastos de subvención" #4) | ✅ Resuelto |

**Conclusión LNA:** el componente real cumple todos los requisitos del
proyecto sin reservas — es el componente mejor verificado de los dos
(a diferencia del PA, que tiene el gap de ACPR).

---

## 5. Otros elementos RF ya definidos

| Elemento | Especificación real | Notas |
|---|---|---|
| Cable coaxial | LMR-400, longitud no fija — dimensionada en sitio (`claudedocs/estructura_fisica_instalacion.md`) | Conectores de terminación del cable comprado sin confirmar — todo el resto de la cadena (antena, LNA, PA, bladeRF) es SMA, ver `claudedocs/estructura_fisica_instalacion.md` |
| Antena LPDA (TX y RX, dedicadas) | WA5VJB 400-1000 MHz, **5 dBi a 500 MHz**, montaje SMA para PCB (`SPECS EQUIPOS/ANTENA_DIRECCIONAL`) | 4 compradas: 2 por nodo — presupuesto ítem #10. El spec de compra pedía ≥10 dBi; la hoja técnica real del fabricante da 5 dBi — `LINK_BUDGET/` ya usa este valor real |
| Antena discone (solo Gateway, sensado RX2) | Tram 1411, 25-1300 MHz, VSWR ≤1.5:1, **conector SO-239 confirmado**, montaje en mástil ≤35mm (`SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`) | No aplica al Cliente — presupuesto ítem #12. Ver `claudedocs/requisitos_antena_sensado.md` para el detalle y el conflicto de diámetro de mástil |
| Mástil | Trípode 3m, 2 tramos (Ø60mm y Ø48mm), 24kg, acero galvanizado ASTM-A123 (`SPECS EQUIPOS/MASTILES`) | Ver `claudedocs/estructura_fisica_instalacion.md` §5 |
| Gabinete Cliente | IP65, 300×250×150mm | 2 unidades compradas (presupuesto ítem #13), ver `claudedocs/estructura_fisica_instalacion.md` §7 sobre el destino de la segunda |

**GDT (protección de sobretensión):** eliminado del diseño el 28/08/2026 —
el enlace de validación opera continuo solo ~3 horas, no como instalación
permanente expuesta a temporada de tormentas, así que no hay línea de GDT
en el presupuesto ni en la cadena RF. Ver `claudedocs/estructura_fisica_instalacion.md`
para el razonamiento; reintroducir si el proyecto pasa a despliegue
permanente.

---

## 6. Si se evalúa un componente de repuesto o alternativo

Aunque el propósito principal de este documento cambió (de "buscar" a
"verificar"), la lista de requisitos de §3 y §4 sigue siendo válida para
evaluar un repuesto o modelo alternativo. Formato esperado:

1. **Indicar contra cuál checklist se evalúa** (PA §3, LNA §4).
2. **Tabla punto por punto**: cumple / no cumple / no especificado en la
   hoja técnica — mismo formato que las tablas de §3.1 y §4.
3. **Veredicto:** apto / apto con reservas / no apto — y por qué.
4. **Precio y disponibilidad de envío a Perú** si se puede determinar, sin
   inventar cifras si no hay dato confirmado.
5. Si falta un dato clave (ej. ACPR, IIP3), decirlo explícitamente en vez
   de asumir que cumple — el PA real comprado ya tiene este gap (§3.3), no
   repetir el mismo error de omisión con un candidato nuevo.
