
import time
import threading
import schedule
import logging
from db.supabase_manager import get_db_connection
from db.gestione_db import (
    check_e_processa_spese_fisse,
    get_server_family_key,
    ottieni_dettagli_conti_utente,
    ottieni_portafoglio,
    aggiorna_prezzo_manuale_asset
)
from utils.yfinance_manager import ottieni_prezzi_multipli

logger = logging.getLogger("BackgroundService")

class BackgroundService:
    def __init__(self):
        self.running = False
        self.scheduler_thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        logger.info("Avvio Background Service...")
        
        # Schedulazione dei task
        # Esegui check spese fisse ogni 6 ore
        schedule.every(6).hours.do(self.run_fixed_expenses_job)
        
        # Esegui aggiornamento asset ogni 12 ore (mercati chiusi/aperti)
        schedule.every(12).hours.do(self.run_asset_updates_job)
        
        # Esegui subito all'avvio (in un thread separato per non bloccare)
        threading.Thread(target=self.run_all_jobs_now).start()

        self.scheduler_thread = threading.Thread(target=self._run_scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()

    def _run_scheduler_loop(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def stop(self):
        self.running = False
        logger.info("Background Service fermato.")

    def run_all_jobs_now(self):
        logger.info("Esecuzione immediata di tutti i job background...")
        self.run_fixed_expenses_job()
        self.run_asset_updates_job()

    def _get_enabled_families(self):
        """Recupera ID famiglie con automazione abilitata."""
        families = []
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                cur.execute("SELECT id_famiglia FROM Famiglie WHERE server_encrypted_key IS NOT NULL AND server_encrypted_key != ''")
                rows = cur.fetchall()
                families = [row['id_famiglia'] for row in rows]
        except Exception as e:
            logger.error(f"Error fetching enabled families: {e}")
        return families

    def run_fixed_expenses_job(self):
        logger.info("Avvio Job: Spese Fisse")
        families = self._get_enabled_families()
        for id_famiglia in families:
            try:
                # 1. Recupera chiave
                fk_b64 = get_server_family_key(id_famiglia)
                if not fk_b64:
                    continue
                
                # 2. Processa
                logger.info(f"Processing family {id_famiglia}...")
                count = check_e_processa_spese_fisse(id_famiglia, forced_family_key_b64=fk_b64)
                if count > 0:
                    logger.info(f"Family {id_famiglia}: {count} spese fisse eseguite.")
            except Exception as e:
                logger.error(f"Error processing expenses for family {id_famiglia}: {e}")
        logger.info("Job Spese Fisse completato.")

    def run_asset_updates_job(self):
        logger.info("Avvio Job: Aggiornamento Asset")
        families = self._get_enabled_families()
        
        # Raccogli tutti gli asset di tutte le famiglie abilitate
        # NOTA: Per aggiornare gli asset, abbiamo bisogno di iterare sui CONTI.
        # Gli asset sono criptati con la chiave famiglia (se in conto inv condiviso?)
        # O con la chiave utente.
        # Se sono criptati con chiave UTENTE, non possiamo aggiornarli (non abbiamo la chiave master utente).
        # Se sono criptati con chiave FAMIGLIA (possibile per conti inv condivisi o se l'utente è un admin che abbiamo "impersonato" con la sua masterkey salvata come family key), ok.
        
        # Nella mia implementazione attuale, ho salvato la MasterKey ADMIN come "server_encrypted_key".
        # Quindi posso decriptare TUTTO ciò che l'admin vede.
        
        # Tuttavia, iterare su tutti i conti di tutti gli utenti di una famiglia è costoso.
        # Semplificazione: Iteriamo sui conti dell'Admin (o dei membri) se riusciamo a decriptarli.
        
        # Approccio:
        # 1. Per ogni famiglia abilitata:
        #    - Recupera la chiave (che è la Master Key dell'Admin).
        #    - Deve trovare CHI è l'admin per usare le funzioni "ottieni_conti_utente". 
        #    - Ma `ottieni_portafoglio` prende id_conto.
        #    - Possiamo fare una query grezza per trovare conti di tipo "Investimento" legati alla famiglia.
        
        for id_famiglia in families:
            try:
                fk_b64 = get_server_family_key(id_famiglia) # Questo è in realtà la Master Key dell'Admin
                if not fk_b64: continue
                
                master_key = fk_b64
                
                # Troviamo i conti investimento accessibili con questa chiave
                # Non sappiamo a priori chi è l'utente della chiave, ma possiamo provare a decriptare
                # o semplicemente cercare tutti i conti investimento della famiglia (se condivisi) o degli utenti.
                
                # Query: Trova tutti i conti di tipo 'Investimento' appartenenti a utenti della famiglia
                # (Questo è un po' aggressivo, proverà a decriptare asset di tutti).
                # Se la chiave fallisce, pazienza.
                
                conti_investimento = []
                with get_db_connection() as con:
                    cur = con.cursor()
                    cur.execute("""
                        SELECT C.id_conto 
                        FROM Conti C
                        JOIN Appartenenza_Famiglia AF ON C.id_utente = AF.id_utente
                        WHERE AF.id_famiglia = %s AND C.tipo = 'Investimento'
                    """, (id_famiglia,))
                    rows = cur.fetchall()
                    conti_investimento = [r['id_conto'] for r in rows]

                all_tickers = set()
                asset_map = [] # List of (id_asset, ticker_decrypted)

                for id_conto in conti_investimento:
                    # Ottieni portafoglio (usa la master key fornita per tentare decrittazione)
                    # `ottieni_portafoglio` usa `_get_key_for_transaction` internamente.
                    # Se passiamo `master_key_b64=fk_b64`, esso userà quella.
                    # Se il conto è di un altro utente, `_get_key_for_transaction` potrebbe fallire nel trovare la family key corretta
                    # se si basa sulla master key dell'utente.
                    # MA se `fk_b64` è la Master Key dell'Admin, funziona solo per i conti dell'Admin.
                    # Se è la Family Key vera, funziona per i conti con Family Key.
                    
                    assets = ottieni_portafoglio(id_conto, master_key_b64=fk_b64)
                    for asset in assets:
                         if asset.get('ticker') and asset['ticker'] != '[ENCRYPTED]':
                             all_tickers.add(asset['ticker'])
                             asset_map.append((asset['id_asset'], asset['ticker']))

                if not all_tickers: continue
                
                # Batch update
                logger.info(f"Aggiornamento {len(all_tickers)} asset per famiglia {id_famiglia}...")
                prezzi = ottieni_prezzi_multipli(list(all_tickers))
                
                updated_count = 0
                for id_asset, ticker in asset_map:
                    if ticker in prezzi and prezzi[ticker] is not None:
                        aggiorna_prezzo_manuale_asset(id_asset, prezzi[ticker])
                        updated_count += 1
                
                if updated_count > 0:
                    logger.info(f"Famiglia {id_famiglia}: {updated_count} prezzi aggiornati.")

            except Exception as e:
                logger.error(f"Error updating assets for family {id_famiglia}: {e}")
        
        logger.info("Job Aggiornamento Asset completato.")
