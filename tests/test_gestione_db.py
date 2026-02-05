
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Adattamento path per importare i moduli corretti
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import gestione_db
from utils.crypto_manager import CryptoManager

class TestGestioneDB(unittest.TestCase):

    @patch('db.gestione_db.get_db_connection')
    def test_get_configurazione_global(self, mock_get_conn):
        # Mocking the connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        
        # Setup the context manager return values
        mock_get_conn.return_value.__enter__.return_value = mock_conn
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

    @patch('db.gestione_db.get_db_connection')
    @patch('db.gestione_db.decrypt_system_data')
    def test_get_configurazione_smtp_encrypted_success(self, mock_decrypt, mock_get_conn):
        # Scenario: Admin requesting SMTP password (encrypted with system key)
        
        # Mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
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

    @patch('db.gestione_db.get_db_connection')
    def test_set_configurazione_global(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        result = gestione_db.set_configurazione('my_key', 'my_val')
        
        self.assertTrue(result)
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch('db.gestione_db.get_db_connection')
    @patch('db.gestione_db.ottieni_budget_famiglia')
    def test_ottieni_totale_budget_allocato(self, mock_get_budget, mock_conn):
        # Logic test: summation of budget
        mock_get_budget.return_value = [
            {'importo_limite': 100},
            {'importo_limite': 50.5},
            {'importo_limite': 0}
        ]
        
        total = gestione_db.ottieni_totale_budget_allocato(id_famiglia=1)
        self.assertEqual(total, 150.5)

    @patch('db.gestione_db.get_db_connection')
    @patch('db.gestione_db._get_family_key_for_user')
    @patch('db.gestione_db._get_crypto_and_key')
    @patch('db.gestione_db._decrypt_if_key')
    def test_calcola_entrate_mensili_mocked(self, mock_decrypt, mock_crypto_key, mock_fam_key, mock_get_conn):
        """
        Testa il calcolo delle entrate verificando che vengano sommate le transazioni personali e condivise
        delle categorie 'Entrate'.
        """
        # Mock connection sequence
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock keys
        mock_crypto_key.return_value = (MagicMock(), b'master')
        mock_fam_key.return_value = b'family'
        
        # Helper per mocking side_effect del cursore per chiamate multiple
        # Sequenza chiamate attesa:
        # 1. SELECT id_categoria... FROM Categorie
        # 2. SELECT id_sottocategoria FROM Sottocategorie
        # 3. SELECT SUM(...) FROM Transazioni (personali)
        # 4. SELECT SUM(...) FROM TransazioniCondivise (condivise)
        
        # Setup dati mocked
        mock_categories = [{'id_categoria': 10, 'nome_categoria': 'Stipendio (Enc)'}]
        mock_subcategories = [{'id_sottocategoria': 101}, {'id_sottocategoria': 102}]
        mock_sum_personal = {'totale': 1500.0}
        mock_sum_shared = {'totale': 500.0}

        # side_effect per gestire le diverse query di fetchall/fetchone
        # Nota: fetchall viene chiamato per Categorie e Sottocategorie
        # fetchone per le somme
        
        # Purtroppo side_effect dipende dall'ordine di esecuzione. 
        # Categorie -> fetchall
        # Sottocategorie -> fetchall
        # Somma Personale -> fetchone
        # Somma Condivisa -> fetchone
        
        mock_cursor.fetchall.side_effect = [mock_categories, mock_subcategories]
        mock_cursor.fetchone.side_effect = [mock_sum_personal, mock_sum_shared]

        # Mock decrypt (chiamato per il nome categoria)
        def decrypt_side_effect(data, key, crypto):
            if data == 'Stipendio (Enc)': return 'Stipendio ed Entrate Varie'
            return data
        mock_decrypt.side_effect = decrypt_side_effect

        total = gestione_db.calcola_entrate_mensili_famiglia(id_famiglia=1, anno=2024, mese=12, master_key_b64='k', id_utente=1)
        
        # Verify
        # 1500 + 500 = 2000
        self.assertEqual(total, 2000.0)

    @patch('db.gestione_db.calcola_entrate_mensili_famiglia')
    @patch('db.gestione_db.get_db_connection')
    @patch('db.gestione_db.ottieni_impostazioni_budget_storico')
    @patch('db.gestione_db.get_impostazioni_budget_famiglia')
    @patch('db.gestione_db.ottieni_totale_budget_storico')
    @patch('db.gestione_db.ottieni_totale_budget_allocato')
    @patch('db.gestione_db.ottieni_dati_analisi_annuale')
    @patch('db.gestione_db._get_crypto_and_key')
    @patch('db.gestione_db._get_family_key_for_user')
    @patch('db.gestione_db._decrypt_if_key')
    def test_ottieni_dati_analisi_mensile_workflow(self, mock_dec, mock_fam, mock_cry, mock_annuale, mock_budget, mock_budget_storico, mock_curr_imp, mock_hist_imp, mock_conn, mock_entrate):
        """
        Testa il flusso di ottieni_dati_analisi_mensile.
        Verifica che vengano chiamate le funzioni giuste e ritornata la struttura corretta.
        """
        # 0. Mock Entrate
        mock_entrate.return_value = 3000.0
        
        # 1. Mock Impostazioni (facciamo finta non ci sia storico)
        mock_hist_imp.return_value = None
        mock_curr_imp.return_value = {'entrate_mensili': 3000.0}
        
        # 2. Mock Budget Totale
        mock_budget.return_value = 2500.0
        mock_budget_storico.return_value = 2500.0
        
        # 3. Mock Analisi Annuale (ritorna un dict vuoto per semplicita)
        mock_annuale.return_value = {}
        
        # 4. Mock DB per le spese
        # Sequenza query attesa in ottieni_dati_analisi_mensile:
        # - Spese Personali (fetchall)
        # - Spese Condivise (fetchall)
        # - Categorie (fetchall)
        # - Sottocategorie per ogni categoria (fetchall) ...
        
        conn = MagicMock()
        cursor = MagicMock()
        mock_conn.return_value.__enter__.return_value = conn
        conn.cursor.return_value = cursor
        
        # Setup dati spese
        # Personali: Sub 10 -> 100
        spese_pers = [{'id_sottocategoria': 10, 'totale': -100}] 
        # Condivise: Sub 10 -> 50, Sub 20 -> 200
        spese_cond = [{'id_sottocategoria': 10, 'totale': -50}, {'id_sottocategoria': 20, 'totale': -200}]
        
        # Categorie: Cat 1 (Sub 10), Cat 2 (Sub 20)
        cats = [{'id_categoria': 1, 'nome_categoria': 'Cibo'}, {'id_categoria': 2, 'nome_categoria': 'Auto'}]
        
        # Sottocategorie fetch: 
        # 1a chiamata (per Cat 1) -> [{'id_sottocategoria': 10}]
        # 2a chiamata (per Cat 2) -> [{'id_sottocategoria': 20}]
        
        cursor.fetchall.side_effect = [
            spese_pers, # 1. Spese personali
            spese_cond, # 2. Spese condivise
            cats,       # 3. Categorie
            [{'id_sottocategoria': 10}], # 4. Sub per Cat 1
            [{'id_sottocategoria': 20}]  # 5. Sub per Cat 2
        ]
        # Mock keys
        mock_cry.return_value = (MagicMock(), b'master')
        mock_fam.return_value = b'family'
        mock_dec.side_effect = lambda x, y, z: x
        
        # Execute
        res = gestione_db.ottieni_dati_analisi_mensile(1, 2024, 12, 'key', 1)
        
        # Checks
        # Spese totali = 100 (pers sub10) + 50 (cond sub10) + 200 (cond sub20) = 350
        self.assertEqual(res['spese_totali'], 350.0)
        self.assertEqual(res['entrate'], 3000.0)
        self.assertEqual(res['budget_totale'], 2500.0)
        self.assertEqual(res['risparmio'], 3000.0 - 350.0) # 2650
        self.assertEqual(res['delta_budget_spese'], 2500.0 - 350.0) # 2150
        
        # Verifica categorie
        # Cat 1 (Cibo): sub 10 -> 150
        # Cat 2 (Auto): sub 20 -> 200
        self.assertEqual(len(res['spese_per_categoria']), 2)
        # Ordinate per importo decrescente -> Auto (200) then Cibo (150)
        self.assertEqual(res['spese_per_categoria'][0]['nome_categoria'], 'Auto')
        self.assertEqual(res['spese_per_categoria'][0]['importo'], 200.0)

if __name__ == '__main__':
    unittest.main()
