# Investigación: proveedores peruanos que puedan cotizar el bladeRF 2.0 micro xA4

> ⚠ **Verificar antes de usar:** existe `PEDIDOS/PF-001 COMPRAS.pdf` en la
> raíz del repo, que podría indicar que la compra ya se gestionó o
> concretó desde que se hizo esta investigación (2026-07-02) — revisar ese
> documento antes de asumir que sigue siendo necesario cotizar desde cero.

**Fecha:** 2026-07-02
**Alcance:** búsqueda exhaustiva de distribuidores/revendedores establecidos en Perú capaces de emitir una cotización formal para el SDR Nuand bladeRF 2.0 micro xA4 (u equivalente), para el proyecto de radio cognitiva TVWS (UNI, VRI 2026).
**Profundidad:** standard (multi-hop, ~15 búsquedas web + verificación de sitios de proveedores)

## Resumen ejecutivo

**No existe un distribuidor autorizado ni revendedor establecido del bladeRF (marca Nuand) en Perú.** Nuand es un fabricante boutique (EE.UU.) que vende principalmente de forma directa desde su tienda online (nuand.com) y a través de un puñado de revendedores internacionales especializados en SDR/seguridad radioeléctrica (Lab401 en Europa, Hacker Warehouse en EE.UU., Antratek en Países Bajos), ninguno de los cuales tiene presencia comercial en Perú ni figura como "distribuidor nacional".

Dado eso, hay dos rutas realistas para obtener una cotización "nacional" en el sentido de una empresa peruana que pueda facturar/gestionar la compra:

1. **Distribuidores peruanos de instrumentación RF/electrónica de prueba** que ya tienen canal de importación de EE.UU. y podrían aceptar un pedido especial (special order) aunque el bladeRF no esté en su catálogo estándar — la ruta más prometedora encontrada es **VVA Industrial**.
2. **Agentes de aduana / brokers de importación** para nacionalizar una compra hecha directamente a Nuand — esto no es "cotizar el equipo" sino la logística de traerlo, pero es la ruta que en la práctica usan universidades/laboratorios peruanos para equipos de nicho que ningún distribuidor local stockea.

No se encontró evidencia de que PUCP, UNI u otras universidades peruanas hayan importado bladeRF previamente (no se hallaron tesis públicas mencionándolo), por lo que no hay un precedente documentado de agente de importación ya probado para este equipo específico en el país.

## Hallazgos por proveedor

### 1. VVA Industrial — la opción más prometedora para cotización local
- **Qué es:** distribuidor/importador industrial mayorista con sucursales en Lima, Arequipa y Piura (además de Ecuador, Chile, Colombia, Bolivia).
- **Relevancia:** es distribuidor autorizado de **Keysight** y **VIAVI** en Perú — ambas marcas de instrumentación y prueba RF/telecomunicaciones — lo que indica que ya tiene canal de importación establecido para equipos de medición/RF desde fabricantes internacionales. Su catálogo también incluye ABB, Siemens, Phoenix Contact, Advantech, Vacon, etc., es decir, operan como importador multi-marca con pedidos especiales, no solo catálogo fijo.
- **No tiene línea Nuand/SDR publicada** — habría que solicitarles una cotización de "pedido especial" (sourcing on request), no un ítem de catálogo.
- **Contacto:** ventas3@vva-industrial.com · WhatsApp/tel +51 915 111 043 · oficina Lima: Paseo de la Castellana, Torre B, Santiago de Surco 15049.

### 2. QIPSAC — instrumentación científica, pero fuera de su rubro
- **Qué es:** distribuidor de instrumentación científica/industrial con +25 años en Perú, especializado en importar equipos de investigación desde EE.UU.
- **Líneas que maneja:** electroquímica (potenciostatos), detección nuclear/radiación (ORTEC-AMETEK, exclusivo), análisis de materiales (XRF), laboratorio clínico — **ningún equipo RF/SDR ni marcas relacionadas (Nuand, Ettus, Keysight, R&S)**.
- **Veredicto:** su expertise de importación es real, pero el rubro no calza — improbable que acepten cotizar un SDR salvo como favor fuera de catálogo. Contacto: bte@qipsac.com · +51 997 021 603 / (01) 677-4378.

### 3. Cistronix Perú — importador de TI, sin evidencia de RF/SDR
- Importador/distribuidor de equipos y repuestos de cómputo y redes (switches Cisco, terminales portátiles, accesorios). No se encontró producto o línea de RF/SDR en su catálogo público. Contacto disponible en cistronixperu.com/contactenos.php.

### 4. Nuand (fabricante, EE.UU.) — venta directa, sin distribuidor regional
- No publica lista de distribuidores autorizados ni presencia en Latinoamérica. La única vía documentada es comprar directo en nuand.com/shop o contactar bladerf@nuand.com / support@nuand.com, y nacionalizar el envío por cuenta propia.

### 5. Revendedores internacionales especializados (no nacionales, pero opción de respaldo)
Ninguno tiene sede en Perú; se listan por si la ruta de importación directa es más viable que encontrar un revendedor local:
- **Lab401** (lab401.com) — Europa, vende bladeRF 2.0 micro xA4 en paquetes starter/deluxe.
- **Hacker Warehouse** (hackerwarehouse.com) — EE.UU.
- **Antratek** (antratek.com) — Países Bajos.
- **Mouser / Digi-Key** — distribuidores globales de componentes; en las búsquedas solo aparecieron listando accesorios del bladeRF (cables USB Blaster), no el equipo completo — habría que verificar directamente en sus sitios si el bladeRF 2.0 micro xA4 está en catálogo antes de asumir que lo tienen.

### 6. Ettus Research / National Instruments (USRP) — mencionado por comparación, mismo problema
Se investigó como posible canal alterno (otro fabricante líder de SDR) por si compartiera distribuidor regional con Nuand. El selector de país de Ettus Research incluye Perú como región seleccionable pero **no lista ningún distribuidor o partner peruano**. Mismo patrón que Nuand: sin canal nacional.

## Ruta recomendada (no es una decisión — para que el usuario elija)

1. **Cotizar primero directo con Nuand** (bladerf@nuand.com) para tener el precio/lead-time base en USD FOB/EXW.
2. **En paralelo, pedir a VVA Industrial** una cotización de pedido especial citando el modelo exacto (bladeRF 2.0 micro xA4) y el link del fabricante — es el único distribuidor peruano encontrado con canal de importación RF/test-equipment activo que podría gestionar la compra+nacionalización como parte de su servicio.
3. Si ambas rutas fallan, usar un **agente de aduana** (PIC Cargo Perú, Antares Aduanas — ambos con servicios de despacho para equipos electrónicos, comisión ~0.5–1% del valor CIF) para nacionalizar una compra hecha directamente en nuand.com o en uno de los revendedores internacionales (Lab401/Hacker Warehouse/Antratek).

## Limitaciones de esta investigación

- Ninguna cotización fue confirmada directamente por los proveedores — son hallazgos de catálogo/presencia comercial, no precios ni disponibilidad confirmada.
- No fue posible verificar si Mouser/Digi-Key venden el bladeRF 2.0 micro xA4 completo (vs. solo accesorios) con envío a Perú — pendiente de confirmar en sus sitios directamente.
- No se identificó ningún revendedor de radioafición o tienda de electrónica peruana (Mercado Libre Perú, Hi-Fi SAC, Gamatec, DigitalStore, RFJ Comunicaciones, NETSAT) que tenga el bladeRF en catálogo actual — el listado de Mercado Libre Perú no arrojó resultados para "bladeRF", a diferencia de los sitios de Argentina y México.

## Fuentes

- [bladeRF 2.0 micro xA4 - Nuand](https://www.nuand.com/product/bladerf-xa4/)
- [Nuand Support](https://www.nuand.com/support/)
- [Blade RF 2.0 Micro xA4 — Lab401](https://lab401.com/products/bladerf-sdr-2-micro-xa4)
- [bladeRF 2.0 xA4 Kit - Hacker Warehouse](https://hackerwarehouse.com/product/bladerf-2-xa4-kit/)
- [bladeRF 2.0 micro xA4 - Antratek](https://www.antratek.com/nuand-bladerf-2-0-micro-xa4-sdr)
- [VVA Industrial - Keysight en Perú](https://vva-industrial.net/keysight/keysight-en-mexico/)
- [VVA Industrial - VIAVI en Perú](https://vva-industrial.net/viavi/viavi-en-peru/)
- [VVA Industrial sitio principal](https://vva-industrial.net/)
- [QIPSAC](https://www.qipsac.com/)
- [Cistronix Perú](https://www.cistronixperu.com/)
- [Ettus Research - selector de región](https://www.ettus.com/region/)
- [Mercado Libre Perú - listado SDR](https://listado.mercadolibre.com.pe/radio-sdr)
- [PIC Cargo Perú - Agente de Aduana](https://pic-cargoperu.com/agente-aduana-peru/)
- [Guía práctica del importador (MINCETUR)](https://acuerdoscomerciales.gob.pe/Documentos/manuales/guia_del_importador_wr.pdf)
