# Estructura física de instalación — Gateway y Cliente

> **Propósito de este documento:** traducir la arquitectura RF ya descrita
> en `README.md` §4 y las hojas técnicas reales de `SPECS EQUIPOS/` en un
> plano de instalación física concreto — qué va montado dónde, con qué
> conector, con qué tramo de cable, y en qué orden. `README.md` §4 dice
> **qué** cadena de componentes existe; este documento dice **cómo se monta
> y conecta físicamente**, y señala los huecos que quedan pendientes.
>
> **Fuente de las características de cada equipo: `SPECS EQUIPOS/`** — un
> archivo por equipo, con la hoja técnica real del modelo comprado. Este
> documento no repite cifras de link budget (EIRP, NF, margen) — esas
> viven en `LINK_BUDGET/`.

---

## 0. Decisiones y hallazgos de esta revisión (28/08/2026)

1. **Sin GDT.** El proyecto decidió no usar descargador de sobretensión en
   ninguna rama RF, en ningún nodo. El enlace de validación opera de forma
   continua solo **~3 horas** — no es una instalación permanente expuesta
   a una temporada de tormentas. **Si el proyecto pasa a un despliegue
   permanente más adelante, reintroducir GDT** — la ausencia de GDT es una
   decisión válida para *esta* ventana de uso, no una conclusión general.
2. **Longitudes de cable no fijas.** El LMR-400 real se corta en sitio
   según §3.0.
3. **Toda la cadena de RF (antena, LNA, PA) resultó ser SMA, no N.** Las
   hojas técnicas reales muestran que la antena LPDA, el LNA y el PA tienen
   conector **SMA-hembra** — el diseño anterior de este documento asumía
   conectores N-tipo en varios tramos (heredado del spec de compra
   original de la antena, que pedía "N-hembra con balun") que no coincide
   con lo que realmente se compró. Esto simplifica la cadena: en principio
   no hacen falta adaptadores N↔SMA en ningún punto, salvo en el LMR-400
   si se compró pre-terminado en N (a confirmar, ver §7) y en la discone
   de sensado (conector SO-239 confirmado, sí necesita adaptador).
4. **El bias-tee para el LNA en el tope del mástil es una función del
   propio bladeRF, no un componente aparte.** `SPECS EQUIPOS/SDR_ENLACE`
   confirma que el bladeRF trae "circuito Bias-Tee de 3.3V controlado por
   software integrado en todos los puertos RF, capaz de suministrar
   energía a amplificadores LNA". No hay que comprar ni instalar un
   inyector de bias-tee separado — se activa por software (libbladeRF/
   `gr-bladeRF`) en el puerto RX correspondiente.
5. **El mástil real puede que ya resuelva el requisito de "no penetrante".**
   `SPECS EQUIPOS/MASTILES` describe el mástil comprado como **"Mástil Tipo
   Trípode de 3 Metros"** — una estructura de trípode autosoportada, no un
   simple poste que necesite anclaje a una pared/techo. Esto podría ser
   ya la solución al requisito "sin penetrar techo/piso" que la memoria
   `hardware-mastiles-antenas` marcaba como pendiente de cotizar por
   separado (ESYCOM/PCenterPerú) — **a confirmar con el equipo**: ¿el
   trípode de 24kg por sí solo es la base no-penetrante, o todavía hace
   falta una base/lastre adicional para pararlo sin anclaje? Ver §5.
6. **Hallazgo nuevo: la discone de sensado no calza en el mástil real.**
   `SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL` especifica un diámetro de mástil
   máximo de 35mm; el mástil real tiene dos tramos, Ø60mm y Ø48mm — ninguno
   cabe en la abrazadera de la discone. Ver §3.3 y §5.
7. **El PA tiene una entrada máxima tolerada de +3 dBm**, menor que el TX
   máximo del bladeRF (~+6 dBm). Hay que operar el bladeRF a ganancia
   reducida antes de conectar el PA — ver §3.1 y §6.3.

Hallazgos que siguen abiertos (no resueltos por lo anterior):

- **El Cliente no tiene ningún ítem de alimentación en el presupuesto**
  (sin panel solar, batería, ni controlador de carga) — ahora con un dato
  concreto de consumo del PA (12V DC, 300-400mA, `SPECS EQUIPOS/PA.md`)
  para dimensionar. Ver §6.2.
- **La ganancia y polarización reales de la discone de sensado no están
  documentadas** ni en el spec de compra ni en la hoja técnica real — ver
  `claudedocs/requisitos_antena_sensado.md`.
- **El ACPR/OIP3 real del PA no está documentado** — ver
  `claudedocs/requisitos_pa_lna.md` §3.3.

---

## 1. Topología física general

Dos sitios, cada uno con un mástil de 3 m (trípode) sobre base — pendiente
de confirmar si el trípode ya es la base no-penetrante o hace falta algo
adicional (§5):

```
        GATEWAY (localidad con fibra)              CLIENTE (comunidad rural)
        techo/azotea, con acceso a red eléctrica    campo, sin red eléctrica (batería/solar)

  ┌─────────────────────────┐              ┌─────────────────────────┐
  │  Mástil trípode 3 m      │              │  Mástil trípode 3 m      │
  │  (Ø60mm tramo1/          │              │  (Ø60mm tramo1/          │
  │   Ø48mm tramo2)          │              │   Ø48mm tramo2)          │
  │                          │              │                          │
  │  ┌───┐ ┌───┐  (discone)  │              │  ┌───┐ ┌───┐             │
  │  │LPDA│ │LPDA│    │      │    4 km      │  │LPDA│ │LPDA│           │
  │  │ TX │ │ RX │    │      │◄════════════►│  │ RX │ │ TX │           │
  │  └─┬─┘ └─┬─┘    ──┴──    │   OFDM TDD   │  └─┬─┘ └─┬─┘             │
  │    │    LNA-tope│LNA-tope│              │    │LNA-tope│    │       │
  │    │    (datos) │(sens.) │              │    │(datos) │    │       │
  │    │        │       │     │              │    │        │       │    │
  │  LMR-400  LMR-400 LMR-400 │              │  LMR-400  LMR-400    │
  │  (long.   (long.  (long.  │              │  (long.   (long.     │
  │   según    según   según  │              │   según    según     │
  │   sitio)   sitio)  sitio) │              │   sitio)   sitio)    │
  └────┼────────┼───────┼─────┘              └────┼────────┼─────────┘
       │        │       │                         │        │
  ┌────┴────────┴───────┴─────┐              ┌────┴────────┴─────────┐
  │  Interior / junto al PC     │              │  Gabinete IP65 (campo) │
  │  PA · bladeRF · PC · CNN    │              │  PA · bladeRF ·        │
  │  (indoor, red eléctrica)    │              │  Orange Pi 5           │
  └──────────────────────────────┘              │  (batería/solar — sin │
                                                 │   ítem presupuestado) │
                                                 └────────────────────────┘
```

**Gateway:** 3 antenas en el mástil (LPDA TX, LPDA RX, discone de sensado
— con conflicto de montaje pendiente, §3.3/§5).
**Cliente:** 2 antenas en el mástil (LPDA RX downlink, LPDA TX uplink).

---

## 2. Inventario de antenas y su rol

| Equipo (`SPECS EQUIPOS/`) | Cant. | Rol físico | Ubicación | Conector real |
|---|---|---|---|---|
| `ANTENA_DIRECCIONAL` — LPDA PCB WA5VJB, 400-1000 MHz, **5 dBi a 500 MHz** | 4 | 2 en Gateway (TX + RX datos), 2 en Cliente (TX + RX datos) | Tope de mástil, en la parte más alta libre de obstrucciones | **SMA** (montaje SMA para PCB, o cable soldado directo) |
| `ANTENA_OMNIDIRECCIONAL` — Discone Tram 1411, 25-1300 MHz | 1 | Sensado RX2, solo Gateway | Tope de mástil, junto a las LPDA del Gateway — **conflicto de montaje, ver §3.3/§5** | **SO-239 (UHF hembra)**, confirmado |

`LINK_BUDGET/` ya usa la ganancia real de la antena LPDA (5 dBi a 500 MHz)
— el spec de compra original pedía ≥10 dBi, cifra que el fabricante real
(WA5VJB) nunca confirmó; usar la hoja técnica real, no el spec de compra,
para cualquier cálculo.

### 2.1 Separación entre antenas en el mismo mástil (abierto, no cuantificado)

`claudedocs/riesgos_arquitectura_transmision.md` solo dice que las cadenas
TX/RX necesitan "separación física/angular adecuada" sin dar una cifra en
metros. Con TDD por software (no full-duplex real) el requisito de
aislamiento es menos duro que los 90-110 dB que exigiría un full-duplex
simultáneo, pero sigue siendo relevante para evitar que el front-end de
recepción se sature durante el instante de conmutación TX→RX. **No hay
todavía un número de diseño** — pendiente de definir antes de fijar las
abrazaderas. Recomendación práctica mientras no se mida: separar TX y RX
al menos ~0.5–1 m verticalmente en el mástil (varias longitudes de onda a
600 MHz, λ≈0.5 m) y evitar apuntarlas una contra el otro en el mismo eje.

---

## 3. Cadena RF del Gateway

### 3.0 Criterio para dimensionar cada tramo de LMR-400

El LMR-400 real se corta en sitio — no viene en tramos fijos. Criterio a
aplicar en los 5 tramos de este documento (2 Gateway datos + 1 Gateway
sensado + 2 Cliente):

1. **Medir la distancia real** entre el punto de montaje en el mástil
   (tope para antena/LNA, base para el equipo) antes de cortar.
2. **Dejar un pequeño exceso de servicio** (~0.3–0.5 m), sin sobrar tanto
   que haga falta enrollar el cable en una vuelta cerrada (agrega pérdida
   a estas frecuencias) — preferir curva amplia (radio ≥5 cm) si sobra.
3. **Minimizar el tramo antes del LNA** (RX) — el jumper corto de fábrica
   del LNA a la antena, sin LMR-400 de por medio ahí (ver §3.2). El tramo
   largo de LMR-400 va **después** del LNA.
4. **El tramo del PA (TX) es menos sensible** — unos metros extra de
   LMR-400 después del PA cuestan fracciones de dB de EIRP, ya absorbidos
   por el margen de enlace (§9.1 de `README.md`, +7.0 dB incluso en
   16-QAM).
5. **Conectores del LMR-400 sin confirmar** — todo el resto de la cadena
   (antena, LNA, PA, bladeRF) es SMA (§0 punto 3). Si el LMR-400 comprado
   viene pre-terminado en N (común para cable de este grosor), usar
   adaptadores N↔SMA en ambos extremos de cada tramo; si se termina a
   pedido, terminar directamente en SMA para no necesitar adaptador.

### 3.1 TX Downlink (Gateway → Cliente)

```
bladeRF TX1 — ganancia TX reducida por software (⚠ NO usar la ganancia
  máxima del SDR — el PA solo tolera +3 dBm de entrada; con ganancia
  máxima el bladeRF entrega ~+5.7 dBm, por encima del límite. Configurar
  la ganancia TX para entregar aprox. -5 a -6 dBm al PA, dada su ganancia
  típica real de 30 dB a 500 MHz — ver claudedocs/requisitos_pa_lna.md §3.4)
  │ RG-316 pigtail (SMA-M↔SMA-M)      ← indoor, junto al PC
  ▼
PA "OEM 2W 1-900MHz" (P1dB real 32 dBm, backoff 7.5 dB → salida
  promedio +24.5 dBm, clase A, SMA-hembra ambos lados)
  │
LMR-400 (longitud según distancia real PA↔antena, ver §3.0)   ← sube por el mástil
  ▼
LPDA TX 5 dBi (SMA) — tope del mástil
```

El PA se queda junto al bladeRF/PC (indoor, con red eléctrica) porque ahí
no hay penalidad crítica de NF — solo resta una fracción de dB de EIRP por
la pérdida del tramo después del PA, ya contemplado en el margen de
`LINK_BUDGET/` (+7.0 dB de sobra incluso en 16-QAM, recalculado 28/08/2026
con las hojas técnicas reales — menos margen que antes de tener el
datasheet real, pero sigue cerrando).

**Térmico:** el PA es clase A (más calor por vatio de RF que clase AB) con
disipador pasivo únicamente, sin ventilador (`SPECS EQUIPOS/PA.md`). Para
una prueba de ~3h esto probablemente no es crítico, pero si el PA queda en
un gabinete cerrado (caso del Cliente, ver §4.1) conviene verificar que no
se acumule calor sin ventilación durante la operación continua.

### 3.2 RX Uplink — LNA en la boca de la antena

El NF de sistema que usa todo el proyecto (~0.94 dB, `README.md` §9.1) solo
se reproduce si el LNA está en el punto de alimentación de la antena, no
después de un tramo largo de cable. La instalación queda así:

```
LPDA RX 5 dBi (SMA, tope de mástil)
  │ jumper corto de fábrica del LNA (< 20 cm, prácticamente sin pérdida,
  │ ambos conectores SMA — sin adaptador)
  ▼
LNA Nooelec LaNA (NF 0.9 dB típico, +20 dB a 1000MHz) — atornillado
  directo al conector de la antena, en el tope del mástil, alimentado
  por bias-tee del propio bladeRF (circuito integrado en el puerto RX,
  activado por software — sin inyector de hardware adicional, ver §6.1)
  │
LMR-400 (longitud según distancia real LNA↔bladeRF, ver §3.0)   ← baja por el mástil
  │
RG-316 pigtail (SMA-M↔SMA-H)
  ▼
bladeRF RX1
```

**Costo de esto:** ninguno adicional — es el mismo LNA ya comprado, en un
orden físico específico. Montar el LNA en una carcasa apta para intemperie
en el tope del mástil — el LNA Nooelec ya viene encapsulado (`SPECS EQUIPOS/LNA.md`,
"Construcción mecánica: Módulo encapsulado", 80×30×20mm) — verificar que
ese encapsulado es apto para exterior por la duración de la prueba.

### 3.3 RX2 — Sensado espectral (independiente, solo Gateway)

```
Discone Tram 1411 (SO-239) — ⚠ montaje: la abrazadera de la discone
  soporta mástil de máx. 35mm de diámetro; el mástil real tiene tramos de
  Ø60mm y Ø48mm, ninguno calza — resolver con reductor o punto de montaje
  auxiliar más angosto antes de instalar (ver §5)
  │
  adaptador SO-239↔SMA (todo lo demás en la cadena es SMA)
  ▼
LNA de sensado (mismo modelo Nooelec LaNA) — en el tope del mástil,
  junto a la discone, bias-tee del propio bladeRF (RX2)
  │
LMR-400 (longitud según distancia real)
  ▼
bladeRF RX2
  → Barrido continuo 470–698 MHz → CNN cada 100–200 ms
```

---

## 4. Cadena RF del Cliente

Misma lógica que el Gateway, en espejo (uplink en vez de downlink), mismos
componentes reales (mismo modelo de PA y LNA en ambos nodos).

### 4.1 TX Uplink (Cliente → Gateway)

```
bladeRF TX1 (Cliente) — ganancia TX reducida por software, misma
  advertencia que el Gateway (§3.1): no exceder +3 dBm de entrada al PA
  │ RG-316 pigtail (SMA-M↔SMA-M)
  ▼
PA "OEM 2W 1-900MHz" — mismo modelo real que el Gateway (backoff 7.5 dB
  → ~+24.5 dBm, clase A, disipador pasivo sin ventilador)
  │
LMR-400 (longitud según distancia real, ver §3.0)
  ▼
LPDA TX 5 dBi (SMA, tope del mástil)
```

**Térmico, caso Cliente:** a diferencia del Gateway (PA puede quedar
indoor), en el Cliente el PA vive dentro del gabinete IP65 de campo (§4.2)
— sin ventilación activa, verificar temperatura interna del gabinete
durante la prueba, especialmente si coincide con exposición solar directa.

### 4.2 RX Downlink (en el Cliente)

```
LPDA RX 5 dBi (SMA, tope de mástil)
  │ jumper corto de fábrica (SMA, sin adaptador)
  ▼
LNA Nooelec LaNA — en el tope del mástil, junto a la antena, bias-tee
  del propio bladeRF
  │
LMR-400 (longitud según distancia real)
  │
RG-316 pigtail (SMA-M↔SMA-H)
  ▼
bladeRF RX1 (Cliente)
```

El Cliente no tiene antena de sensado — su bladeRF RX2 no se usa en campo
(§2.2 de `README.md`: la lógica cognitiva corre íntegramente en el
Gateway). El gabinete IP65 (300×250×150mm, `PRESUPUESTO COMPLETO.xlsx`
ítem #13) aloja bladeRF + PA + Orange Pi 5 — el PA real (55×40×30mm,
`SPECS EQUIPOS/PA.md`) y el bladeRF (127×63.5×25.4mm, `SPECS EQUIPOS/SDR_ENLACE`)
caben holgadamente en ese volumen.

### 4.3 Restricción física adicional: cable USB entre bladeRF y el cómputo

bladeRF 2.0 micro xA4 usa USB 3.0 SuperSpeed Tipo B (`SPECS EQUIPOS/SDR_ENLACE`);
un cable USB 3.0 pasivo estándar tiene un límite práctico de ~3 m antes de
necesitar un repetidor/extensor activo. Esto fija que **el bladeRF de cada
nodo debe estar a ≤3 m de su computadora** (PC Gateway indoor; Orange Pi 5
en el gabinete IP65 del Cliente) — no se puede alejar el bladeRF hacia el
mástil para acortar el cableado RF sin agregar un extensor USB activo. Es
la razón física (no solo de conveniencia) por la que el PA/bladeRF se
quedan "abajo" y es el LMR-400, no el USB, el que sube el mástil.

**Alimentación del bladeRF:** `SPECS EQUIPOS/SDR_ENLACE` especifica un
conector DC Jack externo (5.5mm×2.1mm, 5V) "requerido para uso intensivo
de FPGA o Bias-Tee" — dado que este proyecto SÍ usa bias-tee de forma
continua (para los LNA en el tope del mástil, §6.1), conviene alimentar
ambos bladeRF con fuente DC externa en vez de depender solo del bus USB,
para no arriesgar un brownout del bias-tee bajo carga sostenida.

---

## 5. Mástiles y montaje

`SPECS EQUIPOS/MASTILES` — "Mástil Tipo Trípode de 3 Metros":

- **Altura:** 3 m, en 2 tramos tubulares de 1.5 m cada uno: tramo 1 (más
  bajo) Ø60mm (2") x 3mm pared, tramo 2 (más alto) Ø48mm (1.5") x 3mm
  pared.
- **Peso:** ~24 kg. Estructura de trípode (ángulo 1.5"x3mm), acero
  ASTM-A36/A500 Gr.A, soldadura MIG, galvanizado en caliente ASTM-A123.
- **¿Resuelve el requisito "no penetrante"?** Al ser un trípode
  autosoportado (no un poste que necesite anclaje a pared/techo), es
  candidato a ser ya la solución al requisito de la memoria
  `hardware-mastiles-antenas` (no perforar techo/piso, presupuesto
  separado de S/1000 para una base). **Confirmar con el equipo antes de
  cotizar una base adicional** — si el trípode de 24kg ya para solo (con
  o sin lastre extra), ese presupuesto de S/1000 podría no hacer falta, o
  reducirse solo a lastre (bloques/bidones) en vez de una base a medida
  completa.
- **Abrazaderas de antena:** la LPDA (`ANTENA_DIRECCIONAL`) especifica
  abrazadera para mástil de 25-50mm — **calza en el tramo 2 (Ø48mm), no
  en el tramo 1 (Ø60mm)**. Montar ambas LPDA (TX y RX) en el tramo
  superior.
- **Discone:** máximo 35mm de diámetro de mástil — **no calza en ningún
  tramo** (60mm ni 48mm). Necesita un reductor (adaptador de abrazadera) o
  un mástil/poste auxiliar más angosto fijado al trípode principal,
  específicamente para la discone. Resolver antes de instalar — es un
  problema físico real, no solo de documentación.
- **Puesta a tierra:** no es necesaria para protección de sobretensión
  (sin GDT, §0) dado el uso de ~3h. Sigue siendo buena práctica de
  seguridad eléctrica general enlazar el mástil metálico a tierra si hay
  una toma disponible cerca, pero no es bloqueante.

---

## 6. Alimentación

### 6.1 LNA en el tope del mástil — bias-tee del propio bladeRF

`SPECS EQUIPOS/SDR_ENLACE` confirma que el bias-tee (3.3V) está integrado
y controlado por software en **todos** los puertos RF del bladeRF —
**no hace falta comprar ni instalar un inyector de bias-tee separado**.
Para alimentar el LNA en el tope del mástil, basta con habilitar el
bias-tee del puerto RX correspondiente (RX1 para datos, RX2 para sensado)
por software (`libbladeRF`/`gr-bladeRF`) — la corriente DC viaja sobre el
mismo LMR-400 que lleva la señal RF, en sentido contrario. El LNA Nooelec
consume 70-100mA a 3.3-5.5V (`SPECS EQUIPOS/LNA.md`) — dentro de lo que el
bias-tee del bladeRF puede entregar.

### 6.2 Alimentación del nodo Cliente — hueco del presupuesto

`README.md` y `claudedocs/requisitos_pa_lna.md` asumen explícitamente que
el Cliente corre con batería/solar por no tener red eléctrica en la
comunidad rural. **El presupuesto no tiene ningún ítem de panel solar,
batería, controlador de carga ni inversor.** Con los datos reales de
consumo ya disponibles:

- PA: 12V DC, 300-400mA (`SPECS EQUIPOS/PA.md`) ≈ 3.6-4.8W
- LNA: 3.3-5.5V, 70-100mA (`SPECS EQUIPOS/LNA.md`) ≈ <0.5W
- bladeRF: alimentación USB o DC externa 5V (consumo no especificado en
  `SPECS EQUIPOS/SDR_ENLACE`, a confirmar)
- Orange Pi 5: consumo no cubierto por `SPECS EQUIPOS/` (no hay archivo
  para este equipo — fuera del alcance de esa carpeta, confirmar con la
  ficha propia del SBC)

Para una prueba de validación de ~3 horas puntuales, sumar estos consumos
reales (más el de la Orange Pi 5, pendiente) permite dimensionar una
batería portátil/power station simple, sin necesidad de panel solar — pero
ese cálculo integral todavía no está hecho. Sigue siendo un vacío que
bloquea la instalación física del Cliente si no se resuelve antes.

### 6.3 ⚠ No conectar el PA a la ganancia máxima del bladeRF

Hallazgo de esta revisión (§0 punto 7): el PA real tolera un máximo de
+3 dBm de entrada; el bladeRF a su ganancia TX máxima entrega ~+5.7 dBm
tras el pigtail — por encima del límite. Antes de conectar el PA en
cualquiera de los dos nodos, configurar la ganancia TX del bladeRF por
software a un nivel bajo (aprox. -5 a -6 dBm de salida del SDR, dada la
ganancia típica real del PA de 30 dB a 500 MHz) — ver el detalle de cálculo
en `claudedocs/requisitos_pa_lna.md` §3.4. El kit de atenuadores SMA ya
comprado (`PRESUPUESTO COMPLETO.xlsx` #2, 1-42dB en pasos de 1dB, hasta 2W)
sirve para verificar en banco el nivel real antes de conectar el PA, si se
quiere confirmar sin depender solo de la calibración de ganancia del SDR.

---

## 7. Componentes que faltan o requieren verificación antes de instalar

| # | Componente | Estado | Qué falta |
|---|---|---|---|
| 1 | ACPR/OIP3 real del PA | No documentado en `SPECS EQUIPOS/PA.md` | Sin instrumentación propia para medirlo — operar dentro del backoff decidido (7.5 dB) como única mitigación disponible, ver `claudedocs/requisitos_pa_lna.md` §3.3 |
| 2 | Conector de terminación del LMR-400 comprado | No especificado en el presupuesto ni en `SPECS EQUIPOS/` (no hay archivo de cable) | Confirmar si viene en N o SMA — todo el resto de la cadena es SMA (§0 punto 3); si es N, comprar adaptadores N↔SMA |
| 3 | Reductor de mástil para la discone (35mm máx. vs. 60/48mm real) | Problema físico confirmado, sin solución comprada | Conseguir abrazadera reductora o mástil auxiliar angosto — ver §5 |
| 4 | ¿El trípode ya es la base no-penetrante? | Sin confirmar con el equipo | Definir si hace falta cotizar una base adicional (ESYCOM/PCenterPerú, memoria `hardware-mastiles-antenas`) o si el trípode de 24kg ya basta, posiblemente con lastre extra |
| 5 | Alimentación del Cliente (batería/solar) | **No presupuestada** | Ver §6.2 — ya hay datos reales de consumo del PA/LNA, falta sumar Orange Pi 5 y bladeRF y dimensionar |
| 6 | Ganancia y polarización reales de la discone | No documentadas ni en el spec de compra ni en la hoja técnica real | Ver `claudedocs/requisitos_antena_sensado.md` §3 |
| 7 | Cinta autofusionable / sellado de conectores exteriores | No presupuestado (consumible menor) | Agregar como insumo de instalación |
| 8 | Carcasa de intemperie del LNA en tope de mástil | El LNA ya viene "encapsulado" (`SPECS EQUIPOS/LNA.md`) | Confirmar que ese encapsulado es apto para exterior por la duración de la prueba |
| 9 | Asignación de los 2 gabinetes IP65 | Comprados x2 | `README.md` solo asigna gabinete al Cliente explícitamente — confirmar si el segundo es repuesto o tiene otro uso |
| 10 | Consumo del bladeRF y de la Orange Pi 5 | No cubierto por `SPECS EQUIPOS/` | Necesario para cerrar el cálculo de §6.2 |

---

## 8. Referencia rápida — qué vive dónde

| Documento | Qué cubre |
|---|---|
| `SPECS EQUIPOS/` | **Fuente única de características de cada equipo ya comprado** — un archivo por equipo |
| `README.md` §4 | Lista de componentes por nodo (alineada con `SPECS EQUIPOS/`) y cadena RF *lógica* |
| `LINK_BUDGET/` | Cifras de dB (EIRP, NF, margen) — corre la calculadora, no copiar números aquí |
| `claudedocs/requisitos_pa_lna.md` | Verificación punto por punto del PA y el LNA reales contra los requisitos del proyecto |
| `claudedocs/requisitos_antena_sensado.md` | Verificación de la antena discone de sensado real |
| Memoria `hardware-mastiles-antenas` | Restricción no-penetrante, presupuesto de soportes, proveedores — a revisar contra el hallazgo del §5 (el trípode puede ya resolver esto) |
| **Este documento** | Geometría de montaje, orden físico de componentes en cada cadena, conectores por tramo, huecos pendientes |

*Última actualización: 28/08/2026 — con hojas técnicas reales de `SPECS EQUIPOS/`.*
