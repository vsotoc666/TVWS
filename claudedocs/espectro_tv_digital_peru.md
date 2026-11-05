# Espectro de TV en el Perú: qué hay, cómo transmite y antecedentes TVWS

Investigación del 04-05/11/2026. Es el doc canónico sobre las señales primarias
de la banda (ISDB-Tb y NTSC-M), su plan de canales y los antecedentes de TVWS en
países con ISDB-T. No reemplaza a los docs canónicos de otros hechos: las cifras
de enlace viven en `LINK_BUDGET/` y el análisis legal en
`claudedocs/cumplimiento_normativo_tvws.md`.

**Nivel de evidencia.** Cada dato cae en uno de estos grupos:

- **Sin marca:** viene de una fuente listada en §10 o de un archivo del repo.
- **[cálculo]:** lo calculamos a partir de datos con fuente; es reproducible, no medido.
- **[inferencia]:** interpretación nuestra, sin confirmación directa.
- **[sin verificar]:** recordado del estándar, sin contrastar contra el texto.

## 1. Resumen

- Un canal digital ocupado es una meseta OFDM casi plana de 5.57 MHz, sin piloto
  fuerte y con flancos muy abruptos, corrida +1/7 MHz dentro del canal de 6 MHz.
- Un canal analógico NTSC-M son tres portadoras angostas. El modelo actual, entrenado
  solo con ISDB-Tb, las declara libres (§8.3).
- La banda legal de TVWS es 470-698 MHz, es decir, canales 14-51. El código usa
  14-52 (§7.1).
- Hay antecedentes de TVWS en países con ISDB-T, pero no encontramos ninguno con
  resultados medidos en el Perú. El más útil es el de Brasil (§6.2).
- Brasil combina base de datos y sensado, el mismo esquema que podría resolver el
  bloqueador normativo de este proyecto.

## 2. Marco y plan de canales

| Aspecto | Dato |
|---|---|
| Estándar digital | ISDB-T con variantes brasileñas (ISDB-Tb). Adoptado en 2009 con la RS 019-2009-MTC |
| Plan de transición | Plan Maestro, DS 017-2010-MTC, modificado después (DS 011-2019, DS 007-2021) |
| Estándar analógico | NTSC-M, según las normas técnicas de la RM 358-2003-MTC/03 |
| Ancho de canal | 6 MHz |
| Banda TVWS | 470-698 MHz, sin licencia (DS 024-2021-MTC, Art. 4) |
| Banda de 700 MHz | 698-806 MHz, con 3 bloques de 2×15 MHz adjudicados a móviles (contratos de 2016) |
| Video digital | H.264 (MPEG-4 AVC). Audio HE-AAC [sin verificar para el Perú] |

### Qué permite la Nota P11A del PNAF

| Banda | Canales | Estado |
|---|---|---|
| 470-608 MHz | 14-36 | TV digital; lo analógico ya asignado puede continuar |
| 608-614 MHz | 37 | **No atribuido a TV digital** |
| 614-692 MHz | 38-50 | TV digital; lo analógico ya asignado puede continuar |
| 692-698 MHz | 51 | **En reserva, sin nuevas asignaciones** |

Eso explica los "36 canales UHF" que cita el MTC: 14-36 (23) más 38-50 (13)
[cálculo]. También explica por qué el RNF de Los Olivos llega solo al canal 50
[inferencia]. **Sin resolver:** ese mismo export marca el canal 37 como "disponible".

### Apagón analógico

- **Lima y Callao:** 1 de enero de 2025.
- **Resto del país:** no encontramos un cronograma vigente. El de 2020 dejaba el
  Territorio 5 para 2027, pero ya no rige, y las fuentes de 2024-2025 se contradicen.
- **Zonas rurales:** el Art. 40 del Reglamento de la Ley de Radio y Televisión permite,
  de forma excepcional, nuevas autorizaciones analógicas en zonas rurales, de
  preferente interés social o de frontera.

### Ocupación real en Lima (Los Olivos, RNF del 14/10/2026)

De los canales 14-50, **25 están autorizados y 12 disponibles** (15, 23, 25, 30, 35,
37, 43, 44, 46, 47, 48, 50). Detalle en `IA/dataset_real/rnf_lima_los_olivos_2026-10-14.csv`.
El número que ve el televidente (por ejemplo, 4.1) es un canal virtual y no coincide
con el canal físico. Según el MTC, ~93 % de las localidades usa menos de 10 de los 36
canales, de modo que Lima no representa la ocupación rural.

## 3. Cómo transmite un canal ISDB-Tb

### 3.1 Posición dentro del canal

```
f_central(n) = 473 + 6·(n − 14) + 1/7 MHz        (canal 14 → 473.143 MHz)

 f_inf                                                         f_sup
 |←0.357 MHz→|███████████ 5.572 MHz ███████████|←0.071 MHz→|
```

Los huecos son asimétricos [cálculo]. Con bins de ~109 kHz, la meseta ocupa unos
51 de 55 bins [cálculo].

### 3.2 Segmentos

El canal se divide en 14 partes de 428.57 kHz. Se usan 13, numeradas desde el centro
hacia afuera:

```
frecuencia →  11  9  7  5  3  1 [0]  2  4  6  8 10 12
                                 └─ segmento 0: recepción parcial (1seg)
```

### 3.3 Parámetros OFDM

La frecuencia de muestreo de la IFFT es 512/63 ≈ 8.127 MHz [cálculo, escalando la
tabla de 8 MHz de DiBEG a 6 MHz].

| | Modo 1 | Modo 2 | Modo 3 |
|---|---|---|---|
| Portadoras activas | 1405 | 2809 | 5617 |
| Separación | 3.968 kHz | 1.984 kHz | 0.992 kHz |
| Símbolo útil Tu | 252 µs | 504 µs | 1.008 ms |
| Ancho ocupado | 5.575 MHz | 5.573 MHz | 5.572 MHz |
| Guarda 1/4 | 63 µs | 126 µs | 252 µs |
| Guarda 1/8 | 31.5 µs | 63 µs | 126 µs |
| Guarda 1/16 | 15.75 µs | 31.5 µs | 63 µs |
| Guarda 1/32 | 7.875 µs | 15.75 µs | 31.5 µs |

- La guarda es común a todas las capas.
- Una trama son 204 símbolos: ~231 ms en modo 3 con guarda 1/8 [cálculo].
- Con guarda 1/4 en modo 3, el eco tolerable equivale a ~75 km [cálculo].

### 3.4 Portadoras por segmento

| Modo 3 (432 portadoras) | Datos | SP | CP | TMCC | AC1 | AC2 |
|---|---|---|---|---|---|---|
| QPSK, 16QAM, 64QAM | 384 | 36 | 0 | 4 | 8 | 0 |
| DQPSK | 384 | 0 | 1 | 20 | 8 | 19 |

- **SP (scattered pilots):** una de cada 12 portadoras [cálculo]. Se corren 3 portadoras
  por símbolo y van con amplitud 4/3 [sin verificar, ARIB STD-B31].
- **CP (continual pilot):** además del de los segmentos DQPSK, hay uno en el borde
  superior de la banda [sin verificar].
- **TMCC:** indica al receptor el modo y los parámetros de cada capa.
- **AC:** canal auxiliar de información adicional.

### 3.5 Capas jerárquicas

Hay hasta 3 capas (A, B, C), cada una con sus propios parámetros:

| Parámetro | Opciones |
|---|---|
| Modulación | DQPSK, QPSK, 16QAM, 64QAM |
| Código interno | Convolucional, tasas 1/2, 2/3, 3/4, 5/6, 7/8 |
| Código externo | Reed-Solomon (204,188) |
| Entrelazado temporal (modo 3) | I = 0, 1, 2, 4 |

### 3.6 Tasa de datos

```
R_seg = 384 · bits/símbolo · tasa_conv · (188/204) / (Tu · (1 + GI))      (modo 3)
```

| Configuración | Tasa [cálculo] |
|---|---|
| 1 segmento, QPSK 2/3, GI 1/16 | 0.44 Mbps (coincide con DiBEG) |
| 12 segmentos, 64QAM 3/4, GI 1/8 | 16.85 Mbps |
| 12 segmentos, 64QAM 3/4, GI 1/16 | 17.98 Mbps |
| Mínimo: 13 segmentos, DQPSK 1/2, GI 1/4 | 3.65 Mbps (coincide con Keysight) |
| Máximo: 13 segmentos, 64QAM 7/8, GI 1/32 | 23.23 Mbps (coincide con Keysight) |

**Configuración típica [sin verificar en el Perú]:** capa A de 1 segmento con QPSK 2/3
para celulares, y capa B de 12 segmentos con 64QAM 3/4 para HD y SD. Coincide con los
subcanales visibles en Lima (HD, SD y móvil), pero **no encontramos los parámetros
reales publicados de ninguna emisora peruana**. Se podrían leer del TMCC de cada canal.

### 3.7 Máscara espectral y potencia (ABNT NBR 15601)

La tabla da la atenuación mínima respecto a la potencia media (RBW 10 kHz, VBW ≤300 Hz):

| Distancia al centro | No crítica | Subcrítica | Crítica |
|---|---|---|---|
| ±2.79 MHz | 0 dB | 0 dB | 0 dB |
| ±2.86 MHz | 20 dB | 20 dB | 20 dB |
| ±3.00 MHz | 27 dB | 34 dB | 34 dB |
| ±3.15 MHz | 36 dB | 43 dB | 50 dB |
| ±4.5 MHz | 53 dB | 60 dB | 67 dB |
| ±9 a ±15 MHz | 83 dB | 90 dB | 97 dB |

La norma es brasileña; no confirmamos qué máscara exige el Perú. Las clases de
estación brasileñas en UHF (ERP máxima, antena a 150 m) son: Especial 80 kW, A 8 kW,
B 0.8 kW y C 0.08 kW. Los planes del MTC fijan la ERP por localidad; uno de los
revisados autoriza como máximo 0.1 kW.

## 4. Cómo transmite un canal NTSC-M

### 4.1 Frecuencias

| Banda | Canales | Rango | ¿Lo ve el sensor (470-698 MHz)? |
|---|---|---|---|
| VHF bajo | 2-4 | 54-72 MHz | No |
| VHF bajo | 5-6 | 76-88 MHz | No |
| VHF alto | 7-13 | 174-216 MHz | No |
| UHF | 14-36 | 470-608 MHz | **Sí** |
| UHF | 38-50 | 614-692 MHz | **Sí** |

Los rangos completos y la portadora de color vienen del estándar NTSC-M; no encontramos
una tabla nacional. Los planes del MTC confirman las de video y audio en VHF (canal 3:
61.25/65.75 MHz; canal 13: 211.25/215.75 MHz). Los planes analógicos revisados
(Lambayeque, Arequipa, Huancavelica) son de VHF, fuera de la banda del proyecto.

**Dato pendiente:** no encontramos cuántas estaciones analógicas UHF siguen activas.
Hay que consultar el RNF de cada localidad y capturar en el sitio.

### 4.2 Portadoras dentro del canal

| Portadora | Posición | Canal 7 | Canal 14 | Canal 50 |
|---|---|---|---|---|
| Video | +1.25 MHz | 175.25 | 471.25 | 687.25 |
| Color | +4.83 MHz | 178.83 | 474.83 | 690.83 |
| Audio | +5.75 MHz | 179.75 | 475.75 | 691.75 |

```
  NTSC-M: picos angostos                ISDB-Tb: meseta
   █ video
   █▓
   █▓▒░                █ audio          ████████████████████
   █▓▒░░░░░░░░░░░█░░░░░█                ████████████████████
 +1.25         +4.83  +5.75 MHz         +0.36             +5.93 MHz
```

| | NTSC-M | ISDB-Tb |
|---|---|---|
| Contenido | Onda continua, 1 programa | Bits, varios programas |
| Señal débil | Se degrada poco a poco | Se corta de golpe |
| PSD | Picos que dependen del contenido | Meseta casi constante |

## 5. Límites legales para un equipo TVWS (DS 024-2021-MTC)

| Artículo | Exigencia |
|---|---|
| Art. 4 | Banda UHF 470-698 MHz |
| Art. 5 | Sin protección contra interferencias; no debe generarlas |
| Art. 7 | Solo ubicaciones fijas, punto a punto o punto a multipunto |
| Art. 8 | Máximo 12.6 dBm/100 kHz hacia la antena |
| Art. 9 | Antena de máximo 14 dBd |
| Art. 10 | Fuera del canal, máximo −42.8 dBm/100 kHz |
| Art. 11 | TPC y relaciones de protección de la RM 358-2003-MTC/03 |
| Art. 12 | Altura máxima de 100 m sobre el terreno; EHAAT de máximo 800 m |
| Art. 13 | Geolocalización integrada en dispositivos maestros |
| Art. 15.2 | Limitado a áreas rurales y de preferente interés social |
| Art. 17-18 | Consulta obligatoria de base de datos, al menos cada 24 h |

Los límites de 12.6 dBm/100 kHz, −42.8 dBm/100 kHz y 14 dBd son los mismos de Colombia,
que reguló antes. Es probable que Perú tomara ese modelo [inferencia].

## 6. Antecedentes de TVWS

### 6.1 En el Perú

| Hecho | Estado |
|---|---|
| DS 024-2021-MTC (jul. 2021) | Habilita la banda. El MTC mencionó futuros pilotos |
| Microsoft + Internet Para Todos (14/12/2020) | Alianza con "potencial" para hasta 15 regiones de sierra y selva. Sin regiones, equipos ni resultados publicados |

**No encontramos** despliegues con resultados medidos ni una base de datos operativa.
No prueba que no existan; hay que confirmarlo con el MTC.

### 6.2 Brasil: el antecedente más sólido

Proyecto de Inatel, NIC.br y UFC con apoyo de Anatel. Prueba 5G-RANGE (GFDM) contra
ISDB-T real, en laboratorio y en Santa Rita do Sapucaí (*Sensors* 25(8):2469, 2025).
La regulación es la Resolución 747 de Anatel (oct. 2021), con un máximo inicial de
1 W pico.

| Medida | Valor |
|---|---|
| Canal de TV en laboratorio | Canal 48 UHF (674-680 MHz), ancho de 5.572 MHz |
| Referencia BT.1368-13, n−1 / n+1 | −26 / −29 dB (64QAM 7/8, BER 2×10⁻⁴ antes de RS, interferente ISDB-T) |
| Mínimo con 5G-RANGE GFDM, n−1 / n+1 | −31.38 / −33.24 dB |
| Promedio en laboratorio, canal adyacente | ~−30 dB |
| Peor caso (TV a −20 dBm, 5G NR en n+1) | −25.85 dB |
| Segundo adyacente (n±2) | ~−50 dB |
| Interferentes simultáneos en n−1 y n+1 | ~3 dB peor |
| Peor caso en campo, n−1 | −30.2 dB |
| Diferencia entre decodificadores, n±2 | ~10 dB |
| ACLR de la señal, n−1 / n+1 | −50.62 / −49.55 dB |
| Umbral de la TV | −77 dBm |
| Cobertura a 1 W pico | 96 Mbps en 24 MHz a 14.7 km |
| Potencia sin efecto sobre la TV | Hasta 4 W pico (6 dB sobre el límite) |

El sistema usa una base de datos para elegir la frecuencia inicial y sensado periódico
para confirmar que siga libre. Es el precedente directo para este proyecto.

### 6.3 Otros países con ISDB-T

| País | Quién y cuándo | Qué se hizo | Resultado |
|---|---|---|---|
| Japón | NICT | 802.22 a 12.7 km (4.5/5.2 Mbps) y 802.11af a 6.3 km (15.5/9 Mbps) | Prueba para desastres, citada por el paper filipino |
| Filipinas | NICT y U. San Carlos (2022); NTC MC 02-04-2017 | 802.11af a 20 dBm en Cebú y Surigao del Norte | 3.43/3.38 Mbps a 530 m sin línea de vista. No menciona ISDB-T |
| Chile | Subtel, Microsoft, U. de Chile (2021) | Comunidad José Painecura (120 familias, 2 escuelas) y prueba con canal adyacente | "No hubo interferencias", sin cifras en la nota |
| Ecuador | CNT, Microsoft, ARCOTEL (nov. 2020) | 2 escuelas en Cotopaxi, 300 estudiantes | Inaugurado, sin mediciones |
| Uruguay | Plan Ceibal, Microsoft (~2013) | 10 escuelas rurales planificadas | Sin resultados encontrados |
| Argentina | ENACOM, Microsoft, ARSAT (2017) | Préstamo de equipos | Sin resultados encontrados |

### 6.4 Colombia: referente regulatorio

Hasta donde sabemos no usa ISDB-T [sin verificar]. Regula TVWS desde 2017 (Resolución
ANE 461, actualizada por la 105 de 2020 y la 61 de 2024). Tiene base de datos nacional
(BDEB) con protocolo PAWS y pilotos en escuelas de Ovejas, Dibulla, Pamplonita y Aguadas.

### 6.5 Sensado sin base de datos

Las reglas de la FCC de 2010 quitaron el sensado a los equipos con geolocalización y
mantuvieron los equipos solo con sensado bajo límites estrictos: 50 mW y detección
de TV a −114 dBm. **Esto choca con** `cumplimiento_normativo_tvws.md`, que dice que la
FCC no reconoció el sensado solo "hasta ~2015". No verificamos qué cambió después de
2010, así que esa frase está pendiente de revisión.

## 7. Implicaciones para el proyecto

### 7.1 El canal 52 está fuera de la banda legal

`IA/nucleo.py:28` define `CANALES_TVWS_PE = list(range(14, 53))`, es decir, 39 canales
hasta 704 MHz. El decreto llega a 698 MHz (canales 14-51, 38 canales). El comentario
del propio código habla de 228 MHz, que corresponde a 38. El canal 52 debe poder
marcarse como ocupado o quitarse de la lista, pero nunca elegirse. **Pendiente.**

### 7.2 Separación necesaria [cálculo]

Estimación con EIRP +28.8 dBm (`LINK_BUDGET/`, verificar si cambia), espacio libre a
600 MHz, televisor en el umbral de −77 dBm y sin ganancia de antena receptora:

| Caso | Interferencia tolerable | Distancia |
|---|---|---|
| Canal adyacente (PR −30 dB) | −47 dBm | ~250 m |
| Mismo canal (PR +20 dB) | −97 dBm | ~78 km |

El +20 dB viene de pruebas de ISDB-Tb a 8 MHz en Botsuana; **no pudimos leer la tabla
de BT.1368**. La RM 358-2003-MTC/03 que cita el Art. 11 tampoco se revisó. El resultado
indica que usar un canal adyacente es viable en zona rural, y que el riesgo real es el
mismo canal [inferencia].

### 7.3 Emisiones fuera de canal [cálculo]

Con la densidad de 6.0-6.5 dBm/100 kHz de `cumplimiento_normativo_tvws.md` (Problema 4),
cumplir el Art. 10 exige unos **49 dB** de supresión. La señal de Brasil logró ACLR de
~50 dB; es otra medida, así que la comparación es orientativa. Refuerza el Problema 6
de ese doc: hace falta filtro de salida.

### 7.4 Límite de la detección por energía [cálculo]

El ruido térmico en 5.57 MHz es de −106.5 dBm. Detectar −114 dBm implica una SNR de
−7.5 dB aun con un receptor ideal, fuera del alcance de un detector de energía.
ISDB-Tb tiene prefijo cíclico: en modo 3 se repite con retardo de 1.008 ms, unas 2419
muestras a 2.4 MS/s. Existe trabajo previo de detección cicloestacionaria para ISDB-T
(IEICE 2007). **No lo probamos** sobre capturas reales. Serviría como QA independiente
del RNF, no como sustituto de la base de datos.

## 8. Lo que muestran los datos del proyecto

### 8.1 Las muestras de Los Olivos

Análisis de las 37 muestras de `IA/dataset_real/etiquetado_losolivos_20261014/`
(25 ocupadas, 12 libres, una sola sesión):

| Prueba | Resultado |
|---|---|
| Nivel medio del PSD, ocupado vs. libre | 0.577 vs. 0.588, AUC 0.43 |
| Centroide con leave-one-out | 64.9 %, peor que la línea base de 67.6 % |
| Rugosidad (media de \|diferencia entre bins vecinos\|) | AUC 0.91, permutación 0/5000 |

- **Nivel:** cada `.npz` guarda solo el PSD normalizado por percentiles 5/95, que borra
  el nivel absoluto. Además, 2.4 MHz cae dentro de la meseta, así que nunca se ven los
  flancos [inferencia].
- **Rugosidad:** es un resultado exploratorio. Se eligió después de ver los datos, entre
  5 variables, con n=37. Quizá sea un efecto indirecto del SNR [inferencia].
- **Dos grupos:** 17 canales autorizados con rugosidad de 0.065-0.107, y otros 20 con
  ≥0.136 que incluyen los 12 libres y 8 autorizados (14, 17, 36, 40, 41, 42, 45, 49).

Esos 8 se parecen a un canal vacío. El QA señaló 12 canales sin energía, pero ese reporte
no está en el repo, así que no se pudieron cruzar.

### 8.2 Opción NTSC del generador

`generar_dataset_sintetico.py --prob_ntsc P` hace que cada canal ocupado sea NTSC-M con
probabilidad P. Cada `.npz` guarda `tipo_senal` (−1 no visible, 0 libre, 1 ISDB-Tb,
2 NTSC-M). Con P=0 (default), la misma semilla reproduce los datasets anteriores
(verificado en 300 muestras).

Las posiciones de las portadoras son del estándar. **Los niveles relativos y las bandas
laterales son rangos aproximados, elegidos por nosotros**, sin captura real detrás.

### 8.3 Efecto en el modelo

450 sub-bandas de prueba con 30 % de los canales ocupados en NTSC:

| Canal | Cantidad | Modelo actual: declarado libre | Prueba: declarado libre |
|---|---|---|---|
| Libre | 2596 | 100 % | 90.2 % |
| ISDB-Tb | 892 | 0.7 % | 0 % |
| **NTSC-M** | 386 | **100 %** | **18.4 %** |

"Prueba" es un modelo descartable: 3000 sub-bandas y 25 épocas, con 30 % de NTSC. No se
guardó en el repo. Estos porcentajes no predicen el desempeño en campo, porque no hay
NTSC real detrás.

Dos simplificaciones del generador pueden afectar el resultado:

- El ruido usa un solo periodograma, mientras `calcular_psd` promedia 20 segmentos, lo
  que puede ocultar más los picos angostos.
- La fuga hacia el canal vecino parece invertida: vale 0 junto al canal y es máxima lejos
  de él. No se corrigió para no cambiar los datasets existentes.

## 9. Pendientes

**Con el MTC:**

- ¿Existe una base de datos TVWS operativa y autorizada?
- ¿Existe una vía de autorización experimental?
- ¿Cuál es el estado de los canales 37 y 51 para TVWS y por qué el RNF marca el 37 como disponible?
- ¿Qué estaciones analógicas UHF siguen activas en la zona de despliegue?

**En el proyecto:**

- Quitar o bloquear el canal 52 (§7.1), revisando todo lo que asume 39 canales.
- Guardar en cada sesión de campo el PSD en dB sin normalizar y conservar algunos `.iq`.
- Reentrenar con `--prob_ntsc` y guardar el modelo en otra carpeta, sin reemplazar
  `modelos/`. Fijar la proporción y validar con datos reales si aparece analógico UHF.
- Probar la detección por prefijo cíclico (§7.4).
- Revisar el ruido y la fuga del generador (§8.3).
- Revisar la frase sobre la FCC (§6.5).

**Fuentes por leer:**

- Tablas de ITU-R BT.1368-13 y RM 358-2003-MTC/03.
- Paper de la UPF sobre qué pasó con los pilotos TVWS (acceso bloqueado).
- Cifra de 281 escuelas en El Salvador: se vio solo en un fragmento de búsqueda y no se usa aquí.

## 10. Fuentes

**Perú**

- [RVM 006-2022-MTC/03: plan VHF, Nota P11A](https://cdn.www.gob.pe/uploads/document/file/2744652/RVM%20006-2022%20canaliza%20UHF%20Lambayeque%20.pdf.pdf)
- [RVM 159-2023-MTC/03: bandas vigentes y reserva](https://cdn.www.gob.pe/uploads/document/file/5510358/4909139-rvm-159-2023-mtc-03-canalizacion-uhf-arequipa.pdf)
- [RVM 381-2020: Art. 40, analógico rural](https://cdn.www.gob.pe/uploads/document/file/1307651/RVM%20381-2020%20canaliza%20VHF%20HUANCAVELICA.pdf)
- [RM 048-2017-MTC](https://cdn.www.gob.pe/uploads/document/file/470139/RM_048-2017_MTC.pdf)
- [DS 007-2021-MTC](https://lpderecho.pe/modifican-plan-maestro-implementacion-television-digital-terrestre-decreto-supremo-007-2021-mtc/)
- [Telecompaper: habilitación de TVWS y 36 canales](https://www.telecompaper.com/news/peru-enables-use-of-tv-white-space-to-connect-underserved-areas--1390834)
- [DPL News: habilitación de TVWS](https://dplnews.com/peru-usara-espacios-en-blanco-de-television-para-cerrar-brecha-digital/)
- [MTC: propuesta de TVWS](https://www.gob.pe/institucion/mtc/noticias/498059-mtc-propone-usar-espacios-en-blanco-de-television-para-fomentar-servicios-de-telecomunicaciones-inalambricas)
- [Microsoft + Internet Para Todos](https://news.microsoft.com/es-xl/internet-para-todos-y-microsoft-anuncian-alianza-para-llevar-conectividad-rural-a-sierra-y-selva-del-peru/)
- [TV digital en Perú (Wikipedia)](https://es.wikipedia.org/wiki/Televisi%C3%B3n_digital_terrestre_en_Per%C3%BA)
- [TAVI Latam: apagón en Lima y Callao](https://tavilatam.com/peru-ministerio-de-comunicaciones-dio-inicio-al-apagon-analogico-discontinuando-la-senal-televisiva-en-lima-y-callao/)
- [TV Perú: apagón](https://www.tvperu.gob.pe/noticias/tecnologia/hoy-es-el-apagon-tecnologico-que-da-paso-a-la-television-digital-terrestre-tdt)
- [Expreso: apagón](https://www.expreso.com.pe/actualidad/television-digital-en-peru-lo-que-cambia-con-el-apagon-analogico-que-ya-empezo-mtc-noticia/1165674/)
- [Gestión: cronograma de 2020](https://gestion.pe/tecnologia/apagon-analogico-2020-que-es-y-cuando-comenzara-en-el-peru-nnda-nnlt-noticia/)
- [GSMA: 700 MHz en Perú](https://www.gsma.com/latinamerica/wp-content/uploads/2016/05/report-coexistencia_banda_700_Peru-ES.pdf)
- [TeleSemana: contratos de 700 MHz](https://www.telesemana.com/blog/2016/07/21/peru-firmaron-los-contratos-de-concesion-las-empresas-que-se-adjudicaron-espectro-en-700-mhz/)

**ISDB-T y coexistencia**

- [Armonización ABNT/ARIB/SBTVD: canales y máscara](https://www.dibeg.org/wp/wp-content/uploads/techp/aribstd/harmonization/2018_04_111_Transmission_ABNT_ARIB_SBTVD_JD.pdf)
- [Keysight: parámetros ISDB-T](https://helpfiles.keysight.com/csg/n7623/Content/RT/RT_ISDBT.htm)
- [DiBEG: seminario de transmisión, orden de segmentos](https://www.dibeg.org/wp/wp-content/uploads/news/0706_3Argentina_ISDB-T_seminar/Argentina_ISDB-T_seminar_3_transmission_systemspanishrev1.pdf)
- [DiBEG: borrador Botsuana, portadoras por segmento](https://www.dibeg.org/wp/wp-content/uploads/news/1308_Japan_Proposed_draft_8MHz_ISDB-T_Standard_for_Botswana/Draft_Botswana_ISDB-T_Standard.pdf)
- [Pruebas de ISDB-Tb en Botsuana: PR +20/−30/−30 dB](https://set.org.br/ijbe/ed1/10_IEEE%20Format%20-%20Results%20of%20Field%20Tests%20of%20the%20ISDB-TB%20System%20at%208%20MHz%20in%20Botswana.pdf)
- [ITU-R BT.1368-13](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.1368-13-201706-I!!TOC-HTM-E.htm)
- [IEICE 2007: detección cicloestacionaria](https://ken.ieice.org/ken/paper/20070727dAWx/eng/)

**Antecedentes TVWS**

- [Sensors 2025: 5G-RANGE vs. ISDB-T](https://doi.org/10.3390/s25082469)
- [Teletime: proyecto NIC.br](https://teletime.com.br/31/08/2022/projeto-estudara-formas-de-usar-white-spaces-no-brasil-para-ampliar-inclusao-digital/)
- [DPL News: Resolución 747](https://dplnews.com/?p=120407)
- [RCR Wireless: piloto de 2015 en Brasil](https://rcrwireless.com/20150122/americas/latam-white-space-trial-brazil-tag5)
- [IECEP 2022: Filipinas](https://www.iecepjournal.net/index.php/iecepjournal/article/view/35)
- [NTC MC 02-04-2017](https://ntc.gov.ph/wp-content/uploads/2017/MC/MC-02-04-2017.pdf)
- [DPL News: Chile](https://dplnews.com/?p=124749)
- [BNamericas: Chile](https://bnamericas.com/en/news/chile-tests-tv-white-space-connectivity)
- [Microsoft: Ecuador](https://news.microsoft.com/es-xl/cnt-y-microsoft-llevan-conectividad-rural-a-la-provincia-de-cotopaxi-a-traves-de-tv-white-spaces/)
- [Microsoft: Uruguay](https://news.microsoft.com/source/2014/05/13/microsoft-and-its-partners-announce-new-affordable-access-projects-on-four-continents/)
- [iProfesional: Argentina](https://www.iprofesional.com/tecnologia/333468-microsoft-presento-el-proyecto-tv-white-spaces-al-enacom)
- [ANE: presentación UIT 2021](https://www.itu.int/en/ITU-R/seminars/rrs/2021-Americas/Forum/Session%207_Cognitive-Software%20Radio/ANE_%20Espacios%20en%20Blanco%20de%20TV.pdf)
- [Resolución ANE 61 de 2024](https://normograma.mintic.gov.co/mintic/compilacion/docs/resolucion_ane_0061_2024.htm)
- [ANE: guía de base de datos](https://www.ane.gov.co/Documentos%20compartidos/ArchivosDescargables/noticias/TV%20White%20Spaces%20Database%20Guidelines%20Colombia.pdf)
- [Reglas FCC de 2010](https://www.commlawblog.com/2010/09/articles/broadcast/fcc-okays-white-space-devices/)
- [Dispositivos TV-band](https://www.Wikipedia.org/wiki/TV-band_device)

**Repositorio**

- `Decreto_Supremo_024-2021-MTC_TVWS.pdf`
- `IA/dataset_real/`
- `IA/nucleo.py`
- `IA/generar_dataset_sintetico.py`
