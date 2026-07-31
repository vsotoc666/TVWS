import math

# Parámetros de diseño LPDA
f_min = 470.0  # MHz
f_max = 698.0  # MHz
c = 300.0      # Velocidad de la luz (Mm/s)

# Factores de diseño estándar para buena ganancia (aprox 7 dBi)
tau = 0.88
sigma = 0.15

# Longitudes del dipolo más largo y más corto
L_max = c / (2 * f_min)
L_min = c / (2 * f_max)

# Cálculo de la cantidad de elementos (N)
N = math.ceil(1 + math.log(L_min / L_max) / math.log(tau))

print(f"Calculando LPDA para {f_min}-{f_max} MHz")
print(f"Número de elementos calculados: {N}")

# Generando geometría
elementos = []
L_actual = L_max
z_actual = 0.0

for i in range(N):
    elementos.append({'L': L_actual, 'Z': z_actual})
    L_next = L_actual * tau
    d = 2 * sigma * L_actual
    z_actual -= d  # Los elementos se hacen más cortos hacia adelante (Z negativo)
    L_actual = L_next

# Invertimos para que el elemento más corto (alimentación) esté en Z=0
z_offset = abs(elementos[-1]['Z'])
for el in elementos:
    el['Z'] += z_offset
elementos.reverse() # Ahora el índice 0 es el elemento más corto (alimentación)

# Generación del archivo NEC
nec_lines = []
nec_lines.append("CM Antena LPDA para Radio Cognitiva TVWS (470-698 MHz)")
nec_lines.append("CM Generado matemáticamente")
nec_lines.append("CE")

# Escribir los cables (GW) - Geometría
# Formato: GW tag_no segments x1 y1 z1 x2 y2 z2 radius
tag = 1
radio_tubo = 0.005 # 5 mm de radio (1 cm de diámetro)
for el in elementos:
    y = el['L'] / 2.0
    z = el['Z']
    # Dipolo en el eje Y, desplazado a lo largo del eje Z
    nec_lines.append(f"GW {tag} 21 0.0 {-y:.4f} {z:.4f} 0.0 {y:.4f} {z:.4f} {radio_tubo}")
    tag += 1

nec_lines.append("GE 0")

# Línea de transmisión (Boom) cruzada
# Formato: TL tag1 seg1 tag2 seg2 Z0 Length
for i in range(1, N):
    # Conecta el centro del dipolo actual con el centro del siguiente dipolo
    # Z0 = 100 ohms (impedancia característica de la línea paralela)
    nec_lines.append(f"TL {i} 11 {i+1} 11 -100.0")

# Excitación (EX) - Fuente de voltaje en el elemento más corto (tag 1, centro seg 11)
nec_lines.append("EX 0 1 11 00 1.0 0.0")

# Frecuencias de simulación (FR) - Barrido de 400 a 800 MHz en pasos de 10 MHz
nec_lines.append("FR 0 41 0 0 400.0 10.0")

# Patrón de Radiación (RP) - Necesario para ver el lóbulo en xnec2c
# RP 0 37 73 1000 0 0 5 5 = Calcula 3D en pasos de 5 grados (Theta y Phi)
nec_lines.append("RP 0 37 73 1000 0.0 0.0 5.0 5.0")

# Fin del archivo
nec_lines.append("EN")

with open("TVWS_LPDA.nec", "w") as f:
    f.write("\n".join(nec_lines) + "\n")

print("Archivo 'TVWS_LPDA.nec' generado exitosamente. Ábrelo en xnec2c.")
