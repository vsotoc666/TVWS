# Riesgos arquitectónicos abiertos — capa de transmisión (full-duplex, OFDM, FEC)

Este doc **no es una guía de implementación** — es un registro de problemas
de diseño detectados al analizar `README.md` §3.1/§5/§9.1 y
`claudedocs/arquitectura_transmision_datos.md` en profundidad, mientras se
ejecutaba el plan de pruebas de `TRANSMISION/pruebas/` (Fase 1-2). Ningún
problema listado aquí bloqueó esas pruebas (son todas de software puro,
sin RF real) — pero sí son riesgos que hay que resolver antes o durante la
Fase 4 (hardware real, bladeRF en ambos nodos).

**Instrucción para quien retome esto:** analizar cada problema, investigar
lo que haga falta (cálculos de link budget, literatura de SIC, medición si
ya hay hardware), y proponer una solución concreta acorde a las
restricciones reales del proyecto (presupuesto ≤S/1000 en algunos rubros,
hardware de consumo bladeRF (mismo modelo en ambos nodos), equipo de estudiantes, timeline del
README §14). No asumir que las "direcciones de solución" sugeridas abajo
son la respuesta correcta — son puntos de partida para investigar, no una
decisión ya tomada.

---

## Decisiones cerradas — sesión 20-21/08/2026 (slot TDD, duty cycle, canales, modulación)

Sesión de seguimiento a `claudedocs/brief_enlace_gemelo_digital.md`, previa
a construir el gemelo digital. Cerró slot/guarda TDD, duty cycle, plan de
canales, modulación/FEC y punto de operación del PA — con dos hechos
nuevos confirmados que cambiaron el resultado respecto al análisis del
13/08: **PA de 2 W en AMBOS nodos** (antes solo el Gateway) y **distancia
real de enlace de 5-6 km** (no 10-15 km). El enlace quedó simétrico y con
mucho más margen del esperado.

**La especificación completa y vigente de estas decisiones vive en
`claudedocs/arquitectura_enlace_datos.md`** (framing TDD detallado, plan
de canales, política de modulación/FEC, punto de operación del PA,
presupuesto de disponibilidad y métricas esperadas) — no se duplica aquí
para evitar que las dos copias diverjan. Este documento conserva el "por
qué" (el análisis que llevó a esas decisiones, más abajo en "Problema 1")
y el registro de lo que sigue sin medirse/decidirse.

> **Nota (28/08/2026):** la distancia de 5-6 km de este párrafo ya no es
> la vigente — el proyecto fijó la distancia final del enlace en **4 km**.
> Ver `claudedocs/arquitectura_enlace_datos.md` y `LINK_BUDGET/` para las
> cifras actuales.

---

## Problema 1 (🔴 el más serio): full-duplex en la misma frecuencia, aislado solo por antenas

### Qué dice el diseño actual

`README.md` §3.1 (líneas 149-165) y §3.2 (línea 357) especifican que DL
(Gateway→Cliente) y UL (Cliente→Gateway) transmiten **simultáneamente en
el mismo canal de 6 MHz** (no TDD, no canales separados en frecuencia).
Cada nodo tiene 2 antenas LPDA dedicadas (una TX, una RX), y la única
medida de aislamiento mencionada es "separación física/angular" entre
ellas (línea 159: *"Requiere separación física/angular adecuada entre las
LPDA de TX y RX de un mismo nodo para minimizar el acoplamiento directo
TX→RX (autointerferencia)"*). No hay ninguna mención de:

- Cancelación de autointerferencia (SIC) digital o analógica.
- Circulador o duplexer.
- Un número concreto de dB de aislamiento requerido/objetivo.

Este diseño reemplazó una arquitectura TDD anterior con conmutador SPDT
(líneas 149-153), descartada por dificultad de conseguir el conmutador en
el mercado local y porque el full-duplex "recupera" ~2 dB de margen que se
perdía en la inserción del switch.

### Por qué es un riesgo real

Para que un receptor no se sature con la señal de su propio transmisor
(33 dBm / 2W en el Gateway, en la *misma* frecuencia que está recibiendo),
hacen falta típicamente **90-110 dB** de aislamiento entre las cadenas
TX/RX. Separar dos antenas LPDA físicamente/angularmente en un mismo
mástil da, en el mejor de los casos, del orden de **30-50 dB** — un
déficit de varias decenas de dB. Sistemas reales de full-duplex en la
misma banda (in-band full-duplex, IBFD) casi siempre combinan aislamiento
por antena **con** cancelación activa (SIC) en RF y/o en el dominio
digital; ninguna de las dos aparece en el diseño.

Si el déficit de aislamiento es tan grande como sugiere la estimación de
arriba, el receptor de cada nodo se desensibiliza o directamente se
satura con su propio TX, y el enlace full-duplex simplemente no funciona
como está descrito — independientemente de qué tan bien esté hecho el
resto de la cadena (MAC/FEC/MOD/OFDM), que es exactamente lo que ya se
validó en `TRANSMISION/pruebas/` Fase 1-2.

### Lo que falta investigar/decidir

1. Calcular el aislamiento **requerido** real: potencia TX (33 dBm
   Gateway con PA, +6 dBm Cliente sin PA — mismo bladeRF, confirmado en
   `claudedocs/bladerf_2_micro_xa4_specs.md`) menos la sensibilidad del
   receptor objetivo, más margen de diseño.
2. Estimar o medir el aislamiento **disponible** por separación de antena
   con la geometría real de instalación (distancia, ángulo, posible
   apantallamiento estructural del mástil) — no asumir un número.
3. Si hay déficit, evaluar direcciones (sin decidir cuál todavía):
   - SIC digital (requiere sustraer una réplica de la señal TX propia del
     stream RX — factible en GNU Radio pero añade cómputo y latencia).
   - Circulador o duplexer con offset de frecuencia (implicaría dejar de
     ser "misma frecuencia exacta" y separar DL/UL por unos MHz dentro de
     la banda TVWS — cambia el link budget y el plan de canales).
   - Volver a TDD (revierte la decisión de líneas 149-153; hay que
     sopesar de nuevo la dificultad de conseguir el conmutador SPDT vs el
     riesgo de que el full-duplex no cierre).
   - FDD real: usar dos canales TVWS distintos para DL y UL (consume 12
     MHz de espectro en vez de 6, pero el filtrado por frecuencia sí es
     trivial de lograr con un simple pasabanda — a diferencia del
     aislamiento por antena).
4. Esto se puede/debe medir en cuanto llegue hardware real (Fase 4 del
   plan de pruebas) — es una de las primeras cosas a verificar, antes de
   invertir más tiempo asumiendo que el full-duplex "solo funciona".

### Solución recomendada (decisión, 26/07/2026): half-duplex por software — TDD sin switch ni filtro

Tras evaluar las tres direcciones del punto 3 (SIC, FDD con filtro
pasabanda, TDD con conmutador RF) contra las restricciones reales del
proyecto (equipo de estudiantes, sin instrumentación de laboratorio RF,
presupuesto ≤S/1000, timeline F2-F4), se descarta perseguir full-duplex
real co-canal y se recomienda esta opción como la de mayor probabilidad
de funcionar:

- **SIC** (cancelación activa RF+digital) para cerrar un déficit de
  ~90-110 dB (cálculo del bloque "Autointerferencia sin filtro", ahora en
  la herramienta `LINK_BUDGET/` — el `.xlsx` original que este documento
  citaba fue reemplazado por esa calculadora Streamlit, ver
  `LINK_BUDGET/README.md`) es trabajo de investigación de punta (ej.
  Bharadia/Katti 2013, ~110 dB con antenas de cancelación y hardware RF
  dedicado) — fuera de alcance en este timeline.
- **FDD con filtro pasabanda** (partir la banda en dos mitades DL/UL) es
  viable en el papel, pero depende de sintonizar bien un filtro DIY de
  cavidad/LC sin VNA/analizador de espectro de laboratorio — alto riesgo
  de no rendir lo calculado a la primera, y además restringe 16-QAM en
  los canales cercanos al borde del filtro (rizado de amplitud/fase).
- **TDD con switch RF** fue descartado originalmente por dificultad de
  aprovisionamiento local de un conmutador con la espec requerida — pero
  resulta que **no hace falta ningún switch** si el "conmutador" es
  simplemente no alimentar el TX cuando toca escuchar: cada nodo ya tiene
  2 antenas dedicadas (TX y RX), así que no hay un puerto de antena
  compartido que conmutar.

**Mecanismo:**

1. Trama TDD periódica con slot DL, slot UL, y ventanas de guarda entre
   ambos.
2. Slot DL: Gateway transmite (TX1 activo); Cliente solo escucha (su TX
   se mantiene apagado — gain=0 / sin alimentar muestras, no un switch
   físico).
3. Slot UL: se invierte — Cliente transmite, Gateway escucha con su TX1
   apagado.
4. Ventana de guarda entre slots para el settling de PA/LNA/AGC al
   conmutar TX on/off (a medir — se espera bastante menor que los 10 ms
   ya usados como guarda de salto de canal, porque ahí la guarda es por
   retuning de PLL, no por apagar/encender potencia).
5. RX2 (sensado, discone del Gateway) sigue operando en paralelo, sin
   relación con este esquema — no comparte antena ni cadena con TX1/RX1.

**Sincronización entre nodos (sin canal fuera de banda):** sin LoRa ni
control OOB (ver `CLAUDE.md`), la sincronización de slots se resuelve con
lo que ya existe: un patrón de trama fijo pre-programado en firmware de
ambos nodos, corregido de forma continua con el mismo preámbulo
Schmidl-Cox que ya se usa para sincronizar el símbolo OFDM (`README.md`
§6.2) — el nodo receptor alinea su propia ventana de TX respecto al
timing de trama que detecta en la señal entrante, evitando que la deriva
de reloj (VCTCXO ±1 ppm Gateway, TCXO ±2 ppm típico Cliente) acumule
error relevante dentro de un slot. No requiere handshake aparte: el mismo
símbolo de sincronización que ya usa el receptor para detectar inicio de
trama sirve de referencia de fase para el slot TDD.

**Costo aceptado:** se pierde el throughput simultáneo DL+UL que motivó
pasar a full-duplex — el sistema vuelve al perfil de un TDD (mitad del
tiempo por dirección, o duty cycle asimétrico si se prioriza DL). La
tabla de throughput de `README.md` §5.3 debe recalcularse con el duty
cycle real elegido. La mejora de ~2 dB de margen que motivó abandonar TDD
(recuperar la pérdida de inserción de un switch) deja de aplicar, pero
tampoco hay switch cuya pérdida recuperar — el balance de enlace de
`README.md` §9.1 no cambia respecto al escenario full-duplex sin
autointerferencia.

**Qué falta medir/decidir antes de Fase 4:**

1. Aislamiento real de "TX apagado" (gain=0 / sin muestras) — verificar
   que el leakage residual del LO/PA en reposo quede muy por debajo del
   piso de ruido del receptor; no asumirlo.
2. **Tiempo de guarda y duty cycle — cerrados como especificación de
   diseño (20-21/08/2026)**, el asentamiento real de bias del PA sigue sin
   medirse en banco. Detalle completo (framing TDD, tabla de sensibilidad
   guarda/slot, por qué 50/50 simétrico) en `claudedocs/arquitectura_enlace_datos.md`
   §2 — no se duplica aquí.
3. Robustez de la sincronización de slot vía Schmidl-Cox en un arranque
   en frío (sin trama previa que sincronizar) — puede requerir un
   período inicial de "solo escucha" en ambos nodos hasta detectar la
   trama del otro.

---

## Problema 2: subportadoras de control pegadas a la zona de peor ruido (DC leakage)

### Qué dice el diseño actual

`README.md` §5.2 (líneas 261-273) ubica el campo de control in-band en
los índices #254-257 del vector OFDM de 512 puntos (convención centrada,
DC ≈ índice 256), explícitamente evitando **solo** el índice #255 por
"DC offset / LO leakage del SDR Cliente" (ahora: del RFIC AD9361, igual
en ambos nodos ya que ambos son el mismo bladeRF). Los índices #254, #256 y #257
—que sí se usan para los 3 bits del mensaje de control— están a 1-2 bins
de esa misma fuente de ruido.

Verificado en la Prueba 10 (`TRANSMISION/pruebas/fase2_integracion_por_pares/prueba10_ofdm_tx/`):
la estructura del símbolo (guardas, índices de control, CP) es correcta
tal como está especificada — este problema no es un bug de
implementación, es una característica de la especificación misma.

### Por qué es un riesgo real

Este es el **único** canal de control del sistema — no hay LoRa ni ningún
canal fuera de banda de respaldo (eliminado por presupuesto, ver
`CLAUDE.md`). Si el DC leakage real de un bladeRF de consumo (sin
calibración perfecta, o con deriva térmica en campo) se extiende un poco
más allá del único bin que se evita, se corrompe la señalización de salto
de canal — incluyendo, en el peor caso, el mecanismo de emergencia que
saca al sistema de un canal ocupado por un primario de TV. Eso no es solo
una pérdida de throughput, es una posible violación regulatoria si el
salto de emergencia falla en el momento en que más se necesita.

### Lo que falta investigar/decidir

1. Caracterizar cuánto se extiende realmente el DC leakage del SDR
   elegido (dato de hoja técnica o medición) — puede que 1 bin de guarda
   sea insuficiente o, al revés, más que suficiente.
2. Evaluar mover el campo de control más lejos de DC (con el costo de
   rediseñar `InbandControlTX`/`InbandControlRX`, que ya asumen los
   índices actuales — ver `README.md` §6.3).
3. Evaluar redundancia adicional en el campo de control (ya hay
   repetición entre símbolos OFDM consecutivos durante el pre-anuncio,
   `README.md` línea 378 — evaluar si alcanza).

---

## Problema 3 (✅ decisión tomada 05/09/2026 — ver abajo): FEC convolucional conservador vs. margen de enlace ajustado

### Qué dice el diseño actual

El código FEC usado en las pruebas de software (`TRANSMISION/pruebas/fase1_unitarias/prueba05_fec_roundtrip/`)
es el estándar CCSDS/"Voyager" (K=7, tasa 1/2, del programa espacial de
los años 70). Es la opción que ya viene integrada en GNU Radio y coincide
con la combinación validada en `README.md` §5.3.

### Por qué era un riesgo (menor que 1 y 2, pero real)

El link budget de diseño (`README.md` §9.1) da solo **~15 dB de margen
NLOS** en el caso conservador validado. Un código LDPC bien ajustado
típicamente da varios dB más de ganancia de codificación que un
convolucional K=7 a la misma tasa — en un enlace con margen ajustado,
esos dB pueden ser la diferencia entre cerrar o no el enlace, aunque con
la distancia final más corta (4 km, actualizada 28/08/2026 — antes 10-15
km) el margen de enlace es más amplio y este riesgo pesa menos que antes.

### Decisión (05/09/2026): CCSDS K=7 convolucional + perforado a tasa 3/4, LDPC explícitamente NO adoptado

**CCSDS K=7 convolucional queda como FEC base para los tres modos de
modulación (BPSK/QPSK/16-QAM)**, con **tasa 3/4 obtenida perforando el
mismo código madre de tasa 1/2** (no un segundo códec). Implementado y
probado en `TRANSMISION/pruebas/fase1_unitarias/prueba05_fec_roundtrip/`
(`perforar()`/`despuncturar()` en `ccsds_fec.py`, `test_puncturing_r34.py`).
Detalle completo, incluyendo la curva de ganancia de codificación medida
(tasa 3/4 ya degrada visiblemente a 1% de BER de canal vs. ~3% de tasa
1/2), en `claudedocs/arquitectura_enlace_datos.md` §4.3 — no se duplica
aquí.

**LDPC fue evaluado y explícitamente descartado** (no diferido, no
prototipado), por tres razones:

1. LDPC es un código de bloque (n,k fijos) — el umbral de fragmentación
   ya cerrado (`claudedocs/arquitectura_enlace_datos.md` §2.4, 505
   bytes/18 símbolos) se derivó alrededor del modelo de streaming
   orientado a bytes del código convolucional; migrar exigiría rehacer
   ese umbral para framing alineado a bloque.
2. **El enlace TDD es simétrico** — ambos nodos codifican y decodifican
   en cada ciclo, y el Cliente es un Orange Pi 5 ARM64, mucho más débil
   que el Gateway (Intel Core Ultra 5). El decoder iterativo de
   belief-propagation de LDPC es inherentemente más costoso por bit que
   Viterbi (trellis de 64 estados para K=7), y ese costo real en el
   Orange Pi 5 **nunca se midió ni se preguntó** en los docs previos
   (que solo consideraban cómputo del lado Gateway) — este riesgo no
   verificado en el nodo más débil fue la razón principal para no
   adoptar LDPC ahora.
3. GNU Radio no trae ninguna matriz LDPC de tasa 3/4 lista
   (`/usr/share/gnuradio/fec/ldpc/` solo trae tasas ~0.23-0.58) —
   construir una es trabajo de diseño de matrices fuera del alcance de
   este equipo, mientras que tasa 3/4 convolucional es gratis vía
   perforado del K=7 ya validado.

### Nuevo riesgo real, preservado para si LDPC se reconsidera algún día

Aunque LDPC no se adoptó, el riesgo de fondo (punto 2 arriba) sigue siendo
un hallazgo genuino, no solo una nota de por qué se descartó: **el costo
real de decodificación Viterbi K=7 en el Orange Pi 5 (ARM64) tampoco se
midió** — no hay hardware Orange Pi 5 disponible en el entorno de
desarrollo actual. Se está asumiendo, sin medir, que Viterbi es lo
bastante liviano para el nodo débil; si esa suposición resultara falsa
(o si el margen de enlace se ajustara más y LDPC se reconsiderara pese al
costo), el primer paso sería medir ambos decoders en el hardware ARM64
real, no seguir asumiendo desde el lado Gateway. Ver también
`claudedocs/arquitectura_enlace_datos.md` §8, punto 4.

### Hallazgo relacionado (Prueba 15, Fase 3): el arnés de pruebas de `ccsds_fec.py` — corregido (04-05/09/2026)

No era un problema de qué código FEC elegir, sino de cómo estaba
*implementado* el wrapper de prueba: `ccsds_fec.codificar()`/`decodificar()`
(`TRANSMISION/pruebas/fase1_unitarias/prueba05_fec_roundtrip/ccsds_fec.py`)
creaban, corrían y destruían un `gr.top_block()` de GNU Radio **por cada
paquete**. La Prueba 15
(`TRANSMISION/pruebas/fase3_loopback_completo/prueba15_throughput_sostenido/`)
había medido el throughput real de la cadena completa y obtenido solo
**~0.35x** del objetivo de `README.md` §5.3 (0.67 Mbps vs. 1.9 Mbps para
BPSK R=1/2), con el desglose de tiempo mostrando que el FEC (codificación
+ decodificación) consumía ~72% del tiempo por paquete — casi todo
overhead de arranque de scheduler, no cómputo real.

**Este arnés ya se reescribió** (04-05/09/2026) para usar un
`gr.top_block()` persistente y de inicialización diferida por dirección
(encode/decode), reutilizado entre llamadas — la firma pública
(`codificar`/`decodificar`) no cambió, así que ningún punto de llamada
existente necesitó modificarse. **Resultado honesto: el fix redujo el
costo por llamada de forma medible (~40-55% menos tiempo), pero no cerró
la brecha al objetivo de throughput** — Prueba 15 sigue midiendo ~0.35x
(~0.67 Mbps). Causa: `tb.run()` conserva overhead de arranque/parada de
scheduler no trivial (~0.25 ms/llamada) incluso con topología persistente,
y a los tamaños de payload medidos el resto de la cadena (MOD/OFDM en
Python puro, símbolo por símbolo, sin vectorización) resultó ser un
cuello de botella igual o mayor que el FEC. Detalle completo en
`TRANSMISION/pruebas/fase3_loopback_completo/prueba15_throughput_sostenido/README.md`.
Esto no invalida la decisión de FEC tomada arriba — es un hallazgo de
performance de la implementación de referencia en Python, no de la
arquitectura del codec en sí.

---

## Problema 4: patrón de subportadoras piloto sin definir

### Qué dice el diseño actual

`README.md` §5.1 solo dice "~55 dispersas" (línea 253) — sin tabla de
índices concretos. La Prueba 10 (`TRANSMISION/pruebas/fase2_integracion_por_pares/prueba10_ofdm_tx/`)
usó `numpy` directo en vez del bloque `digital.ofdm_carrier_allocator_cvc`
de GNU Radio justamente porque ese bloque exige una tabla de pilotos
concreta que todavía no existe, y probó solo lo que el doc sí especifica
(guardas, control, CP) dejando todos los slots de "datos + pilotos" como
datos.

### Por qué es un riesgo

Sin pilotos reales, no hay forma de hacer estimación de canal ni
corrección de CFO (corrimiento de frecuencia por oscilador) en un enlace
NLOS real de 4 km (distancia final, actualizada 28/08/2026 — antes 10-15
km) con multipath desconocido. Esto no bloquea las
pruebas de software (Fases 1-3, sin canal real), pero sí bloquea
cualquier prueba con SDR real (Fase 4+) que dependa de ecualización.

### Lo que falta investigar/decidir

1. Definir el patrón de pilotos (espaciado, símbolos piloto, si son fijos
   o tipo comb/block).
2. Migrar `ofdm_symbol.py` (Prueba 10) a usar
   `digital.ofdm_carrier_allocator_cvc` una vez definido, para heredar el
   soporte nativo de GNU Radio en vez de mantener la implementación
   `numpy` manual.

---

## Problema 5 (✅ decisión tomada 21/08/2026 — ver abajo): no hay límite máximo de tamaño de frame MAC/OFDM

### Qué dice el diseño actual

`ofdm_symbol.dividir_en_simbolos_ofdm()` (verificado en
`TRANSMISION/pruebas/fase2_integracion_por_pares/prueba10_ofdm_tx/`) reparte
un frame MAC en tantos símbolos OFDM consecutivos como haga falta, sin
límite superior. La Prueba 14
(`TRANSMISION/pruebas/fase3_loopback_completo/prueba14_paquete_grande/`)
confirmó que esto funciona correctamente incluso para un payload de 1400
bytes (50 símbolos OFDM consecutivos, ~4.5 ms) — y de paso confirmó que
la fragmentación vía `seq_num` (mencionada como pendiente en `README.md`
línea 126) **no está implementada y, con este diseño, no hace falta**.

### Por qué es un riesgo (menor, pero real)

El campo de control in-band viaja embebido en **cada** símbolo de datos
(`README.md` §6.2) — un frame muy largo ocupa el canal de control durante
toda su duración antes de que pueda insertarse una nueva orden de salto.
Con el presupuesto de evacuación de canal de <300 ms (`README.md` línea
525), un frame de 1400 bytes (~4.5 ms) es insignificante, pero no hay
ningún tope definido que impida un frame mucho más grande (o una cola de
varios frames grandes) retrasar una señal de salto de emergencia más allá
de lo aceptable.

### Decisión (21/08/2026)

El límite quedó fijado por el slot TDD, no por el presupuesto de
evacuación de canal directamente: un frame no puede exceder lo que cabe en
un slot de 20 símbolos a la modulación activa — si un payload lo excede
(pasa en BPSK/QPSK-1/2 para el MTU de 1500B de `tun0`, no en QPSK-3/4 ni
16-QAM), se fragmenta vía `seq_num`/PDU ID + bit MF. Diseño completo,
tabla de símbolos-por-modo y propuesta de cambio de header en
`claudedocs/arquitectura_enlace_datos.md` §2.4 — no se duplica aquí.
Beneficio de paso: acota el peor caso de bloqueo del canal de control
in-band a un slot (~1.78 ms) en vez de los ~4.5-5.7 ms de un frame
monolítico grande.

**✅ Implementado (04/09/2026)** — detalle completo en
`claudedocs/arquitectura_enlace_datos.md` §2.4, no se duplica aquí.

---

## Prioridad sugerida para quien retome esto

1. **Problema 1 (full-duplex)** — el de mayor impacto. **Decisión tomada
   (26/07/2026):** se descarta full-duplex real co-canal; se adopta TDD
   por software (ver "Solución recomendada" arriba) — sin switch RF ni
   filtro, apagando el TX digitalmente durante el slot de recepción.
   **Slot, guarda, duty cycle, canales, modulación/FEC y punto de
   operación del PA cerrados el 20-21/08/2026** — especificación completa
   en `claudedocs/arquitectura_enlace_datos.md`. Pendiente: medir
   aislamiento real de "TX apagado" y el settling real de bias del PA
   antes de Fase 4 (puntos 1 y 2 de esa sección).
2. **Problema 2 (control cerca de DC)** — impacto de seguridad/regulatorio
   si falla en el peor momento; barato de investigar (solo requiere datos
   de hoja técnica o una medición corta).
3. **Problema 4 (pilotos)** — bloquea cualquier prueba con SDR real
   (Fase 4+), así que hay que resolverlo antes de llegar ahí, pero no es
   urgente mientras se siga en Fases 1-3 (software puro).
4. **Problema 3 (FEC)** — **✅ decidido (05/09/2026):** CCSDS K=7
   convolucional base + perforado a tasa 3/4, LDPC explícitamente
   descartado — ver detalle arriba y `claudedocs/arquitectura_enlace_
   datos.md` §4.3. Queda un hallazgo nuevo (no bloqueante): el costo de
   Viterbi en el Orange Pi 5 (ARM64) no se midió, solo se asumió liviano.
5. **Problema 5 (tamaño máximo de frame)** — **✅ decidido e implementado
   (21/08/2026 diseño, 04/09/2026 código):** fragmentación vía `seq_num`/PDU
   ID + bit MF cuando un frame excede lo que cabe en un slot TDD
   (`claudedocs/arquitectura_enlace_datos.md` §2.4).
