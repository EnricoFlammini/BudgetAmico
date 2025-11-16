import sqlite3
import os
import shutil
from db.crea_database import setup_database


def _migra_da_v1_a_v2(vecchio_db_path, nuovo_db_path):
    """
    Logica specifica per migrare un DB dalla versione 1 alla 2.
    In questo esempio, la v2 ha aggiunto la colonna 'note' alla tabella 'SpeseFisse'.
    """
    print("Esecuzione migrazione da v1 a v2...")
    try:
        # Connetti al nuovo DB (vuoto) e attacca il vecchio DB
        with sqlite3.connect(nuovo_db_path) as con:
            cur = con.cursor()
            cur.execute(f"ATTACH DATABASE '{vecchio_db_path}' AS vecchio_db")

            # Ottieni la lista di tutte le tabelle dal vecchio DB
            cur.execute("SELECT name FROM vecchio_db.sqlite_master WHERE type='table'")
            tabelle = [row[0] for row in cur.fetchall()]

            # Copia i dati per ogni tabella
            for tabella in tabelle:
                print(f"  - Migrazione tabella: {tabella}")
                if tabella == 'SpeseFisse':
                    # Gestione specifica per la tabella modificata
                    # Copia le colonne esistenti, la nuova colonna 'note' avrà il suo valore di default (NULL)
                    cur.execute("""
                        INSERT INTO SpeseFisse (id_spesa_fissa, id_famiglia, nome, importo, 
                                                id_conto_personale_addebito, id_conto_condiviso_addebito, 
                                                id_categoria, giorno_addebito, attiva, data_prossima_esecuzione)
                        SELECT id_spesa_fissa,
                               id_famiglia,
                               nome,
                               importo,
                               id_conto_personale_addebito,
                               id_conto_condiviso_addebito,
                               id_categoria,
                               giorno_addebito,
                               attiva,
                               data_prossima_esecuzione
                        FROM vecchio_db.SpeseFisse
                    """)
                elif tabella != 'sqlite_sequence':  # Non copiare la tabella interna di autoincremento
                    # Copia generica per tabelle non modificate
                    cur.execute(f"INSERT INTO {tabella} SELECT * FROM vecchio_db.{tabella}")

            # Imposta la versione corretta sul nuovo DB
            cur.execute("PRAGMA user_version = 2;")
            con.commit()
            print("Migrazione completata con successo.")
            return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v1 a v2: {e}")
        return False


def _migra_da_v2_a_v3(vecchio_db_path, nuovo_db_path):
    """
    Logica specifica per migrare un DB dalla versione 2 alla 3.
    Aggiunge la tabella PasswordResets.
    """
    print("Esecuzione migrazione da v2 a v3...")
    try:
        with sqlite3.connect(nuovo_db_path) as con:
            cur = con.cursor()
            cur.execute(f"ATTACH DATABASE '{vecchio_db_path}' AS vecchio_db")

            tabelle_da_copiare = [row[0] for row in cur.execute(
                "SELECT name FROM vecchio_db.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            for tabella in tabelle_da_copiare:
                print(f"  - Copia tabella: {tabella}")
                cur.execute(f"INSERT INTO {tabella} SELECT * FROM vecchio_db.{tabella}")

            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v2 a v3: {e}")
        return False


def _migra_da_v3_a_v4(vecchio_db_path, nuovo_db_path):
    """
    Logica specifica per migrare un DB dalla versione 3 alla 4.
    Aggiunge la colonna 'email' a Utenti e la popola con il valore di 'username'.
    """
    print("Esecuzione migrazione da v3 a v4...")
    try:
        with sqlite3.connect(nuovo_db_path) as con:
            cur = con.cursor()
            cur.execute(f"ATTACH DATABASE '{vecchio_db_path}' AS vecchio_db")

            tabelle_da_copiare = [row[0] for row in cur.execute(
                "SELECT name FROM vecchio_db.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            for tabella in tabelle_da_copiare:
                if tabella == 'Utenti':
                    print(f"  - Migrazione speciale per tabella: {tabella}")
                    cur.execute("""
                        INSERT INTO Utenti (id_utente, username, email, password_hash, nome, cognome, id_conto_default, id_conto_condiviso_default)
                        SELECT id_utente, username, username, password_hash, nome, cognome, id_conto_default, id_conto_condiviso_default FROM vecchio_db.Utenti
                    """)
                else:
                    print(f"  - Copia tabella: {tabella}")
                    cur.execute(f"INSERT INTO {tabella} SELECT * FROM vecchio_db.{tabella}")
            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v3 a v4: {e}")
        return False

def _migra_da_v4_a_v5(vecchio_db_path, nuovo_db_path):
    """
    Logica specifica per migrare un DB dalla versione 4 alla 5.
    Aggiunge la colonna 'forza_cambio_password' a Utenti.
    """
    print("Esecuzione migrazione da v4 a v5...")
    try:
        with sqlite3.connect(nuovo_db_path) as con:
            cur = con.cursor()
            cur.execute(f"ATTACH DATABASE '{vecchio_db_path}' AS vecchio_db")

            tabelle_da_copiare = [row[0] for row in cur.execute(
                "SELECT name FROM vecchio_db.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            for tabella in tabelle_da_copiare:
                print(f"  - Copia tabella: {tabella}")
                # La nuova colonna 'forza_cambio_password' avrà il suo valore di default (0)
                # quindi una copia generica va bene.
                cur.execute(f"INSERT INTO {tabella} SELECT * FROM vecchio_db.{tabella}")
            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v4 a v5: {e}")
        return False

def _migra_da_v5_a_v6(vecchio_db_path, nuovo_db_path):
    """
    Logica specifica per migrare un DB dalla versione 5 alla 6.
    Aggiunge le colonne del profilo a Utenti.
    """
    print("Esecuzione migrazione da v5 a v6...")
    try:
        with sqlite3.connect(nuovo_db_path) as con:
            cur = con.cursor()
            cur.execute(f"ATTACH DATABASE '{vecchio_db_path}' AS vecchio_db")

            tabelle_da_copiare = [row[0] for row in cur.execute(
                "SELECT name FROM vecchio_db.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
            for tabella in tabelle_da_copiare:
                print(f"  - Copia tabella: {tabella}")
                cur.execute(f"INSERT INTO {tabella} SELECT * FROM vecchio_db.{tabella}")
            con.commit()
            return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v5 a v6: {e}")
        return False

def migra_database(vecchio_db_path, versione_vecchia, versione_nuova):
    """
    Funzione principale che gestisce il processo di migrazione.
    Chiama le funzioni specifiche per ogni salto di versione.
    """
    if versione_vecchia >= versione_nuova:
        print("Nessuna migrazione necessaria.")
        return True

    # Crea un percorso temporaneo per il DB migrato
    percorso_temporaneo = vecchio_db_path + ".migrated"

    # 1. Crea un nuovo DB vuoto con lo schema più recente
    if os.path.exists(percorso_temporaneo):
        os.remove(percorso_temporaneo)
    setup_database(percorso_temporaneo)

    # 2. Esegui le migrazioni in sequenza
    success = True
    if versione_vecchia == 1 and versione_nuova >= 2:
        success = _migra_da_v1_a_v2(vecchio_db_path, percorso_temporaneo)
        if not success:
            return False
        versione_vecchia = 2  # Aggiorna la versione per il prossimo step

    if versione_vecchia == 2 and versione_nuova >= 3:
        success = _migra_da_v2_a_v3(vecchio_db_path, percorso_temporaneo)
        if not success:
            return False
        versione_vecchia = 3

    if versione_vecchia == 3 and versione_nuova >= 4:
        success = _migra_da_v3_a_v4(vecchio_db_path, percorso_temporaneo)
        if not success:
            return False
        versione_vecchia = 4

    if versione_vecchia == 4 and versione_nuova >= 5:
        success = _migra_da_v4_a_v5(vecchio_db_path, percorso_temporaneo)
        if not success:
            return False
        versione_vecchia = 5

    if versione_vecchia == 5 and versione_nuova >= 6:
        success = _migra_da_v5_a_v6(vecchio_db_path, percorso_temporaneo)
        if not success:
            return False
        versione_vecchia = 6

    # 3. Se tutto è andato bene, sostituisci il file originale con quello migrato
    if success:
        # Sovrascrive il file di backup originale con la sua versione migrata
        shutil.move(percorso_temporaneo, vecchio_db_path)
        print(f"File di backup migrato e salvato in: {vecchio_db_path}")
        return True
    else:
        # Pulisci il file temporaneo in caso di errore
        if os.path.exists(percorso_temporaneo):
            os.remove(percorso_temporaneo)
        return False