# Prueba 1 — `tun0` básico

**Objetivo** (según el plan): crear la interfaz `tun0` con `ip tuntap add`,
asignarle IP y verificar con `ping` que el kernel enruta hacia ella. Valida
permisos y existencia de la interfaz — el primero de los 3 puntos de falla
aislados por el plan (kernel↔GNU Radio, antes de tocar GNU Radio en sí).

Esta prueba **no requiere el venv SDR ni GNU Radio** — es pura configuración
de red del kernel Linux.

## Comandos ejecutados

```bash
sudo ip tuntap add dev tun0 mode tun user $USER
sudo ip addr add 10.99.0.1/30 dev tun0
sudo ip link set tun0 up
ping -I tun0 -c 4 10.99.0.2
```

`user $USER` es la parte clave: le da a tu usuario (`victors`, UID 1000)
permiso para abrir el fd de `tun0` sin `sudo`/`CAP_NET_ADMIN` más adelante —
necesario porque el bloque `tuntap_pdu` de GNU Radio en la Prueba 2 se
ejecuta como usuario normal, no root.

## Resultados observados

```
$ ip tuntap show
tun0: tun persist user 1000

$ ip addr show tun0
3: tun0: <NO-CARRIER,POINTOPOINT,MULTICAST,NOARP,UP> mtu 1500 qdisc fq_codel state DOWN group default qlen 500
    link/none
    inet 10.99.0.1/30 scope global tun0

$ ip route show | grep tun0
10.99.0.0/30 dev tun0 proto kernel scope link src 10.99.0.1 linkdown

$ ping -I tun0 -c 4 10.99.0.2
4 packets transmitted, 0 received, 100% packet loss
```

## Interpretación

Los 3 criterios de la prueba se cumplen:

1. **Permisos** — `tun0: tun persist user 1000` confirma que el fd es
   abrible por el usuario sin privilegios extra.
2. **La interfaz existe** — `ip addr show tun0` la muestra con la IP
   asignada y en estado administrativo `UP`.
3. **El kernel enruta hacia ella** — la tabla de rutas tiene la entrada
   `10.99.0.0/30 dev tun0`, que es lo que hace que el `ping` se dirija a
   `tun0` en vez de fallar con "network unreachable".

**El `NO-CARRIER`/`state DOWN` y el 100% de packet loss del ping son
esperados y no indican fallo.** Un TUN solo reporta "carrier" cuando un
proceso userspace tiene el fd abierto — en esta prueba nadie lo tenía. Ese
es exactamente el comportamiento que valida la Prueba 2 (GNU Radio abriendo
el fd vía `tuntap_pdu`).

## Estado: ✅ Aprobada

`tun0` queda en pie (persistente, `10.99.0.1/30`, `up`) para las pruebas
siguientes.
