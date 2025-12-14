"""
Database Helper - Wrapper per transizione da SQLite a PostgreSQL (pg8000)
Questo modulo fornisce funzioni helper per facilitare la migrazione.
"""

import pg8000.dbapi
from contextlib import contextmanager
from db.supabase_manager import SupabaseManager

# Mapping errori per compatibilità: pg8000 solleva semplicemente DatabaseError o IntegrityError
IntegrityError = pg8000.dbapi.IntegrityError
DatabaseError = pg8000.dbapi.DatabaseError

# Factory per cursori che restituiscono dizionari (emula RealDictCursor)
def dict_row_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@contextmanager
def get_db_connection(id_utente=None):
    """
    Context manager per ottenere una connessione al database.
    Gestisce automaticamente commit/rollback e rilascio connessione.
    
    Args:
        id_utente: ID utente per Row Level Security (opzionale)
        
    Yields:
        connection: Connessione al database PostgreSQL
        
    Example:
        with get_db_connection(id_utente=1) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM Conti WHERE id_utente = %s", (id_utente,))
                conti = cur.fetchall()
    """
    conn = None
    try:
        conn = SupabaseManager.get_connection(id_utente)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            SupabaseManager.release_connection(conn)


def convert_placeholders(query):
    """
    Converte i placeholder da SQLite (?) a PostgreSQL (%s).
    
    Args:
        query: Query SQL con placeholder SQLite
        
    Returns:
        str: Query con placeholder PostgreSQL
    """
    return query.replace('?', '%s')


def get_lastrowid(cursor):
    """
    Ottiene l'ID dell'ultima riga inserita.
    In PostgreSQL si usa RETURNING id invece di lastrowid.
    
    Args:
        cursor: Cursor PostgreSQL
        
    Returns:
        int: ID dell'ultima riga inserita
    """
    # In PostgreSQL, dopo un INSERT con RETURNING, il valore è già nel cursor
    result = cursor.fetchone()
    if result:
        # Se è un dizionario (RealDictCursor)
        if isinstance(result, dict):
            # Cerca la prima chiave che contiene 'id'
            for key in result.keys():
                if 'id_' in key or key == 'id':
                    return result[key]
        # Se è una tupla
        else:
            return result[0]
    return None


def execute_with_returning(cursor, query, params=None, returning_col=None):
    """
    Esegue una query INSERT/UPDATE con RETURNING per ottenere l'ID.
    
    Args:
        cursor: Cursor PostgreSQL
        query: Query SQL (senza RETURNING)
        params: Parametri della query
        returning_col: Nome della colonna da restituire (es. 'id_conto')
        
    Returns:
        int: Valore della colonna RETURNING
    """
    # Converti placeholder
    query = convert_placeholders(query)
    
    # Aggiungi RETURNING se non presente
    if returning_col and 'RETURNING' not in query.upper():
        query += f" RETURNING {returning_col}"
    
    cursor.execute(query, params or ())
    
    if returning_col:
        return get_lastrowid(cursor)
    return None


def dict_factory_cursor(conn):
    """
    Crea un cursor che restituisce dizionari invece di tuple.
    In pg8000 (dbapi) impostiamo row_factory.
    
    Args:
        conn: Connessione PostgreSQL (pg8000)
        
    Returns:
        cursor: Cursor configurato
    """
    # In pg8000 dbapi possiamo impostare row_factory sul cursore
    # NOTA: pg8000 implementation specifica può variare, controlliamo la doc o proviamo.
    # pg8000 standard non ha cursor_factory nel metodo cursor().
    # Ma ha una property row_factory sulla connessione o cursore in versioni recenti.
    # Se fallisce, useremo un wrapper al momento del fetch.
    
    cursor = conn.cursor()
    # pg8000 non supporta nativamente row_factory come sqlite3 in tutte le versioni
    # Ma il nostro codice client si aspetta che fetchall() ritorni dict.
    # Quindi avvolgiamo il cursore o usiamo una logica diversa.
    # PROVIAMO: Usare la nostra funzione custom quando serve.
    # ATTENZIONE: pg8000 non ha row_factory. Dobbiamo farlo manualmente.
    
    # Monkey patch del cursore per autoconvertire? Troppo rischioso.
    # Restituiamo un nostro wrapper
    return DictCursorWrapper(cursor)

class DictCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
        
    def execute(self, query, params=None):
        return self.cursor.execute(query, params)
        
    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None: return None
        return dict_row_factory(self.cursor, row)
        
    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict_row_factory(self.cursor, row) for row in rows]
        
    def __getattr__(self, name):
        return getattr(self.cursor, name)


# Funzioni di compatibilità per codice esistente
def enable_foreign_keys(cursor):
    """
    Abilita i foreign keys.
    In PostgreSQL sono sempre abilitati, questa è una no-op per compatibilità.
    """
    pass  # PostgreSQL ha sempre foreign keys abilitati


def get_row_factory(conn):
    """
    Imposta row_factory per compatibilità con SQLite.
    In PostgreSQL usiamo RealDictCursor.
    """
    # Questa funzione non è necessaria in PostgreSQL
    # perché usiamo già RealDictCursor nel connection pool
    pass
