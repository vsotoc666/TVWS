# Brief — Pruebas alternativas: banco cableado full-duplex (sin LNA/PA)

> **Tipo de doc:** kickoff/brief (como `brief_enlace_gemelo_digital.md` en su
> momento) — punto de partida para desarrollar esta línea de pruebas a lo
> largo de muchas sesiones futuras, no la especificación cerrada. Actualizar
> este mismo archivo a medida que se cierren decisiones; no crear un doc
> paralelo (ver "Cómo mantener esta documentación sincronizada" en
> `CLAUDE.md`).
>
> Creado: 13/09/2026.

## 0. Qué es esto y dónde encaja

Esta NO es una arquitectura nueva del enlace. Es el desarrollo detallado de
la **Fase 4** que `claudedocs/arquitectura_transmision_datos.md` ya
preveía y dejó abierta ("Con SDR real, en banco, cable/atenuador — requiere
hardware", pruebas #16-18) — la fase intermedia entre el loopback 100%
software ya aprobado (`TRANSMISION/pruebas/`, 15/15) y el enlace real de
campo por antena a 4 km (Fase 5 del mismo doc). El kit de atenuadores SMA
para esto **ya está comprado** (`PRESUPUESTO COMPLETO.xlsx` #2, citado en
`claudedocs/requisitos_pa_lna.md` §3.4).

Lo que este brief agrega sobre el plan original de Fase 4 (que solo decía
"cable/atenuador", genérico):

1. **Full-duplex real y simultáneo** (no half-duplex TDD por software del
   diseño de campo, §3.1 de `README.md`) — motivo en §2.
2. **Sin LNA ni PA en la cadena de datos** — el cable + atenuador reemplaza
   directamente a antena+aire+LNA/PA; los niveles se controlan por
   atenuación fija/variable y ganancia de software del bladeRF, no por
   amplificación de hardware.
3. **La cadena de sensado (RX2 + discone) sigue operando igual que en el
   diseño de campo** — antena real, aire real, barrido de 5 posiciones,
   CNN, mapa de 39 canales. Solo el enlace de **datos** (TX1/RX1) se
   reemplaza por cable; el sensado no se simula.
4. **Dos sitios de ejecución: UNI (Lima) y Huánuco** — ver §7 para el
   supuesto de trabajo sobre el rol de cada uno (a confirmar con el equipo).

**Relación con el diseño de campo (half-duplex TDD, §3.1 de `README.md`):
no lo reemplaza.** El diseño de despliegue en campo sigue siendo TDD por
software — eso no cambia por este brief. Esto es una vía de validación
adicional que corre en paralelo, aprovechando que el banco cableado no
tiene el problema físico que forzó a descartar full-duplex en campo (§2).
Si algo de acá termina informando una revisión del diseño de campo, se
actualiza `README.md`/`riesgos_arquitectura_transmision.md` explícitamente
citando este brief como origen — no al revés.

---

## 1. Objetivo

Validar el **bloque cognitivo GNU Radio completo** (Capas 1-5 de `README.md`
§2.2: `RadioInterface`, `SpectralSensor`+CNN, `CognitiveEngine`,
`InbandControlLayer`) operando **con dos bladeRF reales**, en un esquema
**full-duplex simultáneo** DL/UL, con el canal de propagación simulado por
atenuación fija/calibrada en vez de antenas y trayecto real — antes de
necesitar el hardware de campo completo (PA, LNA, antenas LPDA/discone
montadas, mástil, 4 km LOS).

Preguntas concretas que este banco debe responder (no son todas del mismo
peso — priorizar de arriba hacia abajo si el tiempo aprieta):

1. ¿El control in-band bidireccional (Formatos A/B/C, subportadoras
   #254/256/257) funciona igual de bien cuando DL y UL corren
   **simultáneos** (full-duplex) en vez de alternados por slot TDD? Esto
   nunca se probó — todo el trabajo de `SDR/inband_control.py` y
   `TRANSMISION/pruebas/` asume half-duplex por software.
2. ¿Cuánto aislamiento TX↔RX hay realmente **dentro de un mismo bladeRF**
   (acoplamiento intra-chip AD9361, no por antena) cuando TX1 y RX1
   transmiten/reciben simultáneamente? Esto decide si full-duplex real es
   viable en este hardware específico, con cables dedicados, sin el
   problema de antena del Problema 1.
3. ¿El `CognitiveEngine` decide y ejecuta saltos de canal correctamente
   (Targeted Rendezvous, §7.4 de `README.md`) cuando el "canal" es en
   realidad una atenuación fija en un cable de banda ancha, no un canal TV
   real con propagación variable?
4. ¿La cadena completa (MAC/FEC/MOD/OFDM, ya validada en software) se
   sostiene con hardware real de extremo a extremo (DAC/ADC del AD9361,
   calibración de DC offset/IQ) en el nivel de atenuación calculado para
   simular 4 km?

---

## 2. Por qué full-duplex es viable aquí (y no lo es en campo)

`claudedocs/riesgos_arquitectura_transmision.md`, Problema 1, descartó
full-duplex real en campo (26/07/2026) porque el aislamiento TX→RX
**requerido** (~90-110 dB, para que el receptor de un nodo no se sature con
su propio TX de 2W) supera por mucho el aislamiento **disponible** solo por
separación física/angular de dos antenas LPDA en el mismo mástil (~30-50 dB
estimado).

**Ese déficit es específico del acoplamiento por aire entre dos antenas
compartiendo el mismo mástil.** En el banco cableado propuesto aquí:

- TX1 y RX1 de cada bladeRF son **puertos SMA físicamente distintos**
  (`SPECS EQUIPOS/SDR_ENLACE`: "4x conectores SMA Hembra — 2x TX, 2x RX"),
  cada uno conectado por su propio cable/atenuador dedicado al nodo
  contrario — no hay una antena compartida a la que ambos "escuchen".
- El acoplamiento cruzado que queda no es por aire sino **intra-chip**
  (AD9361, fuga entre las cadenas TX/RX del mismo transceptor) — una
  cifra de aislamiento distinta y, en principio, mucho más alta que 30-50
  dB (el datasheet del AD9361 ya en el repo, `SPECS EQUIPOS/`, documenta
  fugas del orden de −95 a −122 dBm para LO leakage, ver
  `SPECS EQUIPOS/SDR_ENLACE` "Impairments RF" — pero esa cifra es sobre
  fuga de LO, **no** el aislamiento TX-puerto→RX-puerto que hace falta
  para esta pregunta; **queda como verificación pendiente**, no asumir
  que aplica directo).

**⚠ Esto es una hipótesis de trabajo, no un hecho verificado.** La primera
sub-prueba del banco (§5, Fase 4a-1) es precisamente medir ese aislamiento
real antes de asumir que el full-duplex cableado funciona. Si el
aislamiento intra-chip resulta insuficiente también, este brief debe
registrar ese hallazgo igual que `riesgos_arquitectura_transmision.md`
registró el de antena — no se descarta la posibilidad de que full-duplex
tampoco cierre aquí.

---

## 3. Arquitectura propuesta del banco

Reemplaza, solo para el enlace de **datos** (TX1/RX1), la cadena de campo
(antena LPDA → LNA/PA → aire → LNA/PA → antena LPDA) por cable + atenuador
punto a punto. La cadena de **sensado** (RX2 + discone) no cambia.

```
NODO GATEWAY                                          NODO CLIENTE
(Mini PC / Orange Pi 5, según qué máquina esté         (el otro nodo del par)
disponible en cada sitio — ver §7)

┌─────────────────────┐                          ┌─────────────────────┐
│ bladeRF 2.0 micro xA4│                          │ bladeRF 2.0 micro xA4│
│                      │                          │                      │
│  TX1 (SMA) ──────────┼── cable + ATT (DL) ──────┼──▶ RX1 (SMA)         │
│                      │      calibrado a         │                      │
│  RX1 (SMA) ◀─────────┼── cable + ATT (UL) ──────┼── TX1 (SMA)          │
│                      │      FSPL simulado       │                      │
│  RX2 (SMA) ──────────┼── LNA sensado ── discone  │  (RX2 no aplica —   │
│  (sensado, sin       │      (aire real, TVWS     │   solo el Gateway    │
│   cambios vs campo)  │      real)                │   sensa, §3.3 de     │
│                      │                          │   README.md)         │
└─────────────────────┘                          └─────────────────────┘
```

**Puntos clave:**

- **Dos caminos de cable independientes** (DL: Gateway TX1→Cliente RX1; UL:
  Cliente TX1→Gateway RX1), cada uno con su propio atenuador — full-duplex
  real porque ambos caminos pueden llevar señal simultáneamente sin
  compartir medio.
- **Sin LNA ni PA en TX1/RX1** — el atenuador en línea reemplaza a la vez la
  ganancia del PA (negativa, en vez de positiva) y la pérdida de espacio
  libre; no hace falta el LNA porque no hay una pérdida de cable larga que
  compensar (el "cable" aquí es corto, de banco).
- **RX2/discone/LNA-sensado sin cambios** respecto al diseño de campo — es
  la única antena real de todo el banco, sensando el espectro TVWS real del
  sitio (Lima o Huánuco, con ocupación real de canales TV distinta en cada
  uno — dato interesante en sí mismo, ver §7).
- **Ganancia TX/RX del bladeRF por software** ajustada para no saturar
  (mismo cuidado que con el PA real, `claudedocs/requisitos_pa_lna.md`
  §3.4, pero aquí el límite es el rango dinámico del propio AD9361, no la
  entrada máxima de un PA externo).

---

## 4. Cálculo de la atenuación a usar (ejecutado 13/09/2026)

**Cambio de criterio respecto a la primera versión de este brief:** en vez
de calibrar al punto de diseño de campo (4 km, con margen enorme:
+34.5/+31.5/+25.5 dB), estas pruebas se calibran a la **distancia máxima
que el enlace real podría alcanzar** con el PA (2W, backoff 7.5 dB) y el
LNA (Nooelec LaNA, +20 dB/NF 0.9 dB) que el proyecto va a usar —
i.e. el punto donde el margen de enlace llega a 0 dB. Es el escenario más
exigente que el hardware real podría enfrentar, no el punto de diseño
cómodo.

**Cómo se ejecutó:** `LINK_BUDGET/app.py` es una app Streamlit interactiva
(requiere navegador); en este entorno sin sesión gráfica se corrió el mismo
motor que usa (`LINK_BUDGET/core.py::calcular_enlace`/`fspl_db`, sin pasar
por la UI) desde un script directo. Antes de extrapolar, se verificó que
reproduce exactamente el link budget ya documentado a 4 km — **EIRP
+28.80 dBm, PRx −66.24 dBm, márgenes +34.53/+31.53/+25.53 dB
BPSK/QPSK/16-QAM** (coincide con `README.md` §9.1) — confirmando que los
defaults de `core.py` (hardware real de `SPECS EQUIPOS/`) están bien
calibrados antes de usarlos para este cálculo nuevo.

### 4.1 Distancia máxima por modulación (mismo PA/LNA reales, LOS ideal)

| Modulación | Distancia máxima teórica (margen = 0 dB) | FSPL en ese punto | Distancia práctica (colchón 6 dB*) | FSPL en ese punto |
|---|---|---|---|---|
| BPSK | 213.1 km | 134.6 dB | 106.8 km | 128.6 dB |
| QPSK | 150.9 km | 131.6 dB | 75.6 km | 125.6 dB |
| 16-QAM | 75.6 km | 125.6 dB | 37.9 km | 119.6 dB |

*Colchón de 6 dB sugerido por consistencia con el rango de backoff que el
proyecto ya usa en otras decisiones (6-9 dB, `requisitos_pa_lna.md`
§3.1/§3.2) — el margen-0 exacto es un límite matemático, no un punto de
operación repetible para una demo (cualquier variación de ±1dB en la
calibración del atenuador tumba la demodulación).

**⚠ Estas distancias son un límite puramente matemático de FSPL (Friis),
asumiendo LOS ideal sin curvatura de la Tierra, obstrucción de zona de
Fresnel, lluvia ni ningún otro factor real — 200 km terrestres a 600 MHz
con una antena LPDA de 5 dBi es físicamente irreal como enlace de campo.**
No se están proponiendo estos kilómetros como alcance real del sistema —
son el valor de FSPL a usar como calibración del atenuador, que es
exactamente lo que un atenuador puede reproducir sin importar si la
distancia real es plausible o no.

### 4.2 De FSPL a atenuador de banco (sin PA ni LNA en la cadena de datos)

El banco (§3) no tiene PA ni LNA en TX1/RX1 — solo el atenuador. Por eso el
atenuador **no es igual a la FSPL pura**: hay que compensar que el banco
tampoco tiene la ganancia del PA (+18.8 dB efectivos sobre el bladeRF
solo) ni la del LNA (+20 dB) que sí tendría la cadena de campo real. El
atenuador de banco se calculó igualando el nivel de señal que llegaría al
puerto RX del bladeRF en ambos casos (campo real con LNA vs. banco sin
LNA), no solo copiando el número de FSPL:

| Modulación | Escenario | Atenuador de banco (bladeRF→ATT→bladeRF, sin PA/LNA) | Kits de 42 dB necesarios |
|---|---|---|---|
| BPSK | Máxima teórica | 87.2 dB | 3 |
| BPSK | Práctica (colchón 6dB) | 81.2 dB | 2 |
| QPSK | Máxima teórica | 84.2 dB | 3 |
| QPSK | Práctica (colchón 6dB) | 78.2 dB | 2 |
| 16-QAM | Máxima teórica | 78.2 dB | 2 |
| 16-QAM | Práctica (colchón 6dB) | 72.2 dB | 2 |
| — | Referencia: 4 km (diseño original de campo) | 52.6 dB | 2 |

**⚠ Caveat de NF no compensado (secundario frente al hallazgo de §4.3):**
igualar el nivel de señal en dBm no iguala el margen exacto, porque el
banco sin LNA tiene peor NF nativo del AD9361 (2.5 dB) que la cadena de
campo con LNA (NF de sistema 0.94 dB) — una diferencia de ~1.5 dB. A
igual nivel de señal, el margen real en el banco es ~1.5 dB menor que en
campo. Para las pruebas de margen-0 exacto esto puede tumbar la
demodulación un poco antes de lo calculado; para las de colchón 6dB no
debería importar en la práctica.

### 4.3 🔴 Hallazgo bloqueante: el kit de atenuadores ya comprado no alcanza

El kit ya comprado (`PRESUPUESTO COMPLETO.xlsx` #12, verificado
13/09/2026: **"SMA Attenuator Kit — 1 dB a 42 dB en pasos de 1 dB, 6 pads,
2W máx."**) da como máximo **42 dB en serie** con todos sus pads. Ningún
escenario de §4.2 (72-87 dB, o incluso los 52.6 dB del punto de diseño
original de 4 km) es alcanzable con un solo kit.

- Con **2 kits en serie (84 dB total)** se cubren los 6 escenarios
  "práctica (colchón 6dB)" de §4.2 (máximo requerido: 81.2 dB) — **1 kit
  idéntico adicional resuelve esto** para el objetivo práctico.
- Con **3 kits en serie (126 dB total)** se cubren además los 3 escenarios
  de "máxima teórica" (máximo requerido: 87.2 dB).
- **VSWR de cascada — verificado 13/09/2026, ya no es una incógnita**: el
  producto real (identificado por búsqueda web, ver §6.1) es el **Nooelec
  SMA Attenuator Kit**, con VSWR <1.2 (típico <1.1) hasta 6 GHz por
  pad — suficientemente bueno como para cascadear 2-3 kits sin
  desadaptación relevante en la banda TVWS. Sigue pendiente vigilar
  blindaje/apriete de conectores a partir de ~60-80 dB total (fugas de RF
  alrededor del atenuador, no un problema del componente en sí).

**Acción recomendada:** comprar 2 kits idénticos adicionales (mismo
SKU, Nooelec — pedido armado en §6.1) para llegar a 3 kits (126 dB) y
cubrir todos los escenarios de §4.2, incluida la distancia máxima teórica.
Si el presupuesto/tiempo solo permite 1 kit adicional, cubre igual los 3
escenarios "práctica (colchón 6dB)" (2 kits, 84 dB). Si no es viable a
tiempo ninguna compra, empezar la Fase 4a con el kit actual (42 dB,
equivalente a ~1.2 km de campo real sin PA en el banco, ~135 m con PA en
el banco — ver cálculo completo en el script de referencia) para validar
el hardware básico (4a-1, 4a-2) mientras se consigue la atenuación
adicional para 4a-3 en adelante.

### 4.4 Nota sobre variación de FSPL dentro de TVWS

Los atenuadores fijos de banco típicos son de banda ancha (DC-6 GHz o
similar) — la atenuación no cambia apreciablemente al saltar de canal
dentro de TVWS (470-698 MHz), a diferencia del FSPL real que sí varía ~3.4
dB entre extremos de la banda (`README.md` §7.4, nota histórica sobre 470
MHz vs 698 MHz). Si esa variación importa para alguna prueba específica de
salto de canal, hace falta un atenuador variable o recalibrar entre
pruebas — dejar marcado, no asumido, hasta decidir si es necesario.

---

## 5. Fases de prueba propuestas (Fase 4a — inserta antes de la Fase 4 original)

Sigue la convención de `TRANSMISION/pruebas/` (carpeta por prueba, README +
código reusable). Sugerido: `TRANSMISION/pruebas/fase4a_banco_cableado_fd/`,
con sub-carpetas `pruebaXX_nombre/` igual que las fases existentes.

| # | Prueba | Qué confirma | Bloquea con |
|---|---|---|---|
| 4a-1 | Medir aislamiento TX1→RX1 intra-bladeRF (TX activo a potencia conocida, medir qué llega al RX1 del mismo equipo sin el cable cruzado conectado) | Verifica o refuta la hipótesis de §2 antes de construir nada más sobre ella | Nada — es la primera prueba, sin dependencias. **🟡 Diseñada y auto-validada en software 13/09/2026** — código + metodología completa en `TRANSMISION/pruebas/fase4a_banco_cableado_fd/prueba4a1_aislamiento_intrachip/`, pendiente de correr con bladeRF real |
| 4a-2 | Loopback simple: un bladeRF, TX1→cable/ATT→RX1 propio (sin segundo nodo) | El hardware real (DAC/ADC) no rompe lo ya validado en software (Fase 3, `TRANSMISION/pruebas/fase3_loopback_completo/`) — equivale a la prueba #16 ya prevista, ahora con el atenuador calibrado de §4 | 4a-1 (saber cuánto aislamiento hay entre los dos puertos del mismo equipo antes de fiarse del loopback) |
| 4a-3 | Dos bladeRF por cable, half-duplex (TDD software, como en el diseño de campo) — línea base de comparación | Confirma que el banco cableado reproduce el comportamiento ya conocido de TDD antes de complicar con full-duplex — equivale a la prueba #18 ya prevista | 4a-2 |
| 4a-4 | Dos bladeRF por cable, **full-duplex real simultáneo** — DL y UL activos al mismo tiempo | Responde la pregunta central de este brief (§1.1-2): ¿el control in-band y la cadena OFDM sobreviven full-duplex real con este hardware? | 4a-1, 4a-3 (comparar contra la línea base half-duplex) |
| 4a-5 | Full-duplex + salto de canal ordenado a mitad de transmisión (Formato A) | Pérdida de paquetes acotada, igual que la prueba #17 original pero en full-duplex | 4a-4 |
| 4a-6 | Full-duplex + degradación abrupta simulada (subir atenuación de golpe) → Targeted Rendezvous (§7.4 `README.md`) | El protocolo de contingencia funciona con canal simulado, no solo en el papel | 4a-4 |
| 4a-7 | Full-duplex + sensado real simultáneo (RX2/discone activa, CNN corriendo, `CognitiveEngine` recibiendo el mapa de 39 canales real del sitio) | Integración de las 5 capas completas, no solo el enlace de datos aislado | 4a-4, IA/ (modelo entrenado y exportado a ONNX) |
| 4a-8 | Throughput sostenido en full-duplex, por modo de modulación/FEC | Comparar contra la tabla de §5.3 de `README.md` (que asume TDD 50/50) — full-duplex sin duty cycle debería, en teoría, duplicar el throughput por dirección si el aislamiento cierra | 4a-4 |

**Prioridad si el tiempo aprieta:** 4a-1 primero siempre — si el aislamiento
intra-chip no alcanza, el resto de la fila full-duplex (4a-4 en adelante)
no tiene sentido intentarla y el banco colapsa a ser simplemente una
versión cableada de TDD (4a-2/4a-3), que igual vale la pena como
validación de hardware aunque no responda la pregunta de full-duplex.

---

## 6. Material adicional necesario / a verificar

| Ítem | Estado |
|---|---|
| Kit de atenuadores SMA | Ya comprado 1x (`PRESUPUESTO COMPLETO.xlsx`, hoja "Requerimientos", fila N° 2: "JUEGO DE ATENUADORES FIJOS 2 W CON CONECTOR SMA X 6", modelo "SMA Attenuator Kit - 1dB to 42dB..."). **🔴 Insuficiente en solitario** — máximo 42 dB, muy por debajo de los 72-87 dB que necesita cualquier escenario de §4.2 (incluso el punto de diseño original de 4 km, 52.6 dB, ya lo supera). **Pedido de 2 kits idénticos adicionales armado en §6.1** — con 2 kits (84 dB) alcanza para los 3 escenarios "práctica" de §4.2, con 3 kits (126 dB, el pedido de §6.1) alcanza también los "máxima teórica". Ver §4.3. |
| Cables SMA-SMA cortos (pigtail) para las 2 rutas cruzadas (DL/UL) | A verificar — el proyecto ya tiene pigtails LMR-100 para la cadena de campo (`diagrama_tvws.md`); confirmar si alcanza con esos o hace falta comprar cables adicionales para banco |
| Segundo bladeRF disponible en el mismo sitio simultáneamente | **Bloqueante lógico** — el proyecto tiene 2 unidades (1 Gateway + 1 Cliente, `SPECS EQUIPOS/SDR_ENLACE`); confirmar logística de tener ambas en la UNI (o en Huánuco) al mismo tiempo sin dejar al otro nodo sin equipo para otras pruebas en curso |
| Discone + LNA de sensado disponibles en el sitio de prueba | Depende de si se prueba en UNI, Huánuco, o ambos — ver §7 |
| Medidor de potencia RF (opcional pero recomendado) | El proyecto no reportó instrumentación de laboratorio RF de precisión (`claudedocs/requisitos_pa_lna.md` §3.3) — sin esto, calibrar el atenuador por cálculo (§4) y verificar indirectamente por BER/constelación, no por medición directa de potencia |

### 6.1 Pedido — kits de atenuadores adicionales

Identificado por búsqueda web (13/09/2026) contra la descripción exacta del
ítem ya comprado: es el **Nooelec SMA Attenuator Kit** (ASIN
`B07YYMT65T`), 6 pads SMA macho-hembra de 1/2/3/6/10/20 dB (suman 42 dB en
serie), 2W máx., VSWR <1.2 (típico <1.1) hasta 6 GHz — mismo modelo exacto
que el ya comprado, así que no hace falta re-evaluar alternativas ni
volver a calificar el componente.

**Fila lista para copiar a `PRESUPUESTO COMPLETO.xlsx` (hoja
"Requerimientos"), mismo formato que la fila N° 2 existente:**

| N° | DENOMINACIÓN | SUSTENTO DEL BIEN DE ACUERDO A LOS OBJETIVOS DEL PROYECTO | CANT. | MODELO |
|---|---|---|---|---|
| 2b | JUEGO DE ATENUADORES FIJOS 2 W CON CONECTOR SMA X 6 (adicional, mismo modelo que fila N° 2) | Amplía el rango de atenuación total en cascada (42 dB → 126 dB con 3 kits en serie) para simular en el banco cableado la distancia máxima de enlace alcanzable con el PA/LNA reales del proyecto (§4 de `claudedocs/brief_pruebas_banco_cableado_fullduplex.md`), no solo la distancia de diseño de 4 km — la Fase 4a (validación full-duplex del bloque cognitivo) no es ejecutable sin esta atenuación adicional. | 2 | SMA Attenuator Kit - 1dB to 42dB of Attenuation in 1dB Increments. Pack of 6. 2W maximum power (Nooelec, ASIN B07YYMT65T — mismo modelo que la fila N° 2) |

- **Cantidad recomendada: 2 unidades** (para llegar a 3 kits en total, 126
  dB combinados — cubre los 6 escenarios de §4.2 incluida la distancia
  máxima teórica). Si el presupuesto solo alcanza para 1 unidad adicional
  (2 kits, 84 dB total), cubre igual los 3 escenarios "práctica (colchón
  6dB)" — ver tabla de §4.2 antes de decidir cuál priorizar.
- **Precio de referencia:** la fila N° 2 ya pagó US$ 116 (S/ 400.20) por 1
  kit — verificar el precio vigente al momento de comprar, puede variar
  por tienda/envío/aranceles; no asumir que sigue siendo exactamente ese
  monto.
- **Dónde comprar** (mismo producto, varias tiendas — usar la que ya se
  usó para la fila N° 2 si el equipo lo recuerda, para repetir
  envío/aranceles conocidos):
  - Tienda oficial Nooelec: <https://www.nooelec.com/store/attenuator-bundle.html>
  - Amazon (EE.UU.): <https://www.amazon.com/Nooelec-SMA-Attenuator-Kit-Line/dp/B07YYMT65T>
- **No es una alternativa de menor costo sin evaluar primero**: existen
  kits de atenuadores SMA genéricos más baratos en AliExpress/eBay con la
  misma combinación nominal de valores (1/2/3/6/10/20 dB), pero sin la
  especificación de VSWR verificada arriba — cambiar de marca reintroduce
  la pregunta de cascada/VSWR que comprar el mismo modelo ya evita.

---

## 7. Sitios: UNI (Lima) y Huánuco

**Supuesto de trabajo (⚠ a confirmar con el equipo, no verificado en este
repo):** UNI = laboratorio en el campus de Lima, donde probablemente está
el hardware y el equipo de desarrollo; Huánuco = el sitio real (o
representativo) de la comunidad rural objetivo del despliegue (`README.md`
menciona "Comunidad rural — 4 km" y "zonas rurales" de forma genérica, sin
nombrar la región). Si Huánuco es en efecto la región del despliegue final,
correr el mismo banco cableado ahí (no solo en Lima) tiene una razón
concreta más allá de logística: **la ocupación real de canales TV
(sensado, RX2/discone) es distinta en cada sitio** — Lima urbano
probablemente con más canales TV activos, Huánuco rural probablemente con
más canales libres — y eso es justo lo que el `CognitiveEngine` tiene que
manejar bien en ambos extremos. Confirmar esta lectura antes de asumirla
en el cronograma.

Preguntas a resolver (no bloquean iniciar en UNI, sí afectan cómo planear
Huánuco):

1. ¿Huánuco es el sitio final de despliegue (el "Cliente" real) o un sitio
   de prueba adicional distinto de ambos nodos de campo?
2. ¿Se lleva el mismo hardware físico de la UNI a Huánuco (secuencial), o
   hay/habrá una segunda pareja de equipos allá?
3. ¿Qué parte del banco corre en cada sitio? (p. ej.: ¿todo el banco
   completo en ambos, o solo confirmar sensado real de espectro en
   Huánuco mientras el full-duplex se valida a fondo en la UNI donde hay
   más soporte de laboratorio?)
4. Fechas/ventanas de acceso a Huánuco (viaje, permisos, disponibilidad del
   equipo) — condiciona el cronograma real de §8.

---

## 8. Cronograma tentativo (a ajustar)

| Hito | Sitio | Depende de |
|---|---|---|
| ~~Calcular atenuación objetivo (§4)~~ | Cualquiera | ✅ Hecho 13/09/2026 — ver §4 |
| Comprar 1-2 kits de atenuadores SMA adicionales (§4.3/§6) | Cualquiera (no requiere hardware) | Presupuesto/logística de compra |
| 4a-1, 4a-2 (aislamiento intra-chip, loopback simple) | UNI | Atenuación suficiente (§4.3), 1 bladeRF |
| 4a-3, 4a-4 (línea base TDD, full-duplex real) | UNI | 2 bladeRF disponibles simultáneamente |
| 4a-5 a 4a-8 (salto de canal, rendezvous, sensado integrado, throughput) | UNI | 4a-4 aprobada |
| Repetir el subconjunto relevante en Huánuco | Huánuco | Resolver §7, viaje/logística |

**No hay fechas fijas todavía** — este brief es el punto de partida; llenar
esta tabla con fechas reales en cuanto el equipo las defina, siguiendo la
misma disciplina que el resto del repo (fechas absolutas, no relativas, y
actualizar la fila de estado en `CLAUDE.md` cuando algo cierre o abra).

---

## 9. Riesgos y preguntas abiertas (resumen)

- **§2**: el aislamiento intra-chip TX1→RX1 del AD9361 en full-duplex real
  es una hipótesis, no un hecho — puede que tampoco alcance, igual que con
  antenas. Primera prueba del plan (4a-1) existe justo para esto.
- **§4.3 (🔴 nuevo, bloqueante de material)**: el kit de atenuadores ya
  comprado (42 dB máx.) no alcanza para ningún escenario calculado —
  incluso el punto de diseño original de 4 km (52.6 dB) lo supera. Hace
  falta comprar 1-2 kits idénticos adicionales antes de 4a-2 en adelante.
- **§6**: logística de tener 2 bladeRF simultáneamente en el mismo sitio
  sin bloquear otras pruebas del proyecto que puedan estar usando el
  segundo equipo.
- **§7**: rol real de Huánuco en el proyecto — confirmar antes de planear
  el viaje/logística en detalle.
- No cubierto todavía en este brief: cómo el `CognitiveEngine` decide
  "modulación adaptativa" cuando el canal es una atenuación fija de banco
  (no hay fading real que justifique cambiar de modulación dinámicamente)
  — puede que estas pruebas solo tengan sentido a atenuación fija por
  corrida, variándola manualmente entre corridas en vez de esperar
  adaptación en tiempo real dentro de una sola corrida. Decidir esto antes
  de 4a-4.

---

## 10. Cómo continuar en próximas sesiones

- ~~Antes de tocar código: correr `LINK_BUDGET/app.py` y cerrar §4~~ — hecho
  13/09/2026, ver §4. Próximo paso de material: comprar 1-2 kits de
  atenuadores adicionales (§4.3) antes de intentar 4a-2 en adelante.
- Antes de empezar 4a-1: leer `SPECS EQUIPOS/SDR_ENLACE` completo (ya
  tiene datos de impairments del AD9361, aunque no específicamente
  aislamiento TX-puerto↔RX-puerto) y buscar en el datasheet completo del
  AD9361 (`SPECS EQUIPOS/AD9361 datasheet.pdf`) si hay una cifra directa
  de aislamiento TX-RX entre canales del mismo chip — evitaría tener que
  medirlo a ciegas.
- Crear `TRANSMISION/pruebas/fase4a_banco_cableado_fd/README.md` cuando
  arranque la ejecución real (siguiendo el formato de las fases
  existentes) — este brief queda como el documento de diseño/motivación,
  ese README como el registro de evidencia, igual que el resto del plan de
  pruebas.
- Actualizar la fila "TRANSMISION" de la tabla de estado en `CLAUDE.md`
  cuando esta fase arranque o cierre — no crear una tabla de estado nueva.
- Si Huánuco resulta ser el sitio final de despliegue (§7), enlazar este
  brief desde `README.md` (sección de cronograma/cómo se valida el bloque
  cognitivo) para que quede visible fuera de `claudedocs/`.
