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
            cur.execute("UPDATE Transazioni SET id_sottocategoria = ? WHERE id_categoria = ?",(id_sottocat_nuova, id_cat))
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



def _migra_da_v2_a_v3(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 2 alla 3.
    - Aggiunge id_sottocategoria_pagamento_default alla tabella Prestiti.
    - Aggiunge addebito_automatico alla tabella Prestiti.
    """
    print("Esecuzione migrazione da v2 a v3...")
    try:
        cur = con.cursor()

        # 1. Aggiungi colonna id_sottocategoria_pagamento_default
        print("  - Aggiunta colonna id_sottocategoria_pagamento_default a Prestiti...")
        try:
            cur.execute("ALTER TABLE Prestiti ADD COLUMN id_sottocategoria_pagamento_default INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_sottocategoria_pagamento_default già esistente (ignorato).")

        # 2. Aggiungi colonna addebito_automatico
        print("  - Aggiunta colonna addebito_automatico a Prestiti...")
        try:
            cur.execute("ALTER TABLE Prestiti ADD COLUMN addebito_automatico BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            print("    Colonna addebito_automatico già esistente (ignorato).")

        con.commit()
        print("Migrazione a v3 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v2 a v3: {e}")
        con.rollback()
        return False




def _migra_da_v3_a_v4(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 3 alla 4.
    - Aggiunge id_conto_condiviso_pagamento_default alla tabella Prestiti.
    """
    print("Esecuzione migrazione da v3 a v4...")
    try:
        cur = con.cursor()

        # Aggiungi colonna id_conto_condiviso_pagamento_default
        print("  - Aggiunta colonna id_conto_condiviso_pagamento_default a Prestiti...")
        try:
            cur.execute("ALTER TABLE Prestiti ADD COLUMN id_conto_condiviso_pagamento_default INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_conto_condiviso_pagamento_default già esistente (ignorato).")

        con.commit()
        print("Migrazione a v4 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v3 a v4: {e}")
        con.rollback()
        return False




def _migra_da_v4_a_v5(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 4 alla 5.
    - Aggiunge addebito_automatico alla tabella SpeseFisse.
    """
    print("Esecuzione migrazione da v4 a v5...")
    try:
        cur = con.cursor()

        # Aggiungi colonna addebito_automatico
        print("  - Aggiunta colonna addebito_automatico a SpeseFisse...")
        try:
            cur.execute("ALTER TABLE SpeseFisse ADD COLUMN addebito_automatico BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            print("    Colonna addebito_automatico già esistente (ignorato).")

        con.commit()
        print("Migrazione a v5 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v4 a v5: {e}")
        con.rollback()
        return False




def _migra_da_v5_a_v6(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 5 alla 6.
    - Aggiunge id_sottocategoria alla tabella SpeseFisse.
    """
    print("Esecuzione migrazione da v5 a v6...")
    try:
        cur = con.cursor()

        # Aggiungi colonna id_sottocategoria
        print("  - Aggiunta colonna id_sottocategoria a SpeseFisse...")
        try:
            cur.execute("ALTER TABLE SpeseFisse ADD COLUMN id_sottocategoria INTEGER REFERENCES Sottocategorie(id_sottocategoria) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_sottocategoria già esistente (ignorato).")

        con.commit()
        print("Migrazione a v6 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v5 a v6: {e}")
        con.rollback()
        return False


def _migra_da_v6_a_v7(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 6 alla 7.
    - Aggiunge borsa_default alla tabella Conti.
    """
    print("Esecuzione migrazione da v6 a v7...")
    try:
        cur = con.cursor()

        # Aggiungi colonna borsa_default
        print("  - Aggiunta colonna borsa_default a Conti...")
        try:
            cur.execute("ALTER TABLE Conti ADD COLUMN borsa_default TEXT")
        except sqlite3.OperationalError:
            print("    Colonna borsa_default già esistente (ignorato).")

        con.commit()
        print("Migrazione a v7 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v6 a v7: {e}")
        con.rollback()
        return False

def _migra_da_v15_a_v16(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 15 alla 16.
    - Aggiunge la colonna id_carta_default alla tabella Utenti.
    """
    print("Esecuzione migrazione da v15 a v16...")
    try:
        cur = con.cursor()

        print("  - Aggiunta colonna id_carta_default a Utenti...")
        try:
            # Riferimento alla tabella Carte
            cur.execute("ALTER TABLE Utenti ADD COLUMN id_carta_default INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_carta_default già esistente (ignorato).")

        con.commit()
        print("Migrazione a v16 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v15 a v16: {e}")
        try:
            con.rollback()
        except: 
            pass
        return False


def _migra_da_v7_a_v8(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 7 alla 8.
    - Crea la tabella Budget_Storico se non esiste.
    - Popola Budget_Storico con i dati retroattivi.
    """
    print("Esecuzione migrazione da v7 a v8...")
    try:
        cur = con.cursor()

        # 1. Crea la tabella Budget_Storico
        print("  - Creazione tabella Budget_Storico...")
        cur.execute(TABLES["Budget_Storico"])

        con.commit() # Committa la creazione della tabella prima di popolarla

        # 2. Popola Budget_Storico
        print("  - Popolamento storico budget retroattivo...")
        # Importazione locale per evitare cicli
        from db.gestione_db import storicizza_budget_retroattivo
        
        # Recupera tutti gli ID famiglia per eseguire la storicizzazione
        cur.execute("SELECT id_famiglia FROM Famiglie")
        famiglie = cur.fetchall()
        
        for (id_famiglia,) in famiglie:
            print(f"    Processing family ID: {id_famiglia}")
            # Nota: storicizza_budget_retroattivo apre una propria connessione.
            # Assumiamo che la commit() sopra abbia rilasciato eventuali lock di scrittura.
            success = storicizza_budget_retroattivo(id_famiglia)
            if not success:
                print(f"    ⚠️ Attenzione: storicizzazione fallita per famiglia {id_famiglia}")

        print("Migrazione a v8 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v7 a v8: {e}")
        con.rollback()
        return False



def _migra_da_v8_a_v9(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 8 alla 9.
    - Aggiunge rettifica_saldo alla tabella ContiCondivisi.
    - Aggiunge data_aggiornamento alla tabella Asset.
    """
    print("Esecuzione migrazione da v8 a v9...")
    try:
        cur = con.cursor()

        # 1. Aggiungi colonna rettifica_saldo a ContiCondivisi
        print("  - Aggiunta colonna rettifica_saldo a ContiCondivisi...")
        try:
            cur.execute("ALTER TABLE ContiCondivisi ADD COLUMN rettifica_saldo REAL DEFAULT 0.0")
        except sqlite3.OperationalError:
            print("    Colonna rettifica_saldo già esistente (ignorato).")

        # 2. Aggiungi colonna data_aggiornamento a Asset
        print("  - Aggiunta colonna data_aggiornamento a Asset...")
        try:
            cur.execute("ALTER TABLE Asset ADD COLUMN data_aggiornamento TEXT")
        except sqlite3.OperationalError:
            print("    Colonna data_aggiornamento già esistente (ignorato).")

        con.commit()
        print("Migrazione a v9 completata con successo.")
        return True


    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v8 a v9: {e}")
        con.rollback()
        return False


def _migra_da_v9_a_v10(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 9 alla 10.
    - Crea la tabella Carte.
    - Aggiunge id_carta alla tabella Transazioni.
    """
    print("Esecuzione migrazione da v9 a v10...")
    try:
        cur = con.cursor()

        # 1. Crea la tabella Carte
        print("  - Creazione tabella Carte...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Carte (
                id_carta INTEGER PRIMARY KEY AUTOINCREMENT,
                id_utente INTEGER NOT NULL REFERENCES Utenti(id_utente) ON DELETE CASCADE,
                nome_carta TEXT NOT NULL,
                tipo_carta TEXT NOT NULL CHECK(tipo_carta IN ('credito', 'debito')),
                circuito TEXT NOT NULL,
                id_conto_riferimento INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                id_conto_contabile INTEGER REFERENCES Conti(id_conto) ON DELETE SET NULL,
                massimale_encrypted TEXT,
                giorno_addebito_encrypted TEXT,
                spesa_tenuta_encrypted TEXT,
                soglia_azzeramento_encrypted TEXT,
                giorno_addebito_tenuta_encrypted TEXT,
                addebito_automatico BOOLEAN DEFAULT 0,
                data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                attiva BOOLEAN DEFAULT 1
            );
        """)

        # 2. Aggiungi colonna id_carta a Transazioni
        print("  - Aggiunta colonna id_carta a Transazioni...")
        try:
            cur.execute("ALTER TABLE Transazioni ADD COLUMN id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL")
        except sqlite3.OperationalError:
             print("    Colonna id_carta già esistente (ignorato).")

        con.commit()
        print("Migrazione a v10 completata con successo.")
        return True

    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v9 a v10: {e}")
        con.rollback()
        return False



def _migra_da_v10_a_v11(con: sqlite3.Connection):
    """
    Placeholder migrazione v10 -> v11
    """
    print("Esecuzione migrazione da v10 a v11...")
    return True

def _migra_da_v11_a_v12(con: sqlite3.Connection):
    """
    Placeholder migrazione v11 -> v12
    """
    print("Esecuzione migrazione da v11 a v12...")
    return True

def _migra_da_v12_a_v13(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 12 alla 13.
    - Crea la tabella StoricoMassimaliCarte.
    """
    print("Esecuzione migrazione da v12 a v13...")
    try:
        cur = con.cursor()
        print("  - Creazione tabella StoricoMassimaliCarte...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS StoricoMassimaliCarte (
                id_storico INTEGER PRIMARY KEY AUTOINCREMENT,
                id_carta INTEGER NOT NULL REFERENCES Carte(id_carta) ON DELETE CASCADE,
                data_inizio_validita TEXT NOT NULL,
                massimale_encrypted TEXT NOT NULL,
                UNIQUE(id_carta, data_inizio_validita)
            );
        """)
        con.commit()
        print("Migrazione a v13 completata con successo.")
        return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v12 a v13: {e}")
        con.rollback()
        return False

def _migra_da_v13_a_v14(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 13 alla 14.
    - Aggiunge colonne per supporto conti condivisi nella tabella Carte.
    """
    print("Esecuzione migrazione da v13 a v14...")
    try:
        cur = con.cursor()
        print("  - Aggiunta colonne condivise a Carte...")
        try:
            cur.execute("ALTER TABLE Carte ADD COLUMN id_conto_riferimento_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_conto_riferimento_condiviso già esistente.")
            
        try:
            cur.execute("ALTER TABLE Carte ADD COLUMN id_conto_contabile_condiviso INTEGER REFERENCES ContiCondivisi(id_conto_condiviso) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_conto_contabile_condiviso già esistente.")

        con.commit()
        print("Migrazione a v14 completata con successo.")
        return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v13 a v14: {e}")
        con.rollback()
        return False

def _migra_da_v14_a_v15(con: sqlite3.Connection):
    """
    Logica specifica per migrare un DB dalla versione 14 alla 15.
    - Aggiunge colonna id_carta alla tabella TransazioniCondivise.
    """
    print("Esecuzione migrazione da v14 a v15...")
    try:
        cur = con.cursor()
        print("  - Aggiunta colonna id_carta a TransazioniCondivise...")
        try:
            cur.execute("ALTER TABLE TransazioniCondivise ADD COLUMN id_carta INTEGER REFERENCES Carte(id_carta) ON DELETE SET NULL")
        except sqlite3.OperationalError:
            print("    Colonna id_carta già esistente.")
        
        # Ensure importo_nascosto exists (sanity check, as it was missing in crea_database def)
        try:
            cur.execute("ALTER TABLE TransazioniCondivise ADD COLUMN importo_nascosto BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass 

        con.commit()
        print("Migrazione a v15 completata con successo.")
        return True
    except Exception as e:
        print(f"❌ Errore critico durante la migrazione da v14 a v15: {e}")
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
            
            if versione_vecchia == 2 and versione_nuova >= 3:
                if not _migra_da_v2_a_v3(con):
                    raise Exception("Migrazione da v2 a v3 fallita.")
                versione_vecchia = 3
            
            if versione_vecchia == 3 and versione_nuova >= 4:
                if not _migra_da_v3_a_v4(con):
                    raise Exception("Migrazione da v3 a v4 fallita.")
                versione_vecchia = 4
            
            if versione_vecchia == 4 and versione_nuova >= 5:
                if not _migra_da_v4_a_v5(con):
                    raise Exception("Migrazione da v4 a v5 fallita.")
                versione_vecchia = 5
            
            if versione_vecchia == 5 and versione_nuova >= 6:
                if not _migra_da_v5_a_v6(con):
                    raise Exception("Migrazione da v5 a v6 fallita.")
                versione_vecchia = 6

            if versione_vecchia == 6 and versione_nuova >= 7:
                if not _migra_da_v6_a_v7(con):
                    raise Exception("Migrazione da v6 a v7 fallita.")
                versione_vecchia = 7

            if versione_vecchia == 7 and versione_nuova >= 8:
                if not _migra_da_v7_a_v8(con):
                    raise Exception("Migrazione da v7 a v8 fallita.")
                versione_vecchia = 8

            if versione_vecchia == 8 and versione_nuova >= 9:
                if not _migra_da_v8_a_v9(con):
                    raise Exception("Migrazione da v8 a v9 fallita.")
                versione_vecchia = 9

            if versione_vecchia == 9 and versione_nuova >= 10:
                if not _migra_da_v9_a_v10(con):
                    raise Exception("Migrazione da v9 a v10 fallita.")
                versione_vecchia = 10
            
            if versione_vecchia == 10 and versione_nuova >= 11:
                if not _migra_da_v10_a_v11(con):
                    raise Exception("Migrazione da v10 a v11 fallita.")
                versione_vecchia = 11

            if versione_vecchia == 11 and versione_nuova >= 12:
                if not _migra_da_v11_a_v12(con):
                    raise Exception("Migrazione da v11 a v12 fallita.")
                versione_vecchia = 12

            if versione_vecchia == 12 and versione_nuova >= 13:
                if not _migra_da_v12_a_v13(con):
                    raise Exception("Migrazione da v12 a v13 fallita.")
                versione_vecchia = 13

            if versione_vecchia == 13 and versione_nuova >= 14:
                if not _migra_da_v13_a_v14(con):
                    raise Exception("Migrazione da v13 a v14 fallita.")
                versione_vecchia = 14

                if not _migra_da_v14_a_v15(con):
                    raise Exception("Migrazione da v14 a v15 fallita.")
                versione_vecchia = 15

            if versione_vecchia == 15 and versione_nuova >= 16:
                if not _migra_da_v15_a_v16(con):
                    raise Exception("Migrazione da v15 a v16 fallita.")
                versione_vecchia = 16

            # Se tutto è andato bene, aggiorna la versione del DB
            cur.execute(f"PRAGMA user_version = {versione_nuova}")
            con.commit()
            print(f"Database migrato con successo alla versione {versione_nuova}.")
            return True

    except Exception as e:
        print(f"❌ Errore durante la migrazione: {e}. Ripristino dal backup.")
        # Ripristina dal backup in caso di errore
        # ensure copy back only if something failed after backup
        if os.path.exists(backup_path):
             shutil.copyfile(backup_path, db_path) # Changed to copyfile to enable retry
        return False