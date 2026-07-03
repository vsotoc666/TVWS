"""
SDR/test_inband_control.py
==========================
Pruebas unitarias para validar la lógica del canal de control In-Band.
Para ejecutar: python3 -m unittest SDR/test_inband_control.py
"""

import unittest
import numpy as np
from SDR.inband_control import (
    crc16, 
    InbandPacketBuilder, 
    InbandSymbolBuffer, 
    InbandControlTx, 
    InbandControlRx
)

class TestInbandControl(unittest.TestCase):

    def test_crc16(self):
        # Prueba básica para verificar que el CRC funciona
        data = b"TVWS"
        crc = crc16(data)
        self.assertTrue(isinstance(crc, int))
        self.assertTrue(0 <= crc <= 0xFFFF)

    def test_format_a_generation(self):
        # Generar un Formato A: next_ch = 36, t_hop = 10
        word = InbandPacketBuilder.build_format_a(36, 10)
        
        # Desarmar el word
        payload = word & 0xFFFF
        flag = payload & 0x3
        next_ch = (payload >> 2) & 0x3F
        t_hop = (payload >> 8) & 0xFF
        
        self.assertEqual(flag, 0b00)
        self.assertEqual(next_ch, 36)
        self.assertEqual(t_hop, 10)

        # Verificar CRC interno
        crc_recibido = (word >> 16) & 0xFFFF
        crc_calculado = crc16(payload.to_bytes(2, 'big'))
        self.assertEqual(crc_recibido, crc_calculado)

    def test_buffer_sliding_window(self):
        buffer = InbandSymbolBuffer()
        word_original = InbandPacketBuilder.build_format_a(42, 5)
        bits_msg = InbandPacketBuilder.word_to_bpsk_bits(word_original, 32)
        bits_msg.append(0) # Padding bit
        
        # Simulamos que antes había ruido (basura)
        ruido = [1, 0, 1, 1, 0, 0, 1, 0, 1] # 3 símbolos de basura
        for i in range(0, len(ruido), 3):
            buffer.push(ruido[i], ruido[i+1], ruido[i+2])
            self.assertIsNone(buffer.flush())
            
        # Ahora inyectamos los símbolos válidos de nuestro mensaje
        for i in range(0, len(bits_msg), 3):
            buffer.push(bits_msg[i], bits_msg[i+1], bits_msg[i+2])
            
            # El flush solo debería devolver el word en el último ciclo (símbolo 11)
            resultado = buffer.flush()
            if i < len(bits_msg) - 3:
                self.assertIsNone(resultado)
            else:
                self.assertEqual(resultado, word_original)

    def test_ofdm_round_trip(self):
        word_tx = InbandPacketBuilder.build_format_b(rank=1, channel=18, mod=0, power=1, quiet=1)
        
        # Simulamos la recepción a través de GNU Radio (11 símbolos OFDM)
        buffer = InbandSymbolBuffer()
        
        for symbol_index in range(11):
            # 1. El TX crea un frame de 512 vacío (datos aleatorios)
            frame_tx = np.random.randn(512) + 1j * np.random.randn(512)
            
            # 2. El TX inyecta los 3 bits correspondientes a este símbolo
            frame_modificado = InbandControlTx.inject(frame_tx, word_tx, symbol_index)
            
            # ... viaja por el aire ...
            
            # 3. El RX recibe el frame (asumimos canal ideal sin ruido para este test)
            frame_rx = frame_modificado
            
            # 4. El RX extrae los 3 bits
            b254, b256, b257 = InbandControlRx.extract(frame_rx)
            
            # 5. Se empujan al buffer
            buffer.push(b254, b256, b257)
            
            # 6. Intentamos flushear
            resultado = buffer.flush()
            if symbol_index == 10:
                self.assertEqual(resultado, word_tx, "El word recuperado debe ser idéntico al transmitido")
            else:
                self.assertIsNone(resultado)

if __name__ == '__main__':
    unittest.main()
