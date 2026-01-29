"""
DBLogger - Modulo per logging centralizzato su database PostgreSQL.

Questo modulo fornisce un sistema di logging che scrive direttamente
sul database, permettendo la consultazione dei log da interfaccia web.
"""

import threading
import traceback
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from db.supabase_manager import get_db_connection


class DBLogger:
    """
    Logger che scrive direttamente sul database PostgreSQL.
    
    Usage:
        logger = DBLogger("BackgroundService")
        logger.info("Operazione completata")
        logger.error("Errore durante l'esecuzione", {"errore": str(e)})
    """
    
    def __init__(self, componente: str):
        """
        Inizializza il logger per un componente specifico.
        
        Args:
            componente: Nome del componente (es. "BackgroundService", "WebController")
        """
        self.componente = componente
    
    def _log(self, livello: str, messaggio: str, dettagli: Optional[Dict[str, Any]] = None,
             id_utente: Optional[int] = None, id_famiglia: Optional[int] = None):
        """
        Metodo interno per scrivere un log sul database.
        Esegue l'inserimento in un thread separato per non bloccare.
        """
        def _insert_log():
            try:
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    
                    # Converti dettagli in JSON string se presente
                    dettagli_str = json.dumps(dettagli, ensure_ascii=False, default=str) if dettagli else None
                    
                    cur.execute("""
                        INSERT INTO Log_Sistema 
                        (livello, componente, messaggio, dettagli, id_utente, id_famiglia)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (livello, self.componente, messaggio, dettagli_str, id_utente, id_famiglia))
                    
                    conn.commit()
            except Exception as e:
                # Fallback: stampa su console se DB fallisce
                print(f"[DB_LOGGER ERROR] Impossibile scrivere log: {e}")
                print(f"[{livello}] {self.componente}: {messaggio}")
        
        # Esegui in thread separato per non bloccare
        thread = threading.Thread(target=_insert_log, daemon=True)
        thread.start()
    
    def debug(self, messaggio: str, dettagli: Optional[Dict[str, Any]] = None,
              id_utente: Optional[int] = None, id_famiglia: Optional[int] = None):
        """Log di livello DEBUG."""
        self._log("DEBUG", messaggio, dettagli, id_utente, id_famiglia)
    
    def info(self, messaggio: str, dettagli: Optional[Dict[str, Any]] = None,
             id_utente: Optional[int] = None, id_famiglia: Optional[int] = None):
        """Log di livello INFO."""
        self._log("INFO", messaggio, dettagli, id_utente, id_famiglia)
        # Echo su console
        print(f"[INFO] {self.componente}: {messaggio}")
    
    def warning(self, messaggio: str, dettagli: Optional[Dict[str, Any]] = None,
                id_utente: Optional[int] = None, id_famiglia: Optional[int] = None):
        """Log di livello WARNING."""
        self._log("WARNING", messaggio, dettagli, id_utente, id_famiglia)
        print(f"[WARNING] {self.componente}: {messaggio}")
    
    def error(self, messaggio: str, dettagli: Optional[Dict[str, Any]] = None,
              id_utente: Optional[int] = None, id_famiglia: Optional[int] = None,
              include_traceback: bool = False):
        """
        Log di livello ERROR.
        
        Args:
            include_traceback: Se True, include lo stack trace nei dettagli
        """
        if include_traceback:
            if dettagli is None:
                dettagli = {}
            dettagli["traceback"] = traceback.format_exc()
        
        self._log("ERROR", messaggio, dettagli, id_utente, id_famiglia)
        print(f"[ERROR] {self.componente}: {messaggio}")
    
    def critical(self, messaggio: str, dettagli: Optional[Dict[str, Any]] = None,
                 id_utente: Optional[int] = None, id_famiglia: Optional[int] = None,
                 include_traceback: bool = True):
        """
        Log di livello CRITICAL.
        Di default include lo stack trace.
        """
        if include_traceback:
            if dettagli is None:
                dettagli = {}
            dettagli["traceback"] = traceback.format_exc()
        
        self._log("CRITICAL", messaggio, dettagli, id_utente, id_famiglia)
        print(f"[CRITICAL] {self.componente}: {messaggio}")


# --- Funzioni di utilità ---

def cleanup_old_logs(days: int = 30) -> int:
    """
    Rimuove i log più vecchi di un certo numero di giorni.
    
    Args:
        days: Numero di giorni di conservazione (default: 30)
    
    Returns:
        Numero di log eliminati
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            cur.execute("""
                DELETE FROM Log_Sistema 
                WHERE timestamp < %s
                RETURNING id_log
            """, (cutoff_date,))
            
            deleted_count = cur.rowcount
            conn.commit()
            
            if deleted_count > 0:
                print(f"[DB_LOGGER] Eliminati {deleted_count} log più vecchi di {days} giorni")
            
            return deleted_count
    except Exception as e:
        print(f"[DB_LOGGER ERROR] Errore durante pulizia log: {e}")
        return 0


def get_logs(
    livello: Optional[str] = None,
    componente: Optional[str] = None,
    da_data: Optional[datetime] = None,
    a_data: Optional[datetime] = None,
    id_famiglia: Optional[int] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Recupera i log dal database con filtri opzionali.
    
    Args:
        livello: Filtra per livello (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        componente: Filtra per componente
        da_data: Data inizio range
        a_data: Data fine range
        id_famiglia: Filtra per famiglia
        limit: Numero massimo di log da recuperare
        offset: Offset per paginazione
    
    Returns:
        Lista di dizionari con i log
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Costruisci query dinamica
            query = "SELECT * FROM Log_Sistema WHERE 1=1"
            params = []
            
            if livello:
                query += " AND livello = %s"
                params.append(livello)
            
            if componente:
                query += " AND componente = %s"
                params.append(componente)
            
            if da_data:
                query += " AND timestamp >= %s"
                params.append(da_data)
            
            if a_data:
                query += " AND timestamp <= %s"
                params.append(a_data)
            
            if id_famiglia:
                query += " AND id_famiglia = %s"
                params.append(id_famiglia)
            
            query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            # Converti RealDictRow in dict standard
            logs = []
            for row in rows:
                log_entry = dict(row)
                # Parse dettagli JSON se presente
                if log_entry.get("dettagli"):
                    try:
                        log_entry["dettagli"] = json.loads(log_entry["dettagli"])
                    except:
                        pass
                logs.append(log_entry)
            
            return logs
    except Exception as e:
        print(f"[DB_LOGGER ERROR] Errore durante recupero log: {e}")
        return []


def get_log_stats() -> Dict[str, Any]:
    """
    Recupera statistiche sui log.
    
    Returns:
        Dizionario con statistiche (count per livello, ultimo log, etc.)
    """
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            # Count per livello
            cur.execute("""
                SELECT livello, COUNT(*) as count 
                FROM Log_Sistema 
                GROUP BY livello
            """)
            level_counts = {row["livello"]: row["count"] for row in cur.fetchall()}
            
            # Componenti attivi nelle ultime 24h
            cur.execute("""
                SELECT DISTINCT componente 
                FROM Log_Sistema 
                WHERE timestamp > NOW() - INTERVAL '24 hours'
            """)
            active_components = [row["componente"] for row in cur.fetchall()]
            
            # Ultimo log
            cur.execute("""
                SELECT timestamp FROM Log_Sistema 
                ORDER BY timestamp DESC LIMIT 1
            """)
            last_log = cur.fetchone()
            
            return {
                "count_per_livello": level_counts,
                "componenti_attivi_24h": active_components,
                "ultimo_log": last_log["timestamp"] if last_log else None,
                "totale_log": sum(level_counts.values())
            }
    except Exception as e:
        print(f"[DB_LOGGER ERROR] Errore durante recupero statistiche: {e}")
        return {}


def get_distinct_components() -> List[str]:
    """Recupera la lista dei componenti distinti presenti nei log."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT componente FROM Log_Sistema ORDER BY componente")
            return [row["componente"] for row in cur.fetchall()]
    except Exception as e:
        print(f"[DB_LOGGER ERROR] Errore durante recupero componenti: {e}")
        return []
