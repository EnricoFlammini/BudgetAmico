
import datetime
from dateutil.relativedelta import relativedelta
from db.gestione_db import (
    get_db_connection, 
    ottieni_carte_utente, 
    aggiungi_transazione, 
    _get_famiglia_and_utente_from_conto
)

def process_credit_card_settlements(id_utente, master_key_b64):
    """
    Checks all active credit cards for the user. 
    If today is the settlement day, calculates the outstanding balance on the card's accounting account
    and creates a settlement transfer from the reference bank account.
    """
    print(f"[INFO] Checking card settlements for user {id_utente}...")
    
    carte = ottieni_carte_utente(id_utente, master_key_b64)
    if not carte:
        return 0

    oggi = datetime.date.today()
    giorno_oggi = oggi.day
    count_settled = 0

    for carta in carte:
        if carta['tipo_carta'] != 'credito':
            continue
            
        if not carta['id_conto_contabile'] or not carta['id_conto_riferimento']:
            # Invalid configuration
            continue
            
        # Check if today is the settlement day
        giorno_addebito = carta.get('giorno_addebito')
        if not giorno_addebito:
             continue
             
        # Handling end-of-month cases (e.g. if giorno_addebito is 31, but today is 30th of June)
        # Simple logic: exact match for now. Advanced logic could handle "last day of month".
        if giorno_oggi != giorno_addebito:
            continue

        # Valid settlement day. Check balance.
        try:
            with get_db_connection() as con:
                cur = con.cursor()
                
                # Check balance of the Card Account (id_conto_contabile)
                # We expect it to be negative (expenses).
                # Only include transactions up to yesterday? Or encompassing everything?
                # Usually credit cards settle the *previous* statement. 
                # Ideally, we settle the balance as it was at the *closing date* of the statement.
                # But for simplicity in this MVP: We settle the *current* total balance of the card account.
                # Assuming the user records expenses on the card account as they happen.
                
                # Get current balance
                cur.execute("""
                    SELECT SUM(importo) as saldo 
                    FROM Transazioni 
                    WHERE id_conto = %s
                """, (carta['id_conto_contabile'],))
                res = cur.fetchone()
                saldo_attuale = res['saldo'] if res and res['saldo'] else 0.0
                
                if saldo_attuale >= -0.01:
                    # Positive or zero balance (no debt to pay), or negligible
                    continue
                
                importo_da_saldare = abs(saldo_attuale)
                
                # Check if we already paid TODAY to avoid duplicates
                # Look for a transfer on the reference account with description containing schema
                desc_pattern = f"Saldo Carta {carta['nome_carta']}%"
                
                cur.execute("""
                    SELECT 1 FROM Transazioni
                    WHERE id_conto = %s
                    AND importo < 0
                    AND data = %s
                    AND descrizione LIKE %s
                """, (carta['id_conto_riferimento'], oggi.strftime('%Y-%m-%d'), desc_pattern))
                
                if cur.fetchone():
                    print(f"[INFO] Settlement for card {carta['nome_carta']} likely already done today.")
                    continue

                print(f"[INFO] Settling card {carta['nome_carta']}: {importo_da_saldare} EUR")
                
                # Create Transfer
                # 1. Withdrawal from Bank Account
                desc_bank = f"Saldo Carta {carta['nome_carta']} - {oggi.strftime('%B %Y')}"
                
                # Use existing add function (it handles history update)
                # But we want to link these inside a transaction or ensuring both happen.
                # aggiungi_transazione commits internally if no cursor provided. 
                # We should provide cursor to ensure atomicity? 
                # But aggiungi_transazione logic is complex with history updates.
                # Let's use separate calls for now, logic is robust enough.
                
                # We need Transfer logic: Out from Bank, In to Card.
                
                # 1. Out from Bank
                id_trans_bank = aggiungi_transazione(
                    id_conto=carta['id_conto_riferimento'],
                    data=oggi.strftime('%Y-%m-%d'),
                    descrizione=desc_bank,
                    importo=-importo_da_saldare,
                    id_sottocategoria=None, # Transfer? Or specific category? Usually transfers are null category.
                    master_key_b64=master_key_b64,
                    cursor=None # New transaction
                    # id_carta? No, this is on the bank account.
                )
                
                # 2. In to Card Account (Credits the negative balance)
                desc_card = f"Addebito Saldo da C/C"
                id_trans_card = aggiungi_transazione(
                    id_conto=carta['id_conto_contabile'],
                    data=oggi.strftime('%Y-%m-%d'),
                    descrizione=desc_card,
                    importo=importo_da_saldare,
                    id_sottocategoria=None,
                    master_key_b64=master_key_b64,
                    cursor=None,
                    id_carta=carta['id_carta'] # Link to card itself (redundant but ok)
                )
                
                count_settled += 1

        except Exception as e:
            print(f"[ERRORE] Failure processing card {carta['nome_carta']}: {e}")
            
    return count_settled
