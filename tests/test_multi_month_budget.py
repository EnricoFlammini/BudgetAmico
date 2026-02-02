
import sqlite3
import datetime
import unittest
from dateutil.relativedelta import relativedelta

# --- PROTOTIPO NUOVE FUNZIONI ---

def get_configurazione(cur, chiave, id_famiglia=None):
    if id_famiglia is None:
        cur.execute("SELECT valore FROM Configurazioni WHERE chiave = ? AND id_famiglia IS NULL", (chiave,))
    else:
        cur.execute("SELECT valore FROM Configurazioni WHERE chiave = ? AND id_famiglia = ?", (chiave, id_famiglia))
    res = cur.fetchone()
    return res[0] if res else None

def set_configurazione(cur, chiave, valore, id_famiglia=None):
    if id_famiglia is None:
        cur.execute("""
            INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
            VALUES (?, ?, NULL)
            ON CONFLICT (chiave) WHERE id_famiglia IS NULL
            DO UPDATE SET valore = EXCLUDED.valore
        """, (chiave, valore))
    else:
        cur.execute("""
            INSERT INTO Configurazioni (chiave, valore, id_famiglia) 
            VALUES (?, ?, ?)
            ON CONFLICT (chiave, id_famiglia) 
            DO UPDATE SET valore = EXCLUDED.valore
        """, (chiave, valore, id_famiglia))

def get_impostazioni_budget_famiglia(cur, id_famiglia, anno=None, mese=None):
    today = datetime.date.today()
    is_current = (anno is None or (anno == today.year and mese == today.month))
    
    if is_current:
        entrate = get_configurazione(cur, 'budget_entrate_mensili', id_famiglia)
        tipo = get_configurazione(cur, 'budget_risparmio_tipo', id_famiglia)
        valore = get_configurazione(cur, 'budget_risparmio_valore', id_famiglia)
    else:
        chiave_base = f"budget_storico_{anno}_{mese:02d}"
        entrate = get_configurazione(cur, f"{chiave_base}_entrate", id_famiglia)
        tipo = get_configurazione(cur, f"{chiave_base}_risparmio_tipo", id_famiglia)
        valore = get_configurazione(cur, f"{chiave_base}_risparmio_valore", id_famiglia)
        
        # Fallback al corrente se non esiste storico per quel mese? 
        # Forse meglio di no, per permettere di vedere che non è configurato.
        # Ma se l'utente lo chiede, di solito vuole vedere "cosa ho pianificato".
    
    return {
        'entrate_mensili': float(entrate or 0),
        'risparmio_tipo': tipo or 'percentuale',
        'risparmio_valore': float(valore or 0),
        'is_historical': not is_current
    }

def set_impostazioni_budget_famiglia(cur, id_famiglia, entrate_mensili, risparmio_tipo, risparmio_valore, anno=None, mese=None):
    today = datetime.date.today()
    is_current = (anno is None or (anno == today.year and mese == today.month))
    
    if is_current:
        set_configurazione(cur, 'budget_entrate_mensili', str(entrate_mensili), id_famiglia)
        set_configurazione(cur, 'budget_risparmio_tipo', risparmio_tipo, id_famiglia)
        set_configurazione(cur, 'budget_risparmio_valore', str(risparmio_valore), id_famiglia)
    else:
        chiave_base = f"budget_storico_{anno}_{mese:02d}"
        set_configurazione(cur, f"{chiave_base}_entrate", str(entrate_mensili), id_famiglia)
        set_configurazione(cur, f"{chiave_base}_risparmio_tipo", risparmio_tipo, id_famiglia)
        set_configurazione(cur, f"{chiave_base}_risparmio_valore", str(risparmio_valore), id_famiglia)
    return True

def ottieni_budget_famiglia(cur, id_famiglia, anno=None, mese=None):
    today = datetime.date.today()
    is_current = (anno is None or (anno == today.year and mese == today.month))
    
    if is_current:
        cur.execute("""
            SELECT B.id_sottocategoria, S.nome_sottocategoria, B.importo_limite
            FROM Budget B
            JOIN Sottocategorie S ON B.id_sottocategoria = S.id_sottocategoria
            WHERE B.id_famiglia = ? AND B.periodo = 'Mensile'
        """, (id_famiglia,))
    else:
        cur.execute("""
            SELECT BS.id_sottocategoria, BS.nome_sottocategoria, BS.importo_limite
            FROM Budget_Storico BS
            WHERE BS.id_famiglia = ? AND BS.anno = ? AND BS.mese = ?
        """, (id_famiglia, anno, mese))
    
    rows = cur.fetchall()
    return [{'id_sottocategoria': r[0], 'nome_sottocategoria': r[1], 'importo_limite': float(r[2])} for r in rows]

def imposta_budget(cur, id_famiglia, id_sottocategoria, importo_limite, anno=None, mese=None):
    today = datetime.date.today()
    is_current = (anno is None or (anno == today.year and mese == today.month))
    
    if is_current:
        cur.execute("""
            INSERT INTO Budget (id_famiglia, id_sottocategoria, importo_limite, periodo)
            VALUES (?, ?, ?, 'Mensile') 
            ON CONFLICT(id_famiglia, id_sottocategoria, periodo) 
            DO UPDATE SET importo_limite = EXCLUDED.importo_limite
        """, (id_famiglia, id_sottocategoria, str(importo_limite)))
    else:
        # Recupera il nome della sottocategoria per lo storico
        cur.execute("SELECT nome_sottocategoria FROM Sottocategorie WHERE id_sottocategoria = ?", (id_sottocategoria,))
        nome_sub = cur.fetchone()[0]
        
        cur.execute("""
            INSERT INTO Budget_Storico (id_famiglia, id_sottocategoria, nome_sottocategoria, anno, mese, importo_limite, importo_speso)
            VALUES (?, ?, ?, ?, ?, ?, 0.0)
            ON CONFLICT(id_famiglia, id_sottocategoria, anno, mese)
            DO UPDATE SET importo_limite = EXCLUDED.importo_limite
        """, (id_famiglia, id_sottocategoria, nome_sub, anno, mese, str(importo_limite)))
    return True

def clona_budget_corrente_su_mese(cur, id_famiglia, anno_target, mese_target):
    # 1. Clona impostazioni
    correnti = get_impostazioni_budget_famiglia(cur, id_famiglia)
    set_impostazioni_budget_famiglia(cur, id_famiglia, correnti['entrate_mensili'], correnti['risparmio_tipo'], correnti['risparmio_valore'], anno_target, mese_target)
    
    # 2. Clona limiti sottocategorie
    limiti_correnti = ottieni_budget_famiglia(cur, id_famiglia)
    for l in limiti_correnti:
        imposta_budget(cur, id_famiglia, l['id_sottocategoria'], l['importo_limite'], anno_target, mese_target)
    
    return True

# --- TEST SUITE ---

class TestMultiMonthBudget(unittest.TestCase):
    def setUp(self):
        # Database in memoria per test rapidi
        self.conn = sqlite3.connect(':memory:')
        self.cur = self.conn.cursor()
        
        # Crea schema minimo
        self.cur.execute("CREATE TABLE Famiglie (id_famiglia INTEGER PRIMARY KEY, nome_famiglia TEXT)")
        self.cur.execute("CREATE TABLE Categorie (id_categoria INTEGER PRIMARY KEY, id_famiglia INTEGER, nome_categoria TEXT)")
        self.cur.execute("CREATE TABLE Sottocategorie (id_sottocategoria INTEGER PRIMARY KEY, id_categoria INTEGER, nome_sottocategoria TEXT)")
        self.cur.execute("""
            CREATE TABLE Budget (
                id_budget INTEGER PRIMARY KEY,
                id_famiglia INTEGER,
                id_sottocategoria INTEGER,
                importo_limite TEXT,
                periodo TEXT,
                UNIQUE(id_famiglia, id_sottocategoria, periodo)
            )
        """)
        self.cur.execute("""
            CREATE TABLE Budget_Storico (
                id_storico INTEGER PRIMARY KEY,
                id_famiglia INTEGER,
                id_sottocategoria INTEGER,
                nome_sottocategoria TEXT,
                anno INTEGER,
                mese INTEGER,
                importo_limite TEXT,
                importo_speso TEXT,
                UNIQUE(id_famiglia, id_sottocategoria, anno, mese)
            )
        """)
        self.cur.execute("""
            CREATE TABLE Configurazioni (
                id_configurazione INTEGER PRIMARY KEY,
                id_famiglia INTEGER,
                chiave TEXT,
                valore TEXT,
                UNIQUE(id_famiglia, chiave)
            )
        """)
        
        # Dati di test
        self.cur.execute("INSERT INTO Famiglie VALUES (1, 'Famiglia Test')")
        self.cur.execute("INSERT INTO Categorie VALUES (10, 1, 'Cibo')")
        self.cur.execute("INSERT INTO Sottocategorie VALUES (101, 10, 'Spesa')")
        self.conn.commit()

    def test_budget_corrente(self):
        # Imposta budget corrente
        set_impostazioni_budget_famiglia(self.cur, 1, 2000.0, 'percentuale', 10.0)
        imposta_budget(self.cur, 1, 101, 500.0)
        
        # Verifica
        imps = get_impostazioni_budget_famiglia(self.cur, 1)
        self.assertEqual(imps['entrate_mensili'], 2000.0)
        
        limits = ottieni_budget_famiglia(self.cur, 1)
        self.assertEqual(len(limits), 1)
        self.assertEqual(limits[0]['importo_limite'], 500.0)

    def test_budget_futuro(self):
        anno_futuro = 2026
        mese_futuro = 3
        
        # Imposta budget futuro
        set_impostazioni_budget_famiglia(self.cur, 1, 3000.0, 'importo', 200.0, anno=anno_futuro, mese=mese_futuro)
        imposta_budget(self.cur, 1, 101, 600.0, anno=anno_futuro, mese=mese_futuro)
        
        # Verifica futuro
        imps_f = get_impostazioni_budget_famiglia(self.cur, 1, anno=anno_futuro, mese=mese_futuro)
        self.assertEqual(imps_f['entrate_mensili'], 3000.0)
        self.assertEqual(imps_f['risparmio_tipo'], 'importo')
        
        limits_f = ottieni_budget_famiglia(self.cur, 1, anno=anno_futuro, mese=mese_futuro)
        self.assertEqual(limits_f[0]['importo_limite'], 600.0)
        
        # Verifica che il corrente sia rimasto invariato (vuoto in questo caso)
        imps_c = get_impostazioni_budget_famiglia(self.cur, 1)
        self.assertEqual(imps_c['entrate_mensili'], 0.0)

    def test_clonazione(self):
        # Setup corrente
        set_impostazioni_budget_famiglia(self.cur, 1, 2000.0, 'percentuale', 10.0)
        imposta_budget(self.cur, 1, 101, 500.0)
        
        # Clona su Aprile 2026
        clona_budget_corrente_su_mese(self.cur, 1, 2026, 4)
        
        # Verifica Aprile
        imps = get_impostazioni_budget_famiglia(self.cur, 1, 2026, 4)
        self.assertEqual(imps['entrate_mensili'], 2000.0)
        
        limits = ottieni_budget_famiglia(self.cur, 1, 2026, 4)
        self.assertEqual(limits[0]['importo_limite'], 500.0)

    def tearDown(self):
        self.conn.close()

if __name__ == '__main__':
    unittest.main()
