"""
Supabase Manager - Gestione connessioni PostgreSQL con Row Level Security
"""

import psycopg2
from psycopg2 import pool, extras
import os
from dotenv import load_dotenv
import threading

class SupabaseManager:
    """
    Gestisce il connection pool per Supabase PostgreSQL e il contesto utente per RLS.
    """
    _connection_pool = None
    _current_user_id = None
    _lock = threading.Lock()
    
    @classmethod
    def initialize_pool(cls):
        """
        Inizializza il connection pool per PostgreSQL.
        Legge la configurazione da variabili d'ambiente.
        """
        load_dotenv()
        db_url = os.getenv('SUPABASE_DB_URL')
        
        if not db_url:
            raise ValueError(
                "SUPABASE_DB_URL non trovato nelle variabili d'ambiente. "
                "Assicurati di aver configurato il file .env"
            )
        
        try:
            with cls._lock:
                if cls._connection_pool is None:
                    cls._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=1,
                        maxconn=10,
                        dsn=db_url,
                        cursor_factory=extras.RealDictCursor  # Restituisce dizionari invece di tuple
                    )
                    print("[OK] Connection pool Supabase inizializzato con successo")
        except Exception as e:
            print(f"[ERRORE] Errore durante l'inizializzazione del connection pool: {e}")
            raise
    
    @classmethod
    def get_connection(cls, id_utente=None):
        """
        Ottiene una connessione dal pool e imposta il contesto utente per RLS.
        
        Args:
            id_utente: ID dell'utente corrente (opzionale, per RLS)
            
        Returns:
            psycopg2.connection: Connessione al database
        """
        if cls._connection_pool is None:
            cls.initialize_pool()
        
        try:
            conn = cls._connection_pool.getconn()
            
            # Imposta contesto utente per Row Level Security
            user_id_to_set = id_utente if id_utente is not None else cls._current_user_id
            
            if user_id_to_set is not None:
                cls.set_user_context(conn, user_id_to_set)
            else:
                # Assicura che non ci sia un contesto residuo se la connessione è riciclata male
                with conn.cursor() as cur:
                    cur.execute("RESET app.current_user_id")
                    conn.commit()
            
            return conn
        except Exception as e:
            print(f"[ERRORE] Errore durante l'ottenimento della connessione: {e}")
            raise
    
    @classmethod
    def set_user_context(cls, conn, id_utente):
        """
        Imposta l'ID utente corrente nella sessione PostgreSQL per Row Level Security.
        
        Args:
            conn: Connessione al database
            id_utente: ID dell'utente corrente
        """
        try:
            cls._current_user_id = id_utente
            with conn.cursor() as cur:
                # Imposta la variabile di sessione per RLS
                cur.execute("SET app.current_user_id = %s", (id_utente,))
                conn.commit()
        except Exception as e:
            print(f"[ERRORE] Errore durante l'impostazione del contesto utente: {e}")
            conn.rollback()
            raise
    
    @classmethod
    def release_connection(cls, conn):
        """
        Rilascia una connessione al pool.
        
        Args:
            conn: Connessione da rilasciare
        """
        if cls._connection_pool and conn:
            try:
                # Reset del contesto utente prima di rilasciare
                with conn.cursor() as cur:
                    cur.execute("RESET app.current_user_id")
                    conn.commit()
            except:
                pass  # Ignora errori durante il reset
            finally:
                cls._connection_pool.putconn(conn)
    
    @classmethod
    def close_all_connections(cls):
        """
        Chiude tutte le connessioni nel pool.
        Da chiamare quando l'applicazione si chiude.
        """
        if cls._connection_pool:
            with cls._lock:
                cls._connection_pool.closeall()
                cls._connection_pool = None
                cls._current_user_id = None
                print("[OK] Connection pool chiuso")
    
    @classmethod
    def get_current_user_id(cls):
        """
        Restituisce l'ID dell'utente corrente.
        
        Returns:
            int: ID utente corrente o None
        """
        return cls._current_user_id
    
    @classmethod
    def test_connection(cls):
        """
        Testa la connessione al database Supabase.
        
        Returns:
            bool: True se la connessione funziona, False altrimenti
        """
        try:
            conn = cls.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
            cls.release_connection(conn)
            print("[OK] Test connessione Supabase riuscito")
            return True
        except Exception as e:
            print(f"[ERRORE] Test connessione Supabase fallito: {e}")
            return False


# Context manager per gestione automatica delle connessioni
class SupabaseConnection:
    """
    Context manager per gestione automatica delle connessioni Supabase.
    
    Esempio d'uso:
        with SupabaseConnection(id_utente=1) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM Conti")
                conti = cur.fetchall()
    """
    
    def __init__(self, id_utente=None):
        self.id_utente = id_utente
        self.conn = None
    
    def __enter__(self):
        self.conn = SupabaseManager.get_connection(self.id_utente)
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is not None:
                # In caso di errore, rollback
                self.conn.rollback()
            SupabaseManager.release_connection(self.conn)
        return False  # Non sopprime le eccezioni

def get_db_connection(id_utente=None):
    """
    Helper function per ottenere una connessione al database.
    Restituisce un context manager SupabaseConnection.
    """
    return SupabaseConnection(id_utente)
