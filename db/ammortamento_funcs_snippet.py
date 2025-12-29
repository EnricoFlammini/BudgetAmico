
# --- GESTIONE PIANO AMMORTAMENTO ---

def aggiungi_rata_piano_ammortamento(id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse=0, stato='da_pagare'):
    """
    Aggiunge una rata al piano di ammortamento di un prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                INSERT INTO PianoAmmortamento 
                (id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse, stato)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (id_prestito, numero_rata, data_scadenza, importo_rata, quota_capitale, quota_interessi, spese_fisse, stato))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiunta rata piano ammortamento: {e}")
        return False

def ottieni_piano_ammortamento(id_prestito):
    """
    Recupera il piano di ammortamento completo per un prestito, ordinato per numero rata.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("""
                SELECT * FROM PianoAmmortamento 
                WHERE id_prestito = %s 
                ORDER BY numero_rata ASC
            """, (id_prestito,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"[ERRORE] Errore recupero piano ammortamento: {e}")
        return []

def elimina_piano_ammortamento(id_prestito):
    """
    Elimina tutte le rate del piano di ammortamento per un prestito.
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("DELETE FROM PianoAmmortamento WHERE id_prestito = %s", (id_prestito,))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore eliminazione piano ammortamento: {e}")
        return False

def aggiorna_stato_rata_piano(id_rata, nuovo_stato):
    """
    Aggiorna lo stato di una rata (es. da 'da_pagare' a 'pagata').
    """
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            cur.execute("UPDATE PianoAmmortamento SET stato = %s WHERE id_rata = %s", (nuovo_stato, id_rata))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERRORE] Errore aggiornamento stato rata: {e}")
        return False
