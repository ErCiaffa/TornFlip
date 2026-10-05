# Data Sources Esterne — YATA, Arson Warehouse, DroqsDB

> Torn API non espone direttamente: (1) lo **stock corrente** dei foreign
> shop, (2) i **timing di restock storici**, (3) i **NPC loot timers**,
> (4) i **spy data** (battlestats di altri player). Questi dati esistono
> in ecosistemi terzi (crowdsourced) che vanno integrati.

## 1. YATA — yata.yt

**Cosa è**: Yet Another Torn App, gestito da Kivou (Torn ID 2000607).
Hub crowdsourced principale per dati foreign + spy. La community usa
TornPDA (~88%) e TornTools (~12%) per popolare il DB automaticamente.

### Endpoint base
```
https://yata.yt/api/v1/
```

### Error format unificato
```json
{ "error": { "error": "Message", "code": 1 } }
```
Codici:
- `1` = Server error
- `2` = User error (param sbagliati)
- `3` = Rate limit
- `4` = Torn API error (la key YATA fa pass-through verso Torn)

### Endpoint completi

#### 1.1 `GET /api/v1/loot/`
NPC loot timers (boss come Duke, Leslie, ecc.).

- **Auth**: nessuna.
- **Rate limit**: 10/h per IP.
- **Cache**: fino a quando un `hosp_out` cambia.
- **Risposta**:
```json
{
  "12345": { "hosp_out": 1717000000, "type": "Leslie", "level": 100 },
  "...": ...
}
```
- **Uso TornCiaffa**: feature **NPC Loot Watcher** → notifica quando
  un boss esce ed è loot-able.

#### 1.2 `GET /api/v1/travel/export/`
Stock corrente dei foreign shop (snapshot crowdsourced).

- **Auth**: nessuna.
- **Cache**: invalidata su `import`.
- **Risposta** (estratto):
```json
{
  "stocks": {
    "mex": {
      "update": 1717000000,
      "stocks": [
        { "id": 268, "quantity": 339, "cost": 1000, "name": "Jaguar Plushie" }
      ]
    },
    "uni": { ... }
  }
}
```
- **Codici country** (3 lettere lowercase, standard YATA):
  - `mex` Mexico, `cay` Cayman, `can` Canada, `haw` Hawaii,
  - `uni` UK, `arg` Argentina, `swi` Switzerland, `jap` Japan,
  - `chi` China, `uae` UAE, `sou` South Africa.
- **Uso TornCiaffa**: feature **Foreign Stock Live** → mostra stock
  corrente per ogni paese; **Profit Optimizer** calcola $/min.

#### 1.3 `POST /api/v1/travel/import/`
Importa stock dal proprio script (contribuire al DB).

- **Auth**: richiede status "Verified client" (Kivou approva script).
- **Body**:
```json
{
  "client": "TornCiaffa Browser Helper",
  "version": "v0.1",
  "author_name": "Ciaffa",
  "author_id": 2000607,
  "country": "uni",
  "items": [
    { "id": 268, "quantity": 339, "cost": 1000 },
    { "id": 266, "quantity": 1,   "cost": 200 }
  ]
}
```
- **Comportamento**: item assenti dalla lista → quantity 0.
- **Uso TornCiaffa**: il **browser extension/PWA** rileva quando
  l'utente è al Travel Agency abroad e fa push a YATA.

#### 1.4 `GET /api/v1/targets/export/?key=KEY`
Lista bersagli salvati nell'utente.

- **Auth**: API key YATA (settata in account).
- **Rate limit**: 10/h.
- **Risposta**:
```json
{
  "1": { "name": "Bob", "level": 20, "note": "easy mug", "color": 2, "rank": "..." }
}
```
- **Uso TornCiaffa**: import target list pre-esistente da YATA.

#### 1.5 `POST /api/v1/targets/import/`
Aggiungi/aggiorna target.

- **Auth**: API key.
- **Body**: `{ "target_id": 1, "note": "...", "color": 1 }`.
- **Note**: max 512 char.

#### 1.6 `GET /api/v1/bs/<target_id>?key=KEY`
Stima battle stats di un target.

- **Auth**: API key.
- **Cache**: 1h.
- **Risposta**:
```json
{
  "total": 12500000,
  "build": "balanced",
  "skewness": 0.05,
  "update": 1717000000
}
```
- **Uso TornCiaffa**: **Fair Fight Predictor** prima di un attacco.

#### 1.7 `GET /api/v1/spy/<target_id>?key=KEY`
Singolo spy (battle stats raw se disponibile).

- **Auth**: API key.
- **Cache**: 1h.
- **Risposta**:
```json
{
  "target_id": 1,
  "strength": 1250000,
  "defense": 900000,
  "speed": 1500000,
  "dexterity": 700000,
  "faction": { "id": 8076, "name": "Faction" },
  "update": 1717000000,
  "type": "spy"
}
```

#### 1.8 `GET /api/v1/spies/?key=KEY&faction=FID`
Tutti gli spy di una faction (DB condiviso).

- **Auth**: API key.
- **Rate limit**: **1/h** (heavy endpoint).
- **Risposta**: array di spies.

#### 1.9 `POST /api/v1/spies/import/`
Carica spy data (da revive, attack, fight log).

- **Auth**: API key + optional `secret` per spy database privato faction.
- **Body**: target stats, faction, timestamps.

#### 1.10 `GET /api/v1/faction/members/?key=KEY`
Lista membri faction con stat sharing + status.

- **Auth**: API key.
- **Cache**: 1h.
- **Risposta**:
```json
{
  "1": {
    "torn_id": 1, "name": "Player",
    "status": "Okay", "last_action": 1717000000,
    "share_nnb": true, "share_energy": true,
    "nnb": 100, "energy": 150
  }
}
```
- **Uso TornCiaffa**: **Chain Watcher** ottiene energy/status faction
  in modo aggregato (evita 100 chiamate Torn separate).

### Rate limits riepilogo YATA

| Endpoint | Rate limit |
|----------|-----------|
| `/loot/` | 10/h IP |
| `/targets/export/` | 10/h key |
| `/spies/` (multipli) | 1/h key |
| `/spy/<id>` | 1h cache |
| `/bs/<id>` | 1h cache |
| `/faction/members/` | 1h cache |

### Verified client status

Per `POST /travel/import/` serve essere "Verified Client":
1. Sviluppa lo script.
2. Apri PR/issue su [github.com/Kivou-2000607/yata](https://github.com/Kivou-2000607/yata).
3. Kivou approva e marca il client come verified.
4. Lo script può iniziare a fare import.

**Approccio TornCiaffa**:
- Submitter ufficiale: l'extension/PWA del nostro sito.
- Naming: `client: "TornCiaffa"`, version semver.
- Inviare richiesta verifica una volta in beta pubblica.

---

## 2. Arson Warehouse — arsonwarehouse.com

**Cosa è**: alternativa storica a YATA per foreign stock. Ora hostata
su `ww1.arsonwarehouse.com` (rebrand?), simile in spirito.

### API
- Endpoint principale: `/foreign-stock/` (lettura tabellare).
- Import: `POST` con `{ items: [{ item_id, quantity, cost }] }`.
- Country code: **3 lettere lowercase** (stesso schema YATA).
- Feature differenziante: l'API **detecta automaticamente** item che
  appartengono a un paese ma non sono presenti, **senza** richiedere
  di mandare entry quantity=0.

### Uso TornCiaffa
- **Cross-source validation**: confrontare YATA e Arson per detect
  inconsistenze + scegliere la fonte più fresca (timestamp più recente).
- **Fallback automatico** se uno dei due è giù.

---

## 3. DroqsDB — droqsdb.com

**Cosa è**: tool di travel optimization. Aggrega dati YATA/Arson e
calcola **trip plan ottimale**.

### Feature core
- Tabella opportunità ordinabile per:
  - Stock corrente
  - Prezzo buy / sell
  - Profit per item
  - Profit per minuto
  - Restock estimate
  - Arrival viability (sarai in tempo prima del restock?)
- Filtri: paese, item category, flight type, capacity, sell target.
- 3 sell target: **Item Market** (-5% tax), **Bazaar**, **City Shops**.
- 3 flight type: **Standard**, **Airstrip**, **Business Class** (WLT opz).

### API
- Pagina dedicata "API Docs" disponibile (da verificare access).
- Probabilmente espone gli stessi dati YATA aggregati con calcoli ROI.

### Strategia TornCiaffa
- Non duplicare il calcolo profit (Droqs lo fa bene).
- Linkare DroqsDB come "deep view" per utenti pro.
- Oppure implementare nostro calcolo nativo (richiede solo dati YATA).

---

## 4. Restock mechanics — formula

Da forum guides e benchmarks community:

### Regola 1/3 (canonica)

```
restock_time ≈ depletion_time / 3
```

Se uno stock si svuota in **30 min**, restocca in ~**10 min**.
Se uno stock si svuota in **3h**, restocca in ~**1h**.

Variante alternativa (più recente): "metà del tempo di depletion".

### Stock cap per categoria (esempi)

| Categoria | Cap shop | Note |
|-----------|---------:|------|
| Plushie | ~1.000 (cap 2.500 alcuni) | Rapido restock |
| Flower | ~10.000 | Lento restock |
| Drug | ~100-500 | Varia per drug |
| Weapon | ~10-100 | Lentissimo restock |
| Special items | ~5-20 | Rarissimo |

### Top profit items (snapshot 2025/26)

| Item | Country | Profit/h stimato |
|------|---------|------------------|
| Panda Plushie | China | ~8.619 |
| Camel Plushie | UAE | ~8.559 |
| Cherry Blossom Plushie | Japan | ~8.352 |
| Jaguar Plushie | Mexico | best ROI per minuto (38min roundtrip) |
| Monkey Plushie | Argentina | top short-flight |
| Ceibo Flower | Argentina | top short-flight |
| Tear Gas | Argentina | utility profit |
| Sheep Plushie | UK | doppia opzione plushie |
| Wolverine Plushie | UK | combo con Sheep |

---

## 5. Architettura integrazione TornCiaffa

```
                  ┌──────────────────────────┐
                  │      WORKER POOL         │
                  │  yata.foreign.fetch  ┌───┼─→ yata.yt/api/v1/travel/export/
                  │  yata.loot.fetch     ├───┼─→ yata.yt/api/v1/loot/
                  │  yata.spies.sync     ├───┼─→ yata.yt/api/v1/spies/
                  │  yata.targets.sync   ├───┼─→ yata.yt/api/v1/targets/...
                  │  arson.foreign.fetch ├───┼─→ arsonwarehouse.com
                  │  droqs.opportunity   └───┼─→ droqsdb.com (opt)
                  └────────────┬─────────────┘
                               │
                ┌──────────────▼──────────────┐
                │  ETL / dedup / merge        │
                │  - timestamp picks newer    │
                │  - cross-source validation  │
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │   POSTGRES                  │
                │   foreign_stock_snapshots   │
                │   foreign_restock_events    │
                │   spy_database              │
                │   loot_timers               │
                └──────────────┬──────────────┘
                               │
                ┌──────────────▼──────────────┐
                │   API interna               │
                │   /api/foreign/best         │
                │   /api/foreign/country/:c   │
                │   /api/foreign/item/:id     │
                │   /api/loot/active          │
                │   /api/spy/:targetId        │
                └─────────────────────────────┘
```

### Schema DB

```sql
-- snapshot foreign stock
foreign_stock_snapshots(
  id bigserial pk,
  source enum('yata','arson','manual'),
  country char(3),
  item_id int,
  quantity int,
  cost bigint,
  fetched_at timestamptz,
  index (country, item_id, fetched_at DESC)
)

-- eventi restock derivati (transizione 0 → N)
foreign_restock_events(
  id bigserial,
  country char(3),
  item_id int,
  restock_qty int,
  detected_at timestamptz,
  prev_zero_since timestamptz,
  index (country, item_id, detected_at DESC)
)

-- depletion events (transizione N → 0)
foreign_depletion_events(
  id bigserial,
  country char(3),
  item_id int,
  depleted_at timestamptz,
  prev_full_since timestamptz
)

-- spy DB
spy_data(
  target_id int pk,
  strength bigint, defense bigint, speed bigint, dex bigint,
  total bigint, source enum('yata','self'),
  fetched_at timestamptz
)

-- loot timer NPC
npc_loot(
  npc_id int pk,
  npc_name text,
  hosp_out timestamptz,
  level int,
  fetched_at timestamptz
)
```

### Calcolo restock-time stimato

Per ogni `(country, item_id)`:

```sql
-- depletion rate medio (item/min) dalle ultime N transizioni
avg_depletion_rate = AVG(restock_qty / EXTRACT(EPOCH FROM detected_at - prev_zero_since) * 60)
  FROM foreign_restock_events
  WHERE country=? AND item_id=?
  AND detected_at > NOW() - INTERVAL '30 days'

-- restock interval atteso (regola 1/3)
expected_restock_interval = avg_depletion_time / 3
```

---

## 6. Feature TornCiaffa (alimentate da YATA + co)

| Feature | Sorgente | Note |
|---------|---------|------|
| **Foreign Stock Live** | YATA `/travel/export/` + Arson | Grid 11 paesi × top item, refresh 1-2 min |
| **Restock Predictor** | DB snapshot interno | ETA prossimo restock per item personalizzato |
| **Profit Optimizer** | YATA + `torn/items` market | $/min ordinato; tiene conto travel time e capacity |
| **Trip Planner** | profit optimizer + travel cost | Suggerisce sequenza multi-paese (es. UK → Switzerland) |
| **Push "Item Restocked"** | event detection 0→N | Notifica push se utente sub al watch dell'item |
| **Push "Item Low Stock"** | quantity < soglia | Per item ad alta rotazione |
| **Loot Watcher (NPC)** | YATA `/loot/` | Notifica boss out → loot-able |
| **Fair Fight Predictor** | YATA `/bs/<id>` | Pre-attack FF estimate |
| **Spy Database** | YATA `/spies/` + spy locali | Faction-shared spy DB sincronizzato |
| **Target List Import/Export** | YATA `/targets/` | Sync con altri tool della community |
| **Faction Energy Live** | YATA `/faction/members/` | Aggregato senza chiamare 100 user/bars Torn |
| **Cross-Source Quality Score** | YATA vs Arson diff | Mostra "freshness" del dato (es. "ultimo update: 2min fa da YATA / 8min fa da Arson") |

---

## 7. Submitting back: contribuire al crowdsourced DB

TornCiaffa **deve restituire** i dati che raccoglie:
- Quando l'utente è al Travel Agency e visualizza stock → `POST /travel/import/` a YATA.
- Quando l'utente fa attack/revive → `POST /spies/import/` per condividere spy.

In questo modo:
- L'ecosistema cresce.
- YATA è più probabile che approvi TornCiaffa come "verified client".
- L'utente vede meno stale data (perché contribuisce).

**Implementazione**: estensione browser companion (Chrome/Firefox) o
PWA con permission "active tab" per leggere Travel Agency e Attack
pages, parsing locale, POST a YATA via proxy server-side (per nascondere
le credenziali e centralizzare il rate limit).

---

## 8. Conformità

YATA opera in pieno rispetto del ToS Torn (solo lettura, no automation).
Anche TornCiaffa deve mantenere:
- Niente auto-buy / auto-travel.
- Solo notifiche e raccomandazioni manuali.
- Logging trasparente in Settings ("dati condivisi: stock paese X").
- Opt-out totale per gli utenti che non vogliono contribuire al
  crowdsourced DB.

---

## 9. Riepilogo fonti dati esterne

| Servizio | Cosa fornisce | Auth | Rate |
|----------|---------------|------|-----|
| **Torn API** | Tutto il dato di gioco | API key personale | 100/min user, 1000/min IP, 50k/24h cloud |
| **YATA** | Foreign stock + spy + loot + faction members | API key utente YATA | 10/h-1/h endpoint-specifico |
| **Arson Warehouse** | Foreign stock alternativo | Verified client | n/a |
| **DroqsDB** | Travel opportunities precalcolate | API docs (verificare) | n/a |
| **Tornsy** | Storico prezzi stock | Pubblico | n/a |
| **TornStats** | Spy/HOF tracking | API privata | n/a |

Il pattern è: **Torn API è la verità primaria**, **YATA/Arson/Droqs**
sono il livello "community knowledge" che colma le lacune (stock
foreign, NPC, spy).
