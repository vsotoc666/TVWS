# Cumplimiento normativo — Decreto Supremo N° 024-2021-MTC (TVWS Perú)

Este doc es el **registro canónico de incompatibilidades entre la arquitectura
descrita en `README.md` y la norma legal peruana que regula TVWS**
(`Decreto_Supremo_024-2021-MTC_TVWS.pdf`, en la raíz del repo — "Norma de uso
de la banda de frecuencias 470-698 MHz, para los servicios de
telecomunicaciones inalámbricas referidos en la Nota P11B del PNAF").

**Contexto de por qué existe este doc:** el proyecto se diseñó (mayo-julio
2026) sin haber revisado antes esta norma. Este análisis se hizo el
14/08/2026, ya con F2 en curso (10/07-31/08/2026), cruzando los 20 artículos
del decreto contra la arquitectura de `README.md` completa. **Ningún hallazgo
de aquí bloquea el trabajo de software en curso** (IA, MAC/FEC/OFDM,
`TRANSMISION/pruebas/` son todos válidos independientemente de esto) — pero sí
condicionan qué tan desplegable es el sistema tal como está pensado, sobre
todo de cara a Fase 4 (despliegue rural real, 21/10-02/12/2026).

**Instrucción para quien retome esto:** antes de asumir que un hallazgo sigue
vigente, releer la sección relevante de `README.md` (puede haber cambiado) y
recalcular si depende de un número de link budget (ver `LINK_BUDGET/`, fuente
de verdad de esas cifras). Los cálculos de PSD de este doc son estimaciones
con los datos que había en `README.md` al 14/08/2026, no mediciones de
laboratorio — hay que confirmarlas con analizador de espectro en cuanto haya
hardware.

---

## 🔴 Bloqueantes — chocan con la premisa del proyecto, no con un parámetro

### Problema 1 (el más serio): la norma exige base de datos, el proyecto usa sensado por CNN

**Qué dice la norma:** Art. 17 — todo dispositivo TVWS debe consultar
*obligatoriamente* una base de datos de canales disponibles autorizada
**antes** de transmitir. Art. 18 — el dispositivo debe comunicarse con esa
base de datos al menos una vez cada 24h y reconfigurarse de inmediato si un
canal previamente libre pasa a ser ocupado por un servicio primario. Este es
el modelo clásico "geolocation database" de TVWS (el mismo paradigma que
adoptó la FCC en EE.UU. desde 2010).

**Qué hace el proyecto:** `README.md` §2 describe el aporte central como
"bloque de software GNU Radio... desde el sensado espectral con CNN hasta la
señalización de salto de canal in-band". Las Capas 2-4 (§2.2, RadioInterface
→ SpectralSensor → ChannelClassifier → CognitiveEngine) deciden qué canal
usar **exclusivamente por sensado espectral local** (PSD + CNN). No hay
ningún cliente de base de datos, ninguna consulta previa a TX, ninguna
resincronización periódica con una fuente externa autorizada — el propio §8
del README describe el sensado como *el* mecanismo de acceso dinámico, no
como una capa complementaria.

**Por qué importa:** esto no es un parámetro que se ajusta — es el
paradigma regulatorio completo. La ley peruana no reconoce "sensing-only"
como mecanismo de habilitación de canal (la FCC tampoco lo reconoció hasta
~2015, y solo como *complemento* de la base de datos, nunca sustituto). El
sensado CNN puede seguir siendo valioso como capa de seguridad adicional
(detectar interferencia no prevista por la BD, acelerar el hop en
degradación abrupta — ver §7.6 canal refugio), pero **no puede ser el único
mecanismo de decisión de canal** si el sistema debe operar conforme a Art.
17-18.

**Abierto, sin resolver:** no se confirmó si existe hoy una base de datos de
canales TVWS operativa y autorizada en Perú. Si no existe, es un problema de
todo el ecosistema TVWS peruano, no solo de este proyecto — pero de todos
modos condiciona qué es "cumplir la ley" en la práctica. **Verificar con
MTC/DGPPC antes de rediseñar nada.**

### Problema 2: geolocalización obligatoria, ausente del diseño

**Qué dice la norma:** Art. 13 — los dispositivos maestros TVWS deben tener
capacidad de geolocalización integrada, determinando y reportando
coordenadas exactas (lat/lon) antes de cualquier transmisión y
periódicamente durante la operación.

**Qué hace el proyecto:** ninguna de las 6 capas del bloque cognitivo
(`README.md` §2.2) ni el BOM de hardware (§4.1/§4.2) incluye GPS ni ningún
mecanismo de geolocalización. Falta un módulo completo (hardware + capa de
software que lo reporte, presumiblemente hacia la misma base de datos del
Problema 1, ya que el Art. 13 y el Art. 17 están pensados para trabajar
juntos: la BD necesita saber dónde está el dispositivo para decirle qué
canales están libres *en esa ubicación*).

### Problema 3: homologación de equipos

**Qué dice la norma:** Art. 6 — todo equipo TVWS debe tener certificado de
homologación del MTC antes de operar en el país.

**Qué hace el proyecto:** bladeRF 2.0 micro xA4 + PA custom (2W) + LNA
custom no tienen (ni es realista que tengan, a esta escala de proyecto
universitario) certificado de homologación TVWS. Esto no bloquea pruebas de
laboratorio/banco, pero sí cualquier operación real en campo (Fase 4, enlace
de 4 km — antes 10-15 km, distancia de diseño inicial) sin algún tipo de
autorización experimental — la norma no
contempla explícitamente un régimen de excepción para investigación
universitaria. **Verificar con MTC si existe una vía de autorización
experimental/temporal** independiente de este decreto (es común en la
mayoría de reguladores, pero no está confirmado para este caso).

---

## 🟠 Importantes — violaciones técnicas cuantificables, corregibles con rediseño de RF

### Problema 4 (✅ resuelto 20/08/2026 — ver recálculo abajo): el Gateway excedía la densidad espectral máxima de potencia

**Qué dice la norma:** Art. 8 — la potencia que un equipo TVWS entrega a su
antena no puede superar **12.6 dBm por cada segmento de 100 kHz**.

**Cálculo original con los datos de `README.md` §4.1/§9.1 (14/08/2026):**

```
PA Gateway:        bladeRF TX1 (+6 dBm) + PA 2W (+27 dB) = +33 dBm a la salida del PA
Pérdidas a antena:  LMR-400 3.5m (~0.67 dB) + GDT (≤0.3 dB) ≈ ~1 dB
Potencia en antena: ~+32 dBm
...
PSD ≈ 32 dBm − 17.3~17.8 dB ≈ 14.2–14.7 dBm/100kHz
Límite legal: 12.6 dBm/100kHz
Exceso: ~1.6–2.1 dB (~1.5–1.6×)
```

Ese cálculo asumía la potencia de salida del PA como una ganancia fija
(+27 dB sobre el TX del bladeRF), sin backoff — un modelo que
`LINK_BUDGET/core.py` reemplazó el 30/07/2026 por `Salida = P1dB − backoff`
(más correcto para un PA operando con la señal OFDM de alto PAPR).

**Recálculo (28/08/2026), con la hoja técnica real del PA
(`SPECS EQUIPOS/PA.md` — "OEM 2W 1-900MHz", P1dB real >32 dBm, no el
nominal genérico de 33 dBm) y sin GDT (eliminado del diseño el 28/08/2026 —
enlace de validación de solo ~3h, ver `claudedocs/estructura_fisica_instalacion.md`):**

```
PA Gateway (y Cliente, mismo modelo real): P1dB 32 dBm, backoff 7.5 dB
  → salida promedio +24.5 dBm
Pérdidas a antena: LMR-400 (~0.7 dB, longitud no fija — sin GDT)
Potencia conducida a la antena: +23.8 dBm

PSD ≈ 23.8 dBm − 17.3~17.8 dB ≈ 6.0–6.5 dBm/100kHz
Límite legal: 12.6 dBm/100kHz
Margen: ~6.1–6.6 dB POR DEBAJO del límite — ya no excede, con más margen
todavía que con el P1dB genérico usado antes
```

> **Historial:** hasta el 28/08/2026 este cálculo usaba P1dB=33dBm (nominal
> genérico "PA de 2W") con GDT (potencia conducida +24.5 dBm, margen
> ~5.4-5.9 dB), y luego sin GDT pero todavía con P1dB genérico (+24.8 dBm,
> margen ~5.1-5.6 dB). Con la hoja técnica real del PA (P1dB 32 dBm, no 33)
> la potencia conducida baja a +23.8 dBm — el margen legal mejora
> (~6.1-6.6 dB), en la misma dirección que ya venía la corrección, ahora
> con un dato de hardware real en vez de un nominal genérico.

**El exceso de PSD original se resolvió como efecto secundario de operar
el PA con backoff adecuado para linealidad OFDM (6-9 dB, no la ganancia
fija sin backoff que se asumía antes)** — no hizo falta un TPC dedicado ni
reducir la potencia nominal del PA, y la hoja técnica real confirma que
hay incluso más margen legal del que se pensaba. **Sigue siendo una
estimación, no una medición certificada** — el ACPR/OIP3 real del PA no
está documentado (`claudedocs/requisitos_pa_lna.md` §3.3), así que esta
cifra de PSD media no garantiza ausencia de spectral regrowth fuera de
canal; confirmar con analizador de espectro en cuanto haya hardware real.

**Nota de consistencia:** este cálculo usa el EIRP/potencia de
`README.md` §9.1, que a su vez cita `LINK_BUDGET/` como fuente de verdad
— si esa cifra cambia, recalcular esta sección también.

### Problema 5: no hay control automático de potencia (TPC)

**Qué dice la norma:** Art. 11 — los equipos deben incorporar TPC, operando
con la potencia mínima necesaria para un enlace fiable.

**Qué hace el proyecto:** ninguna capa del bloque cognitivo tiene lógica de
ajuste dinámico de potencia TX (`README.md` §2.2) — el PA opera a ganancia
fija (+27 dB). Esto es además la solución más directa al Problema 4: con TPC
real, bajar ~2-3 dB de potencia en el Gateway resolvería el exceso de PSD
sin tocar hardware.

### Problema 6: sin filtro de salida, riesgo sobre el límite de emisiones espurias

**Qué dice la norma:** Art. 10 — las emisiones espurias no pueden superar
−42.8 dBm/100kHz fuera del canal de operación.

**Qué hace el proyecto:** la cadena TX del Gateway (`README.md` §4.1) no
tiene ningún filtro pasabanda analógico entre el PA y la antena — solo
bandas de guarda digitales dentro del símbolo OFDM, que no atenúan
armónicos ni productos de intermodulación generados por un PA de banda
ancha 400-1000 MHz. Sin filtro físico es razonable esperar que no cumpla
este límite; no hay dato en el repo que lo descarte ni que lo confirme.

---

## 🟡 Menores / a verificar

### Problema 7: altura de antena no documentada

Art. 12 — altura máxima de antena TX 100 m sobre el nivel del terreno, EHAAT
≤800 m. `README.md` no especifica altura de mástil en ninguna sección. La
memoria de proyecto sobre mástiles no-penetrantes (instalación de azotea)
sugiere que probablemente cumple, pero no está verificado por escrito en
ningún doc del repo.

### Problema 8: seguridad de equipos — parámetros RF 100% reconfigurables por software

Art. 14 — el usuario final/operador/instalador no debe poder modificar los
parámetros RF de fábrica (frecuencia, potencia máxima, límites de
emisiones). El prototipo es enteramente reconfigurable por software (GNU
Radio, todos los parámetros expuestos por capa en `README.md` §2.2).
Aceptable en TRL-4/investigación — bloquearía homologación comercial sin un
rediseño que "bloquee" esos parámetros de fábrica, pero eso es un problema
de una fase posterior a este proyecto.

---

## ✅ Lo que sí cumple (para no perder de vista que no todo es un problema)

| Artículo | Requisito | Por qué cumple |
|---|---|---|
| Art. 7 | Ubicaciones fijas, punto a punto/multipunto, no portátil/móvil | Gateway y Cliente son ambos fijos — cumple exactamente |
| Art. 9 | Ganancia de antena ≤14 dBd (16.15 dBi) | LPDA real 5 dBi a 500 MHz (`SPECS EQUIPOS/ANTENA_DIRECCIONAL`, actualizado 28/08/2026), muy por debajo |
| Art. 15.2 | Uso en áreas rurales / interés social | Es el caso de uso declarado del proyecto |
| Art. 5 | No interferir a primarios (objetivo, no mecanismo) | Es el objetivo del sensado CNN — el problema es el *mecanismo* (Problema 1), no la intención |

---

## Evaluación de viabilidad (14/08/2026)

**Como investigación (TRL-4, laboratorio/campo controlado), el proyecto sigue
siendo viable tal cual.** Nada de lo anterior invalida el trabajo de IA,
MAC/FEC/OFDM ni el link budget — esas piezas se pueden seguir desarrollando
y validando sin cambios.

**Como producto desplegable conforme a ley en su forma actual, no lo es** —
y el hallazgo más grave no es de RF sino conceptual (Problema 1): la norma
exige un modelo de base de datos, el proyecto está diseñado alrededor de un
modelo de sensado. Ese es un cambio de diseño en `CognitiveEngine` (Capa 4)
y probablemente en el protocolo de canal refugio (§7.6), no un ajuste de
parámetro.

**Orden de esfuerzo para resolver, de más fácil a más difícil:**

1. **TPC** (Problema 5, todavía abierto — falta lógica de ajuste dinámico
   de potencia, exigida por Art. 11 independientemente del margen de PSD).
   **Problema 4 (exceso de PSD) se resolvió el 20/08/2026** como efecto
   del backoff de 7.5 dB decidido para linealidad OFDM — ya no requiere
   trabajo aparte, ver recálculo en la sección de Problema 4.
2. **Filtro pasabanda TX** (Problema 6) — compra de componente, no
   rediseño de arquitectura.
3. **Geolocalización** (Problema 2) — añadir módulo GPS + capa de reporte,
   del orden de semanas.
4. **Homologación / autorización experimental** (Problema 3) — trámite
   administrativo con MTC, fuera del control del cronograma del equipo;
   es lo que más puede golpear la Fase 4 (21/10-02/12/2026, ya con margen
   ajustado).
5. **Base de datos como mecanismo primario** (Problema 1) — el cambio más
   grande. Antes de rediseñar, confirmar con MTC/DGPPC si existe una vía de
   excepción para pilotos de investigación universitaria — si no hay base
   de datos operativa en Perú todavía, ese camino de excepción podría ser
   la única vía realista de todos modos, independientemente del rediseño.

**Recomendación concreta:** antes de seguir invirtiendo en F2 (en curso
desde 10/07/2026), conseguir una consulta formal con MTC/DGPPC sobre (a) si
existe un régimen de autorización experimental para investigación
universitaria que exima de Art. 6/13/17/18 durante fase de prueba, y (b) si
la base de datos de canales del Art. 17-18 ya está operativa. La respuesta a
esas dos preguntas determina si esto es un ajuste de ingeniería o un
rediseño de arquitectura completo.
