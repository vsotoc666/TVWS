import math
import os

# ==========================================
# Teoría de Diseño LPDA - C.A. Balanis (Cap. 11)
# ==========================================

# 1. ESPECIFICACIONES DE DISEÑO
f_min = 470.0  # MHz (Canal 14)
f_max = 698.0  # MHz (Canal 52)
c = 300.0      # Mm/s
R_in = 50.0    # Ohmios (Impedancia deseada)
d = 0.01       # Diámetro de los elementos: 10 mm (0.01 m)

# De la Figura 11.13 para una directividad de ~7.5 a 8 dB:
tau = 0.88
sigma = 0.15

# 2. CÁLCULOS TEÓRICOS (Balanis)
# Ecuación (11-28): Ángulo de la estructura (alpha)
alpha_rad = math.atan((1 - tau) / (4 * sigma))
alpha_deg = math.degrees(alpha_rad)

# Ecuaciones (11-29) y (11-30): Anchos de banda
B = f_max / f_min
B_ar = 1.1 + 7.7 * (1 - tau)**2 * (1.0 / math.tan(alpha_rad))
B_s = B * B_ar

# Ecuaciones (11-31) y (11-31a): Longitud total del Boom (L)
lambda_max = c / f_min
L_boom = (lambda_max / 4.0) * (1 - (1.0 / B_s)) * (1.0 / math.tan(alpha_rad))

# Ecuación (11-32): Número de elementos (N)
N_calc = 1 + math.log(B_s) / math.log(1.0 / tau)
N = math.ceil(N_calc)

# Construcción de la geometría (longitudes y posiciones)
L_max = lambda_max / 2.0
elementos = []
L_n = L_max
z_n = 0.0

for i in range(N):
    elementos.append({'L': L_n, 'Z': z_n})
    d_n = 2 * sigma * L_n
    z_n -= d_n
    L_n = L_n * tau

# Invertir para que Z=0 sea el feed (elemento más corto)
z_offset = abs(elementos[-1]['Z'])
for el in elementos:
    el['Z'] += z_offset
elementos.reverse()

# Diseño de la línea de transmisión (Boom)
# Promedio de l/d para calcular Za
l_d_promedio = (L_max / d + elementos[0]['L'] / d) / 2.0
# Ecuación (11-33): Impedancia característica promedio de los elementos
Z_a = 120 * (math.log(l_d_promedio) - 2.25)
rel_impedance = Z_a / R_in

# Por Figura 11.14 (aproximación numérica estándar para Z_0)
Z_0 = R_in * math.sqrt(rel_impedance) # Aprox 65-80 ohms

# Ecuación (11-34): Separación centro a centro del boom (s)
s = d * math.cosh(Z_0 / 120.0)
gap = s - d # Separación física de aire

# ==========================================
# GENERACIÓN DEL REPORTE (MARKDOWN)
# ==========================================
report = f"""# Memoria de Cálculo - Antena LPDA (470-698 MHz)
**Referencia:** *Antenna Theory, Constantine A. Balanis, Cap. 11*

## 1. Parámetros Iniciales
- **Banda de Frecuencia:** {f_min} - {f_max} MHz
- **Ganancia Deseada:** ~7.5 dBi
- **Impedancia Objetivo ($R_{{in}}$):** {R_in} $\Omega$
- **Diámetro del tubo de aluminio ($d$):** {d*1000} mm

## 2. Parámetros Geométricos (Fig. 11.13)
Para una directividad óptima y tamaño compacto, se selecciona:
- **Factor de Escala ($\tau$):** {tau}
- **Factor de Espaciado ($\sigma$):** {sigma}

## 3. Cálculos según Ecuaciones de Balanis
- **Ángulo del vértice ($\alpha$):** {alpha_deg:.2f}° *(Ec. 11-28)*
- **Ancho de banda de diseño ($B_s$):** {B_s:.2f} *(Ec. 11-30)*
- **Longitud total del Boom ($L$):** {L_boom*100:.1f} cm *(Ec. 11-31)*
- **Número de Elementos ($N$):** {N} *(Ec. 11-32)*

## 4. Diseño del Boom (Línea de Transmisión)
- **Impedancia promedio de elementos ($Z_a$):** {Z_a:.1f} $\Omega$ *(Ec. 11-33)*
- **Impedancia característica del Boom ($Z_0$):** {Z_0:.1f} $\Omega$ *(Fig 11.14)*
- **Separación centro a centro ($s$):** {s*1000:.1f} mm *(Ec. 11-34)*
- **Espacio físico entre tubos (Gap):** {gap*1000:.1f} mm

## 5. Dimensiones de Corte (Para la Ferretería)
"""
for i, el in enumerate(elementos):
    report += f"- **Elemento {i+1}:** Longitud = {el['L']*100:.1f} cm | Posición Z = {el['Z']*100:.1f} cm\n"

with open("reporte_diseno_antena.md", "w") as f:
    f.write(report)

# ==========================================
# GENERACIÓN DEL ARCHIVO NEC PARA SIMULACIÓN
# ==========================================
nec_lines = []
nec_lines.append("CM Antena LPDA TVWS - Diseño riguroso Balanis")
nec_lines.append(f"CM Impedancia Boom Z0 = {Z_0:.1f} ohms")
nec_lines.append("CE")

tag = 1
radio_tubo = d / 2.0
for el in elementos:
    y = el['L'] / 2.0
    z = el['Z']
    nec_lines.append(f"GW {tag} 21 0.0 {-y:.4f} {z:.4f} 0.0 {y:.4f} {z:.4f} {radio_tubo:.4f}")
    tag += 1

nec_lines.append("GE 0")

for i in range(1, N):
    nec_lines.append(f"TL {i} 11 {i+1} 11 -{Z_0:.1f}")

nec_lines.append("EX 0 1 11 00 1.0 0.0")
nec_lines.append("FR 0 41 0 0 400.0 10.0")
nec_lines.append("RP 0 37 73 1000 0.0 0.0 5.0 5.0")
nec_lines.append("EN")

with open("TVWS_LPDA_Balanis.nec", "w") as f:
    f.write("\n".join(nec_lines) + "\n")

print("Cálculos completados. Reporte y archivo NEC generados.")
