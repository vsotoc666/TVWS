# Transmisión por cable — banco cableado sin antenas (TX1/RX1 directo)

**Estado: 🟡 planificación en curso, sin hardware conectado todavía —
20/09/2026.** Esta carpeta es el punto central para todo lo referido a la
transmisión por cable (dos bladeRF conectados entre sí, sin antenas,
simulando FSPL con atenuadores): el plan/diseño vive acá en este README y
el código (scripts de captura, calibración, verificación) se va a ir
agregando en esta misma carpeta a medida que avancemos — no es una
especificación cerrada como el brief de diseño general de Fase 4a.

La primera prueba concreta que desarrolla este README es **4a-3** (dos
bladeRF por cable, half-duplex TDD, línea base) — ver §1. Este documento
también va a cubrir **4a-4** (full-duplex simultáneo, misma trama OFDM) en
cuanto 4a-3 esté aprobada — ver §1.1. Si después suman más pruebas de esta
línea (loopback simple, salto de canal, etc.), este mismo README se
actualiza o se separa en sub-secciones, sin crear un doc paralelo.

---

## 1. Qué es esta prueba y qué NO es

Valida el **enlace troncal de datos (TX1/RX1)** entre dos bladeRF 2.0 micro
xA4 conectados directamente por cable + atenuador, **sin antenas**, con el
atenuador simulando la pérdida de espacio libre (FSPL) del enlace de campo.
Es la prueba que motivó este documento ("las tarjetas conectadas entre sí,
simulando FSPL, sin antenas").

**Es half-duplex TDD** — mismo esquema del diseño de campo
(`README.md` §3.1 del repo raíz): en cualquier instante, un TX transmite
mientras el otro nodo recibe, nunca los dos TX activos a la vez. **No es**
la variante full-duplex simultáneo del brief (`4a-4` en adelante) — esa
necesita primero la Prueba 4a-1 (aislamiento intra-chip TX1↔RX1), que
todavía no corrió con hardware real. Esta prueba (4a-3) **no depende de
4a-1** porque nunca hay dos TX activos al mismo tiempo.

**Decisión de arquitectura (20/09/2026):** a diferencia del planteo
original de este documento, la cadena de sensado (RX2 + LNA + discone) del
Gateway **sí queda cableada desde el arranque**, con antena real — coincide
con la arquitectura completa del brief (§3) y con el diseño de campo
(`README.md` §3.3, "solo el Gateway sensa"). Lo que sigue **sin antena** es
únicamente el enlace troncal de datos (TX1/RX1), que es lo que da nombre a
este documento — ver §3.

**Qué queda fuera de esta prueba (4a-3 específicamente):**
- Integración funcional del mapa de sensado con el `CognitiveEngine`
  (correr la CNN, tomar decisiones de canal en base al sensado real) — el
  cableado de RX2 queda listo desde ahora, pero probar esa integración es
  4a-7 en la numeración del brief, posterior a esta línea base.
- El esquema full-duplex (4a-4, ver §1.1) — necesita esta línea base
  aprobada primero, más la Prueba 4a-1.
- LNA/PA **en el enlace de datos** — el banco cableado los reemplaza por
  el atenuador, ver §3. (El LNA de sensado en RX2 sí se usa, es la cadena
  real de campo sin cambios.)

### 1.1 Los 2 esquemas de duplexado que cubre este documento (confirmado 20/09/2026)

Este banco cableado va a probar **2 esquemas de transmisión, con la misma
estructura de subportadoras** ya cerrada para el enlace de campo real
(FFT/CP, comb de pilotos escalonado stride 8, subportadoras de control
#254/256/257 — `README.md` raíz, `claudedocs/arquitectura_enlace_datos.md`):

| Esquema | Prueba | Qué cambia respecto a la trama OFDM ya cerrada |
|---|---|---|
| Half-duplex TDD (línea base) | 4a-3, este documento | Nada — mismo esquema de campo, un TX activo a la vez |
| Full-duplex simultáneo | 4a-4 (a desarrollar en este mismo README después de 4a-3) | Nada en la trama — cambia solo el scheduling: los 2 TX quedan activos al mismo tiempo |

**Por qué es viable reusar la misma estructura:** la trama OFDM (pilotos,
control, FFT/CP) es una propiedad de cómo cada nodo arma su propio
símbolo — no depende de si el otro nodo transmite en simultáneo. El
duplexado es una decisión de scheduling, no de formato. Por eso no hace
falta rediseñar ni re-validar MAC/FEC/MOD/OFDM (Fases 1-3, ✅ 15/15) para
el esquema full-duplex.

**Riesgo específico del esquema full-duplex (no del half-duplex):** en
full-duplex, cada nodo recibe su **propio control leakeado** (#254/256/257)
superpuesto al control real del otro nodo, en los mismos bins — algo que
el half-duplex evita estructuralmente (el TX propio está apagado durante
el slot de RX). Esto nunca se probó — es la pregunta 1 del brief
(`claudedocs/brief_pruebas_banco_cableado_fullduplex.md` §1) y depende del
resultado de la **Prueba 4a-1** (aislamiento intra-chip TX1→RX1, diseñada,
sin correr con hardware real — `prueba4a1_aislamiento_intrachip/`). Si el
aislamiento no alcanza (~90-110dB necesarios), no es la estructura de
subportadoras la que falla — es que el full-duplex en sí no cierra con
este hardware, con cualquier estructura.

**⚠️ Alcance explícitamente confirmado (20/09/2026): los 2 esquemas son
solo para este banco cableado, no para el enlace de campo real.** Para el
despliegue con antenas, full-duplex ya fue descartado
(`claudedocs/riesgos_arquitectura_transmision.md`, Problema 1, 26/07/2026)
— el aislamiento disponible por separación de antena (~30-50dB) no
alcanza frente a los ~90-110dB requeridos. El diseño de campo sigue siendo
TDD por software (`README.md` §3.1), sin cambios. Este documento **no
reabre esa decisión** — si algún resultado de 4a-4 llegara a informarla,
se actualiza `README.md`/`riesgos_arquitectura_transmision.md`
explícitamente citando esta prueba como origen, no al revés (mismo
criterio que ya establece el brief §0).

**Ventaja práctica del cableado ya definido (§3/§6):** con las 2 rutas
(DL 20dB, UL 19dB) armadas simultáneamente, el mismo banco físico sirve
para los 2 esquemas sin recablear — lo único que cambia entre 4a-3 y 4a-4
es si el software gatea TX/RX por slot (TDD) o los deja siempre activos.

### 1.2 Criterios de validación por esquema (cerrado 20/09/2026)

Los umbrales de BER se toman de la curva ya medida en la
[Prueba 5](../pruebas/fase1_unitarias/prueba05_fec_roundtrip/) y aplicada
en la [Prueba 13](../pruebas/fase3_loopback_completo/prueba13_canal_sintetico/)
— **no se inventan de nuevo acá**: 0-3% BER = corrección total del FEC,
≥15% = el código se satura, y en cualquier caso el CRC-16 del MAC nunca
debe dejar pasar un payload corrupto como válido (0 falsos positivos).

**Criterios comunes a los 2 esquemas (gate de seguridad, no de desempeño):**

- [ ] En ningún momento la potencia medida/estimada en un puerto RX supera
      +2.5 dBm (§5) — si se supera, la corrida se invalida por completo,
      no solo el resultado de esa métrica.
- [ ] 0 casos de "CRC válido pero payload distinto del original" en ≥20
      corridas por escenario (mismo tamaño de muestra que la Prueba 13,
      para poder comparar la confianza estadística).

**Criterios específicos — 4a-3 (half-duplex TDD, línea base):**

| # | Criterio | Umbral / cómo se mide |
|---|---|---|
| 1 | Corrección de payload | Con la atenuación fija (§6) + `tx_gain` operativo elegido, el BER de canal resultante debe caer en la zona de corrección total de la curva FEC (≤3%) — payload recuperado bit-idéntico tras FEC+CRC, en las 2 direcciones (DL y UL) |
| 2 | Exclusividad temporal del TX | Verificar (log/captura IQ con timestamp) que nunca hay 2 TX activos al mismo tiempo — es la propiedad que define "half-duplex" y la que distingue esta prueba de 4a-4 |
| 3 | Control in-band | Los Formatos A/B/C en #254/256/257 se decodifican correctamente de punta a punta con hardware real — primera vez que se valida con SDR real en vez de canal sintético |
| 4 | Throughput | BPSK R=1/2 (único modo cableado hoy, ver Prueba 15) — no debe ser sustancialmente menor a la línea base de software ya medida (0.67 Mbps); si lo es, es un hallazgo nuevo atribuible al hardware/RF, no al overhead ya conocido de `ccsds_fec.py`. No se exige alcanzar el objetivo de diseño de `README.md` §5.3 (1.9 Mbps) — esa brecha ya está diagnosticada y es de otra causa |

**Criterios específicos — 4a-4 (full-duplex simultáneo):**

| # | Criterio | Umbral / cómo se mide |
|---|---|---|
| 0 | Gate de entrada | La Prueba 4a-1 debe reportar aislamiento intra-chip TX1→RX1 ≥ ~90-110 dB (o cota inferior en ese rango) antes de intentar 4a-4. Si no alcanza, 4a-4 se marca **bloqueada** con el hallazgo documentado como "Problema 1b" en `claudedocs/riesgos_arquitectura_transmision.md` (mismo criterio que ya prevé el brief §5) — no se fuerza la prueba igual |
| 1 | Corrección de payload | Igual que 4a-3 criterio 1, pero con los 2 TX activos al mismo tiempo |
| 2 | Control in-band bajo auto-fuga | El receptor decodifica el control **del nodo remoto** en #254/256/257 a pesar de recibir superpuesto su propio control leakeado en los mismos bins — es la pregunta central del brief (§1, pregunta 1), nunca antes probada |
| 3 | Degradación comparada contra 4a-3 | Medir BER/throughput de 4a-4 en el mismo punto de operación (misma atenuación, mismo `tx_gain`) que la corrida aprobada de 4a-3, y cuantificar la diferencia — el criterio de aprobación es que el BER resultante siga dentro de la zona de corrección total del FEC (≤3%), no que no haya ninguna degradación |

**Qué significa "aprobado" para cada esquema:** todos los criterios
marcados con checklist arriba en verde/✅, más las filas de la tabla
correspondiente con resultado dentro del umbral — se registra en la tabla
de resultados (§9) con el detalle de qué corrida cumplió cada fila, mismo
formato que el resto de `TRANSMISION/pruebas/`.

## 2. Dependencias y relación con el resto del plan

| Doc / prueba | Relación |
|---|---|
| `claudedocs/brief_pruebas_banco_cableado_fullduplex.md` §5 | Define esta prueba como fila `4a-3` de la tabla de 8 sub-pruebas — este documento es su desarrollo operativo, no reemplaza el brief |
| `TRANSMISION/pruebas/fase4a_banco_cableado_fd/prueba4a1_aislamiento_intrachip/` | 🟡 Diseñada, sin correr con hardware — **no bloquea 4a-3** (solo bloquea full-duplex, 4a-4+) |
| Prueba 4a-2 (loopback simple, un solo bladeRF) | **Prerequisito real según el brief, todavía no creada.** Antes de esta prueba (dos equipos) conviene correr 4a-2 primero — confirma que el DAC/ADC/calibración de un bladeRF real no rompe lo ya validado en software (Fases 1-3) antes de sumar la variable de un segundo equipo. **Pendiente decidir si se salta o se hace primero** — ver §9 |
| `TRANSMISION/pruebas/fase3_loopback_completo/` (✅ 15/15 software) | La cadena MAC/FEC/MOD/OFDM ya está validada sin SDR — esta prueba solo agrega el hardware real (2x AD9361) y el canal físico (cable+atenuador), no vuelve a probar la lógica de protocolo |

## 3. Arquitectura física (común a los 2 esquemas)

Dos bladeRF, cada uno en su host real de campo (no una laptop compartida,
ver §4). El Gateway lleva además su cadena de sensado real (RX2 + LNA +
discone) en paralelo al enlace troncal.

```
                    ┌──────────────────────┐
                    │   Discone Tram 1411   │  (antena real, sensado
                    │      (SO-239)         │   TVWS real del sitio)
                    └───────────┬───────────┘
                                │ adaptador SO-239↔SMA
                                ▼
                    ┌──────────────────────┐
                    │  LNA Nooelec LaNA     │  (+20dB, NF 0.9dB,
                    │  (SMA-H in/out)       │   alimentado por bias-tee
                    └───────────┬───────────┘   del propio RX2, software)
                                │ pigtail SMA-M↔SMA-H
                                ▼
PC (Gateway) ══USB3══▶  bladeRF GATEWAY                        bladeRF CLIENTE  ◀══USB3══ Orange Pi 5
                         (4x SMA-H: TX1,TX2,RX1,RX2)            (4x SMA-H: TX1,TX2,RX1,RX2)
                         RX2 ◀── (cadena de arriba)             RX2, TX2: sin conectar
                                                                 (Cliente no sensa, README §3.3)

  GATEWAY.TX1 (SMA-H) ──┐                                    ┌── CLIENTE.RX1 (SMA-H)
                        ├── [pigtail?] ── atenuador cascada ──┤
                        │                    (N dB)           │
                        └──────────────────────────────────────┘
                             RUTA DL: Gateway.TX1 → Cliente.RX1

  GATEWAY.RX1 (SMA-H) ──┐                                    ┌── CLIENTE.TX1 (SMA-H)
                        ├── [pigtail?] ── atenuador cascada ──┤
                        │                    (N dB)           │
                        └──────────────────────────────────────┘
                             RUTA UL: Cliente.TX1 → Gateway.RX1

  GATEWAY.TX2, CLIENTE.RX2/TX2: sin conectar
```

### Lista de componentes

| Componente | Cantidad | Estado |
|---|---|---|
| bladeRF 2.0 micro xA4 | 2 | Disponibles (Gateway + Cliente, `SPECS EQUIPOS/SDR_ENLACE`) |
| PC Gateway (host del bladeRF Gateway) | 1 | Ver §4 — reemplaza a la laptop de desarrollo única, decisión revisada |
| Orange Pi 5 (host del bladeRF Cliente) | 1 | Ver §4 — 🟡 entorno (`gr-osmosdr`+bladerf en ARM64) sin verificar todavía |
| Cable USB 3.0 SuperSpeed (Tipo B) | 2 | Uno por host — a verificar que sean puertos USB3 reales, no USB2 (afecta tasa de muestreo) |
| Kit de atenuadores SMA (Nooelec, 1-42 dB en cascada) | 1 comprado | ✅ Alcanza — repartido sin repetir pads entre DL (20dB) y UL (10+6+3dB), ver §6 |
| Pigtail SMA-M↔SMA-M (RG-316, ya comprados para la cadena de campo) | Según haga falta | 🟡 Pendiente verificar si el kit rosca directo al bladeRF sin pigtail — ver §7 |
| Antena discone Tram 1411 (SO-239) | 1 | ✅ Ya comprada (`SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`) — solo Gateway |
| Adaptador SO-239↔SMA | 1 | 🟡 Necesario según `claudedocs/estructura_fisica_instalacion.md` §3.3 — estado de compra sin confirmar, ver §7 |
| LNA Nooelec LaNA (sensado, RX2) | 1 | Disponible (`SPECS EQUIPOS/LNA.md`) — alimentado por bias-tee del bladeRF, sin hardware adicional |

## 4. Selección de host (común a los 2 esquemas): PC Gateway real + Orange Pi 5 Cliente real

**Decisión (20/09/2026, reemplaza la decisión anterior de este mismo
documento):** cada bladeRF va en su host real de campo desde esta primera
corrida — el bladeRF Gateway conectado a la PC Gateway, el bladeRF Cliente
conectado al Orange Pi 5 — en vez de correr ambos en una sola laptop de
desarrollo. Reproduce el hardware asimétrico real del diseño (Intel Core
Ultra 5 vs. ARM64 Orange Pi 5) desde el arranque, no solo en una migración
posterior.

**Riesgo que esto introduce, a diferencia de la opción de 1 sola laptop**:
suma una variable nueva sin verificar todavía — el entorno (`~/envs/SDR`,
GNU Radio 3.10.1.1 + `gr-osmosdr` con módulo bladerf) solo está confirmado
funcionando en la laptop de desarrollo x86_64 (nota 13/09/2026 en el
README de la Prueba 4a-1), **no en el Orange Pi 5 (ARM64)**. Si algo falla
en la primera corrida, va a hacer falta distinguir si es el cableado
RF/calibración del atenuador o si es el entorno del Orange Pi — dejarlo
anotado acá para no perder de vista esa ambigüedad, no para bloquear la
decisión ya tomada.

**Antes de la primera corrida, resolver en el Orange Pi 5** (ver también
checklist §7):
- Instalar/verificar GNU Radio + `gr-osmosdr` con soporte bladeRF en
  ARM64 (paquetes de Ubuntu/Debian para aarch64, o compilar si no hay
  paquete).
- Confirmar que el Orange Pi reconoce el bladeRF Cliente por USB3 (mismo
  chequeo que ya se hizo en la laptop x86_64 con `lsusb`/`bladeRF-cli`).

## 5. Seguridad (común a los 2 esquemas): límites de potencia RX/TX

Ver `SPECS EQUIPOS/SDR_ENLACE` §"Potencia máxima de entrada RX del AD9361"
(agregado 20/09/2026): el bladeRF entrega hasta **+6 dBm de TX**, el RX
tolera como máximo **+2.5 dBm pico** (entrada single-ended, dato de fuente
externa — no está en los PDF curados del repo). Margen negativo de 3.5 dB
sin atenuador.

**Regla operativa obligatoria para esta prueba:**
- Nunca conectar TX↔RX con el atenuador en 0 dB.
- Armar la cascada de atenuadores **antes** de conectar cualquier cable a
  un puerto RX.
- Empezar cada corrida con el `tx_gain` de software lo más bajo posible y
  subirlo de a pasos, no al revés — igual que la calibración de 4a-1
  (mismo criterio, `tx_gain` idéntico entre pasos para poder comparar).

## 6. Calibración de atenuación (común a los 2 esquemas — misma cascada fija, mismo método de TX gain)

**Decisión (20/09/2026, reemplaza la decisión anterior de "una ruta a la
vez"):** el atenuador físico en cada ruta funciona como **piso de
protección fijo**, no como el mecanismo principal de simulación de FSPL —
el resto de la pérdida (FSPL, NLOS, etc.) se simula **reduciendo la
ganancia TX por software** en cada nodo (rango de control de potencia TX
del AD9361: 90 dB, más que suficiente para cubrir los escenarios de
`claudedocs/brief_pruebas_banco_cableado_fullduplex.md` §4, 52.6-87.2 dB).

**Repartición de pads del kit único (Nooelec, 1/2/3/6/10/20 dB, 42 dB en
total) entre las 2 rutas, sin repetir ningún pad — SÍ se puede armar
ambas rutas simultáneamente:**

| Ruta | Pads usados | Atenuación fija | Peor caso con TX a máxima ganancia (+6 dBm) |
|---|---|---|---|
| DL (Gateway.TX1 → Cliente.RX1) | 20 dB | 20 dB | +6 − 20 = **−14 dBm** (seguro, < +2.5 dBm) |
| UL (Cliente.TX1 → Gateway.RX1) | 10 + 6 + 3 dB | 19 dB | +6 − 19 = **−13 dBm** (seguro, < +2.5 dBm) |
| Sin usar | 1 + 2 dB | 3 dB (repuesto) | — |

Con esto, aunque el software de reducción de TX gain fallara por completo
y quedara a máxima ganancia, ninguna ruta supera el límite destructivo del
RX (+2.5 dBm, §5) — el atenuador fijo es la protección de hardware
independiente del software, tal como se buscaba.

**Por qué esto es mejor que la decisión anterior:** antes, con toda la
atenuación del kit dedicada a simular FSPL directamente, no alcanzaba para
las 2 rutas simultáneas (§4 del brief pedía 52.6-87.2 dB por ruta, muy por
encima de lo que un kit de 42 dB repartido en 2 podía dar) — de ahí la
limitación de "probar una ruta a la vez". Al separar el rol del atenuador
(protección fija, pocos dB) del rol del TX gain (simulación de la pérdida
variable, hasta 90 dB de rango), **las 2 rutas quedan armadas al mismo
tiempo** desde esta primera corrida, sin depender de conseguir el segundo
kit.

**Punto a no perder de vista** (ya anotado antes en la conversación, no
bloquea esta prueba): usar el TX gain para simular la distancia consume el
mismo parámetro que después va a necesitar el `CognitiveEngine` para su
propia potencia/modulación adaptativa (pruebas 4a-5 en adelante) — separar
con claridad, en el procedimiento de ejecución (§8), qué parte del TX gain
es "escenario de distancia fijado por el tester" y cuál sería "decisión
del CognitiveEngine", para no confundirlas cuando llegue esa prueba.

### 6.1 Escenario concreto: 15 km (calculado 20/09/2026, motor `LINK_BUDGET/core.py`)

Antes de extrapolar se verificó que el motor reproduce exactamente los
números ya documentados a 4 km (EIRP +28.80dBm, PRx −66.24dBm, márgenes
+34.53/31.53/25.53dB) — confirma que los defaults con hardware real
(`SPECS EQUIPOS/`) siguen bien calibrados.

| | 4 km (referencia) | 15 km |
|---|---|---|
| FSPL (Friis) | 100.04 dB | **111.52 dB** |
| EIRP | +28.80 dBm | +28.80 dBm (no depende de distancia) |
| PRx en antena | −66.24 dBm | **−77.72 dBm** |
| Señal a la entrada del SDR (post LNA, enlace real) | −47.24 dBm | **−58.72 dBm** |
| Margen BPSK / QPSK / 16-QAM | +34.53 / +31.53 / +25.53 dB | **+23.05 / +20.05 / +14.05 dB** |

El enlace real (con PA+LNA) sigue cerrando a 15 km en las 3 modulaciones,
con menos margen que a 4 km pero positivo.

**⚠️ Caveat que no está en el cálculo:** `perdida_nlos_db=0` (LOS) es el
default que el estudio de sitio confirmó **específicamente a 4 km**
(05/09/2026) — a 15 km eso no está verificado, ni la curvatura terrestre
ni la obstrucción de zona de Fresnel están modeladas acá. Tratar estos
márgenes como el mejor caso, no como un hecho confirmado igual que a 4 km.

**Traducción al punto de operación del banco** (igualando el nivel que
llegaría al puerto RX del bladeRF en el enlace real, −58.72dBm, contra
`TX_gain − atenuador_fijo` del banco sin PA/LNA):

| Ruta | Atenuador fijo (§6) | TX gain necesario | Reducción desde el máx. (+6dBm) |
|---|---|---|---|
| DL | 20 dB | −38.72 dBm | 44.72 dB |
| UL | 19 dB | −39.72 dBm | 45.72 dB |

Ambos valores caben dentro del rango de control de potencia TX del AD9361
(90 dB) — viable de configurar por software. Script de referencia:
`link_budget_15km.py` (a copiar a esta carpeta cuando se arme el código,
ver §8).

## 7. Checklist de materiales / verificaciones pendientes antes de ejecutar

**Comunes a los 2 esquemas (infraestructura/hardware del banco):**

- [ ] Confirmar físicamente si el kit Nooelec rosca directo al SMA-hembra
      del bladeRF o si hace falta un pigtail SMA-M↔SMA-M en cada extremo
      (§3) — no se puede confirmar solo por la ficha del producto.
- [ ] Confirmar que tanto la PC Gateway como el Orange Pi tienen un puerto
      USB3 real libre (no hubs USB2, que limitarían la tasa de muestreo).
- [x] ~~Decidir si se persigue el segundo kit de atenuadores~~ — resuelto
      20/09/2026: no hace falta, la repartición de pads de §6 arma las 2
      rutas con el kit único.
- [ ] Verificar disponibilidad de una carga de 50Ω (dummy load) SMA para
      terminar el puerto que quede sin conectar en cada corrida de §6 —
      si no hay, dejar constancia de que quedó desconectado (mismo
      criterio que la Prueba 4a-1, evita que el puerto abierto actúe como
      antena parásita).
- [ ] Instalar y verificar `gr-osmosdr`+bladerf en el Orange Pi 5 (ARM64)
      — no está confirmado como sí lo está en la laptop x86_64 (§4).
- [ ] Confirmar que el adaptador SO-239↔SMA para la discone está
      comprado/disponible (`claudedocs/estructura_fisica_instalacion.md`
      §3.3 lo da por necesario, pero no encontré confirmación de compra
      en el repo).
- [ ] Confirmar logística: PC Gateway y Orange Pi Cliente disponibles
      simultáneamente en el mismo sitio de prueba, con el bladeRF Gateway
      y su cadena de sensado (LNA + discone) armados en paralelo al
      enlace troncal.

**Específico de 4a-3 (half-duplex TDD):**

- [ ] Decidir si se corre 4a-2 (loopback simple, 1 bladeRF) antes de esta
      prueba, o se salta directo a 4a-3 — ver §2, tabla de dependencias.

**Específico de 4a-4 (full-duplex simultáneo) — no iniciar sin esto:**

- [ ] **Gate de entrada**: Prueba 4a-1 corrida con hardware real,
      aislamiento intra-chip TX1→RX1 reportado ≥ ~90-110dB (o cota
      inferior en ese rango) — ver criterio 0 de §1.2. Sin esto, 4a-4 no
      se intenta.
- [ ] 4a-3 aprobada primero (todos sus criterios de §1.2 en verde) — 4a-4
      necesita la línea base para poder medir degradación comparada
      (criterio 3 de §1.2).

## 8. Procedimiento de ejecución

### 8.1 Procedimiento — 4a-3 (half-duplex TDD, a llenar durante la corrida)

*Pendiente — se completa cuando arranque la ejecución real. Referencia:
mismo formato que
`TRANSMISION/pruebas/fase4a_banco_cableado_fd/prueba4a1_aislamiento_intrachip/README.md`
§3 (comandos exactos, checklist previo, cómo interpretar el resultado).*

### 8.2 Procedimiento — 4a-4 (full-duplex simultáneo, a llenar cuando 4a-3 esté aprobada)

*Pendiente — no empieza hasta que el gate de entrada de §7 esté resuelto
(4a-1 con hardware real + 4a-3 aprobada). Cuando arranque, documentar acá
específicamente cómo se verifica el criterio 2 de §1.2 (control in-band
del nodo remoto decodificado a pesar del propio control leakeado) — es el
único procedimiento que no tiene equivalente en 4a-3.*

## 9. Registro de resultados

### 9.1 Resultados — 4a-3 (half-duplex TDD)

| Fecha | Ruta probada (DL/UL) | Atenuador fijo (dB) | `tx_gain` | Criterios de §1.2 cumplidos | Notas |
|---|---|---|---|---|---|
| — | — | — | — | — | Sin corridas todavía |

### 9.2 Resultados — 4a-4 (full-duplex simultáneo)

| Fecha | Aislamiento medido en 4a-1 (dB) | Atenuador fijo DL/UL (dB) | `tx_gain` DL/UL | Criterios de §1.2 cumplidos | Degradación vs. 4a-3 | Notas |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | Sin corridas todavía — bloqueada por el gate de §7 |

## 10. Cómo continuar

- Resolver el checklist de §7 antes de la primera corrida con hardware.
- Actualizar la fila "TRANSMISION" de la tabla de estado en `CLAUDE.md`
  cuando esta prueba arranque o cierre — no crear una tabla de estado
  nueva.
- Registrar esta prueba en la tabla de Fase 4a de
  `TRANSMISION/pruebas/README.md` una vez que tenga primeros resultados
  (sigue el mismo patrón que la fila de 4a-1).
