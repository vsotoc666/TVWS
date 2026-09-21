# Prueba 4a-1 — Aislamiento intra-chip TX1→RX1 (mismo bladeRF)

**Objetivo** (según `claudedocs/brief_pruebas_banco_cableado_fullduplex.md`
§1 y §5): medir cuánta señal llega al puerto RX1 de un bladeRF cuando su
propio TX1 transmite, **sin ningún cable cruzado conectado entre ambos**
— es decir, aislar específicamente el acoplamiento *intra-chip/intra-placa*
(AD9361, PCB) del acoplamiento por aire que ya se sabe insuficiente
(`claudedocs/riesgos_arquitectura_transmision.md`, Problema 1: ~30-50 dB
disponible por separación de antena vs. ~90-110 dB requerido).

Es la primera prueba del banco cableado full-duplex — todo lo demás (4a-2
en adelante) depende de este resultado: si el aislamiento intra-chip
tampoco alcanza, el full-duplex real tampoco es viable en el banco y hay
que replantear el plan (ver brief §2 y §5, nota de prioridad).

**Estado: 🟡 diseñada y auto-validada en software (`--simular`, sin
hardware) el 13/09/2026 — pendiente de ejecutar con el bladeRF real.** No
hay bladeRF conectado a esta máquina en este momento (verificado por
`lsusb`); esta carpeta deja el procedimiento y el código listos para
correr en cuanto haya hardware disponible (UNI o Huánuco).

---

## 1. Idea del método

No hay medidor de potencia RF en el proyecto (`claudedocs/requisitos_pa_lna.md`
§3.3) — hay que medir el aislamiento **sin** conocer la potencia TX
absoluta en dBm. La solución: dos capturas con la **misma ganancia TX**
(así la potencia TX conducida se cancela algebraicamente) y comparar sus
picos en el PSD:

1. **Calibración**: TX1 → cable + atenuador de valor **conocido** (del kit
   SMA, ver `claudedocs/brief_pruebas_banco_cableado_fullduplex.md` §6.1)
   → RX1. Esto establece una referencia: "tanta atenuación conocida da tal
   pico en el PSD".
2. **Medición**: mismo TX1 a la misma ganancia, **sin el cable cruzado**
   (RX1 idealmente terminado con carga de 50Ω; si no hay carga a mano,
   desconectado — dejar constancia de cuál de las dos en el JSON de
   resultado). Lo único que puede llegar a RX1 ahora es el acoplamiento
   intra-chip/intra-placa.

La ganancia RX puede (normalmente debe) ser distinta entre ambas corridas
— la fuga intra-chip suele ser mucho más débil que la ruta calibrada, así
que la medición necesita más ganancia RX para siquiera intentar verla.
Eso se compensa en la fórmula, no hay que igualarla a mano.

### Derivación de la fórmula

Con `K` una constante del pipeline PSD (ventana, normalización — igual en
ambas corridas si se usan los mismos `--n_fft`/`--n_segmentos`) y
`P_tx` la potencia TX conducida (desconocida, pero **igual** en ambas
corridas por diseño del experimento):

```
pico_calibracion_dBFS = P_tx − atenuador_db          + rx_gain_calibracion + K
pico_medicion_dBFS    = P_tx − aislamiento_intrachip + rx_gain_medicion    + K
```

Restando (P_tx y K se cancelan):

```
Aislamiento_dB = atenuador_db
                 + (rx_gain_medicion − rx_gain_calibracion)
                 − (pico_medicion_dBFS − pico_calibracion_dBFS)
```

Implementado en `calcular_aislamiento.py`. Si la medición no detecta el
tono por encima del piso de ruido, se reporta una **cota inferior**
(el aislamiento real es *al menos* ese valor) usando el piso de ruido en
vez del pico — nunca se inventa un número puntual cuando no hay pico real
que medir.

---

## 2. Hallazgo verificado durante el diseño: ganancia de proceso del FFT

**Importante para interpretar `--margen_deteccion_db` y decidir qué tan
"invisible" puede ser una fuga y aun así detectarse:** un tono que se
suma coherentemente en un bin del FFT gana aproximadamente
`10·log10(n_fft)` dB de SNR aparente frente al ruido de banda ancha
(que se reparte incoherentemente entre todos los bins) — con
`n_fft=512` (default, igual que `IA/nucleo.py`), eso son **~27 dB de
ganancia de proceso**. Verificado empíricamente el 13/09/2026 con
`--simular` (`test_medir_psd_tono.py`): una SNR de amplitud inyectada de
−20 dB midió ~6 dB de SNR por bin; −25 dB midió ~2.7 dB — consistente con
la cifra teórica.

**Consecuencia práctica:** si en la medición real (4a-1 con hardware) el
tono no aparece, **subir `--n_fft` antes que `--rx_gain_db`** — más
ganancia RX no mejora la SNR real (amplifica tono y ruido por igual),
mientras que un FFT más largo sí concentra más energía relativa del tono
por bin. `--n_segmentos` (promediado de Welch) reduce la varianza de la
*estimación* del piso de ruido, no el SNR real — no confundir ambas
palancas.

---

## 3. Cómo correr

### 3.1 Autoprueba de la lógica (sin hardware, ya ejecutada)

```bash
python3 test_medir_psd_tono.py
```

No requiere GNU Radio ni el venv `~/envs/SDR` — solo numpy (usa
`--simular` internamente en `medir_psd_tono.py`, que genera IQ sintético
en vez de abrir el bladeRF). Resultado de la corrida del 13/09/2026 en
`test_output.txt` — valida: (1) que la fórmula recupera un aislamiento
conocido inyectado en un escenario sintético construido a propósito
(~55 dB, ver comentarios en `test_medir_psd_tono.py`), (2) que un
escenario de baja SNR se reporta como cota inferior y no como valor
puntual falso, (3) que una `tx_gain_db` distinta entre corridas se
rechaza con error en vez de dar un número silenciosamente incorrecto.

**Esto NO es la Prueba 4a-1** — es la verificación de que el código está
bien antes de gastar tiempo de banco con hardware real.

### 3.2 Ejecución real (requiere bladeRF conectado)

Requiere el venv `~/envs/SDR` (GNU Radio 3.10.1.1 + numpy 1.26.4 — el
Python de sistema tiene un choque de ABI numpy/gnuradio ya documentado en
`TRANSMISION/pruebas/README.md`) y `gr-osmosdr` con el módulo bladerf
(confirmado 13/09/2026 en la máquina de desarrollo: no hay `gr-bladeRF`
nativo instalado, pero no hace falta — `gr-osmosdr` ya envuelve
`libbladeRF` vía `soapysdr0.8-module-bladerf`; verificar lo mismo en la
máquina de banco real antes de asumirlo).

```bash
source ~/envs/SDR/bin/activate

# 1) Calibración: TX1 -> cable + atenuador conocido -> RX1 (conectado)
python3 medir_psd_tono.py --modo calibracion \
    --tx_gain_db 20 --rx_gain_db 10 --atenuador_db 40 \
    --salida resultados_calibracion.json

# 2) Medición: MISMO tx_gain_db, cable cruzado desconectado
#    (RX1 terminado con carga 50 ohm si hay una a mano; si no, desconectado
#    y anotarlo en la bitácora de la corrida -- no lo registra el script)
python3 medir_psd_tono.py --modo medicion \
    --tx_gain_db 20 --rx_gain_db 50 \
    --salida resultados_medicion.json

# 3) Combinar
python3 calcular_aislamiento.py resultados_calibracion.json resultados_medicion.json
```

**Checklist antes de correr:**

- [ ] `--tx_gain_db` idéntico en los dos comandos (el script #3 lo verifica
      y rechaza si no coincide, pero mejor no depender de eso).
- [ ] Confirmar `bladerf=0` resuelve al equipo correcto si hay más de un
      bladeRF conectado a la misma máquina (`SoapySDRUtil --find`).
- [ ] Elegir `--atenuador_db` de calibración lo bastante grande para no
      saturar el RX1 con la ruta calibrada, pero no tan grande que la
      `--rx_gain_db` de calibración tenga que ser absurdamente alta.
- [ ] Si la medición no detecta nada con `--rx_gain_db` alta, subir
      `--n_fft` antes de asumir "no se puede medir" (ver §2).
- [ ] Anotar en la bitácora si RX1 quedó terminado con carga 50Ω o
      simplemente desconectado durante la medición — el script no lo sabe
      ni lo registra, pero cambia qué tan limpio es el resultado (una
      carga real evita que el puerto abierto actúe como antena parásita
      recogiendo RF ambiental, que contaminaría la medición de fuga
      *intra-chip* con fuga *radiada* del entorno).

---

## 4. Cómo interpretar el resultado

Comparar el número de `calcular_aislamiento.py` contra el rango **90-110
dB** (`claudedocs/riesgos_arquitectura_transmision.md`, Problema 1 — el
aislamiento que un full-duplex real necesitaría):

- **Si el aislamiento medido (o su cota inferior) ≥ ~90-110 dB**: la
  hipótesis del brief se sostiene — el banco cableado, con puertos
  TX1/RX1 dedicados por cable, evita el déficit que mató el full-duplex
  real en campo. Seguir con 4a-2 en adelante.
- **Si es menor**: la hipótesis no se sostiene tal cual — el acoplamiento
  intra-chip por sí solo ya sería insuficiente, sin siquiera contar el
  camino externo por el cable cruzado. Esto **no invalida el banco
  cableado como herramienta de prueba** (4a-2/4a-3, half-duplex TDD
  cableado, siguen siendo válidas), pero sí obliga a revisar 4a-4 en
  adelante (full-duplex real) antes de intentarlas — documentar el
  hallazgo en `claudedocs/riesgos_arquitectura_transmision.md` como un
  "Problema 1b" (mismo problema, causa distinta), no descartarlo en
  silencio.
- **Si se reporta como cota inferior** (`>= X dB`, tono no detectado):
  antes de concluir nada, agotar la palanca de `--n_fft` (§2) — un "no
  detectado" a `n_fft=512` puede volverse "detectado, aislamiento = Y dB"
  a `n_fft=4096` sin cambiar nada del hardware.

---

## 5. Archivos

| Archivo | Qué es |
|---|---|
| `psd_welch.py` | PSD por método de Welch (Hann, segmentos promediados) — **copia deliberada** de `IA/nucleo.py::calcular_psd`, no un import. Ver docstring: `IA/nucleo.py` importa `torch` a nivel de módulo, y torch no está instalado en este entorno de pruebas de TRANSMISION (confirmado 13/09/2026, ni en Python de sistema ni en `~/envs/SDR`) — es el mismo problema que ya listaba `claudedocs/arquitectura_transmision_datos.md` como decisión abierta #6 para el `SpectralSensor` de producción, encontrado acá un nivel más abajo. |
| `medir_psd_tono.py` | Captura + mide un tono CW (real vía bladeRF, o sintético vía `--simular`). Usado para las dos corridas (calibración y medición). |
| `calcular_aislamiento.py` | Combina los dos JSON de resultado y aplica la fórmula de §1. |
| `test_medir_psd_tono.py` | Autoprueba de la lógica completa en modo `--simular` (sin hardware). |
| `test_output.txt` | Salida de la autoprueba de software (13/09/2026, `--simular`) — **no es evidencia de hardware real**, solo confirma que el código/fórmula están bien antes de usarlos en banco. |
| `resultados_calibracion.json`, `resultados_medicion.json` | Se generan al correr contra hardware real (§3.2) — no existen todavía en este repo. |

---

## 6. Relación con el resto del plan

- Brief de diseño: `claudedocs/brief_pruebas_banco_cableado_fullduplex.md`
  §1 (pregunta de investigación 2), §2 (por qué se espera que esto
  funcione), §5 (tabla de sub-pruebas 4a-1 a 4a-8).
- Antecedente que motiva esta prueba:
  `claudedocs/riesgos_arquitectura_transmision.md`, Problema 1.
- Siguiente paso si el resultado es favorable: Prueba 4a-2 (loopback
  simple con el atenuador ya calibrado en `claudedocs/brief_pruebas_banco_cableado_fullduplex.md`
  §4 — carpeta `../prueba4a2_loopback_simple/`, todavía no creada).
