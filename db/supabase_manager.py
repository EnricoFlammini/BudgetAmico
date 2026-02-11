"""
Supabase Manager - Gestione connessioni PostgreSQL con pg8000
Versione unificata e pulita per BudgetAmico Web.
"""

import pg8000.dbapi
import os
import threading
import queue
from urllib.parse import urlparse
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("SupabaseManager")

class DictCursor:
    """Wrapper per cursore pg8000 che restituisce dizionari (emula RealDictCursor)."""
    def __init__(self, cursor):
        self._cursor = cursor
    
    def _row_to_dict(self, row):
        if row is None: return None
        if self._cursor.description is None: return row
        return {col[0]: row[idx] for idx, col in enumerate(self._cursor.description)}
    
    def execute(self, query, params=None):
        try:
            return self._cursor.execute(query, params) if params else self._cursor.execute(query)
        except Exception:
            raise

    def fetchone(self):
        return self._row_to_dict(self._cursor.fetchone())
    
    def fetchall(self):
        return [self._row_to_dict(row) for row in self._cursor.fetchall()]
    
    def fetchmany(self, size=None):
        return [self._row_to_dict(row) for row in self._cursor.fetchmany(size)]
    
    def close(self):
        return self._cursor.close()
    
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()
    def __getattr__(self, name): return getattr(self._cursor, name)


class DictConnection:
    """Wrapper per connessione pg8000 che supporta DictCursor."""
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self):
        return DictCursor(self._conn.cursor())
    
    def commit(self): return self._conn.commit()
    def rollback(self): return self._conn.rollback()
    def close(self): return self._conn.close()
    def __getattr__(self, name): return getattr(self._conn, name)


class SupabaseManager:
    """
    Gestisce un pool di connessioni pg8000 per PostgreSQL (Supabase).
    Thread-safe, gestisce il contesto RLS.
    """
    _pool_queue = queue.Queue(maxsize=20)
    _conn_params = None
    _initialized = False
    _lock = threading.Lock()
    
    @classmethod
    def _initialize(cls):
        """Inizializza i parametri di connessione leggendo l'ambiente."""
        with cls._lock:
            if cls._initialized:
                return
            
            db_url = os.getenv('SUPABASE_DB_URL')
            if not db_url:
                # Se non c'è la variabile, proviamo a caricare il .env come ultima spiaggia
                try:
                    from dotenv import load_dotenv
                    load_dotenv()
                    db_url = os.getenv('SUPABASE_DB_URL')
                except ImportError:
                    pass
            
            if not db_url:
                logger.error("SUPABASE_DB_URL non trovato nell'ambiente!")
                raise ValueError("Configurazione DATABASE mancante (SUPABASE_DB_URL)")

            try:
                result = urlparse(db_url)
                cls._conn_params = {
                    'user': result.username,
                    'password': result.password,
                    'host': result.hostname,
                    'port': result.port or 5432,
                    'database': result.path[1:],
                    'ssl_context': True
                }
                cls._initialized = True
                logger.info(f"Parametri database inizializzati per host: {result.hostname}")
            except Exception as e:
                logger.error(f"Errore parsing SUPABASE_DB_URL: {e}")
                raise

    @classmethod
    def _create_connection(cls):
        """Crea una nuova connessione raw."""
        if not cls._initialized:
            cls._initialize()
        return pg8000.dbapi.connect(**cls._conn_params)

    @classmethod
    def get_connection(cls, id_utente: Optional[int] = None) -> DictConnection:
        """
        Ottiene una connessione dal pool o ne crea una nuova.
        Imposta il contesto RLS per l'utente se specificato.
        """
        if not cls._initialized:
            cls._initialize()

        conn = None
        # 1. Prova a prendere dal pool
        try:
            conn = cls._pool_queue.get(block=False)
            # Verifica se la connessione è ancora attiva
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
            except:
                try: conn.close()
                except: pass
                conn = None
        except queue.Empty:
            pass

        # 2. Se non nel pool, creane una nuova
        if conn is None:
            try:
                conn = cls._create_connection()
            except Exception as e:
                logger.warning(f"Impossibile creare nuova connessione ({e}), attendo pool liberi...")
                try:
                    conn = cls._pool_queue.get(block=True, timeout=15)
                except queue.Empty:
                    logger.error("Database connection pool exhausted and unable to create new one.")
                    raise Exception("Database non raggiungibile (Pool esausto)")

        # 3. Imposta RLS Context
        try:
            cur = conn.cursor()
            if id_utente is not None:
                cur.execute("SET app.current_user_id = %s", (id_utente,))
            else:
                cur.execute("RESET app.current_user_id")
            cur.close()
        except Exception as e:
            logger.error(f"Errore impostazione RLS: {e}")
            try: conn.close()
            except: pass
            raise

        return DictConnection(conn)

    @classmethod
    def release_connection(cls, conn):
        """Rilascia la connessione rimettendola nel pool."""
        if not conn:
            return
        
        raw_conn = conn._conn if isinstance(conn, DictConnection) else conn
        try:
            # Pulizia contesto RLS prima di rimettere nel pool
            cur = raw_conn.cursor()
            cur.execute("RESET app.current_user_id")
            cur.close()
            raw_conn.commit()
            
            cls._pool_queue.put(raw_conn, block=False)
        except queue.Full:
            try: raw_conn.close()
            except: pass
        except Exception as e:
            logger.warning(f"Errore rilascio connessione (chiusura forzata): {e}")
            try: raw_conn.close()
            except: pass

    @classmethod
    def test_connection(cls) -> bool:
        """Verifica se la connessione al database è funzionante."""
        try:
            conn = cls.get_connection()
            cls.release_connection(conn)
            return True
        except Exception as e:
            logger.error(f"Test connessione fallito: {e}")
            return False

    @classmethod
    def close_all_connections(cls):
        """Chiude tutte le connessioni nel pool."""
        count = 0
        while not cls._pool_queue.empty():
            try:
                conn = cls._pool_queue.get(block=False)
                conn.close()
                count += 1
            except: pass
        logger.info(f"Chiuse {count} connessioni dal pool.")


class SupabaseConnection:
    """Context manager per gestire automaticamente get/release connection."""
    def __init__(self, id_utente=None):
        self.id_utente = id_utente
        self.conn = None
    
    def __enter__(self):
        self.conn = SupabaseManager.get_connection(self.id_utente)
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is not None:
                try: self.conn.rollback()
                except: pass
            SupabaseManager.release_connection(self.conn)
        return False

def get_db_connection(id_utente=None):
    """Factory per SupabaseConnection context manager."""
    return SupabaseConnection(id_utente)
