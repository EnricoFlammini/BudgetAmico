# Changelog

Tutte le modifiche notevoli a questo progetto saranno documentate in questo file.

---

## 📅 Changelog
 
### v0.53.01 (15/02/2026)
- **Fix Critici**:
    - **Auto-history**: Risolto errore `NameError: name '_get_family_key_for_user' is not defined` in `gestione_budget.py` che impediva l'aggiornamento dello storico budget.
    - **Integrità Codice**: Rimossa definizione duplicata di `trigger_budget_history_update` e consolidata la logica di sincronizzazione storico (limiti e spese).
- **Esperienza Utente (Navigazione)**:
    - **Standardizzazione Navigazione**: Implementato il reindirizzamento automatico alla tab corretta dopo il salvataggio per: **Immobili** (tab Immobili), **Investimenti** (tab Investimenti), **Conti** (tab Conti, incluso Rettifica Saldo e Fondo Pensione) e **Spese Fisse** (tab Spese Fisse).
### v0.53.00 (14/02/2026)
- **Nuove Funzionalità**:
    - **Tutorial di Onboarding**: Introdotta una guida interattiva per i nuovi utenti che aiuta nella configurazione iniziale (Conto, Carta).
    - **Reindirizzamento Automatico**: Implementata la navigazione automatica dopo la creazione di record (es. reindirizzamento a 'Conti' dopo la creazione di un conto, 'Carte' dopo una carta, 'Home' dopo una transazione).
    - **Navigazione Programmatica**: Aggiunto supporto nel `DashboardView` per la navigazione a tab specifica tramite chiave identificativa (`navigate_to_tab`).
- **Database**:
    - **Persistenza Onboarding**: Aggiunta gestione dello stato di completamento del tutorial nel modulo `gestione_config.py`.

### v0.52.01 (13/02/2026)
- **Fix Critici**:
    - **Background Service**: Risolto errore `Impossibile decriptare chiave famiglia` all'avvio del servizio. Implementato **Lazy Loading** per le chiavi di sistema (`SYSTEM_FERNET_KEY`, `SERVER_SECRET_KEY`) per evitare problemi di importazione circolare e caricamento variabili d'ambiente.
    - **Giroconto Salvadanaio**: Risolto bug che non aggiornava il saldo del salvadanaio nella dashboard dopo un trasferimento. Aggiunta l'invalidazione della cache `family_piggy_banks` dopo ogni operazione di scrittura.
    - **Fix Critici**: Risolto errore `AttributeError: 'AuthView' object has no attribute 'pwd_config'` in registrazione.
- **UI & Experience**:
    - **Fix UI Spinner**: Implementata chiusura automatica spinner (`hide_loading`) ad ogni cambio route per evitare blocchi UI (es. setup-admin) e redirezioni post-login.
    - **Menu Salvadanai**: Migliorata la visualizzazione nel menu a tendina della scheda Conto. I nomi lunghi ora vanno a capo correttamente senza "uscire" dalla scheda.
    - **Highlight Risparmi**: L'icona del salvadanaio sulla scheda conto si colora di **Oro (Amber)** se sono presenti fondi accantonati, permettendo di identificare a colpo d'occhio i conti con risparmi attivi.


### v0.52.00 (13/02/2026)
- **Crittografia Selettiva (Fase 3)**:
    - **Plaintext Data**: Migrati i campi non sensibili (`nome_categoria`, `nome_sottocategoria`, `ticker`, `nome_asset`) in chiaro per migliorare drasticamente le performance di ricerca, filtri e ordinamento.
    - **Native Numeric Types**: Convertiti i campi di importo (`importo_obiettivo`, `importo_assegnato`) da `TEXT` a `NUMERIC` nel database, garantendo precisione nei calcoli e ordinamento numerico corretto.
    - **SQL Optimization**: Aggiornate tutte le query dei moduli `gestione_investimenti`, `gestione_conti`, `gestione_categorie` e `gestione_obiettivi` per utilizzare l'ordinamento nativo del database (`ORDER BY`).
    - **Refactoring Sicurezza**: Rimossa la logica di crittografia/decrittografia superflua per i campi migrati, semplificando il codice e riducendo il carico di lavoro del client.
    - **Storico Asset**: Inclusa la tabella `Storico_Asset` nella migrazione per una gestione coerente dei ticker.
- **Fix & Stabilità**:
    - Corretto errore di indentazione nel modulo `gestione_conti.py`.
    - Migliorata la robustezza dello script di migrazione per la conversione dei tipi numerici.

### v0.50.01 (11/02/2026)
- **Fix Stabilità UI (AssertionError)**:
    - Eliminato completamente l'errore `AssertionError: Control must be added to the page first`.
    - Migrati **tutti** i dialog al pattern sicuro overlay manuale: apertura con `overlay.append()` + `dialog.open = True`, chiusura con `dialog.open = False` + `overlay.remove()`.
    - Applicato a: `ContoDialog`, `CardDialog`, `PortafoglioDialogs` (7 metodi), `AdminDialogs` (7 metodi).
    - Aggiunto guard `if control.page:` a tutte le chiamate `.update()` premature.
- **Fix Contrasto Icone**:
    - Le icone (Flet standard e PNG custom) sono ora avvolte in un container bianco circolare con ombra, garantendo visibilità su qualsiasi sfondo colorato personalizzato.
    - Colore icone di default impostato a nero per massimo contrasto.
- **Fix Picker Icone/Colori**:
    - Corretto il flusso di selezione icona/colore che chiudeva il dialog senza possibilità di salvare.
    - Standardizzato il ciclo picker → selezione → ritorno al dialog principale in `ContoDialog` e `CardDialog`.

### v0.50.00 (11/02/2026)
- **Personalizzazione Conti e Carte**:
    - Introdotta la possibilità di scegliere icone (standard Flet o PNG personalizzati) e colori per ogni conto e carta.
    - Aggiornata la logica di visualizzazione dei loghi in tutta l'applicazione per supportare le personalizzazioni.
- **Ordinamento Avanzato**:
    - Nuova scheda **"Ordinamento"** nel pannello Admin per definire l'ordine di visualizzazione di conti e carte nei menu.
    - L'ordinamento viene salvato persistentemente a livello di famiglia e applicato ai dropdown delle transazioni.
- **Ottimizzazione Database (Performance)**:
    - Implementata migrazione **v27** (indici) e **v29** (supporto personalizzazione).
    - Ridotto drasticamente il timeout del caricamento budget mensile e storico.
    - Introdotta logica avanzata di rilevamento lock e **"Opzione Nucleare"** per terminare processi bloccanti durante le migrazioni.
- **Admin Panel Enhancements**:
    - Nuova scheda **"Versione"** che mostra versione App, versione Schema DB e Ambiente (Dev/Prod).
    - Note di rilascio rapide visibili direttamente nel portale admin.
- **Branding & UI**:
    - Aggiunti asset grafici ufficiali per **PayPal** e **Satispay**.
    - Migliorata la leggibilità delle informazioni di sistema.

### v0.49.00 (07/02/2026)
- **Ottimizzazione Mobile**: Revisione globale di tutti i dialoghi (15+) per garantire una corretta visualizzazione su smartphone:
    - Introdotto scrolling automatico per prevenire overflow con la tastiera attiva.
    - Rimosse altezze fisse e vincoli di espansione che causavano schiacciamento della UI.
    - Standardizzata larghezza a 350px per massima compatibilità.
- **Fix & Stabilità**:
    - **PostgreSQL**: Risolto errore di sintassi (`22P02`) per tipi integer tramite sanificazione automatica degli ID (conversione stringhe vuote in NULL).
    - **Flet Stability**: Introdotto error handling negli aggiornamenti UI dei dialoghi per prevenire crash (`AssertionError`) in scenari di sessione instabile.
- **Admin Panel**: Aggiunte statistiche di accesso (utenti attivi ora, accessi ultime 24h, 48h, 72h) nel portale admin.

### v0.48.01 (07/02/2026)
- **Fix Database**: Risolto errore `42703` (column "nome_categoria" does not exist) nella funzione `ottieni_totale_budget_storico` tramite l'aggiunta delle JOIN corrette con Categorie e Sottocategorie.

### v0.48.00 (06/02/2026)
- **Sicurezza & Privacy**:
    - **Password Complexity**: Requisiti password ora configurabili dal Pannello Admin.
    - **Security Indicator**: Indicatore grafico della forza password.
    - **Verifica Email**: Sistema obbligatorio di verifica email via codice (6 cifre).
    - **Codici Univoci**: Identificativi criptati (Utenti e Famiglie) nelle tabelle Admin.
    - **Privacy Policy**: Nuova vista dedicata accessibile in tutta l'app.
- **Gestione Dati**:
    - **Backup via Email**: Funzione di invio backup completo (JSON) con decriptazione automatica.
    - **Cancellazione Account**: Eliminazione definitiva con verifica password e pulizia dati.
- **UI & UX**:
    - **Responsive Wealth**: Riepilogo patrimonio compattato solo su dispositivi mobile.
    - **Normalizzazione Nomi**: Title Case automatico per Nome e Cognome.
    - **DatePicker**: Introdotto per la Data di Nascita (non obbligatoria).
    - **Semplificazione Profilo**: CF e Indirizzo non più obbligatori.
- **Fix & Stabilità**:
    - **PostgreSQL**: Fix inizializzazione booleani DEFAULT FALSE.
    - **Admin Tools**: Migliorato reset password membri via recovery Master Key.

### v0.47.17 (05/02/2026)
- **Background Service Fix**: Risolto errore `UnboundLocalError: admin_id` nel servizio di background che causava il crash dell'automazione server.
- **Improved Automation**: Riorganizzata la sequenza di recupero membri famiglia per garantire la disponibilità dell'ID amministratore prima di procedere ai pagamenti.

### v0.47.16 (05/02/2026)
- **Cloud Automation Fix**: Risolto il mancato pagamento automatico dei mutui (prestiti) quando è attiva l'automazione lato server.
- **Background Service**: Integrata la funzione `check_e_paga_rate_scadute` nel servizio di background con supporto per le chiavi decriptate forzate.
- **Database Improvement**: Esteso il supporto per `forced_family_key_b64` nelle funzioni di recupero e processamento rate prestiti.


### v0.47.15 (05/02/2026)
- **Loan Dialog Fix**: Risolto il problema del caricamento del conto di pagamento predefinito e delle quote di competenza (normalizzazione prefissi P/C e ID utente).
- **Stability**: Migliorata la gestione dei pagamenti rata distinguendo correttamente tra conti personali e condivisi.
- **Database & Tests**: Rafforzati i test unitari per l'analisi mensile e migliorata la sincronizzazione dinamica dei mutui tra immobili e prestiti.
### v0.47.14 (05/02/2026)
- **Flet Stability Fix**: Risolto `AssertionError` causato da aggiornamenti UI prematuri e ridondanti durante l'apertura dei dialoghi.
- **Optimization**: Ottimizzato il caricamento dei dropdown per evitare chiamate duplicate al database e al framework.
- **Improved Option Keys**: Allineato l'uso delle chiavi nei dropdown per una sincronizzazione più robusta tra client e server.


### v0.47.13 (05/02/2026)
- **Bug Fix**: Risolto `IndexError` nel dialogo transazioni durante la selezione delle carte.
- **Improved Card Logic**: Allineato il formato delle chiavi delle carte tra database e UI per garantire il corretto recupero dei conti associati.
- **Safety**: Aggiunta validazione preventiva per evitare crash in caso di formati chiave imprevisti.


### v0.47.12 (05/02/2026)
- **Security & Family Visibility**: Risolto un bug di visibilità dati causato da chiavi di famiglia incoerenti.
- **Auto-Sync**: Implementata la sincronizzazione automatica della chiave di famiglia tramite crittografia di sistema (Automation Cloud) per garantire coerenza tra tutti i membri.
- **Database Logic**: Migliorata la funzione `ensure_family_key` in `gestione_db.py` per il recupero automatico delle chiavi dal backup del server.


### v0.47.11 (04/02/2026)
- **Database Fix**: Corretto un errore nella migrazione del database che impediva l'applicazione del vincolo UNIQUE sullo storico asset (causato da un'errata gestione dei risultati del cursore).


### v0.47.10 (04/02/2026)
- **Database Fix**: Risolto l'errore `42P10` (missing unique constraint) per lo storico asset globale. Implementata migrazione automatica per pulire duplicati e aggiungere il vincolo `UNIQUE(ticker, data)` necessario per le operazioni di sincronizzazione.


### v0.47.09 (04/02/2026)
- **Database Fix**: Risolto l'errore `25P02` (transaction aborted) durante l'aggiornamento dei prezzi storici degli asset. Introdotta validazione preventiva dei dati per escludere record nulli o non validi che interrompevano le transazioni batch.


### v0.47.08 (04/02/2026)
- **UI & UX**: Rimosse le opzioni "Investimento" e "Altro" dal dialogo di aggiunta nuovo conto per semplificare l'inserimento. I conti esistenti di questo tipo rimangono comunque gestibili e visibili.


### v0.47.07 (04/02/2026)
- **Performance & UX**: Ottimizzata l'apertura di tutti i dialoghi di inserimento (Transazioni, Conti, ecc.).
- **Feedback Caricamento**: Introdotto uno spinner di caricamento globale che appare istantaneamente al click, prevenendo doppi inserimenti accidentali e migliorando la percezione di velocità.
- **Sicurezza UI**: Rinforzato l'overlay di caricamento per bloccare l'interazione con l'interfaccia sottostante durante le operazioni di backend.


### v0.47.06 (04/02/2026)
- **Divisore Pro**: Abilitato l'inserimento di spese con importo pari a zero per gestire partecipanti che non hanno anticipato denaro.
- **Database & Schema**: Allineati gli ambienti Test e Produzione alla versione 22. Consolidata la logica di migrazione per le colonne `id_asset` e `id_obiettivo` nella tabella `Salvadanai`.
- **Sicurezza**: Implementata la protezione per la categoria di sistema "ENTRATE". Inibita la modifica e l'eliminazione sia a livello database che interfaccia utente per preservare l'integrità dei calcoli automatici.


### v0.47.05 (04/02/2026)
- **Fix**: Risolto errore di avvio causato da un parametro non supportato in `ft.app()`. La configurazione della chiave di sicurezza ora avviene correttamente tramite variabili d'ambiente.

### v0.47.04 (04/02/2026)
- **Bug Fix**: Risolto errore `NoneType` durante l'importazione di file CSV in modalità Web. Implementato sistema di upload temporaneo per permettere al server di elaborare i file selezionati nel browser.

### v0.47.03 (04/02/2026)
- **UI Refinement**: Rimossa la sezione "Versione Desktop" dalla pagina Info per focalizzare l'esperienza sulla versione Web.
- **Ottimizzazione Template**: Il template per il piano di ammortamento è ora un file statico pre-caricato sul server, velocizzando il download e garantendo maggiore consistenza.

### v0.47.02 (04/02/2026)
- **Log Cleaning**: Disabilitati i log di debug di basso livello per l'invio email (SMTP) che causavano la visualizzazione di messaggi di successo come "errori" (stderr) nei log del server.

### v0.47.01 (04/02/2026) - HOTFIX
- **Bugfix Login**: Risolto crash `AttributeError` quando veniva inserita una password errata. Standardizzato il ritorno della funzione di autenticazione per gestire correttamente i messaggi di errore del database.
- **Ripristino UI Admin**: Reintrodotto il dialog di conferma email rimosso accidentalmente nella versione precedente, ripristinando la possibilità di inviare Family Key e credenziali membri.

### v0.47.00 (04/02/2026)
- **Sicurezza e Conferma Invio**:
    - **Dialog di Verifica Email**: Implementato un nuovo sistema di sicurezza che richiede la conferma o la modifica dell'indirizzo email del destinatario prima di ogni invio (Backup e Credenziali).
    - **Protezione Dati**: Aumentata la consapevolezza dell'utente sulla sensibilità della Family Key durante l'invio via email.
- **Ottimizzazione UI Admin**:
    - **Semplificazione Web**: Rimossa l'interfaccia di "Abilita Logging" e il pulsante di "Download Locale" (divenuti rimpiazzati dall'invio email sicuro e centralizzato).
    - **Ridenominazione Tasti**: Il pulsante di backup è ora più esplicito: "Invia Family key e configurazione via mail".
    - **Cloud Automation**: Rimossa la dicitura "BETA" dall'automazione Cloud (Koyeb), ora considerata stabile.
- **Privacy Backup**:
    - **Rimozione SMTP**: I file di backup (.json) non contengono più i parametri SMTP della famiglia (ora gestiti globalmente), rendendo il file più leggero e sicuro.
- **Bugfix Navigazione**:
    - **Fix Sidebar Indexing**: Risolto un bug critico nel calcolo degli indici della sidebar che poteva causare il caricamento di tab errate dopo login o refresh.

### v0.46.00 (02/02/2026)
- **Riprogettazione Sistema Budget**:
    - **Auto-salvataggio**: Implementato il salvataggio automatico (on-blur) per entrate stimate, obiettivi di risparmio e limiti delle sottocategorie. Rimossi i pulsanti di salvataggio manuale per un'esperienza più fluida.
    - **Calcolo Real-time**: I totali "Allocato" e "Rimanente" vengono ora ricalcolati istantaneamente durante la digitazione dei budget, con aggiornamento dinamico della barra di avanzamento.
    - **Clonazione Avanzata**: Sostituito il pulsante di copia generico con un menu a tendina per selezionare specificamente da quale periodo passato o futuro copiare la configurazione.
    - **Analisi Mensile Evoluta**: Nella pagina di analisi, le "Entrate" sono ora calcolate automaticamente sommando le transazioni effettive della categoria "Entrate", invece di usare il valore stimato.
    - **Esclusione Categoria Entrate**: La categoria "Entrate" è stata esclusa dalla gestione dei budget di spesa per garantire la coerenza dei calcoli.
- **Database & Sicurezza**:
    - **Fix Type Mismatch**: Convertite le colonne degli importi budget da `REAL` a `TEXT` nel database per supportare correttamente la crittografia (risolto errore di salvataggio).
    - **Script di Migrazione**: Aggiunto `db/apply_budget_encryption_migration.py` per l'aggiornamento sicuro dei database esistenti.

### v0.45.01 (02/02/2026)
- **Fix Download Cross-Platform**:
    - **Compatibilità Desktop**: Centralizzata la logica di download in `utils/file_downloader.py`. Risolti problemi di compatibilità su **macOS** e **Linux** (sostituito comando generico con comandi nativi `open`/`xdg-open`).
    - **Robustezza**: Migliorato il sistema di individuazione della cartella "Downloads" per gestire nomi localizzati o percorsi non standard.

### v0.45.00 (02/02/2026)
- **Gestione Ambienti**:
    - **Guida Operativa**: Aggiunto file `File/istruzioni_ambienti.txt` con le procedure complete per la gestione dei database (test/prod) e deploy su Koyeb.
- **Account & Filtri**:
    - **Filtro Conti Intelligente**: Affinata la logica nei dialoghi **Spese Fisse** e **Prestiti**. Ora i conti correnti associati a carte di debito rimangono visibili, filtrando solo i reali conti tecnici "Saldo" delle carte di credito.
    - **Bugfix Regressioni**: Risolti errori `NameError` nelle logiche di popolazione dei dropdown.

### v0.44.00 (01/02/2026)
- **Admin Panel Enhancements**:
    - **Automazione Cloud Default**: Nuovo switch globale in "Configurazione" per abilitare automaticamente l'automazione cloud (Server Key) per tutte le nuove famiglie create.
    - **Security Audit UI**: Aggiunta la colonna "Algo" nella tabella Utenti per visualizzare l'algoritmo di hashing della password (utile per identificare account legacy).
    - **Stato Cloud Famiglia**: Aggiunta icona di stato (Nuvola Blu/Grigia) nella tabella Famiglie per indicare se l'automazione server è attiva.
    - **Backend**: Aggiornate funzioni di creazione famiglia e admin per rispettare il default di sistema e ottimizzare la gestione delle chiavi.

### v0.43.07 (31/01/2026)
- **Dismissione Desktop**:
    - **Focus Web**: Il progetto è ora ufficialmente una **Web Application**. La versione desktop è stata dismessa per concentrare lo sviluppo sulla versatilità e accessibilità via browser.
    - **Nuovo Entry Point**: L'esecuzione locale (`python main.py`) ora avvia direttamente l'interfaccia web nel browser predefinito.

### v0.43.06 (31/01/2026)
- **Fix Download Web (Fallback)**:
    - **Affidabilità**: Rimosso un metodo di fallback (Javascript URL) che risultava inaffidabile su alcuni browser. Ora, se il metodo principale non è disponibile, il sistema forza il download diretto del file (Data URI Stream), garantendo che il file venga salvato correttamente nella cartella Download.

### v0.43.05 (31/01/2026)
- **Fix Download Web**:
    - **Compatibilità**: Migliorato il sistema di download per supportare versioni precedenti delle librerie grafiche (Flet). Se `run_js` non è disponibile, il sistema tenta automaticamente metodi alternativi (`javascript:` URL o Data URI diretto).

### v0.43.04 (31/01/2026)
- **Fix Universale Download**:
    - **Web**: Implementato nuovo sistema di download lato client (JS injection) che risolve problemi con popup blocker e garantisce privacy totale (nessun salvataggio su server).
    - **Desktop**: Risolti problemi con i file picker. I file (Backup e Template) vengono ora salvati automaticamente nella cartella **Downloads** dell'utente e aperti subito dopo.
    - **Carte**: Migliorato contrasto barra avanzamento (Bianco/Ambra su sfondo scuro) per massima leggibilità su carte colorate.

### v0.43.03 (31/01/2026)
- **Privacy & Download**:
    - **Backup Serverless**: L'esportazione del backup sulla versione Web ora avviene interamente tramite Data URI, evitando qualsiasi salvataggio temporaneo del file sui dischi del server, per garantire la massima privacy e sicurezza.

### v0.43.02 (31/01/2026)
- **HOTFIX Admin Web**:
    - **Gestione Categorie**: Risolto crash (`AttributeError`) che impediva l'apertura dei dialoghi di gestione categorie/sottocategorie sulla versione Web/Cloud.

### v0.43.01 (31/01/2026)
- **HOTFIX Web/Cloud**:
    - **Export Backup**: Risolto errore "No such file or directory" durante il salvataggio del backup su versioni Web/Cloud. Il sistema ora utilizza correttamente la cartella temporanea per avviare il download nel browser.

### v0.43.00 (31/01/2026)
- **Gestione Carte & Spese**:
    - **Fix Conti Tecnici**: Risolto bug che manteneva visibile il conto "Saldo" delle carte eliminate nei menu a tendina.
    - **Filtri Migliorati**:
        - **Nuova Transazione**: Nascosti automaticamente i conti tecnici (Saldo carte), fondi pensione e investimenti dal menu di selezione conto.
        - **Nuova Carta**: Il menu per collegare un conto di addebito ora mostra correttamente solo i Conti Correnti e di Risparmio (risolto problema di visualizzazione).
        - **Giroconti**: Nascosti i conti tecnici delle carte anche dal menu di destinazione dei giroconti.

### v0.42.04 (30/01/2026)
- **Miglioramenti UI**:
    - **Date Picker Esteso**: Ampliato il range di date selezionabili (1980-2050) per permettere l'inserimento di mutui e prestiti storici.
    - **Gestione Carte**: Corretto e migliorato il dialogo di conferma eliminazione carta (ora utilizza l'API nativa corretta).

### v0.42.03 (30/01/2026)
- **Admin Panel Improvements**:
    - **Fix Eliminazione Utenti**: Risolto bug che impediva l'eliminazione degli utenti e implementata cancellazione a cascata sicura (rimozione dati correlati).
    - **Fix Reset Password**: Corretto errore "NameError" nella funzione di reset password admin.
    - **Fix Carte**: Risolto errore nella firma del metodo di aggiornamento della vista Carte (TypeError).

### v0.42.02 (30/01/2026)
- **Security Audit & Hardening**:
    - **Password Hashing**: Migrazione completa a **PBKDF2** (standard sicuro) con aggiornamento trasparente per gli utenti ("Lazy Migration").
    - **Protezione Brute-Force**: Implementato **Rate Limiting** sui login.
        - 5 tentativi falliti: Blocco temporaneo (5 minuti).
        - 15 tentativi falliti: Sospensione account e notifica via email.
    - **Sicurezza Codice**: Audit dipendenze (aggiornamento librerie critiche), rimozione log sensibili e sanitizzazione gestione errori.

### v0.42.00 (30/01/2026)
- **Gestione Visibilità Funzioni**:
    - **Controllo Admin**: L'amministratore può ora abilitare o disabilitare specifiche funzionalità (es. Investimenti, Spese Fisse, Prestiti) per l'intera famiglia.
    - **Menu Dinamici**: Le voci disabilitate vengono automaticamente nascoste dalla barra laterale (Desktop/Web) e dal menu "Nuovo".
- **Interfaccia Utente**:
    - **Nome Utente nel Drawer**: Il menu laterale ora mostra correttamente il nome e cognome dell'utente (o l'username) invece del generico "Utente".
    - **Etichette Corrette**: Rinominata la voce "Nuovo Salvadanaio" in "Nuovo Piano di Risparmio" per maggiore chiarezza.
- **Info & Supporto**:
    - Aggiunto indirizzo email di supporto ufficiale: `budgetamico@gmail.com`.
- **Miglioramenti Admin Panel**:
    - **DB Stats**: Nuova "whitelist" per mostrare solo le tabelle rilevanti e nascondere quelle di sistema. Aggiunta ricerca e ordinamento.
    - **Gestione Utenti e Famiglie**: Aggiunte funzionalità di ricerca (testuale) e ordinamento colonne per facilitare la gestione.

### v0.41.00 (30/01/2026)
- **Monitoraggio e Statistiche**:
    - **Statistiche Database**: Nuova tab nel pannello Admin per visualizzare dimensioni e righe delle tabelle e la dimensione totale del DB.
    - **Stato Koyeb**: Collegamento diretto alla dashboard di monitoraggio Koyeb per controllare le performance del servizio.
- **Controlli Admin Avanzati**:
    - **Sospensione Utenti**: Nuova funzionalità per sospendere temporaneamente l'accesso agli utenti. Colonna "Sospeso" e azioni dedicate nel pannello admin.
    - **Protezione Cancellazione Famiglia**: Impedita la cancellazione accidentale di famiglie che hanno ancora membri associati.
    - **Autenticazione Azioni Sensibili**: Tutte le operazioni distruttive (elimina utente/famiglia, sospendi, reset password) ora richiedono la conferma tramite **Password Admin**.
    - **Database**: Migrazione automatica (v22) per supportare lo stato di sospensione.

### v0.40.00 (29/01/2026)
- **Sistema Logging su Database**:
    - **Tabella Log_Sistema**: Nuova tabella PostgreSQL per logging centralizzato con conservazione 30 giorni.
    - **DBLogger**: Nuovo modulo `utils/db_logger.py` per scrittura asincrona log su database.
    - **Pannello Admin**: Interfaccia web `/admin` per visualizzare, filtrare e gestire i log di sistema.
    - **Autenticazione Admin**: Accesso protetto con credenziali configurabili via variabili d'ambiente (`ADMIN_USERNAME`, `ADMIN_PASSWORD`).
    - **Pulizia Automatica**: Eliminazione automatica log più vecchi di 30 giorni (schedulata ogni 24 ore).
    - **Integrazione BackgroundService**: Tutti i job automatici (spese fisse, aggiornamento asset) ora loggano su database.
    - **Logger Configurabili**: Possibilità di abilitare/disabilitare il logging per singoli componenti.

### v0.39.00 (28/01/2026)
- **Web App - Navigazione Completa**:
    - **Allineamento Desktop**: La sidebar Web ora include tutte le pagine disponibili su Desktop (Prestiti, Immobili, Contatti, Calcolatrice).
    - **FAB Menu Espanso**: Aggiunte opzioni rapide per creare Prestiti, Immobili e Contatti dal pulsante "+".
    - **Dialoghi Correttamente Registrati**: Tutti i dialoghi (Portafoglio, Prestiti, Immobili, Spese Fisse) ora correttamente inizializzati nel controller Web.
- **Controllo Accessi**:
    - **Pagina Calcolatrice**: Visibile solo per l'utente ID 16.
    - **Pagina Contatti**: Ora accessibile a tutti gli utenti.

### v0.38.05 (27/01/2026)
- **Web App - Navigazione Drawer**:
    - **Menu Laterale**: Sostituita la barra di navigazione in basso (troppo affollata) con un elegante menu laterale a scomparsa (Drawer).
    - **Hamburger Menu**: Nuova icona ☰ nell'AppBar per aprire il Drawer.
    - **Header Utente**: Il Drawer mostra nome utente e ID nella parte superiore.
- **Grafici Responsivi**:
    - **Storico Asset e Monte Carlo**: Corretti layout che causavano overflow orizzontale su schermi piccoli. I grafici ora si adattano correttamente.
- **Admin Tab**:
    - **Fix Switch Automazione Cloud**: Corretto bug che mostrava lo switch sempre su "OFF" anche quando l'automazione era già attiva nel database.
- **Schede Aggiuntive Web**:
    - Aggiunte le schede **Admin** e **Impostazioni** alla Web App (visibili in base al ruolo).

### v0.37.00 (25/01/2026)
- **Automazione Cloud (BETA)**:
    - **Server-Side Background Tasks**: Introdotta la possibilità di eseguire operazioni automatiche direttamente sul server (Koyeb/Cloud) senza la necessità di effettuare il login client.
    - **Chiave Famiglia Sicura**: Implementato un sistema seguro per archiviare una copia criptata della chiave di decrittazione famigliare sul server (protetta da Server Secret Key), permettendo al backend di operare in autonomia.
    - **Funzionalità Supportate**:
        - Addebito automatico delle **Spese Fisse** alla scadenza.
        - Aggiornamento periodico dei prezzi degli **Asset Finanziari** (Investimenti).
    - **Pannello Admin**: Aggiunta la sezione "Backup / Export" > "Automazione Cloud" per attivare/disattivare questa funzionalità (opt-in).

### v0.36.00 (25/01/2026)
- **Spese Fisse**:
    - **Giroconti Automatici**: È ora possibile pianificare **Giroconti** automatici nelle Spese Fisse, trasferendo fondi periodicamente tra conti personali o condivisi (anche verso conti Risparmio).
    - **Interfaccia Migliorata**: Aggiunto selettore "Tipo Operazione" (Spesa vs Giroconto) e selezione del conto beneficiario.
- **Bug Fix**:
    - **DatePicker**: Risolto crash critico del calendario in `PortafoglioDialogs` e `AccountTransactionsDialog` causato da un aggiornamento delle librerie.
    - **Migrazione Database**: Eseguiti script correttivi per allineare lo schema del database con le nuove funzionalità.

### v0.35.00 (24/01/2026)
- **Web App**:
    - **Gestione Conti**: Aggiunta la pagina "Conti" anche nella versione Web, permettendo la gestione completa (creazione, modifica, visualizzazione) dei conti direttamente dal browser.
- **Interfaccia Utente**:
    - **Selettore Data**: Aggiunto un calendario pop-up (Date Picker) per la selezione della data nelle transazioni, rendendo l'inserimento più rapido e preciso.
- **Bug Fix**:
    - **Analisi Budget**: Corretto il calcolo delle "Spese Totali" nelle viste Analisi Mensile e Annuale, che in alcuni casi non considerava correttamente le categorie di storno o le spese condivise.

### v0.34.00 (09/01/2026)
- **Gestione Asset Avanzata**:
    - **Eliminazione Asset**: Aggiunto supporto per eliminare asset dal portafoglio (icona Cestino 🗑️) per pulizia dati e rimozione duplicati.
    - **Modifica Avanzata**: Possibilità di correggere manualmente **Quantità** e **Prezzo Medio** nel dialog di modifica (Matita ✏️).
    - **Fix Duplicati**: Risolta la creazione di asset duplicati causata da chiavi di crittografia differenti (Master Key vs Family Key).
- **Bug Fix & Stabilità**:
    - **Accantonamenti**: Risolto conflitto critico che causava ambiguità tra conti personali e condivisi con lo stesso ID durante l'assegnazione fondi.
    - **Manutenzione Dati**: Script di pulizia per salvadanai corrotti e riconciliazione transazioni carte.

### v0.33.04 (05/01/2026)
- **Login Rapido**: È ora possibile effettuare l'accesso premendo semplicemente il tasto **Invio** nei campi Username o Password.
- **Standardizzazione UI & Font**:
    - **Font Global**: Adozione globale del font **Roboto** per un'interfaccia più moderna e leggibile.
    - **Refactoring Stili**: Standardizzazione di tutti i testi (Titoli, Sottotitoli, Corpo) attraverso l'intera applicazione per garantire coerenza visiva.
    - **Investimenti**: Aggiunto titolo pagina per allineamento con il layout standard.
- **Bug Fix**:
    - Risolto crash critico nella scheda Famiglia (`AttributeError`).
    - Aggiornata gestione stili per supportare proprietà estese Flet (es. `expand`, `opacity`).
- **Gestione Conti Unificata**:
    - **Lista Unica**: I conti personali e condivisi sono ora visualizzati in un'unica lista scrollabile per una gestione più semplice e immediata.
    - **Conti Condivisi**: Chiara distinzione visiva per i conti condivisi, con etichetta "Conto Condiviso".
    - **Dialog Unificato**: Unico pannello per la creazione e modifica di conti sia personali che condivisi, con selezione dinamica del tipo.
    - **Pulizia UI**: Rimossa la voce "Conti Condivisi" dalla barra laterale, ora ridondante.
    - **Traduzioni**: Aggiornate e completate le traduzioni per la nuova gestione conti (Italiano, Inglese, Tedesco).

### v0.32.00 (03/01/2026)
- **Spese Fisse migliorate**:
    - **Visualizzazione Carte**: Se una spesa fissa è collegata a una carta, ora viene mostrato il nome della carta (es. "Visa Gold") anziché il conto tecnico sottostante.
    - **Visibilità Proprietari**: I conti e le carte di altri membri della famiglia, prima mostrati come `[ENCRYPTED]`, ora visualizzano "Conto di [Nome]" o "Carta di [Nome]" per una migliore identificazione.
- **Interfaccia Transazioni**:
    - **Ordinamento Conti**: Nei dropdown di selezione conto (Transazioni, Spese Fisse), le carte sono ora mostrate in cima alla lista per maggiore comodità, separate da una linea dai conti bancari.

### v0.31.00 (02/01/2026)
- **Gestione Carte di Credito/Debito**:
    - **Nuovo Modulo Carte**: Supporto completo per la gestione di carte di credito e debito.
    - **Aggiunta Carte**: Possibilità di aggiungere carte definendo massimale, giorno di addebito, costi di tenuta e altro.
    - **Logica di Spesa**: Le spese con carta vengono tracciate separatamente e saldate automaticamente sul conto corrente collegato nel giorno stabilito.
    - **Storico Massimali**: Tracciamento delle variazioni del massimale nel tempo.
- **Backup Database Supabase**:
    - **Script di Backup**: Nuovo strumento automatizzato per eseguire il backup completo del database Supabase.
    - **Schedulazione**: Integrazione con lo Scheduler di Windows per backup giornalieri automatici.
    - **Sicurezza**: I dati sensibili rimangono crittografati anche nel backup.
- **Interfaccia Utente**:
    - **Icone Sidebar**: Aggiornate icone per migliorare la distinzione tra sezioni (es. Prestiti vs Carte).

### v0.30.00 (31/12/2025)
- **Web Layout**:
    - **Navigazione Semplificata**: Rimossi "Conti" e "Famiglia" per una navigazione più pulita (solo Home e Budget).
    - **Header Collassabile**: L'intera sezione superiore (Patrimonio Netto + Selezione Mese) è ora collassabile sulla versione Web per massimizzare lo spazio.
    - **Info Patrimonio**: I dettagli del patrimonio (Liquidità, Investimenti, ecc.) sono collassabili e nascosti di default su Web.
    - **Divisore Pro**: Nuovo strumento per la gestione delle spese di gruppo (Travel Spending), accessibile sia dalla dashboard che dalla pagina di login (senza account). Include calcolo debiti minimi e condivisione WhatsApp.

### v0.29.01 (30/12/2025)
- **HOTFIX BUG**: Risolto problema critico che impediva il corretto salvataggio dello storico budget (errore "NotNullViolation"), causando la visualizzazione errata dei limiti (tutti a 0) nel mese corrente.

### v0.29.00 (30/12/2025)
- **Web App**:
    - **Ottimizzazione Mobile**: La dashboard e la pagina Conti ora utilizzano un layout completamente responsivo per una migliore esperienza su smartphone e tablet.
    - **Pagina Famiglia**: Anche la scheda Famiglia è stata ottimizzata per dispositivi mobili.
    - **Investimenti**: Rimossa la scheda Investimenti dalla versione Web per semplificare l'interfaccia mobile.
- **Info**: Aggiunti link diretti alla Versione Web e al repository GitHub nel pannello Informazioni.

### v0.28.00 (30/12/2025)
- **Pagina Budget Ridisegnata**:
    - **Nuova Logica Colori**: Semplificazione visiva con indicatori di stato più chiari (Verde: OK, Giallo: >100%, Rosso: >110%).
    - **Riepilogo Totale**: Nuova card "Budget Totale" che aggrega limiti e spese di tutte le categorie.
    - **Drilldown Categorie**: Cliccando su una categoria è ora possibile espandere/collassare la vista per mostrare le sottocategorie, mantenendo l'interfaccia pulita.
- **Sidebar Collassabile**:
    - **Modalità Compatta**: La barra laterale è ora compressa di default per massimizzare lo spazio utile su schermo.
    - **Menu Toggle**: Nuovo pulsante nell'AppBar per espandere temporaneamente il menu e visualizzare le etichette di testo.
    - **Tooltip**: In modalità compatta, passando il mouse sulle icone viene mostrato il nome della sezione.

### v0.27.00
- **Analisi Storica Avanzata**:
    - **Storico Esteso a 25 Anni**: È ora possibile visualizzare l'andamento storico degli asset fino a 25 anni (con opzioni 10y, 20y, 25y).
    - **Ottimizzazione Dati**: I dati salvati utilizzano una risoluzione ibrida (giornaliera recenti, mensile storici) per garantire velocità e leggerezza.
    - **Download Intelligente**: Il sistema riconosce la data di inizio trading (inception date) di ogni asset, evitando tentativi inutili di scaricare dati storici inesistenti.
- **Ricerca Asset Potenziata**:
    - **Supporto ISIN Migliorato**: La ricerca ticker ora gestisce correttamente gli ISIN con o senza suffissi di borsa (es. `IT...` o `IT....MI`), verificandoli direttamente su Yahoo Finance se la ricerca standard fallisce.
- **Analisi Monte Carlo**:
    - **Robustezza Migliorata**: Le simulazioni Monte Carlo ora utilizzano dati ricampionati su base mensile per garantire coerenza statistica anche su periodi lunghi e misti.

### v0.26.00
- **Piani Ammortamento Personalizzati**:
    - **Importazione CSV / Inserimento Manuale**: È ora possibile caricare un piano di ammortamento personalizzato (o inserirlo manualmente) per ogni prestito.
    - **Calcoli Precisi**: Il debito residuo, la quota capitale e la quota interessi vengono calcolati direttamente dal piano caricato senza approssimazioni.
    - **Interfaccia Intelligente**:
        - Pulsante rapido "Gestisci Piano Ammortamento" nel dialog del prestito.
        - Protezione campi automatici: quando è attivo un piano, importi e date sono bloccati per garantire la coerenza dei dati.
        - Visualizzazione dettagliata del residuo (Capitale + Interessi) in tutte le schede.
- **Pagamenti Automatici Potenziati**:
    - **Rispetto del Piano**: L'addebito automatico mensile ora verifica se esiste una rata specifica in scadenza nel piano di ammortamento e utilizza l'importo esatto previsto.
    - **Aggiornamento Stato**: Il pagamento automatico segna automaticamente la rata come "Pagata" nel piano.
- **Coerenza Patrimoniale**:
    - **Patrimonio Netto Reale**: I calcoli del patrimonio netto (Personale e Famiglia) ora integrano il debito residuo esatto derivante dai piani di ammortamento personalizzati.
- **Export Livellato**:
    - **Permessi Export Differenziati**: 
        - Gli utenti **Livello 2** possono esportare solo i propri dati personali e quelli condivisi.
        - Gli utenti **Livello 3** non hanno accesso all'export.
- **Gestione Utenti**:
    - **Pulizia Database**: Rimozione automatizzata di utenti di test e duplicati per mantenere l'integrità dei dati.

### v0.25.00
- **Patrimonio Immobiliare Integrato**:
    - **Pagina Personale**: Nuova riga "Patrimonio Immobile" nel riepilogo totali, mostrando il valore netto (valore immobile - mutuo residuo) della quota personale dell'utente.
    - **Pagina Famiglia**: Nuova card riepilogo per Admin/Livello1 con: Patrimonio Totale Famiglia, Liquidità Totale, Investimenti Totali e Patrimonio Immobile Totale.
    - **Esclusione Nuda Proprietà**: Gli immobili contrassegnati come "Nuda Proprietà" sono automaticamente esclusi dai calcoli del patrimonio.
    - **Quote di Proprietà**: Il calcolo tiene conto delle percentuali di proprietà e delle quote mutuo per ogni membro della famiglia.
- **Privacy Transazioni**:
    - **Nascondi Importo**: Nuova opzione "Nascondi importo in Famiglia" nel dialog di creazione/modifica transazione.
    - **Visualizzazione Riservata**: Le transazioni con importo nascosto mostrano "Riservato" invece dell'importo nella pagina Famiglia.
    - **Privacy Selettiva**: Ogni utente può decidere quali transazioni rendere visibili agli altri membri della famiglia.
- **Calcolo Liquidità Migliorato**:
    - **Saldi Reali**: La liquidità ora viene calcolata come somma dei saldi reali dei conti (transazioni + rettifica), non più dalla sola somma delle transazioni.
    - **Pro-Quota Condivisi**: Per i conti condivisi, la liquidità personale è calcolata come saldo / numero partecipanti.
    - **Esclusione Corretta**: I conti di tipo Investimento, Fondo Pensione e Risparmio sono correttamente esclusi dalla liquidità.

### v0.24.00
- **Gestione Conti Migliorata**:
    - **Nascondi Conti a Saldo Zero**: I conti con transazioni ma saldo zero possono ora essere nascosti invece che eliminati, mantenendo lo storico delle transazioni intatto.
    - **Nome Proprietario nei Giroconti**: Il dropdown destinazione nei giroconti mostra ora il nome del proprietario del conto tra parentesi (es. "BBVA (Roberta)").
    - **Esclusione Giroconti dalle Spese**: I trasferimenti tra conti (giroconti) sono ora esplicitamente esclusi dal calcolo delle spese totali mensili e annuali.
- **Sicurezza e Crittografia**:
    - **Crittografia con Family Key**: I nomi dei conti personali vengono ora criptati con la chiave famiglia, permettendo la visibilità tra tutti i membri della famiglia.
    - **Decriptazione Migliorata**: Logica di fallback per decriptare dati legacy (criptati con master_key) mantenendo la retrocompatibilità.
    - **Migrazione Trasparente**: I conti rinominati vengono automaticamente ri-criptati con la nuova chiave famiglia.

### v0.23.00
- **Manuali Utente Integrati**:
    - **Guida Rapida**: Nuovo manuale per i nuovi utenti con i primi passi essenziali (registrazione, creazione conti, prima transazione).
    - **Manuale Completo**: Documentazione dettagliata di tutte le funzionalità dell'applicazione.
    - **Accesso dall'App**: I manuali sono accessibili cliccando sul pulsante ℹ️ (Info) nella barra superiore.
    - **Formato HTML**: I manuali si aprono nel browser predefinito per una facile consultazione.
- **Bug Fix**:
    - **Nomi Utenti Prestiti**: Corretto bug che non mostrava i nomi degli utenti nella sezione "Ripartizione Quote di Competenza" del dialog prestiti/mutui.

### v0.22.00
- **Notifica Aggiornamenti Automatica**:
    - **Controllo Versione GitHub**: All'avvio, l'app controlla se è disponibile una nuova versione su GitHub Releases.
    - **Banner Aggiornamento**: Se disponibile un aggiornamento, appare un banner blu con pulsante "Scarica".
    - **Download Diretto**: Il pulsante apre il browser sulla pagina di download della nuova versione.

### v0.21.00
- **Migrazione Driver Database**:
    - **Da psycopg2 a pg8000**: Migrazione al driver PostgreSQL pure-Python per compatibilità mobile.
    - **Connection Pool Custom**: Implementato pool di connessioni thread-safe per pg8000.
    - **DictCursor Wrapper**: Cursore personalizzato che restituisce dizionari invece di tuple.
- **Preferiti Asset per Utente**:
    - **Preferiti Privati**: I ticker preferiti nel grafico storico sono ora salvati per singolo utente.
    - **Eliminazione Preferiti**: Aggiunto pulsante X rossa per rimuovere i preferiti dalla lista.
- **Bug Fix**:
    - **Fix Commit Database**: Corretto bug che annullava le modifiche al database dopo il commit.
    - **Fix NoneType Error**: Aggiunto controllo null in `InvestimentiTab` per evitare errori.

### v0.20.00
- **Ristrutturazione Livelli Utente**:
    - **Nuova Gerarchia Progressiva**: I livelli utente ora seguono una progressione lineare e intuitiva:
        | Livello | Accesso |
        |---------|---------|
        | **Livello 3** | Solo Dati Personali (ideale per bambini) |
        | **Livello 2** | + Investimenti, Prestiti, Immobili, Famiglia (riepilogo spese mensili) |
        | **Livello 1** | + Dettagli completi transazioni Famiglia |
        | **Admin** | + Gestione pannello Admin |
    - **Visibilità Tab Dinamica**: I tab Budget, Investimenti, Prestiti e Immobili sono nascosti per Livello 3.
    - **Tabella Riferimento Livelli**: Nuova tabella nel pannello Admin > Membri con i permessi per ogni livello.
    - **Descrizioni Aggiornate**: Dialog "Invita Membro" e "Modifica Ruolo" mostrano descrizioni chiare per ogni livello.
- **Permessi Spese Fisse**:
    - **Controllo Accesso Conti**: Le azioni (modifica, elimina, paga) sulle spese fisse sono disabilitate se l'utente non ha accesso al conto associato.
    - **Dropdown Conti Filtrato**: Nel dialog spesa fissa, il dropdown mostra solo i conti dell'utente e quelli condivisi a cui ha accesso.
- **Tab Famiglia per Livello 2**:
    - **Riepilogo Spese Mensili**: Gli utenti Livello 2 vedono entrate, spese totali e risparmio del mese invece del patrimonio dei membri.
    - **Filtro Mese**: Possibilità di selezionare il mese da visualizzare.
- **Logging Opzionale**:
    - **Toggle Admin**: Nuovo switch in Admin > Backup/Export per abilitare/disabilitare il logging.
    - **Default Disabilitato**: Nessun file di log generato di default per risparmiare spazio.
    - **Handler Sicuro Windows**: Risolti errori di rotazione log su Windows.

### v0.19.00
- **Ricerca Ticker con Autocomplete**:
    - **Nuovo Componente `TickerSearchField`**: Campo di ricerca intelligente che interroga Yahoo Finance in tempo reale.
    - **Filtro per Borsa**: Supporto per ricerca combinata nome + borsa (es. "Apple Milano", "Amazon XETRA").
    - **Integrazione Completa nei Dialog**:
        - Dialog "Aggiungi Operazione" (compra/vendi asset)
        - Dialog "Aggiungi Asset Esistente"
        - Dialog "Modifica Asset"
        - Tab "Andamento Storico" per ticker preferiti
    - **Compilazione Automatica Nome**: Selezionando un ticker dal dropdown, il nome dell'asset viene compilato automaticamente.
    - **Debounce Intelligente**: Ritardo di 500ms per evitare chiamate API eccessive durante la digitazione.
- **Miglioramenti Grafici Storici**:
    - **Visualizzazione Descrizione Asset**: Ticker e descrizione ora mostrati su righe separate con tooltip per nomi lunghi.
    - **Preferiti Persistenti**: I ticker preferiti vengono salvati nel client storage e ripristinati all'avvio.

### v0.18.01
- **Miglioramenti Gestione Utenti**:
    - **Soft Delete Utenti**: La rimozione di un membro ora disabilita l'account invece di eliminarlo, preservando tutti i dati storici (transazioni, nomi per riferimento).
    - **Pulsante "Rimanda Credenziali"**: Nuovo pulsante nella gestione membri per inviare nuove credenziali di accesso via email.
- **Correzioni Bug**:
    - **Spese Fisse Automatiche**: Corretto bug che registrava le transazioni con la categoria sbagliata invece della sottocategoria.
    - **Conti Condivisi Criptati**: Risolto problema di visualizzazione nomi criptati per conti creati da altri utenti autorizzati.
    - **Dialog Conto Condiviso**: Risolto errore "Column Control must be added to page first".
    - **Quote Immobili**: I nomi dei membri sono ora visibili correttamente nel dialog di ripartizione quote.
    - **SnackBar Messaggi**: Migrazione a `page.open()` per garantire la visualizzazione corretta dei messaggi di conferma.
- **Logging e Diagnostica**:
    - **Logging Login**: Tracciamento dettagliato dell'inizio sessione con stato master key e forza cambio password.
    - **Pulsante Chiusura App**: Nuovo pulsante nell'AppBar per chiudere l'applicazione con log di chiusura.

### v0.18.00
- **Performance e Caching**:
    - **Sistema Cache Stale-While-Revalidate**: I dati (categorie, sottocategorie) vengono ora memorizzati localmente in `%APPDATA%\BudgetAmico\cache.json` per un avvio quasi istantaneo.
    - **Lazy Loading Tab**: All'avvio l'app carica solo la tab visibile, le altre vengono caricate on-demand quando l'utente ci clicca.
    - **Invalidazione Automatica Cache**: La cache viene invalidata automaticamente dopo ogni operazione di scrittura (aggiunta, modifica, eliminazione di categorie/sottocategorie).
    - **Pulsante Refresh**: Nuovo pulsante 🔄 nell'AppBar per forzare l'aggiornamento manuale di tutti i dati.
- **Stabilità UI**:
    - **Risolto "Rettangolo Grigio"**: Eliminato definitivamente il problema del rettangolo grigio che appariva durante la chiusura dei dialog.
    - **Dialoghi Moderni**: Migrazione dei dialog a `page.open()`/`page.close()` per una gestione più affidabile.
    - **Fix NoneType Errors**: Corretti errori in `subtab_budget_manager.py` relativi a riferimenti pagina nulli.

### v0.17.00
- **Stabilità, Sicurezza e Logging**:
    - **Logging Completo**: Implementazione di un sistema di logging rotativo (conservazione 48h) in `%APPDATA%\BudgetAmico\logs`. Tracciamento dettagliato di errori, operazioni critiche e flusso UI per facilitare il debug.
    - **Database Cleanup**: Risolto un bug critico negli script di pulizia database che causava errori di decrittazione (`InvalidToken`) dopo la ri-registrazione utente.
    - **Row Level Security (RLS)**: Abilitata e configurata la sicurezza a livello di riga su tutte le tabelle critiche, incluse `QuoteImmobili` e `QuotePrestiti`, garantendo che gli utenti accedano solo ai dati della propria famiglia.
    - **UI Debugging**: Aggiunti strumenti diagnostici per monitorare il ciclo di vita degli overlay di caricamento e risolvere problemi di interfaccia (es. "rettangolo grigio").
- **Sicurezza SMTP e Inviti**:
    - **SMTP per Famiglia**: Ogni famiglia ha ora la propria configurazione SMTP, criptata con la chiave server per permettere il recupero password senza contesto utente.
    - **Invito Membri Asincrono**: L'invio email per l'invito membri ora avviene in background, il dialog si chiude immediatamente.
    - **Chiavi Complete per Utenti Invitati**: Gli utenti invitati ora ricevono correttamente `encrypted_master_key_recovery` e `encrypted_master_key_backup` per il recupero password.
    - **Privacy Dati Utente**: I campi legacy `email` e `username` ora sono `NULL` nel database - usiamo solo i campi criptati `*_bindex` e `*_enc`.
- **UI/UX**:
    - **Spinner Uniformati**: Stile inline leggero (cerchio blu) per tutti gli spinner di caricamento.
    - **Feedback Pulsanti**: Disabilitazione pulsanti durante operazioni critiche (login, registrazione, recupero password, salvataggio SMTP) per prevenire click multipli.
    - **Chiusura Dialog Corretta**: I dialog (invito membri, modifica ruolo) ora si chiudono correttamente in tutti i percorsi usando `page.close()`.

### v0.16.00
- **Miglioramenti Tecnici e Qualità del Codice**:
    - **Type Hinting Completo**: Estesa la copertura dei type hints a tutte le funzioni critiche del database per una maggiore robustezza e prevenzione bug.
    - **Refactoring Codebase**: Rimozione di funzioni duplicate e codice legacy (es. vecchie implementazioni di `registra_utente`).
    - **Documentazione**: Potenziata la documentazione inline per le funzioni di gestione database, sicurezza e budget.
    - **Verifica Automatica**: Introduzione di script di verifica per garantire la coerenza delle firme delle funzioni.

### v0.15.00
- **Sicurezza e Privacy (Major Update)**:
    - **Blind Indexing**: Username ed Email sono ora salvati in modo cifrato (non leggibili in chiaro sul DB) ma ricercabili tramite hash sicuri, garantendo massima privacy anche in caso di accesso non autorizzato al DB.
    - **Architettura Server Key**: Introdotta una chiave di sistema (`SERVER_SECRET_KEY`) per gestire funzioni privilegiate come il **Recupero Password** e la **Visibilità Nomi Famiglia** senza compromettere la crittografia End-to-End dei dati personali.
    - **Recupero Password Sicuro**: Il reset della password via email ora ri-cripta correttamente le chiavi di sicurezza, prevenendo la perdita dei dati storici.
    - **Inviti Sicuri**: Corretto il flusso di invito per garantire che i nuovi membri vengano creati immediatamente con gli standard di sicurezza (Blind Index) attivi.

### v0.14.00
- **Analisi Budget Avanzata**:
    - **Nuova Dashboard Analisi**: Pagina completamente ridisegnata con doppia vista (Mensile e Annuale).
    - **Metriche di Dettaglio**:
        - Visualizzazione chiara di Entrate, Spese, Budget allocato e Risparmio effettivo.
        - Calcolo del "Delta" (Budget - Spese) per monitorare lo scostamento.
    - **Logica Annuale Intelligente**:
        - Medie calcolate sui soli "mesi attivi" (periodi con spese registrate) per una stima più realistica.
        - Confronto automatico con l'anno precedente solo se presenti dati storici.
    - **Grafici Interattivi**: Nuovi grafici a torta con logica dinamica per visualizzare la ripartizione del budget o delle entrate.
    - **Prestazioni Ottimizzate**: Caricamento asincrono dei dati per i tab "Admin" e "Impostazioni" per un'esperienza utente fluida e reattiva senza blocchi dell'interfaccia.
    - **Gestione Nuda Proprietà**: Possibilità di contrassegnare gli immobili come "Nuda proprietà", escludendoli dai calcoli del patrimonio netto disponibile ma mantenendoli nell'inventario.
    - **Privacy e Sicurezza**:
        - Risolti problemi di visibilità dei dati familiari crittografati.
        - Migliorata la gestione del pool di connessioni database per prevenire errori sotto carico.

### v0.12.00
- **Migrazione a PostgreSQL/Supabase**:
    - **Database Cloud**: Migrazione completa da SQLite a PostgreSQL su Supabase
    - **Crittografia End-to-End**: Tutti i dati sensibili (nomi conti, importi, transazioni) sono crittografati con chiave per famiglia
    - **Multi-dispositivo**: Accesso sicuro ai dati da qualsiasi dispositivo
- **Miglioramenti UI/UX**:
    - **Stili Centralizzati**: Layout uniformato su tutte le pagine con `AppStyles.section_header()` e `PageConstants`
    - **Spinner di Caricamento**: Feedback visivo durante il cambio pagina e operazioni lunghe
- **Gestione Famiglia**:
    - **Sistema Inviti via Email**: Invita nuovi membri con credenziali temporanee
    - **Configurazione SMTP**: Impostazioni email configurabili dal pannello admin
    - **Export Dati Famiglia**: Backup della chiave famiglia e configurazioni

### v0.11.00
- **Gestione Saldi e Admin**:
    - **Rettifica Saldo (Admin)**: Nuova funzionalità riservata agli amministratori per allineare il saldo dei conti (personali e condivisi) al valore reale.
    - **Protezione Saldo Iniziale**: Il saldo iniziale dei conti non è più modificabile liberamente dopo la creazione.
- **Miglioramenti Investimenti**:
    - **Data Aggiornamento Prezzi**: Visualizzazione chiara della data e ora dell'ultimo aggiornamento prezzi.

### v0.10.00
- **Tab Investimenti Autonomo**:
    - **Separazione Completa**: I conti di tipo "Investimento" sono ora gestiti esclusivamente nel tab "Investimenti", separati dai conti personali
    - **Gestione Autonoma**: Creazione, modifica ed eliminazione conti investimento direttamente dal tab
    - **Sincronizzazione Prezzi**: Recupero automatico prezzi asset tramite API Yahoo Finance
        - Implementazione con chiamate HTTP dirette (senza dipendenze esterne complesse)
        - Sincronizzazione singola per ogni asset
        - Sincronizzazione globale per tutti gli asset
        - Compatibile con PyInstaller per eseguibili standalone
    - **Vista Unificata**: Tutti i portafogli visibili in un'unica schermata con statistiche aggregate
    - **Gestione Errori**: Supporto per ticker internazionali con suffissi di mercato (es. `.MI`, `.L`, `.DE`)
