# Brief: enlace físico (half-duplex, modulación, canales) + gemelo digital

> Punto de partida para retomar esto en un chat nuevo, sin tener que
> re-derivar lo ya decidido/investigado. Fecha de creación: sesión del
> 13/08/2026 (análisis de half-duplex TDD, FDD descartado, y priorización
> de investigación en IA). Si esta fecha es vieja cuando lo leas, verificar
> primero que nada de "Contexto ya resuelto" cambió mientras tanto.
>
> **Nota (28/08/2026):** la distancia de 5-6 km mencionada abajo ya no es
> la vigente — el proyecto fijó la distancia final del enlace en **4 km**.
> Ver `claudedocs/arquitectura_enlace_datos.md` y `LINK_BUDGET/`.
>
> **✅ Etapa 1 (cerrar decisiones) completada el 20/08/2026.** Las 5
> decisiones de la sección "Qué falta decidir" están cerradas — ver
> `claudedocs/riesgos_arquitectura_transmision.md`, sección "Decisiones
> cerradas — sesión 20/08/2026" (al inicio del doc). Dos hechos nuevos que
> no se conocían el 13/08 cambiaron el resultado: PA de 2 W confirmado en
> **ambos** nodos (antes solo el Gateway) y distancia real de enlace de
> **5-6 km** (no 10-15 km) — el enlace quedó simétrico y con mucho más
> margen del esperado. `README.md`, `LINK_BUDGET/`, `requisitos_pa_lna.md`
> y `cumplimiento_normativo_tvws.md` ya están sincronizados con estos
> números. **Este documento queda como registro histórico de cómo se
> llegó ahí** — para el estado vigente de las decisiones, leer el doc de
> riesgos, no este brief. La Etapa 2 (construir el gemelo digital) es lo
> que sigue.

## Objetivo

Cerrar el diseño del enlace físico TX/RX (largo de slot TDD, duty cycle,
cantidad/disposición de canales TVWS, modulación por canal) y construir
una simulación tipo **gemelo digital** de todo el enlace en software,
porque el hardware bladeRF todavía no llegó.

## Cómo arrancar — mi recomendación, no es solo "pegar este archivo"

1. **Que sea una sesión nueva de Claude Code en este mismo repo** (mismo
   directorio de trabajo), no pegar este archivo en un chat sin acceso al
   código. `CLAUDE.md` se carga solo en cualquier sesión nueva acá — ya
   apunta a este doc (ver más abajo) y al resto de la documentación
   canónica. Sin eso, cualquier chat nuevo tendría que re-preguntar todo
   lo que ya está resuelto.
2. **Separar la sesión en dos etapas, no una sola conversación abierta:**
   primero cerrar las decisiones de la sección "Qué falta decidir" (es
   una conversación de diseño, con posible investigación puntual como la
   de esta sesión), y **recién después** empezar a construir el gemelo
   digital — construirlo sin esas decisiones cerradas significa adivinar
   parámetros y rehacer trabajo.
3. **Para el gemelo digital en sí, seguí el mismo patrón que
   `TRANSMISION/pruebas/`** (carpetas por fase, un README por prueba,
   evidencia guardada) en vez de un script de simulación monolítico —
   ya demostró funcionar bien en este proyecto y hace que el resultado
   sea auditable por otro chat/persona después.

## Contexto ya resuelto (no re-litigar sin una razón nueva)

- **Full-duplex real descartado, TDD por software decidido (26/07/2026).**
  Motivo con números: se necesitan ~90-110 dB de aislamiento TX→RX propio;
  separar antenas 4 m da solo ~40 dB (cálculo FSPL); ni con separación
  física razonable en el mismo mástil se cierra ese déficit. Detalle
  completo: `claudedocs/riesgos_arquitectura_transmision.md`, "Problema 1".
- **FDD con grupos de canales distintos para UL/DL, sin filtro físico,
  tampoco resuelve el problema.** El front-end del AD9361 es de banda
  ancha (~56 MHz instantáneos) — sigue "viendo" la potencia cruda del TX
  propio aunque esté en otro canal, a menos que haya un filtro pasabanda
  analógico antes del LNA/ADC. Sin ese filtro, la separación de frecuencia
  es solo una etiqueta lógica, no aislamiento real.
- **Mecanismo de conmutación TX recomendado:** ráfagas con timestamp del
  bladeRF (`BLADERF_META_FLAG_TX_BURST_START`/`END`, contador de FPGA de
  precisión sub-microsegundo) — no `gain=0` (no apaga la fuga de LO de
  verdad) ni parar de alimentar muestras sin más.
- **Hallazgo sin resolver:** el bladeRF no tiene un GPIO dedicado para
  avisarle a un PA externo "ahora toca transmitir" — hay que diseñarlo
  aparte (GPIO de expansión de libbladeRF, con su propia latencia).
- **Cifras de conmutación del AD9361:** confirmadas para *re-sintonía* de
  frecuencia (VCO >37µs + PLL ~15µs + DAC ~18µs, >70µs total). **No
  confirmadas** para conmutación en la *misma* frecuencia (nuestro caso,
  debería ser más rápido) — la investigación se cortó por timeouts de
  fetch antes de cerrar esto; retomar si hace falta el número real.
- **Canales bonded dentro de la ventana de 56 MHz instantánea:** viable
  con el mismo hardware (mismo LO, sin re-sintonía), y ayuda a recuperar
  throughput perdido por el TDD. Canales dispersos fuera de esa ventana
  necesitan re-sintonía por salto (costo ya cuantificado arriba).
- **Regulatorio (Art. 17-18 MTC):** el proyecto va a depender de una base
  de datos de canales autorizados, no de sensado libre — esto acota qué
  canales están siquiera disponibles para evaluar en el diseño del
  enlace. Ver `claudedocs/cumplimiento_normativo_tvws.md`.

## Qué falta decidir (el foco real de la sesión nueva)

1. **Largo de slot TDD y duty cycle DL/UL.** Ya hay una tabla de
   sensibilidad (guarda vs. slot vs. throughput resultante) hecha en la
   sesión del 13/08 — pedirle a Claude que la reconstruya si no está
   guardada todavía en `riesgos_arquitectura_transmision.md` al momento
   de leer esto.
2. **Tiempo de guarda real.** Depende del PA que se elija — no hay modelo
   comprado todavía (`claudedocs/requisitos_pa_lna.md`). Sin PA concreto,
   trabajar con un rango (optimista/pesimista), no un número fijo.
3. **Cantidad y disposición de canales TVWS.** Un canal simple vs.
   agregación dentro de la ventana de 56 MHz vs. multi-ventana con
   re-sintonía — cada uno con trade-offs ya esbozados arriba.
4. **Modulación por canal/dirección** (BPSK/QPSK/16-QAM) y su relación
   con el link budget real — correr `LINK_BUDGET/app.py`, no asumir.
5. **Estructura del gemelo digital** — ver siguiente sección.

## El gemelo digital — qué ya existe, qué falta construir

**No arrancar de cero.** `TRANSMISION/pruebas/fase3_loopback_completo/`
ya es un gemelo digital parcial y validado: TX completo → canal (ideal o
con errores de bit sintéticos) → RX completo, en software puro, sin SDR
(Pruebas 12-15). Reusa `mac_frame.py`, `ccsds_fec.py`, `constelaciones.py`,
`ofdm_symbol.py`, `rx_chain.py`, `loopback_block.py` — todos ya probados.

Lo que falta para que sea un gemelo digital *completo*:

- **Modelo de canal realista**, no solo bit-flips sintéticos: multipath/
  NLOS, corrimiento de frecuencia (CFO, por el VCTCXO real del bladeRF),
  desalineamiento de timing, ruido AWGN calibrado con las cifras reales
  de `LINK_BUDGET/`. GNU Radio ya trae `gr-channels`
  (`channels.channel_model`, `channels.channel_model2`) diseñado
  exactamente para esto — no reimplementar desde cero.
- **El scheduler TDD real** (slots, guardas, apagado de TX) — hoy la
  Fase 3 no lo modela; TX y RX ocurren "instantáneo" en la misma llamada
  Python, sin noción de tiempo real ni de slots.
- **Arreglar el cuello de botella de performance del FEC** (Prueba 15:
  cada llamada a `ccsds_fec.py` crea/destruye un `top_block` de GNU Radio
  por paquete) antes de medir throughput del gemelo digital — si no, los
  números van a reflejar ese overhead, no el diseño real.

## Documentos a leer, en orden

1. `CLAUDE.md` (raíz) — se carga solo, no hace falta pedirlo.
2. `claudedocs/riesgos_arquitectura_transmision.md` — decisión de TDD,
   análisis de aislamiento, y (si se guardó) la tabla de sensibilidad
   guarda/slot/throughput.
3. `TRANSMISION/pruebas/README.md` y
   `TRANSMISION/pruebas/fase3_loopback_completo/README.md` — el gemelo
   digital parcial ya construido.
4. `LINK_BUDGET/README.md` — cifras de link budget, correr la calculadora
   antes de asumir un número.
5. `README.md` §3 (arquitectura del sistema), §5 (parámetros OFDM), §9
   (link budget).
6. `claudedocs/cumplimiento_normativo_tvws.md` — restricción de canales
   disponibles por regulación.
