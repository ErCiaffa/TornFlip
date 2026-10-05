# Torn API — Riferimento esaustivo

> Documento operativo. Tutti i numeri e i comportamenti sono verificati
> contro `api.torn.com/api.html`, lo Swagger v2 e il wiki ufficiale.

## 1. Endpoint base

| Versione | URL pattern |
|----------|-------------|
| v1 | `https://api.torn.com/{section}/{id}?selections={a,b,c}&key={key}` |
| v2 | `https://api.torn.com/v2/{section}/{id}/{selection}?key={key}` |

- `{id}` è opzionale per `user`, `faction`, `company` (default = owner della key).
- `selections` accetta lista comma-separata in v1; v2 lo mette nel path.
- Query opzionali comuni: `from`, `to` (UNIX timestamp), `comment`, `cat`,
  `filter`, `sort`, `limit`, `offset`.

## 2. API key — livelli di accesso

| Livello | Codice key/info | Descrizione |
|---------|-----------------|-------------|
| Public | 1 | Solo dati pubblici (profili, market public) |
| Minimal | 2 | + alcuni dati personali leggeri |
| Limited | 3 | Player tracker tipico |
| Full | 4 | Tutto, incluso faction admin, inventario completo |
| Custom | — | Selezione granulare di selection autorizzate |

> **Raccomandazione TornCiaffa**: l'onboarding genera per l'utente
> il link a `https://www.torn.com/preferences.php#tab=api` con
> preset "Custom — TornCiaffa minimum scope" che include solo le
> selection necessarie alle feature attive.

## 3. Rate limit completo

| Limite | Valore | Risorsa |
|--------|--------|---------|
| Per user (somma di tutte le sue key) | **100 req/min** | rolling 60s |
| Per IP | **1.000 req/min** | rolling 60s |
| Cloud per category | **50.000 record/24h** | rolling 24h |
| Cache server-side | **29-30s** su query identica | gratis (non consuma quota) |
| Key change | **1 cambio chiave / 60s** | per utente |

Categorie soggette al limite **cloud 50k/24h**:
- `user/attacksfull`, `user/personalstats`, `user/revivesfull`
- `faction/attacksfull`, `faction/attacknews`, `faction/news` (subcat)
- `torn/revivesfull`

**Algoritmo da implementare**: token bucket Redis con refill 100 token
ogni 60 sec; coda con priorità (live > batch); telemetria su utilizzo
% del cap.

## 4. Tabella completa codici errore Torn

| Code | Significato | Azione consigliata |
|-----:|-------------|--------------------|
| 0 | Unknown error | Log + retry singolo |
| 1 | Key is empty | Bloccare la key, prompt utente |
| 2 | Incorrect Key (formato/valore) | Bloccare la key, prompt re-input |
| 3 | Wrong type (sezione inesistente) | Bug client → log + alert |
| 4 | Wrong fields (selection inesistente) | Bug client → log + alert |
| 5 | Too many requests (100/min user) | Backoff esponenziale 5-30s |
| 6 | Incorrect ID | Validare input, mostrare 404 user |
| 7 | Incorrect ID-entity relation (private) | Mostrare "private" UI |
| 8 | IP block | Halt globale 1h, alert ops |
| 9 | API disabled (manutenzione globale) | Status page, retry ogni 5min |
| 10 | Key owner in federal jail | Notifica utente, disable key fino a release |
| 11 | Key change error (60s cooldown) | Wait 60s |
| 12 | Key read error (DB Torn) | Retry con backoff |
| 13 | Key temporarily disabled (owner offline 7gg) | Marker, notifica utente |
| 14 | Daily read limit reached (50k cloud) | Reschedule job notturno |
| 15 | Temporary error (test) | Ignorare/log |
| 16 | Access level not high enough | Mostrare CTA "upgrade key access" |
| 17 | Backend error | Retry backoff esponenziale |
| 18 | API key paused by owner | Notifica utente, disable key |
| 19 | Must migrate to Crimes 2.0 | Edge: vecchio user → instruct migrazione |
| 20 | Race not yet finished | Retry su race endpoint dopo ETA |
| 21 | Incorrect category | Validare `cat` param |
| 22 | Selection only in API v1 | Forzare downgrade per quella selection |

Fonti: [Torn API Docs](https://www.torn.com/api.html),
[Forum thread A list of API Error Codes](https://www.torn.com/forums.php?p=threads&f=63&t=16143929).

## 5. Catalogo selection per sezione

### 5.1 `user/`

| Selection | Access | Note |
|-----------|--------|------|
| `ammo` | Limited | Munizioni per arma |
| `attacks` | Limited | Ultimi 100 attacchi |
| `attacksfull` | Limited | **Cloud 50k/24h** |
| `bars` | Limited | energy/nerve/happy/life/chain |
| `basic` | Public | level, name, gender, faction.id |
| `battlestats` | Full | str/def/spd/dex + modificatori |
| `bazaar` | Public | Item nel proprio bazaar |
| `cooldowns` | Limited | drug/booster/medical |
| `crimes` | Full | Stats per ogni crime 2.0 |
| `criminalrecord` | Full | Numero successi/fallimenti per crime |
| `discord` | Limited | Discord linked id |
| `display` | Public | Display Case items |
| `education` | Limited | Course in progress + completati |
| `events` | Limited | Eventi recenti (paginabile) |
| `gym` | Public | Gym corrente |
| `hof` | Public | Posizioni hall of fame |
| `honors` | Public | Honor bars sbloccati |
| `icons` | Public | Icons profilo |
| `inventory` | Full | Inventario completo |
| `jobpoints` | Limited | Job points spendibili |
| `log` | Full | Activity log filtrabile per `cat` |
| `medals` | Public | Medaglie ottenute |
| `merits` | Limited | Merit purchased + spendable |
| `messages` | Full | Inbox |
| `missions` | Limited | Missioni Duke attive |
| `money` | Limited | wallet, bank, casino, points, vault |
| `networth` | Limited | Breakdown patrimonio |
| `newevents` | Limited | Solo nuovi dall'ultimo poll |
| `newmessages` | Limited | Solo nuovi messaggi |
| `notifications` | Limited | Notifiche Torn (push) |
| `perks` | Limited | Tutti i perk sommati (edu, faction, prop, job, merit, stock, sub, enh) |
| `personalstats` | Limited | **Cloud 50k/24h**, statistiche cumulative |
| `profile` | Public | Profilo esteso (status, faction, marriage…) |
| `properties` | Limited | Lista property owned |
| `publicstatus` | Public | Stato corrente (hospital/jail/abroad) |
| `refills` | Limited | Refill utilizzati (energy, nerve, medical, casino, drug) |
| `reports` | Full | Spy reports / company reports |
| `revives` | Limited | Lista revive ricevute/effettuate |
| `revivesfull` | Limited | **Cloud 50k/24h** |
| `skills` | Limited | racing, hunting, reviving, search |
| `stocks` | Limited | Portafoglio + benefit block status |
| `timestamp` | Public | Server time sync |
| `travel` | Limited | Dati volo corrente |
| `weaponexp` | Limited | Mastery % per arma |
| `workstats` | Limited | MAN/INT/END |
| `organizedcrimes` | Minimal | OC2 in recruiting (slot vuoti) |

### 5.2 `faction/`

| Selection | Access | Note |
|-----------|--------|------|
| `applications` | Full | Candidature |
| `armor` / `weapons` / `temporary` / `boosters` / `drugs` / `medical` / `caches` / `cesium` | Full | Armory inventario |
| `armorynews` | Full | Log armory |
| `attacks` | Full | Attacchi recenti |
| `attacksfull` | Full | **Cloud 50k/24h** |
| `attacknews` | Full | **Cloud 50k/24h** |
| `basic` | Limited | Header faction |
| `boosters` | Full | Booster armory |
| `chain` | Limited | Stato live catena (count, mod, timeout) |
| `chains` | Limited | Storia catene |
| `chainreport` | Limited | Report dettagliato post-catena |
| `contributors` | Full | Contribuzioni membri |
| `crimeexp` | Full | CPR per membro per OC1/2 |
| `crimes` | Full | OC attive/completate |
| `crimenews` | Full | News OC |
| `currency` | Full | Cassa faction + points |
| `donations` | Full | Donazioni membri |
| `drugs` | Full | Armory drugs |
| `fundsnews` | Full | News cassa |
| `hof` | Public | Ranking pubblico faction |
| `mainnews` | Full | News principali |
| `medical` | Full | Armory medical |
| `membershipnews` | Full | Join/leave log |
| `news` | Full | Stream unificato |
| `organisedcrimes` / `organizedcrimes` | Full | OC v1 + v2 |
| `positions` | Limited | Posizioni faction (permessi) |
| `rankedwars` | Limited | War dichiarate |
| `rankedwarreport` | Limited | Report finale war |
| `raids` | Limited | Raid attivi |
| `raidreport` | Limited | Report raid |
| `reports` | Full | Spy reports + company reports |
| `revives` | Full | Revive log |
| `stats` | Limited | Statistiche faction |
| `temporary` | Full | Armory temp |
| `territory` | Limited | Territori controllati |
| `territorynames` | Public | Lista nomi territori |
| `territorynews` | Limited | News territori |
| `territorywars` | Limited | War territoriali attive |
| `territorywarreport` | Limited | Report war territoriali |
| `upgrades` | Limited | Upgrade tree acquistati |
| `wars` | Limited | Storico war |
| `weapons` | Full | Armory weapons |

### 5.3 `company/`

| Selection | Access | Note |
|-----------|--------|------|
| `applications` | Full (director) | Candidature pendenti |
| `companies` | Public | Lista tipi azienda (rinominata in `torn/companies`) |
| `detailed` | Full (director) | Income, popularity, env, advertising, efficiency |
| `employees` | Full (director) | Lista dipendenti con stats |
| `news` | Full | Eventi azienda |
| `profile` | Limited | Dati base azienda |
| `stock` | Full (director) | Magazzino prodotto |

### 5.4 `market/{itemID}`

| Selection | Access |
|-----------|--------|
| `bazaar` | Public |
| `itemmarket` | Public |
| `pointsmarket` | Public (su id `points`) |
| `lookup` | Public (metadati item) |

### 5.5 `torn/`

| Selection | Frequenza | Note |
|-----------|-----------|------|
| `bank` | 1h | Tassi banca (CD 1w/2w/1m/2m/3m) |
| `bounties` | 30s | Lista bounty pubblici |
| `caches` | 1h | Cache faction visible |
| `cards` | 1d | Catalogo carte |
| `cesium` | 1h | Cesium spawn map |
| `chainreport` | post-chain | Report catene pubbliche |
| `cityshops` | 5m | Stock città |
| `companies` | 1d | Catalogo tipi azienda + posizioni |
| `competition` | 5m | Competizioni stagionali |
| `dirtybombs` | 1h | Storico bombe |
| `education` | 1d | Catalogo corsi (statico) |
| `factionhof` | 1d | HOF faction |
| `factiontree` | mai | Tree upgrade catalog |
| `gyms` | mai | Catalogo palestre |
| `honors` / `medals` | mai | Cataloghi |
| `itemdetails` | 1d | Item con UUID specifico |
| `items` | 1d | **Catalogo ~1500 item** |
| `itemstats` | 1d | Stats weapon |
| `logcategories` | mai | Dizionario log |
| `logtypes` | mai | Sotto-dizionario log |
| `organisedcrimes` | 1d | OC catalog v1 (deprecato) |
| `pawnshop` | 5m | Pawn deals |
| `pokertables` | 5m | Tavoli poker live |
| `properties` | 1d | Catalogo property |
| `rackets` | 5m | Mappa racket |
| `raids` | 1m | Raid pubblici |
| `rankedwars` | 1m | War pubbliche |
| `revivesfull` | 1h | **Cloud 50k/24h** |
| `rockpaperscissors` | 1m | RPS contest |
| `searchforcash` | 1d | SFC payout per location |
| `shoplifting` | 1m | Stato alarm shop |
| `stats` | 1h | Global game stats |
| `stocks` | 1m | Prezzi 33 stock |
| `subcrimes` | 1d | Catalogo sub-crime |
| `territory` | 1m | Lista territori globale |
| `territorywars` | 1m | War terr. pubblici |
| `timestamp` | 1m | Server time |

### 5.6 `property/{id}`

- `property` (default): metadati property + upgrade list + staff.

### 5.7 `key/`

| Selection | Note |
|-----------|------|
| `info` | Access level + lista selection autorizzate (custom) |
| `log` | Cronologia chiamate (utile in Settings → trasparenza) |

## 6. Query params trasversali

| Param | Tipo | Uso |
|-------|------|-----|
| `from` | unix ts | Inizio finestra |
| `to` | unix ts | Fine finestra |
| `comment` | str | Tagging della call (visibile in `key/log`) |
| `cat` | str | Category filter (es. log) |
| `filter` | str | Specifico per selection |
| `sort` | enum | `ASC` / `DESC` |
| `limit` | int | Massimo record |
| `offset` | int | Paginazione (alcuni endpoint) |
| `striptags` | bool | Strip HTML in news |

## 7. v1 vs v2 — strategia

- **v2 only**: alcune selection nuove (OC2.0, nuovo `crimes` user).
- **v1 only**: rare; al momento `inventory` ha edge case su v1.
- **v2 preferred**: tutto il resto, default del nostro SDK.
- Override per selection con `version: "v1"`.
- Mantenere fixture JSON per regressioni: una versione (snapshot) per
  ogni selection in `packages/torn-sdk/fixtures/`.

## 8. Paginazione e ordinamento

- Endpoint con dataset cumulativo (attacks, log, events) usano `from`/`to`
  o `limit`/`offset`.
- Per backfill storico: cursor sliding-window di 7 giorni alla volta,
  job notturno con rate-limit-aware.

## 9. WebSocket Torn?

**No.** Torn non offre WebSocket API. Il "real-time" lato client deve
essere implementato:
- **Polling intelligente** (10-30s) lato server.
- **Push WebSocket interno** (Socket.IO) verso il browser per ridurre
  polling lato client.
- **Server-Sent Events (SSE)** come fallback per browser senza WS.

## 10. Comportamenti edge da gestire

| Edge case | Comportamento atteso |
|-----------|----------------------|
| Utente in jail federale | Code 10, key inutilizzabile fino a release |
| Utente offline >7gg | Code 13, key marked "needs refresh" |
| Utente pause API | Code 18, marker "paused", retry 6h |
| Manutenzione Torn | Code 9, status page mostra banner |
| Dati storici prima della registrazione | Snapshot fields = null |
| Faction lasciata | Code 7 su faction selection, fallback a basic |

## 11. Telemetria obbligatoria

Per ogni call salvare in `api_call_log`:
- `user_id`, `key_id`, `endpoint`, `selection`, `version` (v1/v2)
- `ts_request`, `latency_ms`, `http_status`, `torn_error_code`
- `cache_hit` (boolean), `bytes_in`, `comment`
- `rate_limit_remaining_user`, `rate_limit_remaining_cloud_category`

Dashboard interno:
- Calls/min per utente (alert > 80%)
- Cache hit ratio (target > 70%)
- Cloud usage `personalstats` per utente (alert > 80% del 50k/24h)
- p95 latency per selection
- Error rate per code
