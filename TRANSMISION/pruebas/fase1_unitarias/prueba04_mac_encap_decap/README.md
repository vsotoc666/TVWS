# Prueba 4 — MAC encapsulado/decapsulado + fragmentación

**Objetivo** (según el plan): test unitario Python puro — `payload →
header (seq_num|frag_flags|mod_scheme|CRC) → decap → payload igual`.
Verifica framing correcto, que el CRC detecta corrupción inyectada a
propósito, y que la fragmentación/reensamblado de PDUs grandes funciona.

No requiere `tun0`, `sudo` ni GNU Radio — corre con el Python del sistema
(`python3 test_mac_frame.py`), a diferencia de las Pruebas 2 y 3.

## Formato de header (decisión cerrada)

`claudedocs/arquitectura_enlace_datos.md` §2.4 cierra el formato de header
y el diseño de fragmentación (decidido 21/08/2026, implementado en esta
prueba). El campo `next_ch` de una versión anterior de esta prueba resultó
vestigial — ningún test lo ligaba a lógica real de salto de canal, porque
el salto de canal real lo maneja el canal de control in-band dedicado
(subportadoras #254/256/257), no el header MAC — así que se **repurpuseó
ese byte como `frag_flags`** en vez de agregar overhead nuevo:

| campo | bytes | rango/valores |
|---|---|---|
| `seq_num` | 1 | 0-255, wrap-around. Semántica: **ID de PDU** — todos los fragmentos de un mismo PDU comparten el mismo `seq_num` |
| `frag_flags` | 1 | bit 0 = MF ("more fragments", análogo a IPv4); bits 1-7 reservados (deben ser 0) |
| `mod_scheme` | 1 | `0`=BPSK, `1`=QPSK, `2`=16-QAM |
| `crc16` | 2 | CRC-16-CCITT (poly `0x1021`, init `0xFFFF`) sobre `header[:3] + payload` |

Overhead total: **5 bytes por frame** (sin cambio — el rediseño reutiliza
el byte que antes era `next_ch`, no agrega uno nuevo). Se usó CRC-16 (no
CRC-32 u otro) por consistencia con el CRC-16 que ya usa
`InbandControlLayer` para la palabra de control de 32 bits (`README.md`
§7).

Ver `claudedocs/arquitectura_enlace_datos.md` §2.4 para el *por qué* de
este diseño (motivado por el slot TDD de 20 símbolos OFDM que un frame de
tamaño MTU no siempre alcanza) — no se repite aquí para evitar que la
explicación se desincronice entre docs.

## Archivos

- **`mac_frame.py`** — `encapsular()` / `decapsular()` + `crc16_ccitt()` +
  `frag_flags_mf()` / `frag_flags_tiene_mf()` (helpers de 1 bit) +
  `fragmentar()` / `reensamblar()`. `decapsular()` lanza `MACFrameError`
  (nunca devuelve datos corruptos en silencio) si el CRC no coincide o el
  frame es más corto que header+CRC; `reensamblar()` reusa la misma
  excepción si cualquier fragmento falla el CRC (descarta el PDU completo
  — no hay ARQ/retransmisión en este diseño, ver §2.4) o si el `seq_num`
  no es consistente entre fragmentos.
- **`test_mac_frame.py`** — 14 casos, corridos como script plano (sin
  pytest, siguiendo la convención del resto del repo de no tener un
  framework de test — ver `CLAUDE.md` de `IA/`).

## Casos cubiertos

1. Round-trip con un payload realista (el mismo paquete UDP/IP armado a
   mano en la Prueba 3, reusado aquí como "PDU crudo de `tuntap_pdu`").
2. Round-trip con payload vacío.
3. Round-trip en los límites de los campos de 1 byte (`seq_num=255`,
   `frag_flags` con MF activo).
4. El overhead de framing es exactamente 5 bytes.
5. CRC detecta 1 byte corrupto en el payload.
6. CRC detecta 1 bit corrupto en el header (`seq_num`).
7. Un frame truncado (más corto que header+CRC) se rechaza con
   `MACFrameError` en vez de reventar con una excepción de `struct`.
8. `mod_scheme` fuera del enum se rechaza en `encapsular()` con
   `ValueError` (no se arma un frame inválido).
9. `frag_flags_mf()`/`frag_flags_tiene_mf()` codifican/leen el bit MF
   correctamente (incluye que bits reservados en 1 no rompen la lectura).
10. Un payload que cabe en un solo fragmento produce exactamente 1 frame
    con MF=0 — idéntico a una llamada directa a `encapsular()`.
11. `fragmentar()` de un payload de 1400 bytes en fragmentos de máximo
    100 bytes produce la cantidad esperada de fragmentos, con MF=1 en
    todos menos el último (MF=0), y `reensamblar()` reconstruye el
    payload original bit-exacto.
12. Un fragmento corrupto (CRC inválido) pasado a `reensamblar()` lanza
    `MACFrameError` — descarta el PDU completo, no hay recuperación
    parcial.
13. Fragmentos con `seq_num` inconsistente entre sí pasados a
    `reensamblar()` lanzan `MACFrameError`.
14. Un payload vacío fragmentado produce exactamente 1 fragmento (MF=0)
    y reensambla de vuelta a vacío.

## Resultado de la ejecución

```
$ python3 test_mac_frame.py
[OK] round-trip payload realista (paquete UDP/IP de la Prueba 3)
[OK] round-trip payload vacio
[OK] round-trip con seq_num=255 y frag_flags=MF (limites del campo de 1 byte)
[OK] overhead de framing es exactamente 5 bytes (3 header + 2 CRC)
[OK] CRC detecta 1 byte corrupto en el payload
[OK] CRC detecta 1 bit corrupto en el header (seq_num)
[OK] frame truncado rechazado con MACFrameError (no crashea)
[OK] mod_scheme invalido rechazado por encapsular() (ValueError)
[OK] frag_flags_mf()/frag_flags_tiene_mf() codifican/leen el bit MF correctamente
[OK] payload que cabe en 1 fragmento produce 1 solo frame (MF=0), identico a encapsular() directo
[OK] 1400B con max 100B/fragmento produce 14 fragmentos
[OK] MF=1 en todos los fragmentos salvo el ultimo (MF=0)
[OK] reensamblar(fragmentar(payload)) == payload original, bit exacto
[OK] fragmento corrupto en reensamblar() lanza MACFrameError (descarta el PDU)
[OK] seq_num inconsistente entre fragmentos lanza MACFrameError
[OK] payload vacio produce exactamente 1 fragmento (MF=0) y reensambla a vacio

14/14 casos aprobados
```

## Estado: ✅ Aprobada

Framing, detección de corrupción y fragmentación/reensamblado funcionan
según lo definido en `claudedocs/arquitectura_enlace_datos.md` §2.4. La
Prueba 14 (`fase3_loopback_completo/prueba14_paquete_grande/`) valida el
mismo mecanismo end-to-end a través de la cadena TX/RX completa (FEC/MOD/
OFDM), con el presupuesto real de un slot TDD de 20 símbolos.
