"""
Cache Manager per Budget Amico
Pattern: Stale-While-Revalidate

All'avvio mostra dati dalla cache (sessione precedente),
poi aggiorna quando l'utente accede alle varie tabs.
"""
import json
import os
import threading
from typing import Any, Dict, Optional, Callable
from datetime import datetime

from utils.logger import setup_logger

logger = setup_logger("CacheManager")

# Percorso del file di cache persistente
APP_DATA_DIR = os.path.join(os.getenv('APPDATA', '.'), 'BudgetAmico')
CACHE_FILE = os.path.join(APP_DATA_DIR, 'cache.json')


class CacheManager:
    """
    Gestisce la cache locale per avvio rapido dell'applicazione.
    
    Pattern: Stale-While-Revalidate
    - get_stale(): ritorna dati dalla cache (anche vecchi) per UI immediata
    - refresh(): aggiorna dal DB e salva in cache
    - invalidate(): invalida la cache dopo operazioni di scrittura
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern per garantire una sola istanza."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._disk_cache: Dict[str, Any] = {}
        self._memory_cache: Dict[str, Dict[str, Any]] = {} # Livello in-memory con TTL
        self._load_from_disk()
        self._initialized = True
        logger.info(f"CacheManager inizializzato. Cache file: {CACHE_FILE}")
    
    def _get_cache_key(self, key: str, id_famiglia: Optional[str] = None) -> str:
        """Genera una chiave cache univoca per famiglia."""
        if id_famiglia:
            return f"family_{id_famiglia}:{key}"
        return key
    
    def _load_from_disk(self) -> None:
        """Carica la cache dal file persistente."""
        if not os.path.exists(CACHE_FILE):
            logger.debug("Nessun file cache esistente")
            return
        
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                self._disk_cache = json.load(f)
            logger.info(f"Cache caricata da disco: {len(self._disk_cache)} entries")
        except Exception as e:
            logger.warning(f"Impossibile caricare cache da disco: {e}")
            self._disk_cache = {}
    
    def _save_to_disk(self) -> None:
        """Salva la cache su file persistente."""
        try:
            if not os.path.exists(APP_DATA_DIR):
                os.makedirs(APP_DATA_DIR)
            
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._disk_cache, f, ensure_ascii=False, indent=2, default=str)
            logger.debug("Cache salvata su disco")
        except Exception as e:
            logger.warning(f"Impossibile salvare cache su disco: {e}")

    def get_or_compute(self, key: str, compute_fn: Callable, id_famiglia: Optional[str] = None, ttl_seconds: int = 600) -> Any:
        """
        Ottiene i dati dalla memoria (se validi) o li calcola tramite compute_fn.
        Ideale per dati decriptati pesanti.
        """
        cache_key = self._get_cache_key(key, id_famiglia)
        now = datetime.now().timestamp()
        
        with self._lock:
            entry = self._memory_cache.get(cache_key)
            if entry and (now - entry['timestamp'] < ttl_seconds):
                logger.debug(f"Memory Cache HIT: {cache_key}")
                return entry['data']
        
        # MISS o Scaduta -> Esegue computazione (fuori dal lock per evitare deadlock)
        logger.debug(f"Memory Cache MISS/EXPIRED: {cache_key}. Computing...")
        data = compute_fn()
        
        with self._lock:
            self._memory_cache[cache_key] = {
                "data": data,
                "timestamp": datetime.now().timestamp()
            }
        return data
    
    def get_stale(self, key: str, id_famiglia: Optional[str] = None) -> Optional[Any]:
        """Ritorna dati dalla cache su disco (stale)."""
        cache_key = self._get_cache_key(key, id_famiglia)
        entry = self._disk_cache.get(cache_key)
        
        if entry is not None:
            return entry.get("data")
        return None
    
    def set(self, key: str, data: Any, id_famiglia: Optional[str] = None, persist: bool = True) -> None:
        """
        Salva dati nella cache.
        
        Args:
            key: Tipo di dato
            data: Dati da salvare
            id_famiglia: ID della famiglia
            persist: Se True, salva anche su disco (JSON serializable richiesto)
        """
        cache_key = self._get_cache_key(key, id_famiglia)
        now_ts = datetime.now().timestamp()
        
        with self._lock:
            # Memory update
            self._memory_cache[cache_key] = {
                "data": data,
                "timestamp": now_ts
            }
            
            # Disk update (opzionale)
            if persist:
                try:
                    self._disk_cache[cache_key] = {
                        "data": data,
                        "timestamp": datetime.now().isoformat()
                    }
                    self._save_to_disk()
                except Exception as e:
                    logger.warning(f"Errore persistenza cache {cache_key}: {e}")
    
    def invalidate(self, key: str, id_famiglia: Optional[str] = None) -> None:
        """Invalida la cache per una specifica chiave."""
        cache_key = self._get_cache_key(key, id_famiglia)
        
        with self._lock:
            changed = False
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                changed = True
            if cache_key in self._disk_cache:
                del self._disk_cache[cache_key]
                changed = True
            
            if changed:
                logger.info(f"Cache INVALIDATED: {cache_key}")
                self._save_to_disk()
    
    def invalidate_all(self, id_famiglia: Optional[str] = None) -> None:
        """Invalida tutta la cache per una famiglia specifica."""
        with self._lock:
            if id_famiglia is None:
                self._memory_cache.clear()
                self._disk_cache.clear()
                logger.info("Cache CLEARED: tutte le entries")
            else:
                prefix = f"family_{id_famiglia}:"
                # Memory
                keys_mem = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
                for k in keys_mem: del self._memory_cache[k]
                # Disk
                keys_disk = [k for k in self._disk_cache.keys() if k.startswith(prefix)]
                for k in keys_disk: del self._disk_cache[k]
                
                logger.info(f"Cache INVALIDATED: {len(keys_mem)} mem, {len(keys_disk)} disk entries per famiglia {id_famiglia}")
        
        self._save_to_disk()
    
    def clear(self) -> None:
        """Pulisce completamente la cache (sia memoria che disco)."""
        with self._lock:
            self._memory_cache.clear()
            self._disk_cache.clear()
        self._save_to_disk()
        logger.info("Cache completamente svuotata")
    
    def get_stats(self) -> Dict[str, Any]:
        """Ritorna statistiche sulla cache."""
        with self._lock:
            return {
                "memory_entries": len(self._memory_cache),
                "disk_entries": len(self._disk_cache),
                "cache_file": CACHE_FILE
            }


# Istanza singleton globale
cache_manager = CacheManager()
