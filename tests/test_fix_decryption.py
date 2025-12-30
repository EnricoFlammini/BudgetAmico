import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import gestione_db

class TestDecryptionFix(unittest.TestCase):
    
    @patch('db.gestione_db.get_db_connection')
    @patch('db.gestione_db._get_crypto_and_key')
    @patch('db.gestione_db._get_key_for_transaction')
    @patch('db.gestione_db._decrypt_if_key')
    def test_ottieni_portafoglio_fallback_bug(self, mock_decrypt, mock_get_key_trans, mock_get_crypto, mock_get_conn):
        """
        Reproduces the bug where failure to decrypt with the first key (Family Key)
        overwrites the data with '[ENCRYPTED]', preventing fallback to Master Key.
        """
        # 1. Setup Mock DB Connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # 2. Setup Mock Data (One asset encrypted with Master Key)
        # Note: In the real bug, Ticker is encrypted with Master Key because the user created it before joining/sharing,
        # or because of some key mismatch.
        fake_encrypted_ticker = "gAAAAABk..." 
        fake_db_row = {
            'id_asset': 1,
            'ticker': fake_encrypted_ticker,
            'nome_asset': 'NOME_ITEM',
            'quantita': 10,
            'prezzo_attuale_manuale': 100,
            'costo_iniziale_unitario': 80,
            'data_aggiornamento': '2024-01-01',
            'gain_loss_unitario': 20,
            'gain_loss_totale': 200,
            'id_conto': 123
        }
        mock_cursor.fetchall.return_value = [fake_db_row]
        
        # 3. Setup Keys
        fake_master_key = b'master_key_123'
        fake_family_key = b'family_key_456' # Different from master
        
        mock_get_crypto.return_value = (MagicMock(), fake_master_key)
        # Simulate that the system thinks it should use Family Key first
        mock_get_key_trans.return_value = fake_family_key 
        
        # 4. Setup Decryption Logic Simulation
        def side_effect_decrypt(data, key, crypto, silent=False):
            # If we try to decrypt the original ciphertext with Family Key -> Fail
            if data == fake_encrypted_ticker and key == fake_family_key:
                return "[ENCRYPTED]" 
            
            # If we try to decrypt the original ciphertext with Master Key -> Success
            if data == fake_encrypted_ticker and key == fake_master_key:
                return "TEST_TICKER"
                
            # THE BUG: If we passed "[ENCRYPTED]" to the fallback, it returns "[ENCRYPTED]" (or fails)
            if data == "[ENCRYPTED]":
                 return "[ENCRYPTED]"

            return data
            
        mock_decrypt.side_effect = side_effect_decrypt
        
        # 5. Execute
        results = gestione_db.ottieni_portafoglio(123, master_key_b64="fake_b64")
        
        # 6. Assert
        # With the bug, we expect "ticker" to be "[ENCRYPTED]" because it got overwritten
        # If fixed, it should be "TEST_TICKER"
        print(f"DEBUG RESULT: {results[0]['ticker']}")
        self.assertEqual(results[0]['ticker'], "TEST_TICKER", "Fallback decryption failed! Data was likely overwritten.")

if __name__ == '__main__':
    unittest.main()
