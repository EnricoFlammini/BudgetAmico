import sqlite3
import os
import shutil
from db.crea_database import setup_database, TABLES


def _migra_da_v1_a_v2(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 1 alla 2.
    - Aggiunge la tabella Sottocategorie.
    - Modifica Transazioni, TransazioniCondivise e Budget per usare id_sottocategoria.
    - Popola le sottocategorie di default per le categorie esistenti.
    """
    print("Esecuzione migrazione da v1 a v2...")
    try:
        cur = con.cursor()

        # 1. Crea la nuova tabella Sottocategorie
        print("  - Creazione tabella Sottocategorie...")
        cur.execute(TABLES["Sottocategorie"])

        # 2. Aggiungi la colonna id_sottocategoria a Transazioni e TransazioniCondivise
        print("  - Modifica tabella Transazioni...")
        cur.execute("ALTER TABLE Transazioni ADD COLUMN id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL")
        print("  - Modifica tabella TransazioniCondivise...")
        cur.execute("ALTER TABLE TransazioniCondivise ADD COLUMN id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL")

        # 3. Popola le sottocategorie e aggiorna le transazioni esistenti
        print("  - Migrazione dati categorie a sottocategorie...")
        cur.execute("SELECT id_categoria, nome_categoria FROM Categorie")
        vecchie_categorie = cur.fetchall()
        for id_cat, nome_cat in vecchie_categorie:
            # Crea una sottocategoria di default per ogni vecchia categoria
            nome_sottocat = f"Generale"
            cur.execute("INSERT INTO Sottocategorie (id_categoria, nome_sottocategoria) VALUES (?, ?)", (id_cat, nome_sottocat))
            id_sottocat_nuova = cur.lastrowid
            
            # Aggiorna le transazioni che usavano la vecchia categoria
            cur.execute("UPDATE Transazioni SET id_sottocategoria = ? WHERE id_categoria = ?", (id_sottocat_nuova, id_cat))
            cur.execute("UPDATE TransazioniCondivise SET id_sottocategoria = ? WHERE id_categoria = ?", (id_sottocat_nuova, id_cat))

        # 4. Ricrea la tabella Budget
        print("  - Ricreazione tabella Budget...")
        cur.execute("ALTER TABLE Budget RENAME TO Budget_old")
        cur.execute(TABLES["Budget"])
        # (Non copiamo i dati perché il budget ora è per sottocategoria, l'utente dovrà reimpostarlo)
        cur.execute("DROP TABLE Budget_old")

        # 5. Ricrea la tabella Transazioni per rimuovere la vecchia colonna
        print("  - Finalizzazione tabella Transazioni...")
        cur.execute("CREATE TABLE Transazioni_new AS SELECT id_transazione, id_conto, id_sottocategoria, data, descrizione, importo FROM Transazioni")
        cur.execute("DROP TABLE Transazioni")
        cur.execute("ALTER TABLE Transazioni_new RENAME TO Transazioni")

        # 6. Ricrea la tabella TransazioniCondivise
        print("  - Finalizzazione tabella TransazioniCondivise...")
        cur.execute("CREATE TABLE TransazioniCondivise_new AS SELECT id_transazione_condivisa, id_utente_autore, id_conto_condiviso, id_sottocategoria, data, descrizione, importo FROM TransazioniCondivise")
        cur.execute("DROP TABLE TransazioniCondivise")
        cur.execute("ALTER TABLE TransazioniCondivise_new RENAME TO TransazioniCondivise")

        con.commit()
        print("Migrazione a v2 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v1 a v2: {e}")
        con.rollback()
        return False


def migra_database(db_path, versione_vecchia, versione_nuova):
    """
    Funzione principale che gestisce il processo di migrazione.
    Chiama le funzioni specifiche per ogni salto di versione.
    """
    if versione_vecchia >= versione_nuova:
        print("Nessuna migrazione necessaria.")
        return True

    # Crea una copia di backup del database prima di iniziare
    backup_path = db_path + f".v{versione_vecchia}.bak"
    shutil.copyfile(db_path, backup_path)
    print(f"Backup del database creato in: {backup_path}")

    try:
        with sqlite3.connect(db_path) as con:
            cur = con.cursor()
            
            # Esegui le migrazioni in sequenza
            if versione_vecchia == 1 and versione_nuova >= 2:
                if not _migra_da_v1_a_v2(con):
                    raise Exception("Migrazione da v1 a v2 fallita.")
                versione_vecchia = 2
            
            # Aggiungi qui futuri blocchi di migrazione (es. da v2 a v3)

            # Se tutto è andato bene, aggiorna la versione del DB
            cur.execute(f"PRAGMA user_version = {versione_nuova}")
            con.commit()
            print(f"Database migrato con successo alla versione {versione_nuova}.")
            return True

    except Exception as e:
        print(f"❌ Errore durante la migrazione: {e}. Ripristino dal backup.")
        # Ripristina dal backup in caso di errore
        shutil.move(backup_path, db_path)
        return False