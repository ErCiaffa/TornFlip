# ⚡ TornFlip — Personal Market Flipping Assistant

**TornFlip** è uno script e advisor personale sviluppato per analizzare il mercato di **Torn City**, identificare opportunità di profitto, monitorare prezzi anomali/sottocosto ed eseguire flipping ad alto rendimento.

---

## 🎯 Strategie di Flipping Implementate

1. **Zero-Risk Pawn Shop Arbitrage**:
   - Rileva oggetti venduti nei bazaar dei giocatori a un prezzo inferiore a quello a cui il **Banco dei Pegni / NPC** di Torn li riacquista istantaneamente (`bazaar_price < sell_price`).
   - Guadagno matematicamente certo a rischio zero.

2. **Underpriced Bazaar Deals & Dollar Bazaars**:
   - Monitora oggetti ad alta liquidità (Plushies, Fiori, Droghe come Xanax/Vicodin, Cans, Boosters, Caches) venduti con uno sconto netto rispetto alla media di mercato (`market_value`).
   - Ideale per acquistare e rivendere subito sul proprio Bazaar (tassa 0%) o sull'Item Market.

3. **Travel Arbitrage (YATA Live)**:
   - Integrazione live con YATA (`https://yata.yt/api/v1/travel/export/`) per monitorare in tempo reale stock e prezzi all'estero nei negozi di 11 paesi (Messico, Canada, UK, Cina, UAE, Sudafrica, ecc.).
   - Calcola profitto netto per run (29 item) e profitto orario effettivo (`$/hr`).

4. **Spread & Market Inefficiency**:
   - Rileva listing anomali dove il prezzo più basso è sensibilmente inferiore al 2° e 3° venditore, permettendo di acquistare l'intero stock e riposizionarlo al floor di mercato.

5. **City Shops Arbitrage**:
   - Trova oggetti nei negozi ufficiali della città (Pharmacy, Sweet Shop, Bits 'n' Bobs) acquistabili a prezzo base NPC e rivendibili sul bazaar con markup elevati.

---

## 🚀 Installazione e Configurazione

### 1. Configurazione API Key
Crea/modifica il file `.env` inserendo la tua chiave API di Torn (è sufficiente una chiave **Public** o **Limited**):

```env
TORN_API_KEY=la_tua_chiave_api_qui
MIN_PROFIT_PERCENT=8.0
MIN_PROFIT_VALUE=15000
MAX_BUY_BUDGET=100000000
POLL_INTERVAL_SECONDS=60
```

> Puoi generare la chiave su [Torn API Preferences](https://www.torn.com/preferences.php#tab=api).

---

## 💻 Utilizzo

### 🌐 Interfaccia Grafica Web (Dashboard)
Per avviare la nuova interfaccia grafica moderna con dark mode e aggiornamenti live:

```bash
python3 app.py
# oppure
python3 main.py web
```
Poi apri nel browser: **`http://localhost:5000`**

Dall'interfaccia puoi:
- Visualizzare in tempo reale il **Radar Affari** (Zero-Risk Pawn, sconti su bazaar, spread gaps).
- Cliccare **"Compra"** per aprire direttamente il bazaar del venditore su Torn.
- Consultare la matrice **Travel Flipping** live con slider per la capienza valigia (da 5 a 29 slot).
- Controllare i **City Shops** di Torn per arbitraggio immediato da negozio NPC.
- Usare il **Calcolatore Margine e Tasse** (confronto 0% bazaar vs 5% item market).
- Impostare la tua API Key e personalizzare soglie e budget direttamente dalla UI.

---

### ⌨️ Comandi CLI (Terminale)

# 2. Opportunità di viaggio live (senza bisogno di API key, dati YATA in tempo reale)
python3 main.py travel

# 3. Sincronizzazione catalogo oggetti (richiede API key una tantum)
python3 main.py sync

# 4. Scansione istantanea degli affari di mercato sui bazaar
python3 main.py scan

# 5. Controllo negozi della città (Pharmacy, Sweet Shop, ecc.)
python3 main.py city

# 6. Monitoraggio continuo in background (allerta quando compaiono deal)
python3 main.py monitor

# 7. Visualizza lo storico degli affari trovati
python3 main.py deals
```

---

## 📂 Struttura del Progetto

- `main.py`: CLI principale e visualizzazione tabelle formattate.
- `analyzer.py`: Motore di calcolo margini, ROI e regole di arbitraggio.
- `torn_api.py`: Client per le API ufficiali di Torn con token-bucket e rate limiter (rispetta il limite di 100 req/min).
- `external_sources.py`: Connettori per dati crowdsourced (YATA travel export, weav3r.dev).
- `database.py`: Database SQLite locale (`tornflip.db`) per memorizzazione oggetti, snapshot e storico affari.
- `docs/`: Documentazione conservata sulle API di Torn, meccaniche di viaggio, droghe/consumabili e data sources esterne.
