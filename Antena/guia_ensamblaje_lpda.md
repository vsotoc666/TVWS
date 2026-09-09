# Guía de Construcción y Ensamblaje: Antena LPDA para TVWS (470-698 MHz)

Este documento detalla los materiales y el procedimiento de ensamblaje para construir la antena Log-Periódica (LPDA) diseñada rigurosamente bajo las ecuaciones del Cap. 11 de *Antenna Theory* de C.A. Balanis. El diseño está optimizado para climas hostiles (selva/sierra) y puede manejar potencias muy por encima de 100 W RMS.

---

## 1. Lista de Materiales

### Estructura Metálica
*   **Tubos de Aluminio para Dipolos (10 mm de diámetro):** ~2 metros en total. El aluminio es ligero, barato y excelente conductor.
*   **Tubos para el Boom (Eje Central):** 2 tubos cuadrados de aluminio (de 10 mm o 15 mm de lado) de **60 cm de largo** cada uno. El tubo cuadrado facilita fijar las varillas sin que roten.

### Tornillería y Aislamiento Climático
*   **Tornillería ACERO INOXIDABLE:** Tornillos pasantes, tuercas y arandelas (M3 o M4). *Bajo ninguna circunstancia usar fierro galvanizado o zincado.*
*   **Pasta Antioxidante (Penetrox A o Jet-Lube SS-30):** Grasa conductiva para evitar la corrosión galvánica entre metales.
*   **Taquitos/Lámina de Teflón, Nylon o Acrílico:** Cortados para formar separadores de exactamente **1.8 mm a 2.0 mm** de grosor.
*   **Cinta Autofundente (Self-amalgamating tape):** Sello hermético principal para las conexiones RF.
*   **Cinta Aislante UV (3M Scotch Super 33+ o 88):** Protección solar sobre la cinta autofundente.

### Conexión RF
*   **Cable Coaxial de 50 ohms:** Para alta potencia/frecuencia (LMR-400 o RG-8 grueso). *Prohibido usar RG-58 a potencias >20W en UHF.*
*   **Conector N-Hembra:** Asegurarse de que el dieléctrico interno sea de Teflón (PTFE), no de plástico (Delrin).

---

## 2. Dimensiones de Corte (Los 9 Dipolos)

Las 9 varillas representan dipolos completos. Debes cortar cada medida **exactamente por la mitad**, ya que una mitad se atornillará al "Boom A" y la otra al "Boom B".

*   **El. 1 (Feed frontal, más corto):** 11.5 cm (Cortar en 2 x 5.75 cm)
*   **El. 2:** 13.0 cm (Cortar en 2 x 6.50 cm)
*   **El. 3:** 14.8 cm (Cortar en 2 x 7.40 cm)
*   **El. 4:** 16.8 cm (Cortar en 2 x 8.40 cm)
*   **El. 5:** 19.1 cm (Cortar en 2 x 9.55 cm)
*   **El. 6:** 21.7 cm (Cortar en 2 x 10.85 cm)
*   **El. 7:** 24.7 cm (Cortar en 2 x 12.35 cm)
*   **El. 8:** 28.1 cm (Cortar en 2 x 14.05 cm)
*   **El. 9 (Reflector trasero, más largo):** 31.9 cm (Cortar en 2 x 15.95 cm)

---

## 3. Procedimiento de Ensamblaje

### Paso 1: Perforación del Boom
Toma los dos tubos cuadrados de 60 cm (Boom A y Boom B). Colócalos lado a lado y marca las posiciones de los 9 elementos según la memoria de cálculo. Taladra los agujeros pasantes en ambos tubos simultáneamente para garantizar alineación.

### Paso 2: Fijación Alternada (Zig-Zag de Fase)
La LPDA requiere que la fase se invierta entre elementos adyacentes:
1.  Aplica una gota de pasta *Penetrox* en cada agujero.
2.  **Elemento 1:** Atornilla la mitad derecha en el Boom A, y la mitad izquierda en el Boom B.
3.  **Elemento 2:** ¡Invertir! Atornilla la mitad izquierda en el Boom A, y la mitad derecha en el Boom B.
4.  Repite esta alternancia estricta hasta el Elemento 9.

### Paso 3: Unión del Boom (El "Gap" de Impedancia)
Para mantener la impedancia característica de ~70 ohms (acoplada a los 50 ohms de la entrada), los booms deben estar separados:
1.  Coloca los espaciadores de Teflón/Nylon de 1.8 mm entre el Boom A y el Boom B.
2.  Únelos firmemente. **Atención:** Si usas tornillos pasantes para unirlos, los tornillos deben estar aislados (tubos termocontraíbles, arandelas de nylon) para no crear un cortocircuito entre el Boom A y el B. Alternativamente, amárralos con bridas plásticas UV gruesas.

### Paso 4: El "Balun Infinito" (Alimentación)
1.  Ingresa el cable coaxial por la parte trasera (Elemento 9) y extiéndelo por todo el cuerpo del **Boom A** hasta llegar al Elemento 1 (al frente). Sujétalo con cintillos.
2.  Al llegar al frente, pela el coaxial.
3.  Fija la **Malla (Tierra)** directamente al aluminio del **Boom A**.
4.  Cruza el "gap" de 1.8 mm y fija el **Núcleo de cobre (Señal)** al aluminio del **Boom B**.

### Paso 5: Weatherproofing Extremo
1.  En la conexión frontal del coaxial, envuelve todo vigorosamente con **Cinta Autofundente**, estirándola hasta que se vulcanice en una capa de goma sólida.
2.  Cubre la goma con una capa final de **Cinta Eléctrica UV (3M)**.
3.  **Drip Loop:** Antes de que el cable coaxial descienda por el mástil hacia los equipos de radio, crea un lazo o bucle colgante ("U"). Esto fuerza al agua de lluvia a gotear hacia el suelo desde la base de la curva, evitando que fluya por el cable directo al equipo.
