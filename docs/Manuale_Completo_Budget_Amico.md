# Manuale Completo Budget Amico v0.48.00

## Indice

### Non vedo alcune sezioni
- Verifica il tuo ruolo (visibile in Impostazioni)
- **Funzioni Disabilitate**: Alcune sezioni (es. Investimenti, Prestiti) potrebbero essere state disabilitate per semplificare l'interfaccia.

### L'app si avvia lentamente

1. [Introduzione](#1-introduzione)
2. [Registrazione e Accesso](#2-registrazione-e-accesso)
3. [Dashboard e Navigazione](#3-dashboard-e-navigazione)
4. [Gestione Conti (Personali e Condivisi)](#4-gestione-conti-personali-e-condivisi)
5. [Carte](#5-carte)
6. [Transazioni e Categorie](#6-transazioni-e-categorie)
7. [Budget Mensile](#7-budget-mensile)
8. [Spese Fisse](#8-spese-fisse)
9. [Investimenti e Portafogli](#9-investimenti-e-portafogli)
10. [Prestiti e Mutui](#10-prestiti-e-mutui)
11. [Immobili](#11-immobili)
12. [Gestione Famiglia](#12-gestione-famiglia)
13. [Impostazioni e Privacy](#13-impostazioni-e-privacy)
14. [Backup e Sicurezza](#14-backup-e-sicurezza)
15. [Divisore Pro](#15-divisore-pro)
16. [FAQ e Risoluzione Problemi](#16-faq-e-risoluzione-problemi)

---

## 1. Introduzione

### Cos'è Budget Amico?

Budget Amico è un'applicazione per la gestione completa del budget personale e familiare. Ti permette di:

- ✅ Tracciare entrate e uscite su più conti
- ✅ Impostare e monitorare budget mensili
- ✅ Gestire investimenti e portafogli
- ✅ Tenere traccia di mutui e prestiti
- ✅ Catalogare i tuoi immobili
- ✅ Condividere dati finanziari con la famiglia
- ✅ Esportare report in Excel

---

## 2. Registrazione e Accesso

### 2.1 Creare un Account

1. Avvia Budget Amico
2. Clicca su **"Non hai un account? Registrati"**
3. Compila il modulo di registrazione:
   - **Nome** e **Cognome**: verranno automaticamente normalizzati (es. Mario Rossi).
   - **Username**: identificativo univoco per il login.
   - **Email**: necessaria per la verifica e il recupero password.
   - **Password**: l'app valuterà la forza della tua password durante la digitazione.
4. Clicca su **"Registrati"**

### 2.2 Verifica Email
Dopo la registrazione, il sistema invierà un **codice di verifica a 6 cifre** alla tua email. Inserisci il codice nell'applicazione per attivare il tuo profilo. Senza questa verifica, non potrai accedere ai dati.

### 2.3 Recovery Key

Dopo la registrazione e verifica, ti verrà mostrata una **Recovery Key** di 24 caratteri.

> ⚠️ **IMPORTANTE**: Conserva questa chiave in un luogo sicuro! È l'unico modo per recuperare i tuoi dati se dimentichi la password.

### 2.4 Login

1. Inserisci **Username** (o Email)
2. Inserisci **Password**
3. Clicca **"Accedi"** oppure premi **Invio** sulla tastiera

---

## 3. Dashboard e Navigazione

### 3.1 Layout della Dashboard

La dashboard è composta da:

| Area | Descrizione |
|------|-------------|
| **Barra superiore (AppBar)** | Titolo, pulsanti azioni rapide, logout |
| **Barra laterale (Sidebar)** | Navigazione tra le sezioni |
| **Area contenuti** | Visualizzazione della sezione selezionata |
| **FAB (+)** | Pulsante per azioni rapide |

### 3.2 Navigazione Sidebar

La sidebar mostra le sezioni disponibili. È possibile espanderla cliccando sul pulsante **Menu** (☰).

- **Tutti gli utenti**: Dashboard, I Miei Conti, Spese Fisse, Budget, Investimenti, Prestiti, Immobili, Famiglia, Privacy, Impostazioni.

---

## 4. Gestione Conti (Personali e Condivisi)

### 4.1 Creare un Conto

1. Vai in **"I Miei Conti"**
2. Clicca sul pulsante **"+ Aggiungi Conto"**
3. Seleziona se il conto è **Personale** o **Condiviso**.

---

## 5. Carte
  
Il modulo **Carte** permette di gestire carte di credito o debito, monitorare il saldo "da saldare" e impostare l'addebito automatico sul conto di appoggio.

---

## 6. Transazioni e Categorie

Le transazioni possono essere registrate con segni (+/-) per entrate e uscite. Il sistema supporta categorie e sottocategorie per un'organizzazione capillare.

---

## 7. Budget Mensile

### 7.1 Nuova Interfaccia
Le categorie del budget supportano il **Drilldown**: clicca su una categoria principale per vedere il dettaglio delle sottocategorie e gestire i limiti di spesa.

---

## 8. Spese Fisse

Gestisci i tuoi abbonamenti. Se attivi l'**Addebito automatico**, il sistema genererà la transazione il giorno della scadenza.

---

## 9. Investimenti e Portafogli

Tieni traccia di azioni, ETF e criptovalute. Il sistema recupera automaticamente i prezzi di mercato.
- **Supporto Storico**: Dati storici fino a 25 anni.
- **Simulazione Monte Carlo**: Proiezione statistica del portafoglio futuro.

---

## 10. Prestiti e Mutui

Gestisci i tuoi finanziamenti. È possibile caricare un **Piano di Ammortamento** CSV per una precisione millimetrica sul debito residuo e sulla ripartizione tra capitale e interessi.

---

## 11. Immobili

Cataloga le tue proprietà e nuda proprietà. Il valore degli immobili viene conteggiato nel tuo patrimonio netto totale.

---

## 12. Gestione Famiglia

Visualizza il patrimonio consolidato della tua famiglia.
- **Privacy**: Negli estratti conto comuni, i dettagli dei conti personali di altri membri rimangono oscurati (es. "Conto di [Nome]").

---

## 13. Impostazioni e Privacy

### 13.1 Pagina Privacy
Una nuova sezione dedicata illustra come i tuoi dati vengono protetti.
- **Crittografia**: Tutti i dati sensibili sono cifrati localmente prima dell'invio al database.
- **Codici Univoci**: Per garantire l'anonimato, l'applicazione utilizza codici identificativi criptati invece di mostrare i veri ID database.

### 13.2 Cancellazione Account
Dalla sezione Impostazioni è possibile richiedere la cancellazione definitiva del proprio account. Verranno rimossi a cascata tutti i dati associati, inclusi transazioni, conti e asset.

---

## 14. Backup e Sicurezza

### 14.1 Backup via Email
È possibile inviare un backup completo dei propri dati familiari al proprio indirizzo email in formato JSON. Questo backup contiene i dati decriptati per permetterti una conservazione sicura e leggibile al di fuori dell'app.

### 14.2 Sicurezza Password
Il sistema richiede password che rispettino criteri di complessità configurati per la sicurezza della tua famiglia.

---

## 15. Divisore Pro

Strumento per la gestione delle spese di gruppo (viaggi, cene). È accessibile anche senza login dalla pagina iniziale.

---

## 16. FAQ e Risoluzione Problemi

Per bug o richieste funzionalità, riferirsi al canale GitHub ufficiale del progetto.

---

*Budget Amico - *Versione documento: 0.48.00*
*Sviluppato con ❤️ da Iscavar79*
