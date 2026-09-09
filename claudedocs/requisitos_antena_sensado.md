# Antena de sensado espectral (RX2, Gateway) — verificación contra hoja técnica real

> **Propósito de este documento (actualizado 28/08/2026):** hasta el
> 28/08/2026 este documento era una guía para **buscar** un modelo
> comercial de antena de sensado. Ya no lo es — la antena está comprada
> (discone Tram 1411, `PRESUPUESTO COMPLETO.xlsx` ítem #12) y su hoja
> técnica real vive en `SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`. Este
> documento ahora verifica esa antena real contra los requisitos que se
> habían identificado — §5 sigue sirviendo de formato si en algún momento
> se evalúa un repuesto o alternativa.

---

## 1. Contexto del proyecto (lo mínimo para entender el "por qué")

Proyecto universitario (UNI, Perú, VRI 2026): radio cognitiva TVWS (TV
White Space, UHF 470–698 MHz) para dar Internet a una comunidad rural sin
fibra. El nodo **Gateway** corre un bloque GNU Radio que, entre otras
cosas, **sensa continuamente el espectro TVWS** con una CNN (`IA/`) para
detectar canales ocupados por primarios (canales de TV) vs. libres. Esta
antena es la entrada de ese sensado — un canal de radio (RX2 del bladeRF)
completamente independiente de las antenas de datos (TX/RX del enlace en
sí, que son LPDA WA5VJB 400-1000 MHz, 5 dBi a 500 MHz — ver `SPECS EQUIPOS/ANTENA_DIRECCIONAL`).

**Por qué importa que esta antena rinda bien:** un falso negativo en el
sensado (declarar "libre" un canal que en realidad tiene un primario
activo) es una violación regulatoria, no solo una pérdida de eficiencia —
por eso el umbral de decisión del modelo ya está sesgado hacia el lado
conservador (`UMBRAL_LIBRE=0.20`, no 0.5). Una antena/cadena RF floja acá
empeora directamente la sensibilidad para detectar primarios débiles o
lejanos, que es exactamente el caso que más importa no perderse.

---

## 2. Verificación contra `SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`

El componente real es una **antena base discone Tram 1411**.

| # | Requisito | Objetivo (análisis previo, 21/08/2026) | Valor real (`SPECS EQUIPOS/ANTENA_OMNIDIRECCIONAL`) | ¿Cumple? |
|---|---|---|---|---|
| 1 | Rango de frecuencia | Idealmente algo más ajustado a 400-900/380-1000 MHz, no un discone extremadamente ancho | **25 MHz–1300 MHz** (banda ancha genérica) | ⚠ Sigue siendo el discone de banda ancha que el análisis previo cuestionaba — sin cifra de ganancia por sub-banda para confirmar si esto sacrifica rendimiento en 470-698 MHz (ver punto 2) |
| 2 | Ganancia en banda (470-698 MHz) | ≥2 dBi | **No especificada en la hoja técnica.** El documento solo da VSWR, manejo de potencia, dimensiones y conector — ningún dato de ganancia en dBi ni gráfico vs. frecuencia | ❌ **Gap real, sigue abierto** — la preocupación original (ganancia posiblemente floja en la sub-banda de interés) no se puede confirmar ni descartar con esta hoja técnica |
| 3 | Patrón de radiación | Omnidireccional (horizontal) | Discone — diseño intrínsecamente omnidireccional | ✅ Cumple por diseño |
| 4 | Polarización | A verificar contra la polarización real de ISDB-Tb en la zona | **No especificada en la hoja técnica** (los discones típicos son polarización vertical, pero no está confirmado para este modelo) | ❌ Sigue sin verificar — mismo gap que antes, ahora confirmado que tampoco lo dice el datasheet real |
| 5 | Conector | N-hembra (spec de compra original) | **UHF Hembra (SO-239)** — confirmado, no N | ⚠ No es N-hembra como se documentaba — necesita adaptador SO-239↔SMA para empalmar con el LNA de sensado (SMA-hembra, `SPECS EQUIPOS/LNA.md`), ver `claudedocs/estructura_fisica_instalacion.md` |
| 6 | Intemperie | Apto para exterior, rango de temperatura amplio | Estructura de acero inoxidable a prueba de óxido | ✅ Cumple |
| 7 | VSWR | ≤2:1 en 470-698 MHz específicamente | **≤1.5:1 máximo** (no se desglosa por sub-banda, pero el máximo publicado ya es mejor que el objetivo) | ✅ Cumple — mejor de lo pedido, aunque sigue sin desglose por sub-banda |
| 8 | Mercado | Ruta de compra viable desde Perú | Ya comprada | ✅ Resuelto |
| — | Montaje en mástil | No evaluado antes | **Diámetro de mástil máximo: 35mm** | ❌ **Hallazgo nuevo (28/08/2026):** el mástil real comprado (`SPECS EQUIPOS/MASTILES`) tiene dos tramos, Ø60mm y Ø48mm — ninguno cabe en la abrazadera de esta antena. Necesita un reductor o un punto de montaje auxiliar más angosto — ver `claudedocs/estructura_fisica_instalacion.md` §5 |

## 3. Qué sigue abierto después de la hoja técnica real

Dos de las tres dudas originales (ganancia en banda, polarización) **siguen
sin resolverse** — la hoja técnica comprada no las documenta. Esto no es
un defecto de este análisis, es una limitación real de la información
disponible del producto. Opciones si se quiere cerrar esto antes de
tratarlo como aceptable:

- **Ganancia:** buscar la hoja técnica completa del fabricante (Tram) o
  medir en campo con un generador de referencia — no hay atajo documental.
- **Polarización:** confirmar la polarización real de los transmisores
  ISDB-Tb de la zona de despliegue (dato del operador de TV o medición),
  y asumir polarización vertical para la antena (típico de discones) salvo
  que se confirme lo contrario con el fabricante.
- **Montaje:** resolver el reductor de diámetro antes de instalar — sin
  esto la discone físicamente no se puede fijar al mástil real.

Ninguno de estos tres puntos bloquea usar la antena ya comprada — bloquean
tratar su rendimiento de sensado como confiable sin más verificación, algo
particularmente relevante dado que un falso negativo de sensado es una
violación regulatoria (§1).

---

## 4. LNA y cableado de esta cadena (referencia, definidos en otros docs)

- **LNA de sensado:** mismo modelo Nooelec LaNA que las cadenas de datos
  (NF 0.9dB típico a 1000MHz, +20dB, SMA-hembra, bias-tee del propio
  bladeRF) — ver `claudedocs/requisitos_pa_lna.md` §4, que cubre LNA
  aunque el título diga "PA, LNA".
- **Cable coaxial:** LMR-400, longitud no fija a propósito, dimensionada
  en sitio — el LNA se monta junto a la antena (boca de la discone), con
  el tramo largo de cable después del LNA, no antes, para no perder la
  mejora de NF. No hay GDT en esta cadena (eliminado del diseño del
  proyecto el 28/08/2026 — enlace de validación de solo ~3h). Ver
  `claudedocs/estructura_fisica_instalacion.md` §3.3 para el plano físico
  completo de esta cadena.

---

## 5. Formato de respuesta esperado si se evalúa un repuesto/alternativa

Para cada candidato encontrado, reportar:

1. **Nombre/modelo, fabricante, link de compra o distribuidor.**
2. **Rango de frecuencia real** (no solo el marketing — buscar la hoja
   técnica con el gráfico de ganancia/VSWR vs. frecuencia si está
   disponible).
3. **Ganancia específicamente en 470-698 MHz** (interpolar del gráfico si
   no da un número directo para esa sub-banda) — este es el dato que la
   antena actualmente comprada NO tiene documentado, priorizarlo si se
   evalúa reemplazo.
4. **Polarización** — mismo comentario, dato faltante en la antena actual.
5. **Conector de salida** (y si necesita adaptador — la antena actual usa
   SO-239, no N ni SMA).
6. **Diámetro máximo de mástil soportado** — la antena actual (35mm) no
   calza con el mástil real del proyecto (60mm/48mm), confirmar que un
   reemplazo sí calce o que se resuelva con un reductor.
7. **Precio y disponibilidad de envío a Perú** (o si hay stock/distribuidor
   local).
