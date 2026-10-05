# Travel & Foreign Markets

Riferimenti: [Travel Wiki](https://wiki.torn.com/wiki/Travel),
[Business Class Ticket](https://wiki.torn.com/wiki/Business_Class_Ticket).

## 1. Metodi di viaggio

| Metodo | Costo | Tempo | Item capienza | Sblocco |
|--------|-------|------|---------------|---------|
| Standard | per trip | base | 5 | Default |
| Airstrip | gratis | -30% | 15 | PI + Airstrip + Pilot |
| Private (WLT) | gratis | -50% | 15 | 1 benefit block WLT (~7.5-8B$) |
| Business Class (BCT) | BCT/trip | -70% | 15 | BCT acquistabile (rarità) |

> Per il sito: mostrare quanto stai pagando in tempo/€ tra metodi
> alternativi, costo equivalente di un upgrade (es. break-even WLT
> block vs BCT continuativo).

## 2. Destinazioni

12 paesi:

| Paese | Tempo std (~min) | Famoso per |
|-------|-----------------:|------------|
| Mexico | ~25 | Drugs entry, Cocaine market base |
| Cayman Islands | ~35 | Banking interest bonus, Flowers |
| Canada | ~40 | Hunting items, plushies |
| Hawaii | ~135 | Big Kahuna burger, Aloha |
| United Kingdom | ~160 | Newspaper, donatorpacks |
| Argentina | ~170 | Steaks, leather |
| Switzerland | ~175 | Luxury watches, chocolate |
| Japan | ~225 | Sake, Plushies, weapons |
| China | ~240 | Drugs, rare books, items |
| UAE | ~270 | Diamonds (jewelry), oil |
| South Africa | ~300 | Cesium, mining items |
| (event) | varia | Antarctica, etc. |

(Numeri standard; ridotti del fattore travel method.)

## 3. Shop esteri

Suddivisi in **3 tipi**:

- **General Store** — souvenir, flowers, plushies, normal items.
- **Arms Dealer** — weapons & armor specifici del paese.
- **Black Market** — drugs, contraband (cesium, jewelry sospetti).

Ogni shop ha:
- **Stock limitato** (item count visibile).
- **Restock** ciclico o irregolare (alcuni item gold-tier).
- **Prezzo locale** + **valore market Torn** → profit opportunity.

## 4. Foreign restock & profit

Pattern advisor:
1. Polling `market/{itemID}?selections=bazaar`/`itemmarket` per stimare
   il prezzo a Torn.
2. Tabella `torn/items` con `circulation` e `buy_price` foreign.
3. Calcolo `profit = (market_value − foreign_buy_price) * capacity`.
4. **Restock detector**: notifica push "OK X just restocked in Y, 15
   slot da 95k profit cad.".
5. **Travel planner**: mostra il break-even per BCT vs Airstrip.

## 5. Travel bonus & perks

- **Travel agency cooldown**: gli ultimi mesi hanno aggiunto un cap
  sull'orderly restock.
- **Subscription**: travel cost halved in alcune varianti.
- **Education**: Aviation course (-flight time? minimo).
- **Faction Adept tree**: -% travel time.
- **Stock Benefit "Avianoline"** etc. — verificare current Stocks 3.0.

## 6. Eventi mentre in viaggio

In flight non puoi:
- Attaccare
- Allenare
- Crimini

Puoi:
- Vendere/comprare sul market
- Forum / messaggi
- Gestire faction (con limitazioni)
- Stocks / banca

API durante volo:
- `user/travel` espone `time_left`, `destination`, `method`, `departed`.
- `user/basic` riporta `status: { state: "Traveling" }`.

## 7. Foreign stocks (Stocks 3.0)

Le **stocks** sono globali, ma alcuni benefit richiedono "viaggio +
stock detenuto". Esempi:
- **WLT** → unlock private travel (descritto sopra).
- **TCSE** → +10 vault interest %.
- **MCS** → +100 energy per block (max 10 = +1000 cap).
- **CNC** → bonus pubblicità company.
- **MSG** → +happy cap.
- **YAZ** → -company addiction.
- (lista completa in `torn/stocks` + benefit JSON).

## 8. Feature sito

| Feature | Note |
|---------|------|
| **Travel Tracker** | ETA, item capienza usata, metodo |
| **Restock Watcher** | Push su restock paese/item personalizzato |
| **Profit Optimizer** | Top N item con miglior $/min per metodo |
| **Trip Planner** | Suggerisce itinerario multi-step (es. Switzerland → Japan) |
| **BCT vs WLT vs Airstrip Calculator** | Break-even sul tuo flight volume |
| **Foreign Inventory** | Snapshot inventario foreign vs Torn |
| **Cesium/Diamond Smuggler Advisor** | Profilo high-value, risk-aware |

> **Stock crowdsourced**: i dati di stock corrente nei foreign shop
> non sono esposti da Torn API. Li otteniamo da YATA (yata.yt) e
> Arson Warehouse via API documentata in
> [`19-EXTERNAL-DATA-SOURCES.md`](./19-EXTERNAL-DATA-SOURCES.md).
> Il restock segue la regola "1/3 del depletion time".
