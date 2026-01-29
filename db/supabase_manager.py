"""
Supabase Manager - Gestione connessioni PostgreSQL con pg8000
"""

import pg8000.dbapi
import os
from dotenv import load_dotenv
import threading
import queue
from urllib.parse import urlparse
from utils.logger import setup_logger

logger = setup_logger("SupabaseManager")

# --- ADAPTERS PER COMPATIBILITÀ ---

class DictCursor:
    """Wrapper per cursore che restituisce dizionari (emula RealDictCursor)."""
    def __init__(self, cursor):
        self._cursor = cursor
    
    def _row_to_dict(self, row):
        if row is None: return None
        if self._cursor.description is None: return row
        return {col[0]: row[idx] for idx, col in enumerate(self._cursor.description)}
    
    def execute(self, query, params=None):
        try:
            return self._cursor.execute(query, params) if params else self._cursor.execute(query)
        except Exception as e:
            # logger.error(f"SQL Error: {query} params: {params} - {e}")
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
    """Wrapper per connessione pg8000 che restituisce DictCursor."""
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self):
        return DictCursor(self._conn.cursor())
    
    def commit(self): return self._conn.commit()
    def rollback(self): return self._conn.rollback()
    def close(self): return self._conn.close()
    def __getattr__(self, name): return getattr(self._conn, name)


# --- MANAGER PRINCIPALE ---

class SupabaseManager:
    """
    Gestisce un pool di connessioni pg8000 per PostgreSQL.
    Thread-safe, gestisce RLS e riconnessioni.
    """
    _pool = None
    _pool_lock = threading.Lock()
    _conn_params = None
    MAX_POOL_SIZE = 15  # Limitato per evitare 'max clients reached'
    
    @classmethod
    def _init_pool(cls):
        load_dotenv()
        db_url = os.getenv('SUPABASE_DB_URL')
        if not db_url:
            raise ValueError("SUPABASE_DB_URL non trovato in .env")

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
            cls._pool = queue.Queue(maxsize=cls.MAX_POOL_SIZE)
            logger.info(f"Pool Supabase inizializzato (Max: {cls.MAX_POOL_SIZE})")
        except Exception as e:
            logger.error(f"Errore inizializzazione pool: {e}")
            raise

    @classmethod
    def _create_connection(cls):
        return pg8000.dbapi.connect(**cls._conn_params)

    @classmethod
    def get_connection(cls, id_utente=None):
        with cls._pool_lock:
            if cls._conn_params is None:
                cls._init_pool()

        conn = None
        try:
            # 1. Prova a prendere dal pool (non bloccante per performance)
            conn = cls._pool.get(block=False)
            
            # 2. Verifica se la connessione è viva
            try:
                # Ping leggero
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
            except:
                # Se morta, chiudi e ignora
                try: conn.close()
                except: pass
                conn = None
        except queue.Empty:
            # Pool vuoto
            pass

        # 3. Se non abbiamo una connessione valida, creane una nuova
        if conn is None:
            try:
                conn = cls._create_connection()
            except Exception as e:
                # Se errore di connessione (es. troppi client), riprova ad aspettare dal pool
                # Questo gestisce il caso di picchi di traffico
                logger.warning(f"Impossibile creare nuova connessione ({e}), attendo pool liberi...")
                try:
                    conn = cls._pool.get(block=True, timeout=20) # Attesa lunga
                    # Verifica di nuovo la conn recuperata
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT 1")
                        cur.close()
                    except:
                        try: conn.close()
                        except: pass
                        conn = cls._create_connection() # Riprova forte se la conn attesa era morta ed era l'unica chance
                except queue.Empty:
                    logger.error("Pool esausto e impossibile connettersi.")
                    raise Exception("Database connection pool exhausted")

        # 4. Imposta RLS Context
        try:
            if id_utente is not None:
                cur = conn.cursor()
                cur.execute("SET app.current_user_id = %s", (id_utente,))
                cur.close()
            else:
                # Reset per chiamate di sistema che non richiedono user context
                # Nota: importante resettare se la conn è riciclata
                cur = conn.cursor()
                cur.execute("RESET app.current_user_id")
                cur.close()
        except Exception as e:
            logger.error(f"Errore RLS context: {e}")
            # Se fallisce RLS, meglio non usare questa conn per sicurezza
            try: conn.close()
            except: pass
            raise

        # 5. Ritorna wrapper (per DictCursor)
        return DictConnection(conn)

    @classmethod
    def release_connection(cls, conn):
        if conn:
            # Unwrappa se necessario
            raw_conn = conn._conn if isinstance(conn, DictConnection) else conn
            
            try:
                # Rollback di sicurezza per transazioni aperte
                raw_conn.rollback()
                
                # Reset RLS per pulizia
                cur = raw_conn.cursor()
                cur.execute("RESET app.current_user_id")
                cur.close()
                raw_conn.commit()
                
                # Rimetti nel pool
                cls._pool.put(raw_conn, block=False)
            except queue.Full:
                # Se pool pieno (o ridimensionato), chiudi
                try: raw_conn.close()
                except: pass
            except Exception as e:
                # Se errore nel reset/rollback, connessione compromessa, chiudi
                try: raw_conn.close()
                except: pass

    @classmethod
    def close_all_connections(cls):
        if cls._pool:
            while not cls._pool.empty():
                try:
                    conn = cls._pool.get(block=False)
                    conn.close()
                except: pass
            logger.info("Tutte le connessioni DB chiuse.")

    @classmethod
    def test_connection(cls):
        try:
            conn = cls.get_connection()
            cls.release_connection(conn)
            return True
        except:
            return False


# Context manager per gestione automatica
class SupabaseConnection:
    def __init__(self, id_utente=None):
        self.id_utente = id_utente
        self.conn = None
    
    def __enter__(self):
        self.conn = SupabaseManager.get_connection(self.id_utente)
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            SupabaseManager.release_connection(self.conn)
        # Non sopprime eccezioni
        return False


def get_db_connection(id_utente=None):
    return SupabaseConnection(id_utente)

class DictCursor:
    """
    Wrapper per cursore pg8000 che restituisce dizionari invece di tuple.
    Emula il comportamento di psycopg2.extras.RealDictCursor.
    """
    def __init__(self, cursor):
        self._cursor = cursor
    
    def _row_to_dict(self, row):
        if row is None:
            return None
        if self._cursor.description is None:
            return row
        return {col[0]: row[idx] for idx, col in enumerate(self._cursor.description)}
    
    def execute(self, query, params=None):
        if params is None:
            return self._cursor.execute(query)
        return self._cursor.execute(query, params)
    
    def fetchone(self):
        row = self._cursor.fetchone()
        return self._row_to_dict(row)
    
    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._row_to_dict(row) for row in rows]
    
    def fetchmany(self, size=None):
        rows = self._cursor.fetchmany(size)
        return [self._row_to_dict(row) for row in rows]
    
    def close(self):
        return self._cursor.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    def __getattr__(self, name):
        return getattr(self._cursor, name)


class DictConnection:
    """
    Wrapper per connessione pg8000 che restituisce DictCursor.
    """
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self):
        return DictCursor(self._conn.cursor())
    
    def commit(self):
        return self._conn.commit()
    
    def rollback(self):
        return self._conn.rollback()
    
    def close(self):
        return self._conn.close()
    
    def __getattr__(self, name):
        return getattr(self._conn, name)

class CustomConnectionPool:
    """
    Un pool di connessioni thread-safe semplice per pg8000.
    pg8000 non ha un pool nativo come psycopg2.
    """
    def __init__(self, minconn, maxconn, user, password, host, port, database):
        self.minconn = minconn
        self.maxconn = maxconn
        self.connection_params = {
            'user': user,
            'password': password,
            'host': host,
            'port': port,
            'database': database,
            'ssl_context': True  # Supabase richiede SSL
        }
        self.pool = queue.Queue(maxsize=maxconn)
        self.current_connections = 0
        self._lock = threading.Lock()
        
        # Pre-fill pool con minconn
        for _ in range(minconn):
            self._create_new_connection()

    def _create_new_connection(self):
        with self._lock:
            if self.current_connections < self.maxconn:
                try:
                    conn = pg8000.native.Connection(**self.connection_params)
                    self.pool.put(conn)
                    self.current_connections += 1
                    return conn
                except Exception as e:
                    logger.error(f"Impossibile creare nuova connessione: {e}")
                    raise
            else:
                return None

    def getconn(self):
        try:
            # Prova a prendere una connessione dal pool (non bloccante)
            conn = self.pool.get(block=False)
            
            # Verifica se la connessione è viva (semplice ping)
            try:
                # pg8000 non ha un metodo ping esplicito semplice, ma possiamo verificare lo stato
                # o eseguire una query leggera. Per ora assumiamo sia viva.
                return conn
            except Exception:
                # Se è morta, crea una nuova (gestito dalla logica di chiusura)
                self.current_connections -= 1
                return self._create_new_connection() or self.pool.get()
                
        except queue.Empty:
            # Se pool vuoto, prova a crearne una nuova
            new_conn = self._create_new_connection()
            if new_conn:
                return new_conn
            
            # Se raggiunto limite max, aspetta che se ne liberi una
            logger.warning("Pool esausto, attesa connessione...")
            return self.pool.get(block=True, timeout=10) # Timeout 10s

    def putconn(self, conn):
        if conn:
            try:
                # Rollback di sicurezza
                conn.run("ROLLBACK")
            except:
                pass
            
            # Rimetti nel pool
            try:
                self.pool.put(conn, block=False)
            except queue.Full:
                # Se pool pieno (magari ridimensionato), chiudi
                conn.close()
                with self._lock:
                    self.current_connections -= 1

    def closeall(self):
        with self._lock:
            while not self.pool.empty():
                try:
                    conn = self.pool.get(block=False)
                    conn.close()
                except:
                    pass
            self.current_connections = 0

# --- MANAGER PRINCIPALE ---

class SupabaseManager:
    """
    Gestisce il connection pool per Supabase PostgreSQL e il contesto utente per RLS.
    Implementazione pg8000.
    """
    _connection_pool = None
    _current_user_id = None
    _lock = threading.Lock()
    
    @classmethod
    def initialize_pool(cls):
        """
        Inizializza il connection pool per PostgreSQL (pg8000).
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
            # Parsing URL connessione (postgresql://user:pass@host:port/dbname)
            result = urlparse(db_url)
            username = result.username
            password = result.password
            database = result.path[1:]
            hostname = result.hostname
            port = result.port or 5432

            with cls._lock:
                if cls._connection_pool is None:
                    cls._connection_pool = CustomConnectionPool(
                        minconn=1,
                        maxconn=20,
                        user=username,
                        password=password,
                        host=hostname,
                        port=port,
                        database=database
                    )
                    logger.info("Connection pool Supabase (pg8000) inizializzato con successo")
        except Exception as e:
            logger.error(f"Errore durante l'inizializzazione del connection pool: {e}")
            raise
    
    @classmethod
    def get_connection(cls, id_utente=None):
        """
        Ottiene una connessione dal pool e imposta il contesto utente per RLS.
        """
        if cls._connection_pool is None:
            cls.initialize_pool()
        
        try:
            conn = cls._connection_pool.getconn()
            
            # Impostazione Context Manager Wrapper per compatibilità con il codice esistente
            # Il codice usa `with conn.cursor() as cur:` e `conn.commit()`
            # pg8000 nativo ha `conn.run()` ma non cursor complessi.
            # Dobbiamo wrapparla in un adapter o usare la compatibilità DBAPI di pg8000.
            # Nota: pg8000.native e pg8000 (dbapi) sono diversi.
            # Qui stiamo usando pg8000.native nel pool, ma per compatibilità massima 
            # col codice esistente (che si aspetta dbapi 2.0 cursor), dovremmo probabilmente usare pg8000 standard.
            
            # FIX: Passiamo a pg8000 standard (dbapi) nel pool o wrappiamo.
            # Per semplicità ora, wrappiamo il context user
            
            if id_utente is not None:
                cls.set_user_context(conn, id_utente)
            else:
                # Reset
                try:
                    conn.run("RESET app.current_user_id")
                    conn.run("COMMIT") # pg8000 native richiede commit esplicito se non autocommit
                except:
                   pass # Potrebbe non essere stato settato
            
            # Per compatibilità DBAPI (cursor, execute, fetchall), dobbiamo assicurarci
            # che chi chiama riceva un oggetto compatibile.
            # Convertiamo la Native Connection in qualcosa di usabile?
            # NO: pg8000.native è molto diverso. Meglio usare pg8000 (dbapi) per meno refactoring.
            # Riscrivo il pool per usare `import pg8000` (non native).
            
            return conn
        except Exception as e:
            print(f"[ERRORE] Errore durante l'ottenimento della connessione: {e}")
            raise
    
    @classmethod
    def set_user_context(cls, conn, id_utente):
        """
        Imposta l'ID utente per RLS.
        """
        try:
            cls._current_user_id = id_utente
            conn.run("SET app.current_user_id = :id_utente", id_utente=id_utente)
        except Exception as e:
            print(f"[ERRORE] Errore durante l'impostazione del contesto utente: {e}")
            raise
    
    @classmethod
    def release_connection(cls, conn):
        """
        Rilascia una connessione al pool.
        """
        if cls._connection_pool and conn:
            try:
                conn.run("RESET app.current_user_id")
                conn.run("COMMIT") 
            except:
                pass
            finally:
                cls._connection_pool.putconn(conn)
    
    @classmethod
    def close_all_connections(cls):
        if cls._connection_pool:
            with cls._lock:
                cls._connection_pool.closeall()
                cls._connection_pool = None
                cls._current_user_id = None
                logger.info("Connection pool chiuso")

    @classmethod
    def test_connection(cls):
        try:
            conn = cls.get_connection()
            conn.run("SELECT 1")
            cls.release_connection(conn)
            logger.info("Test connessione Supabase riuscito")
            return True
        except Exception as e:
            logger.error(f"Test connessione Supabase fallito: {e}")
            return False

# --- RE-IMPLEMENTAZIONE COMPLETA CON PG8000 DBAPI (NON NATIVE) ---
# Sovrascrivo quanto sopra perché ho realizzato che il codice esistente usa CURSORI
# e pg8000.native non ha cursori. Per minimizzare il refactoring, usiamo pg8000 standard.

import pg8000.dbapi

class SupabaseManager:
    _connection_pool = None
    _current_user_id = None
    _lock = threading.Lock()

    @classmethod
    def initialize_pool(cls):
        load_dotenv()
        db_url = os.getenv('SUPABASE_DB_URL')
        if not db_url: raise ValueError("SUPABASE_DB_URL mancante")

        result = urlparse(db_url)
        port = result.port or 5432
        
        # Pool rudimentale (una lista protetta da lock)
        # In produzione reale useremmo qualcosa di più robusto, ma per desktop/single user questo va bene.
        cls._pool_queue = queue.Queue(maxsize=20)
        cls._conn_params = {
            'user': result.username,
            'password': result.password,
            'host': result.hostname,
            'port': port,
            'database': result.path[1:],
            'ssl_context': True
        }
        
    @classmethod
    def _create_conn(cls):
        conn = pg8000.dbapi.connect(**cls._conn_params)
        return conn

    @classmethod
    def get_connection(cls, id_utente=None):
        if cls._connection_pool is None and not hasattr(cls, '_pool_queue'):
            cls.initialize_pool()

        try:
            raw_conn = cls._pool_queue.get(block=False)
        except queue.Empty:
            try:
                raw_conn = cls._create_conn()
            except Exception as e:
                logger.error(f"Pool vuoto e impossibile creare conn: {e}")
                raw_conn = cls._pool_queue.get(timeout=10)

        # Ping check usando cursor (pg8000.dbapi non ha execute diretto)
        try:
            cur = raw_conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except:
            try:
                raw_conn.close()
            except: pass
            raw_conn = cls._create_conn()

        # RLS Context
        if id_utente is not None:
            cursor = raw_conn.cursor()
            cursor.execute("SET app.current_user_id = %s", (id_utente,))
            cursor.close()
        
        # Restituisce DictConnection per compatibilità con RealDictCursor
        return DictConnection(raw_conn)

    @classmethod
    def release_connection(cls, conn):
        if conn:
            # Estrai la connessione raw se è wrappata
            raw_conn = conn._conn if isinstance(conn, DictConnection) else conn
            try:
                # NON fare rollback qui - il commit è già stato fatto dal chiamante
                # Resettiamo solo il contesto RLS
                cursor = raw_conn.cursor()
                cursor.execute("RESET app.current_user_id")
                cursor.close()
                raw_conn.commit()  # Commit del RESET
                cls._pool_queue.put(raw_conn, block=False)
            except:
                try: raw_conn.close()
                except: pass

    @classmethod
    def close_all_connections(cls):
        while hasattr(cls, '_pool_queue') and not cls._pool_queue.empty():
            try:
                conn = cls._pool_queue.get(block=False)
                conn.close()
            except: pass

    @classmethod
    def test_connection(cls):
        try:
            conn = cls.get_connection()
            cls.release_connection(conn)
            return True
        except Exception as e:
            logger.error(f"Test connessione fallback fallito: {e}")
            return False

    @classmethod
    def get_current_user_id(cls):
        """Restituisce l'ID dell'utente corrente."""
        return cls._current_user_id


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
