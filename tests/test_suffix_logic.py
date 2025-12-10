
import unittest

import unittest
import sys
import os

# Aggiungi la root del progetto al path per importare i moduli
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.yfinance_manager import applica_suffisso_borsa

class TestSuffixLogic(unittest.TestCase):

    def test_suffix_added(self):
        """Test che il suffisso venga aggiunto se manca e c'è un default."""
        ticker = "AAPL"
        borsa_default = ".MI"
        result = applica_suffisso_borsa(ticker, borsa_default)
        self.assertEqual(result, "AAPL.MI")

    def test_suffix_not_added_already_present(self):
        """Test che il suffisso NON venga aggiunto se c'è già."""
        ticker = "AAPL.US"
        borsa_default = ".MI"
        result = applica_suffisso_borsa(ticker, borsa_default)
        self.assertEqual(result, "AAPL.US")

    def test_suffix_not_added_no_default(self):
        """Test che il suffisso NON venga aggiunto se non c'è borsa di default."""
        ticker = "AAPL"
        borsa_default = ""
        result = applica_suffisso_borsa(ticker, borsa_default)
        self.assertEqual(result, "AAPL")

    def test_suffix_not_added_none_default(self):
        """Test che il suffisso NON venga aggiunto se il default è None."""
        ticker = "AAPL"
        borsa_default = None
        result = applica_suffisso_borsa(ticker, borsa_default)
        self.assertEqual(result, "AAPL")

if __name__ == '__main__':
    unittest.main()
