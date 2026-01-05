
import unittest
import queue
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.supabase_manager import SupabaseManager, CustomConnectionPool

class TestSupabaseManager(unittest.TestCase):
    def setUp(self):
        # Reset singleton state
        SupabaseManager._connection_pool = None
        SupabaseManager._current_user_id = None
        
        # Mock env vars
        self.env_patcher = patch.dict(os.environ, {"SUPABASE_DB_URL": "postgresql://user:pass@host:5432/db"})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch('pg8000.dbapi.connect')
    def test_initialize_pool(self, mock_connect):
        SupabaseManager.initialize_pool()
        self.assertIsNotNone(SupabaseManager._pool_queue)
        
    @patch('pg8000.dbapi.connect')
    def test_get_connection_creates_new_if_empty(self, mock_connect):
        # Initializing pool
        SupabaseManager.initialize_pool()
        
        # Mock connection
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # Get connection
        conn = SupabaseManager.get_connection()
        
        self.assertTrue(mock_connect.called)
        self.assertIsNotNone(conn)
        
    @patch('pg8000.dbapi.connect')
    def test_release_connection(self, mock_connect):
        SupabaseManager.initialize_pool()
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        conn = SupabaseManager.get_connection()
        SupabaseManager.release_connection(conn)
        
        # Should be back in the pool
        self.assertFalse(SupabaseManager._pool_queue.empty())

    @patch('pg8000.dbapi.connect')
    def test_context_manager(self, mock_connect):
        from db.supabase_manager import get_db_connection
        SupabaseManager.initialize_pool()
        
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        with get_db_connection() as conn:
            self.assertIsNotNone(conn)
        
        # Should be released
        self.assertFalse(SupabaseManager._pool_queue.empty())

if __name__ == '__main__':
    unittest.main()
