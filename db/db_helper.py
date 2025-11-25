"""
Database Helper - Wrapper per transizione da SQLite a PostgreSQL
Questo modulo fornisce funzioni helper per facilitare la migrazione graduale.
"""

import psycopg2
from psycopg2 import extras
import psycopg2.errors
from contextlib import contextmanager
from db.supabase_manager import SupabaseManager

# Mapping errori SQLite -> PostgreSQL
IntegrityError = psycopg2.errors.IntegrityConstraintViolation

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
    Equivalente a sqlite3.Row per PostgreSQL.
    
    Args:
        conn: Connessione PostgreSQL
        
    Returns:
        cursor: Cursor con dict factory
    """
    return conn.cursor(cursor_factory=extras.RealDictCursor)


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
