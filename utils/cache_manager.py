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
        
        self._cache: Dict[str, Any] = {}
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
                self._cache = json.load(f)
            logger.info(f"Cache caricata da disco: {len(self._cache)} entries")
        except Exception as e:
            logger.warning(f"Impossibile caricare cache da disco: {e}")
            self._cache = {}
    
    def _save_to_disk(self) -> None:
        """Salva la cache su file persistente."""
        try:
            if not os.path.exists(APP_DATA_DIR):
                os.makedirs(APP_DATA_DIR)
            
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2, default=str)
            logger.debug("Cache salvata su disco")
        except Exception as e:
            logger.warning(f"Impossibile salvare cache su disco: {e}")
    
    def get_stale(self, key: str, id_famiglia: Optional[str] = None) -> Optional[Any]:
        """
        Ritorna dati dalla cache (anche vecchi) per avvio rapido.
        
        Args:
            key: Tipo di dato (es. "categories", "accounts")
            id_famiglia: ID della famiglia
        
        Returns:
            Dati cachati o None se non presenti
        """
        cache_key = self._get_cache_key(key, id_famiglia)
        entry = self._cache.get(cache_key)
        
        if entry is not None:
            logger.debug(f"Cache HIT (stale): {cache_key}")
            return entry.get("data")
        
        logger.debug(f"Cache MISS: {cache_key}")
        return None
    
    def set(self, key: str, data: Any, id_famiglia: Optional[str] = None) -> None:
        """
        Salva dati nella cache.
        
        Args:
            key: Tipo di dato
            data: Dati da salvare
            id_famiglia: ID della famiglia
        """
        cache_key = self._get_cache_key(key, id_famiglia)
        
        self._cache[cache_key] = {
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.debug(f"Cache SET: {cache_key}")
        self._save_to_disk()
    
    def invalidate(self, key: str, id_famiglia: Optional[str] = None) -> None:
        """
        Invalida la cache per una specifica chiave.
        Chiamare dopo operazioni di scrittura (aggiungi, modifica, elimina).
        
        Args:
            key: Tipo di dato da invalidare
            id_famiglia: ID della famiglia
        """
        cache_key = self._get_cache_key(key, id_famiglia)
        
        if cache_key in self._cache:
            del self._cache[cache_key]
            logger.info(f"Cache INVALIDATED: {cache_key}")
            self._save_to_disk()
    
    def invalidate_all(self, id_famiglia: Optional[str] = None) -> None:
        """
        Invalida tutta la cache per una famiglia specifica.
        
        Args:
            id_famiglia: ID della famiglia (se None, invalida tutto)
        """
        if id_famiglia is None:
            self._cache.clear()
            logger.info("Cache CLEARED: tutte le entries")
        else:
            prefix = f"family_{id_famiglia}:"
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._cache[k]
            logger.info(f"Cache INVALIDATED: {len(keys_to_delete)} entries per famiglia {id_famiglia}")
        
        self._save_to_disk()
    
    def clear(self) -> None:
        """Pulisce completamente la cache (sia memoria che disco)."""
        self._cache.clear()
        self._save_to_disk()
        logger.info("Cache completamente svuotata")
    
    def get_stats(self) -> Dict[str, Any]:
        """Ritorna statistiche sulla cache."""
        return {
            "entries": len(self._cache),
            "keys": list(self._cache.keys()),
            "cache_file": CACHE_FILE
        }


# Istanza singleton globale
cache_manager = CacheManager()
