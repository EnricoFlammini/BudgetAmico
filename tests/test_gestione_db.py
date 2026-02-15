import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Adattamento path per importare i moduli corretti
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock env vars BEFORE importing anything that might trigger DB initialization
os.environ["SUPABASE_DB_URL"] = "postgresql://user:pass@host:5432/db"
os.environ["SERVER_SECRET_KEY"] = "test_secret_key_32_chars_long_long"

from db import gestione_db
from utils.cache_manager import cache_manager

class TestGestioneDB(unittest.TestCase):

    def setUp(self):
        # Disabilita la cache per i test
        cache_manager.get_or_compute = lambda key, compute_fn, **kwargs: compute_fn()

    @patch('db.supabase_manager.SupabaseManager.get_connection')
    @patch('db.supabase_manager.SupabaseManager.release_connection')
    def test_get_configurazione_global(self, mock_release, mock_get_conn):
        # Mocking the connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Setup query result
        mock_cursor.fetchone.return_value = {'valore': 'test_value'}
        
        # Execute
        result = gestione_db.get_configurazione('some_key')
        
        # Assertions
        self.assertEqual(result, 'test_value')
        mock_cursor.execute.assert_called()
        args, _ = mock_cursor.execute.call_args
        self.assertIn("SELECT valore FROM Configurazioni", args[0])
        self.assertEqual(args[1], ('some_key',))

    @patch('db.supabase_manager.SupabaseManager.get_connection')
    @patch('db.supabase_manager.SupabaseManager.release_connection')
    @patch('db.gestione_config.decrypt_system_data')
    def test_get_configurazione_smtp_encrypted_success(self, mock_decrypt, mock_release, mock_get_conn):
        # Mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Query returns encrypted value
        mock_cursor.fetchone.return_value = {'valore': 'encrypted_stuff'}
        
        # Mock system decryption
        mock_decrypt.return_value = 'decrypted_password'
        
        # Execute
        result = gestione_db.get_configurazione(
            'smtp_password', 
            id_famiglia=1
        )
        
        # Verify
        self.assertEqual(result, 'decrypted_password')
        mock_decrypt.assert_called_with('encrypted_stuff')

    @patch('db.supabase_manager.SupabaseManager.get_connection')
    @patch('db.supabase_manager.SupabaseManager.release_connection')
    def test_set_configurazione_global(self, mock_release, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        result = gestione_db.set_configurazione('my_key', 'my_val')
        
        self.assertTrue(result)
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('db.gestione_budget.ottieni_budget_famiglia')
    def test_ottieni_totale_budget_allocato(self, mock_get_budget):
        # Logic test: summation of budget
        mock_get_budget.return_value = [
            {'importo_limite': 100},
            {'importo_limite': 50.5},
            {'importo_limite': 0}
        ]
        
        total = gestione_db.ottieni_totale_budget_allocato(id_famiglia=1)
        self.assertEqual(total, 150.5)

    @patch('db.gestione_budget.get_db_connection')
    @patch('db.gestione_budget._get_family_key_for_user')
    @patch('db.gestione_budget._get_crypto_and_key')
    @patch('db.gestione_budget._decrypt_if_key')
    def test_calcola_entrate_mensili_mocked(self, mock_decrypt, mock_crypto_key, mock_fam_key, mock_get_db):
        # Mock connection sequence
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock keys
        mock_crypto_key.return_value = (MagicMock(), b'master')
        mock_fam_key.return_value = b'family'
        
        # Setup dati mocked
        mock_categories = [{'id_categoria': 10, 'nome_categoria': 'Stipendio (Enc)'}]
        mock_subcategories = [{'id_sottocategoria': 101}, {'id_sottocategoria': 102}]
        mock_sum_personal = {'totale': 1500.0}
        mock_sum_shared = {'totale': 500.0}

        mock_cursor.fetchall.side_effect = [mock_categories, mock_subcategories]
        mock_cursor.fetchone.side_effect = [mock_sum_personal, mock_sum_shared]

        # Mock decrypt (chiamato per il nome categoria)
        def decrypt_side_effect(data, key, crypto, silent=False):
            if data == 'Stipendio (Enc)': return 'Stipendio ed Entrate Varie'
            return data
        mock_decrypt.side_effect = decrypt_side_effect

        total = gestione_db.calcola_entrate_mensili_famiglia(id_famiglia=1, anno=2024, mese=12, master_key_b64='k', id_utente=1)
        
        self.assertEqual(total, 2000.0)

    @patch('db.gestione_db.calcola_entrate_mensili_famiglia')
    @patch('db.gestione_budget.calcola_entrate_mensili_famiglia')
    @patch('db.gestione_budget.get_db_connection')
    @patch('db.gestione_budget.ottieni_impostazioni_budget_storico')
    @patch('db.gestione_budget.get_impostazioni_budget_famiglia')
    @patch('db.gestione_budget.ottieni_totale_budget_storico')
    @patch('db.gestione_budget.ottieni_totale_budget_allocato')
    @patch('db.gestione_budget.ottieni_dati_analisi_annuale')
    @patch('db.gestione_budget._get_crypto_and_key')
    @patch('db.gestione_budget._get_family_key_for_user')
    @patch('db.gestione_budget._decrypt_if_key')
    def test_ottieni_dati_analisi_mensile_workflow(self, mock_dec, mock_fam, mock_cry, mock_annuale, mock_budget, mock_budget_storico, mock_curr_imp, mock_hist_imp, mock_get_db, mock_entrate, mock_entrate_db):
        # 0. Mock Entrate
        mock_entrate.return_value = 3000.0
        
        # 1. Mock Impostazioni
        mock_hist_imp.return_value = None
        mock_curr_imp.return_value = {'entrate_mensili': 3000.0}
        
        # 2. Mock Budget Totale
        mock_budget.return_value = 2500.0
        mock_budget_storico.return_value = 2500.0
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Setup mock results (SpesePers -> SpeseCond -> Categorie -> SubsCat)
        mock_cursor.fetchall.side_effect = [
            [{'id_sottocategoria': 101, 'totale': -100.0}],           # 1. ottieni_dati: Spese personali
            [{'id_sottocategoria': 102, 'totale': -50.0}],            # 2. ottieni_dati: Spese condivise
            [{'id_categoria': 10, 'nome_categoria': 'Spese (Enc)'}],    # 3. ottieni_dati: Tutte le categorie
            [{'id_sottocategoria': 101}, {'id_sottocategoria': 102}]  # 4. ottieni_dati: Sottocategorie Cat 10
        ]
        
        mock_cursor.fetchone.side_effect = [] # Not used by ottieni_dati directly
        
        # Mock keys
        mock_fam.return_value = b'family'
        mock_cry.return_value = (MagicMock(), b'master')
        # Mock decryption logic
        def decrypt_side_effect(data, key, crypto, silent=False):
            if data == 'Spese (Enc)': return 'Spese Varie'
            if data == 'Entrate (Enc)': return 'Entrate ed altro'
            return data
        mock_dec.side_effect = decrypt_side_effect
        
        # Execute
        res = gestione_db.ottieni_dati_analisi_mensile(
            id_famiglia=1, anno=2024, mese=12, master_key_b64='k', id_utente=1
        )
        
        # Assertions
        self.assertIsNotNone(res)
        self.assertEqual(res['entrate'], 3000.0)
        self.assertEqual(res['spese_totali'], 150.0)
        self.assertEqual(len(res['spese_per_categoria']), 1)

if __name__ == '__main__':
    unittest.main()
