# bladeRF 2.0 micro xA4 — especificaciones confirmadas

> **Actualizado 28/08/2026 — `SPECS EQUIPOS/SDR_ENLACE` es ahora la fuente
> primaria** para características de este equipo ya comprado (esa carpeta
> es la única fuente para specs de hardware del proyecto en general). Este
> documento se conserva porque tiene información que `SPECS EQUIPOS/SDR_ENLACE`
> no cubre — específicamente el **rango de ganancia TX** y la **potencia TX
> máxima real** (ambos de foro oficial de Nuand, no de una hoja técnica
> formal) — y el análisis narrativo de por qué ese hallazgo importó para el
> proyecto (§"Implicación directa"). Para todo lo demás (frecuencia, ADC,
> canales, FPGA, conectores, bias-tee, dimensiones), consultar
> `SPECS EQUIPOS/SDR_ENLACE` en vez de este archivo.
>
> Recopilado originalmente de fuentes oficiales (Nuand, foro oficial, Analog
> Devices) para reemplazar los valores "por definir"/placeholder que tenía
> el proyecto mientras el SDR Cliente era una incógnita. Ambos nodos
> (Gateway y Cliente) usan este mismo modelo.
>
> El **link budget agregado** que se deriva de estas specs (EIRP, NF de
> sistema, margen DL/UL) no vive aquí ni se recalcula a mano: la fuente de
> verdad es la calculadora `LINK_BUDGET/` (ver `LINK_BUDGET/README.md`).
>
> Nota: "2×2 MIMO full-duplex" abajo describe una **capacidad del chip**
> AD9361 (puede transmitir y recibir simultáneamente) — no implica que el
> *sistema* la use en modo full-duplex. El proyecto decidió el 26/07/2026
> operar en TDD por software (ver `claudedocs/riesgos_arquitectura_transmision.md`,
> "Problema 1"), así que el chip nunca transmite y recibe al mismo tiempo en
> la práctica, aunque sea capaz de hacerlo.

## Specs confirmadas

| Parámetro | Valor confirmado | Fuente |
|---|---|---|
| Rango de frecuencia | 47 MHz – 6 GHz | Nuand |
| RFIC | Analog Devices AD9361 | Nuand |
| ADC/DAC | 12 bits | AD9361 (arquitectura) |
| Canales | 2×2 MIMO (2 TX, 2 RX) full-duplex | Nuand |
| Tasa de muestreo | 61.44 MSPS (hasta 122.88 MSPS con undersampling) | Nuand |
| Interfaz | USB 3.0 SuperSpeed, 5 Gbps | Nuand |
| FPGA | Cyclone V 49 kLE (~32 kLE libres para el usuario) | Nuand |
| Referencia de frecuencia | VCTCXO SiTime MEMS, calibrado de fábrica a ±1 Hz de 38.4 MHz; PLL interno permite disciplinar contra referencia externa de 10 MHz | Nuand |
| **Rango de ganancia TX** | **-23.5 dB a 66 dB** | Foro oficial bladeRF |
| **Potencia TX máxima** | **ganancia 66 dB ≈ +6 dBm** (ganancia 60 dB ≈ 0 dBm) | Foro oficial bladeRF |
| NF nativo del RFIC (RX, sin LNA externo) | <2.5 dB (spec del AD9361) | Analog Devices |

## Implicación directa para este proyecto

**El TX del Cliente sin PA externo tiene un máximo real de ~+6 dBm, no +10 dBm.**
El +10 dBm que tenía el diseño era un valor de referencia genérico de cuando
el SDR Cliente era "por definir" (podía ser un LimeSDR/PlutoSDR con otro
rango de potencia). Con el bladeRF confirmado, el límite físico real coincide
con el que el propio Gateway ya usa como TX1 nominal (+6 dBm antes de su PA) —
consistente, ya que es literalmente el mismo hardware.

## Recalculo del link budget de Uplink (afectado)

Downlink no cambia (el Gateway ya usaba +6 dBm + PA, sin corrección
necesaria). Uplink sí, porque pierde 4 dB de EIRP:

| Parámetro | Valor original (placeholder +10 dBm TX, 10 dBi antena) | Valor actual (+6 dBm TX real, 6 dBi antena real) |
|---|---|---|
| TX Cliente (sin PA) | +10 dBm | **+6 dBm** |
| Ganancia de antena (TX y RX) | 10 dBi | **6 dBi** |
| EIRP UL (TX + antena) | +20 dBm | **+12 dBm** |
| PRx Gateway (EIRP + FSPL/NLOS -126dB + antena RX) | ~-96 dBm | **~-108 dBm** |
| Margen BPSK UL | +3.7 dB | **-7.3 dB (no cierra)** |
| Margen QPSK UL | +0.7 dB (marginal) | **-10.3 dB (no cierra)** |

> **Nota (29/07/2026):** la columna "valor actual" ya incorpora dos
> correcciones aplicadas en momentos distintos: la potencia TX real del
> bladeRF (+6 dBm, no +10 dBm — el hallazgo original de esta sección) y la
> ganancia de antena real (6 dBi, no 10 dBi — corrección posterior, ver
> `claudedocs/requisitos_pa_lna.md` §2 y `README.md` §9.1). Con ambas
> aplicadas, el UL sin PA no cierra en ninguna modulación soportada, ni
> siquiera BPSK.
>
> **Nota (28/08/2026, ya no vigente tampoco):** este análisis quedó
> superado en la práctica desde el 30/07/2026, cuando el Cliente confirmó
> PA de 2W (igual al Gateway) — el escenario "UL sin PA" de esta tabla ya
> no es la arquitectura del proyecto. Se conserva como registro histórico
> de por qué el PA del Cliente pasó de opcional a obligatorio. La ganancia
> de antena de 6 dBi que usa esta tabla también quedó desactualizada — la
> hoja técnica real de la antena comprada (`SPECS EQUIPOS/ANTENA_DIRECCIONAL`)
> da 5 dBi a 500 MHz, valor que ya usa `LINK_BUDGET/`.

**Esto es un hallazgo importante, no solo una corrección cosmética:** el
margen UL en BPSK pasa de "cómodo" a **negativo** — el enlace de subida
directamente no cierra sin PA en el Cliente, con cualquier condición de
campo (lluvia, error en la estimación NLOS, desalineación de antena, deriva
térmica) empeorando aún más un déficit que ya existe en el peor caso
nominal. QPSK en UL, que ya figuraba como "marginal", tampoco cierra.

La nota que ya existía en el README ("el PA en el Cliente queda como
contingencia documentada para Fase 4 solo si las mediciones reales lo
requieren") deja de ser una contingencia hipotética: con specs de hoja
técnica confirmadas (sin necesidad de medir en campo todavía), el margen UL
es negativo. El PA en el Cliente es un requisito, no una opción — y su
ganancia objetivo subió a ~20–23 dB (ver
`claudedocs/requisitos_pa_lna.md` §2) para compensar la pérdida combinada
de potencia TX y ganancia de antena.

## Lo que sigue sin confirmar (no está en ninguna hoja técnica pública)

- Cuánto varía la potencia TX máxima (+6 dBm) específicamente en la banda
  470–698 MHz — el dato de foro no especifica frecuencia de medición.
- Cuánto se extiende realmente el DC leakage en bins del FFT tras la
  calibración de `libbladeRF` (sigue siendo el Problema 2 abierto — esto
  requiere medición propia, no hay cifra pública de "cuántos bins").
- NF del sistema completo con el LNA externo (NF≤1dB) en cascada — el AD9361
  solo (<2.5dB) no es el número relevante una vez que el LNA externo domina
  la cascada de Friis, como ya asume el README.

## Fuentes

- [bladeRF 2.0 micro xA4 — Nuand (producto oficial)](https://www.nuand.com/product/bladerf-xa4/)
- [New to SDR, BladeRF 2.0 xA4 gain question — foro oficial bladeRF](https://nuand.com/forums/viewtopic.php?t=12862)
- [AD9361 Datasheet and Product Info — Analog Devices](https://www.analog.com/en/products/ad9361.html)
- [RF Agile Transceiver Data Sheet AD9361 — Analog Devices](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9361.pdf)
