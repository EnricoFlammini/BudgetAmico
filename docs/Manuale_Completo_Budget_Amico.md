# Manuale Completo Budget Amico v0.30.00

## Indice

1. [Introduzione](#1-introduzione)
2. [Registrazione e Accesso](#2-registrazione-e-accesso)
3. [Dashboard e Navigazione](#3-dashboard-e-navigazione)
4. [Conti Personali](#4-conti-personali)
5. [Conti Condivisi](#5-conti-condivisi)
6. [Transazioni e Categorie](#6-transazioni-e-categorie)
7. [Budget Mensile](#7-budget-mensile)
8. [Spese Fisse](#8-spese-fisse)
9. [Investimenti e Portafogli](#9-investimenti-e-portafogli)
10. [Prestiti e Mutui](#10-prestiti-e-mutui)
11. [Immobili](#11-immobili)
12. [Gestione Famiglia](#12-gestione-famiglia)
13. [Pannello Admin](#13-pannello-admin)
14. [Impostazioni](#14-impostazioni)
15. [Backup e Sicurezza](#15-backup-e-sicurezza)
16. [FAQ e Risoluzione Problemi](#16-faq-e-risoluzione-problemi)

---

## 1. Introduzione

### Cos'è Budget Amico?

Budget Amico è un'applicazione desktop per la gestione completa del budget personale e familiare. Ti permette di:

- ✅ Tracciare entrate e uscite su più conti
- ✅ Impostare e monitorare budget mensili
- ✅ Gestire investimenti e portafogli
- ✅ Tenere traccia di mutui e prestiti
- ✅ Catalogare i tuoi immobili
- ✅ Condividere dati finanziari con la famiglia
- ✅ Esportare report in Excel

### Requisiti di Sistema

- Windows 10/11, macOS 10.14+ o Linux
- Connessione internet (per sincronizzazione)
- 100 MB di spazio libero

---

## 2. Registrazione e Accesso

### 2.1 Creare un Account

1. Avvia Budget Amico
2. Clicca su **"Non hai un account? Registrati"**
3. Compila il modulo di registrazione:
   - **Nome** e **Cognome**: i tuoi dati personali
   - **Username**: identificativo univoco per il login
   - **Email**: per recupero password e inviti familiari
   - **Password**: minimo 8 caratteri
   - **Data di nascita**: opzionale
4. Clicca su **"Registrati"**

### 2.2 Recovery Key

Dopo la registrazione, ti verrà mostrata una **Recovery Key** di 24 caratteri.

> ⚠️ **IMPORTANTE**: Conserva questa chiave in un luogo sicuro! È l'unico modo per recuperare i tuoi dati se dimentichi la password. Scrivila su carta e conservala separatamente dai tuoi dispositivi.

### 2.3 Login

1. Inserisci **Username** (o Email)
2. Inserisci **Password**
3. Clicca **"Accedi"**

### 2.4 Recupero Password

Se hai dimenticato la password:

1. Clicca su **"Password dimenticata?"**
2. Inserisci la tua **Email**
3. Riceverai un'email con le istruzioni
4. Segui il link per reimpostare la password

> **Nota**: Per il recupero password è necessario che l'Admin della famiglia abbia configurato le impostazioni SMTP.

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

### 3.2 Pulsanti AppBar

| Icona | Azione |
|-------|--------|
| 🔄 | Aggiorna tutti i dati dal database |
| ℹ️ | Informazioni app e manuali |
| 📥 | Esporta dati in Excel |
| 🚪 | Logout |
| ✖️ | Chiudi applicazione |

### 3.3 Navigazione Sidebar

La sidebar mostra le sezioni disponibili in base al tuo ruolo.
*   **Novità v0.28**: La sidebar è **collassabile**. Per default è compatta (solo icone). Clicca sul pulsante **Menu** (☰) in alto a sinistra per espanderla e leggere le etichette.

- **Tutti gli utenti**: Conti, Spese Fisse, Impostazioni
- **Livello 2+**: Budget, Investimenti, Prestiti, Immobili, Famiglia
- **Solo Admin**: Pannello Admin

---

## 4. Conti Personali

### 4.1 Creare un Conto

1. Vai in **"Conti Personali"**
2. Clicca **"+ Nuovo Conto"**
3. Compila:
   - **Nome conto**: nome descrittivo
   - **Tipo**: Corrente, Risparmio, Contanti, Carta di Credito
   - **Saldo iniziale**: saldo attuale
   - **Data saldo**: data di riferimento
4. Clicca **"Salva"**

### 4.2 Tipi di Conto

| Tipo | Descrizione |
|------|-------------|
| **Corrente** | Conto bancario principale |
| **Risparmio** | Conti deposito o accumulo |
| **Contanti** | Denaro fisico |
| **Carta di Credito** | Carte con saldo negativo |

> **Nota**: I conti di tipo "Investimento" e "Fondo Pensione" sono gestiti nelle rispettive sezioni dedicate.

### 4.3 Visualizzare le Transazioni

1. Clicca su un conto per espandere i dettagli
2. Usa il selettore mese per filtrare le transazioni
3. Ogni transazione mostra: data, descrizione, categoria, importo

### 4.4 Modificare/Eliminare un Conto

- **Modifica**: clicca sull'icona ✏️ accanto al conto
- **Elimina**: clicca sull'icona 🗑️

> ⚠️ L'eliminazione di un conto rimuove anche tutte le transazioni associate!

---

## 5. Conti Condivisi

I conti condivisi permettono a più membri della famiglia di registrare transazioni sullo stesso conto.

### 5.1 Creare un Conto Condiviso

1. Vai in **"Conti Condivisi"**
2. Clicca **"+ Nuovo Conto Condiviso"**
3. Compila i dati del conto
4. Seleziona i **partecipanti** (membri della famiglia)
5. Definisci le **quote di partecipazione** (percentuali)
6. Clicca **"Salva"**

### 5.2 Quote di Partecipazione

Le quote determinano come vengono suddivise le spese:
- Es. Coppia 50%/50%: le spese vengono divise equamente
- Es. Famiglia: 40%/40%/20% per tre membri

---

## 6. Transazioni e Categorie

### 6.1 Aggiungere una Transazione

**Metodo rapido:**
1. Clicca il pulsante **"+"** (FAB)
2. Seleziona **"Nuova Transazione"**
3. Compila i campi e salva

**Dalla lista transazioni:**
1. Espandi un conto
2. Clicca **"+ Aggiungi"**

### 6.2 Campi della Transazione

| Campo | Descrizione |
|-------|-------------|
| **Conto** | Il conto su cui registrare |
| **Importo** | Positivo = entrata, Negativo = uscita |
| **Data** | Data della transazione |
| **Descrizione** | Note descrittive |
| **Categoria** | Categoria principale |
| **Sottocategoria** | Sottocategoria specifica |

### 6.3 Giroconto

Per trasferire denaro tra conti (es. da Corrente a Risparmio):

1. Clicca **"+"** → **"Nuovo Giroconto"**
2. Seleziona **conto origine** e **conto destinazione**
3. Inserisci **importo** e **data**
4. Clicca **"Esegui"**

Il giroconto crea automaticamente due transazioni collegate.

---

## 7. Budget Mensile

## 7. Budget Mensile

### 7.1 Nuova Interfaccia (v0.28)
La pagina Budget è stata ridisegnata per offrirti una visione più chiara:

1.  **Riepilogo Totale**: In cima alla lista trovi una card "Budget Totale" che somma tutti i limiti e le spese del mese.
2.  **Drilldown Categorie**: Le categorie sono inizialmente chiuse. Clicca su una categoria per **espanderla** e vedere le sottocategorie.
3.  **Colori Intuitivi**:
    *   🟢 **Verde**: Spesa OK (<= 100%).
    *   🟡 **Giallo**: Attenzione (100% - 110%).
    *   🔴 **Rosso**: Criticità (> 110%).

### 7.2 Impostare un Budget

1.  Vai nella sezione **"Budget"**
2.  Clicca sulla **Categoria** per espanderla
3.  Clicca sull'importo "Budget" di una sottocategoria
4.  Inserisci il nuovo limite e conferma

### 7.3 Monitorare le Spese

La sezione Budget mostra per ogni voce:
- **Barra di progresso**: Colorata secondo la logica sopra descritta.
- **Importo Speso / Budget**: Es. "€ 150 / € 200"
- **Percentuale**: Es. "75%"
- **Riepilogo mensile**: totale entrate, spese, risparmio (nella dashboard).

### 7.3 Analisi Annuale

Clicca su **"Vista Annuale"** per vedere:
- Media mensile delle spese
- Confronto con l'anno precedente
- Trend delle categorie principali

---

## 8. Spese Fisse

Le spese fisse sono pagamenti ricorrenti come affitto, bollette, abbonamenti.

### 8.1 Aggiungere una Spesa Fissa

1. Vai in **"Spese Fisse"**
2. Clicca **"+ Nuova Spesa Fissa"**
3. Compila:
   - **Nome**: es. "Netflix", "Affitto"
   - **Importo**: costo mensile
   - **Giorno scadenza**: giorno del mese (1-28)
   - **Conto**: conto da addebitare
   - **Categoria/Sottocategoria**: per classificazione
   - **Addebito automatico**: se attivo, la transazione viene creata automaticamente

### 8.2 Gestione Automatica

Se attivi **"Addebito automatico"**, Budget Amico:
- Crea la transazione il giorno della scadenza
- Aggiorna il saldo del conto
- Registra la spesa nella categoria corretta

---

## 9. Investimenti e Portafogli

### 9.1 Creare un Conto Investimento

1. Vai in **"Investimenti"**
2. Clicca **"+ Nuovo Conto"** nella sezione portafogli
3. Compila nome e tipo (Investimento o Fondo Pensione)

### 9.2 Aggiungere Asset

1. Espandi un portafoglio
2. Clicca **"+ Aggiungi Asset"**
3. Cerca il **Ticker** (es. AAPL, VWCE.MI)
4. Inserisci: quantità, prezzo medio, data acquisto
5. Il nome viene compilato automaticamente

### 9.3 Sincronizzazione Prezzi

Budget Amico recupera i prezzi da Yahoo Finance:
- **Automatico**: all'avvio dell'app
- **Manuale**: clicca 🔄 accanto all'asset

### 9.4 Suffissi di Mercato

Per asset non americani, usa il suffisso corretto:

| Mercato | Suffisso | Esempio |
|---------|----------|---------|
| Milano | .MI | ENI.MI |
| Londra | .L | VUSA.L |
| Francoforte | .DE | VWCE.DE |
| Parigi | .PA | AIR.PA |

### 9.5 Statistiche Portafoglio

Per ogni portafoglio puoi vedere:
- Valore totale attuale
- Gain/Loss (guadagno o perdita)
- Percentuale di rendimento

### 9.6 Analisi Storica Avanzata

Nel tab "Andamento Storico" puoi visualizzare il grafico dei prezzi degli asset selezionati:
- **Periodi estesi**: Seleziona periodi fino a **25 anni** (10y, 20y, 25y) per analisi di lungo termine.
- **Risoluzione mista**: Il sistema carica dati giornalieri per gli ultimi 5 anni e mensili per lo storico profondo, garantendo velocità.
- **Download intelligente**: Se un asset è nato di recente (es. 2019), il sistema lo riconosce ed evita download inutili di dati inesistenti.

### 9.7 Simulazione Monte Carlo

Il tab "Monte Carlo" permette di proiettare l'andamento futuro del tuo portafoglio:
- **Simulazione Statistica**: Esegue migliaia di simulazioni basate sulla volatilità e rendimento storico dei tuoi asset.
- **Dati Mensili**: Utilizza rendimenti mensili per una maggiore robustezza statistica su lunghi periodi.
- **Analisi del Rischio**: Visualizza i possibili scenari futuri (pessimistico, medio, ottimistico) per pianificare i tuoi obiettivi.

---

## 10. Prestiti e Mutui

### 10.1 Aggiungere un Prestito

1. Vai in **"Prestiti"**
2. Clicca **"+ Aggiungi Prestito"** o **"+ Aggiungi Mutuo"**
3. Compila:
   - **Nome**: es. "Mutuo Casa"
   - **Importo finanziato**: capitale totale
   - **Importo interessi**: totale interessi
   - **Rata mensile**: importo rata
   - **Numero rate totali**: durata in mesi
   - **Rate rimanenti**: quante ne mancano
   - **Giorno scadenza rata**: giorno del mese

### 10.2 Ripartizione Quote

Per prestiti condivisi (es. mutuo cointestato):
1. Nella sezione **"Ripartizione Quote"**
2. Assegna la percentuale a ciascun membro
3. Le quote devono sommare al 100%

### 10.3 Pagamento Rata

Per registrare il pagamento di una rata:
1. Clicca **"Paga Rata"** accanto al prestito
2. Conferma importo e data
3. La transazione viene creata automaticamente

### 10.4 Addebito Automatico

Se attivi **"Addebito automatico"**, la rata viene registrata automaticamente alla scadenza.
Se è presente un piano di ammortamento personalizzato (vedi 10.5), il sistema utilizzerà l'importo esatto previsto per quella specifica scadenza e aggiornerà lo stato della rata nel piano.

### 10.5 Piano di Ammortamento Personalizzato

Puoi caricare o gestire manualmente il piano di ammortamento per avere calcoli precisi su quota capitale e interessi.

1.  Apri il dettaglio del prestito (Modifica).
2.  Clicca su **"Gestisci Piano Ammortamento"** (visibile subito sotto la descrizione).
3.  Nel dialog che si apre:
    *   **Importa CSV**: Carica un file CSV con le colonne (Numero, Scadenza, Importo Rata, Quota Capitale, Quota Interessi, Debito Residuo).
    *   **Aggiungi Rata**: Inserisci manualmente le singole rate.
    *   **Modifica/Elimina**: Gestisci le rate esistenti.
4.  Quando un piano è attivo, i campi riepilogativi del prestito (Rate residue, Importi) vengono calcolati automaticamente dal piano e "bloccati" per garantire coerenza.
5.  Il sistema userà questi dati per il calcolo preciso del Patrimonio Netto personale e familiare.

---

## 11. Immobili

### 11.1 Aggiungere un Immobile

1. Vai in **"Immobili"**
2. Clicca **"+ Aggiungi Immobile"**
3. Compila:
   - **Nome/Indirizzo**: identificativo
   - **Tipologia**: Appartamento, Villa, Terreno, ecc.
   - **Valore stimato**: valore di mercato attuale
   - **Nuda proprietà**: se è solo nuda proprietà

### 11.2 Nuda Proprietà

Gli immobili contrassegnati come **"Nuda proprietà"**:
- Sono evidenziati con colore diverso
- **Non** vengono inclusi nel patrimonio netto disponibile
- Rimangono visibili nell'inventario

### 11.3 Quote di Proprietà

Per immobili in comproprietà:
1. Nella sezione quote, assegna la percentuale a ogni membro
2. Il valore visualizzato è proporzionale alla quota

---

## 12. Gestione Famiglia

### 12.1 Ruoli Utente

| Ruolo | Accesso |
|-------|---------|
| **Livello 3** | Solo dati personali |
| **Livello 2** | + Investimenti, Prestiti, Immobili, Famiglia (riepilogo) |
| **Livello 1** | + Dettagli completi transazioni familiari |
| **Admin** | + Pannello Admin, gestione membri |

### 12.2 Visualizzazione Famiglia

La sezione **"Famiglia"** mostra:
- **Livello 1**: tutte le transazioni di tutti i membri
- **Livello 2**: solo riepilogo spese mensili (entrate, uscite, risparmio)

---

## 13. Pannello Admin

Accessibile solo agli utenti con ruolo **Admin**.

### 13.1 Gestione Categorie

1. Vai in **Admin** → **"Categorie"**
2. Per aggiungere: clicca **"+ Categoria"** o **"+ Sottocategoria"**
3. Per modificare: clicca ✏️
4. Per eliminare: clicca 🗑️

### 13.2 Gestione Membri

1. Vai in **Admin** → **"Gestione Membri"**
2. Visualizza tutti i membri della famiglia
3. **Invita nuovo membro**: clicca "Invita Membro", inserisci email
4. **Modifica ruolo**: clicca su un membro per cambiare livello
5. **Rimanda credenziali**: per inviare nuove credenziali via email

### 13.3 Configurazione SMTP

Per permettere l'invio email (inviti, recupero password):

1. Vai in **Admin** → **"Impostazioni Email"**
2. Compila:
   - **Server SMTP**: es. smtp.gmail.com
   - **Porta**: es. 587
   - **Username**: la tua email
   - **Password**: password app (non la password normale!)
   - **Email mittente**: indirizzo visualizzato

> **Per Gmail**: usa una "Password per le app" generata nelle impostazioni sicurezza Google.

### 13.4 Budget Manager

Gestione avanzata dei budget per categoria/sottocategoria.

### 13.5 Backup/Export

- **Esporta dati**: scarica un file Excel con tutti i dati
- **Logging**: abilita/disabilita i log di sistema

---

## 14. Impostazioni

### 14.1 Profilo Utente

Modifica i tuoi dati personali:
- Nome e Cognome
- Email
- Password

### 14.2 Conto Predefinito

Imposta il conto che viene preselezionato nelle nuove transazioni.

### 14.3 Lingua e Valuta

Cambia lingua dell'interfaccia e simbolo valuta.

---

## 15. Backup e Sicurezza

### 15.1 Crittografia

Budget Amico utilizza crittografia **End-to-End**:
- I tuoi dati sono criptati prima di essere inviati al database
- Solo tu (con la tua password) puoi decriptarli
- Nemmeno gli amministratori del server possono leggere i tuoi dati

### 15.2 Backup Manuale

Gli Admin possono esportare i dati dalla sezione **Admin** → **"Backup/Export"**.

### 15.3 Recovery Key

La Recovery Key generata alla registrazione è l'unico modo per recuperare i tuoi dati se:
- Dimentichi la password
- Il recupero via email non è disponibile

**Conservala in modo sicuro!**

---

## 16. FAQ e Risoluzione Problemi

### Non riesco ad accedere
- Verifica username e password
- Prova il recupero password via email
- Contatta l'Admin della tua famiglia

### I prezzi degli asset non si aggiornano
- Verifica la connessione internet
- Controlla che il ticker sia corretto (incluso suffisso mercato)
- Prova il refresh manuale (🔄)

### Non vedo alcune sezioni
- Verifica il tuo ruolo (visibile in Impostazioni)
- Contatta l'Admin per modificare i permessi

### L'app si avvia lentamente
- È normale al primo avvio (caricamento cache)
- Gli avvii successivi saranno più veloci

### Come cambio famiglia?
- Non è possibile cambiare famiglia
- Contatta l'Admin per essere rimosso e ricevere un nuovo invito

---

## Contatti e Supporto

- **GitHub Issues**: per segnalare bug o richiedere funzionalità
- **Email Admin**: contatta l'Admin della tua famiglia per problemi di accesso

---

*Budget Amico - *Versione documento: 0.29.00*
*Sviluppato con ❤️ da Iscavar79*
