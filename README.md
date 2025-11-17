# BudgetAmico
BudgetAmico è un'applicazione desktop completa per la gestione delle finanze personali e familiari. L'obiettivo principale è fornire agli utenti uno strumento unico e centralizzato per tracciare entrate e uscite, monitorare l'andamento del proprio patrimonio, gestire debiti e investimenti, e collaborare alla gestione del budget familiare.
L'applicazione è progettata per essere multi-utente, con un sistema di "famiglie" che permette a più persone di condividere la visibilità su conti e spese comuni, pur mantenendo la privacy sui conti personali.
Funzionalità Principali
Il progetto è strutturato attorno a un dashboard a schede che organizza le diverse aree di gestione finanziaria.
1. Gestione Utenti e Famiglia:
  - Autenticazione: Sistema di registrazione e login per gli utenti.
  - Creazione Famiglia: Il primo utente registrato può creare una "famiglia", diventandone l'amministratore.
  - Inviti e Ruoli: L'amministratore può invitare altri utenti a far parte della famiglia tramite email, assegnando ruoli con diversi livelli di permesso (admin, livello1, livello2, ecc.) che limitano l'accesso a determinate informazioni.
2. Gestione Finanziaria di Base:
  - Conti Personali e Condivisi: Creazione e gestione di più conti, che possono essere personali (visibili solo al proprietario) o condivisi (visibili a tutta la famiglia o a un gruppo specifico di utenti).
  - Tipologie di Conto: Supporto per diversi tipi di conto, tra cui conti correnti, risparmi, investimenti e fondi pensione.
  - Gestione Transazioni: Un dialogo centrale permette di inserire nuove transazioni (spese o incassi), associandole a un conto e a una categoria.
  - Giroconti: Funzionalità per trasferire fondi tra i vari conti (personali e condivisi).
  - Spese Fisse: Possibilità di definire spese ricorrenti (es. affitto, abbonamenti) che vengono registrate automaticamente ogni mese.
3. Tracciamento del Patrimonio (Asset Tracking):
  - Gestione Prestiti e Mutui: Creazione e monitoraggio di prestiti, finanziamenti e mutui, con indicazione dell'importo residuo, delle rate pagate e del progresso totale.
  - Gestione Immobili: Censimento degli immobili di proprietà, con tracciamento del valore di acquisto e del valore attuale. È possibile collegare un mutuo a un immobile per calcolarne il valore netto.
  - ortafogli di Investimento: Per i conti di tipo "Investimento", è disponibile un'interfaccia dedicata per gestire un portafoglio di asset (azioni, criptovalute, ecc.), tracciando quantità, prezzo di acquisto, prezzo attuale, e calcolando guadagni e perdite (G/L).
5. Budgeting e Analisi:
  - Dashboard Riepilogativa: La schermata principale offre una visione d'insieme del patrimonio netto, della liquidità e del valore degli investimenti, sia a livello personale che familiare.
  - Budget Mensile: L'amministratore può impostare limiti di spesa mensili per categoria, che vengono poi tracciati e visualizzati.
  - Storico e Filtri: Le viste delle transazioni e del budget permettono di filtrare i dati per mese e anno.
6. Gestione Dati e Impostazioni:
  - Backup e Ripristino: Funzionalità per creare un backup locale del database SQLite e per ripristinarlo.
◦
Sincronizzazione con Google Drive (prevista): Il codice include le basi per l'autenticazione con Google e la sincronizzazione del database su Google Drive, per garantire la portabilità dei dati.
◦
Esportazione Dati: Possibilità di esportare i dati finanziari in formato Excel.
◦
Localizzazione: Il sistema è predisposto per supportare più lingue e valute, utilizzando un gestore di localizzazione (LocalizationManager).
Architettura Tecnica
•
Framework UI: Flet, un framework Python che permette di creare applicazioni multi-piattaforma (desktop, web, mobile) con un'interfaccia utente moderna.
•
Linguaggio: Python per tutta la logica applicativa.
•
Database: SQLite come database locale (budget_familiare.db), gestito tramite la libreria standard sqlite3. Questo lo rende un'applicazione serverless e facilmente portabile.
•
API Esterne:
◦
Google Drive API: Per le funzionalità di backup e sincronizzazione del database.
◦
Gmail API: Per l'invio delle email di invito ai nuovi membri della famiglia.
Struttura del Progetto
Il codice è organizzato in modo modulare per separare le responsabilità:
•
main.py: Punto di ingresso dell'applicazione, imposta la pagina Flet e avvia il controller principale.
•
app_controller.py: Il "cervello" dell'applicazione. Gestisce il routing, lo stato della sessione, e coordina l'interazione tra le viste, i dialoghi e il database.
•
views/: Contiene le classi per le schermate principali (es. DashboardView, AuthView).
•
tabs/: Ogni file definisce una delle schede visualizzate nel dashboard (es. tab_conti.py, tab_prestiti.py).
•
dialogs/: Contiene le classi per tutte le finestre di dialogo modali usate per creare o modificare dati (es. TransactionDialog, ImmobileDialog).
•
db/: Moduli per l'interazione con il database.
◦
gestione_db.py: Contiene tutte le funzioni per leggere e scrivere dati (CRUD).
◦
crea_database.py: Definisce lo schema del database e lo crea se non esiste.
•
utils/: Moduli di utilità, come localization.py per la gestione delle lingue.
