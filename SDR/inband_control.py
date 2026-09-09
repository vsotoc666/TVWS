"""
SDR/inband_control.py
=====================
Capa de Control In-Band para Radio Cognitiva TVWS.
Implementa el empaquetado, inyección y extracción de bits de control
en las subportadoras OFDM #254, #256 y #257.

Diseño basado en el README Punto 7: 3 Formatos de Control y Contingencia Rendezvous.
"""

import numpy as np
from typing import Optional, Tuple, List

# ─────────────────────────────────────────────────────────────────────────────
# 1. UTILIDADES CRIPTOGRÁFICAS LIGERAS (Sin dependencias externas)
# ─────────────────────────────────────────────────────────────────────────────

def crc16(data: bytes) -> int:
    """
    Calcula el CRC-16/CCITT-FALSE estándar.
    Polinomio: 0x1021, Valor inicial: 0xFFFF.
    Es el mismo algoritmo estandarizado que se usa en tarjetas SD y Bluetooth.
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021)
            else:
                crc = (crc << 1)
            crc &= 0xFFFF
    return crc

# ─────────────────────────────────────────────────────────────────────────────
# 2. CONSTRUCTOR DE PAQUETES (El empacador de bits)
# ─────────────────────────────────────────────────────────────────────────────

class InbandPacketBuilder:
    """
    Construye las palabras de 32 bits (words) para los 3 formatos del protocolo.
    Estructura general: [Payload 16 bits] + [CRC-16 16 bits] = 32 bits.
    """

    @staticmethod
    def build_format_a(next_ch: int, t_hop: int) -> int:
        """
        Formato A: Salto Inmediato. (Flag 00)
        GW -> Cliente.
        """
        payload = (0b00) | ((next_ch & 0x3F) << 2) | ((t_hop & 0xFF) << 8)
        crc = crc16(payload.to_bytes(2, 'big'))
        return payload | (crc << 16)

    @staticmethod
    def build_format_b(rank: int, channel: int, mod: int, power: int, quiet: int) -> int:
        """
        Formato B: Actualización de Respaldo Proactiva. (Flag 01)
        GW -> Cliente. (Top-4 Targeted Rendezvous).
        """
        payload = (0b01) | ((rank & 0x3) << 2) | ((channel & 0x3F) << 4)
        payload |= ((mod & 0x3) << 10) | ((power & 0x1) << 12) | ((quiet & 0x1) << 13)
        crc = crc16(payload.to_bytes(2, 'big'))
        return payload | (crc << 16)

    @staticmethod
    def build_format_c(ack_type: int, rank_ack: int, rssi_dbm: float, snr_db: float) -> int:
        """
        Formato C: ACK y Métricas Uplink. (Flag 10)
        Cliente -> GW.
        Mapea el RSSI de [-100, -68] dBm a [0, 31] enteros.
        Mapea el SNR de [0, 31] dB a [0, 31] enteros.
        """
        rssi_bits = int(max(0, min(31, rssi_dbm + 100)))
        snr_bits = int(max(0, min(31, snr_db)))
        
        payload = (0b10) | ((ack_type & 0x3) << 2) | ((rank_ack & 0x3) << 4)
        payload |= ((rssi_bits & 0x1F) << 6) | ((snr_bits & 0x1F) << 11)
        crc = crc16(payload.to_bytes(2, 'big'))
        return payload | (crc << 16)

    @staticmethod
    def word_to_bpsk_bits(word: int, n_bits: int = 32) -> List[int]:
        """Desensambla la palabra de 32 bits en un array de 1s y 0s (MSB primero)."""
        return [(word >> i) & 1 for i in range(n_bits - 1, -1, -1)]

    @staticmethod
    def bpsk_bits_to_word(bits: List[int]) -> int:
        """Reensambla un array de 32 bits a un entero puro."""
        word = 0
        for bit in bits:
            word = (word << 1) | (bit & 1)
        return word

# ─────────────────────────────────────────────────────────────────────────────
# 3. BUFFER DESLIZANTE (La magia de la sincronización sin estado)
# ─────────────────────────────────────────────────────────────────────────────

class InbandSymbolBuffer:
    """
    Acumula símbolos OFDM de 3 en 3 y valida el paquete.
    Como el mensaje de 32 bits se envía en 11 símbolos OFDM (11 * 3 = 33 bits),
    este buffer descarta el bit de padding #33 y valida los primeros 32 con CRC-16.
    """
    def __init__(self):
        self.bits: List[int] = []

    def push(self, bit_254: int, bit_256: int, bit_257: int):
        """Añade los 3 bits extraídos de un símbolo OFDM al final de la cinta."""
        self.bits.extend([bit_254, bit_256, bit_257])
        # Solo necesitamos guardar los últimos 33 bits recibidos
        if len(self.bits) > 33:
            self.bits = self.bits[-33:]

    def is_complete(self) -> bool:
        """¿Tenemos suficientes bits para evaluar un paquete (11 símbolos = 33 bits)?"""
        return len(self.bits) == 33

    def flush(self) -> Optional[int]:
        """
        Aplica la validación CRC-16 sobre los últimos 32 bits recibidos.
        Si la ventana encajó a la perfección y no hay ruido, devuelve el Word y se limpia.
        Si hay basura o está desalineado, devuelve None silenciosamente (falla el 90% del tiempo).
        """
        if not self.is_complete():
            return None

        # Descartamos el bit de padding #33. Evaluamos solo los primeros 32.
        payload_bits = self.bits[:32]
        word = InbandPacketBuilder.bpsk_bits_to_word(payload_bits)
        
        # El Word es: [CRC (16)] | [Payload (16)]
        payload = word & 0xFFFF
        received_crc = (word >> 16) & 0xFFFF
        
        calculated_crc = crc16(payload.to_bytes(2, 'big'))
        
        if received_crc == calculated_crc:
            self.bits.clear() # ¡Paquete válido! Limpiamos el buffer
            return word
            
        return None

# ─────────────────────────────────────────────────────────────────────────────
# 4. INYECTOR OFDM (TRANSMISOR)
# ─────────────────────────────────────────────────────────────────────────────

class InbandControlTx:
    """Se ejecuta en el Transmisor, JUSTO ANTES del OFDM Carrier Allocator."""
    
    @staticmethod
    def inject(frame: np.ndarray, word: int, symbol_index: int) -> np.ndarray:
        """
        Inyecta 3 bits de nuestro mensaje de 32 bits en el frame de 512 subportadoras.
        
        Args:
            frame: Array NumPy complejo de tamaño 512 (las subportadoras OFDM).
            word: El paquete de control de 32 bits (Generado por InbandPacketBuilder).
            symbol_index: En qué símbolo OFDM del fragmento estamos (0 a 10).
        """
        bits = InbandPacketBuilder.word_to_bpsk_bits(word, 32)
        bits.append(0)  # Agregamos el bit de padding para completar 33 (11 símbolos x 3)
        
        idx = symbol_index * 3
        b254, b256, b257 = bits[idx], bits[idx+1], bits[idx+2]
        
        # Modulación BPSK: bit 1 = +1+0j, bit 0 = -1+0j
        frame[254] = complex(1 if b254 else -1, 0)
        frame[256] = complex(1 if b256 else -1, 0)
        frame[257] = complex(1 if b257 else -1, 0)
        
        return frame

# ─────────────────────────────────────────────────────────────────────────────
# 5. EXTRACTOR OFDM (RECEPTOR)
# ─────────────────────────────────────────────────────────────────────────────

class InbandControlRx:
    """Se ejecuta en el Receptor, JUSTO DESPUÉS de calcular la FFT del espectro."""
    
    @staticmethod
    def extract(frame: np.ndarray) -> Tuple[int, int, int]:
        """
        Demaea (demodula) ciegamente las posiciones 254, 256 y 257.
        Devuelve (bit_254, bit_256, bit_257) listos para meter al InbandSymbolBuffer.
        """
        # Demodulación BPSK dura: > 0 = 1, <= 0 = 0
        b254 = 1 if frame[254].real > 0 else 0
        b256 = 1 if frame[256].real > 0 else 0
        b257 = 1 if frame[257].real > 0 else 0
        
        return b254, b256, b257
