---

# Appendice — API e strumenti dati per il flipping

## 1. TornW3B API (Weav3r) — `https://weav3r.dev/api`
Documentata nel file principale (marketplace, ranked weapons, dollar bazaars, pricelist, trades, health).
- Rate limit: 100 req/min (Cloudflare), cache TTL 30–180s
- Auth: `?apiKey=` o header `X-API-Key` (solo pricelist/trades)

## 2. TornPal API — live bazaar monitoring
È lo strumento citato nella guida come alternativa pubblica ai tool privati per monitorare i bazaar in tempo reale.
- Endpoint combinato mercato + item market:
`GET https://tornpal.com/api/v1/markets/clist/{itemId}`
- Endpoint solo bazaar (ordinati per prezzo/quantità/aggiornamento):
`GET https://tornpal.com/api/v1/bazaar/item/{itemId}`
- Documentazione: `https://tornpal.com/swagger` · Interfaccia web: `https://tornpal.com/markets`
- Nessuna chiave richiesta; dati raccolti scansionando i bazaar dei giocatori attivi (refresh ~5 min – 4 ore)
- Limite di fatto ~100 req/min su base IP

## 3. Torn Official API — v1 (`api.torn.com`)
Formato: `https://api.torn.com/:SECTION/:ID?selections=:SELECTIONS&key=:KEY`
- Prezzi di mercato: `GET /torn/{itemId}?selections=items` (supporta ID multipli separati da virgola)
- Listato item market di un item: `GET /market/{itemId}?selections=itemmarket`
- Bazaar di un utente: `GET /user/{userID}?selections=bazaar`
- Attenzione: `bazaar` NON è una selection del sezione `torn` (errore "Wrong fields")
- Livelli chiave: public / minimal / limited / full access

## 4. Torn Official API — v2
- Listini item market: `GET /market/{item_id}/itemmarket` (fino a ~100 listing di vendita)
- Listini bazaar: `GET /market/{item_id}/bazaar`
- Uso tipico: leggere l'order book per calcolare il prezzo d'ingresso

## 5. YATA (yata.alwaysdata.net)
Usato nella guida per identificare i mercati sopra/in/sotto valore.
- Bazaar overview con prezzi correnti e tendenze del market value
- Sezione API (loot levels, stocks abroad); richiede chiave per funzioni complete

## 6. Altri tool citati
| Tool | Scopo | Costo |
|------|-------|-------|
| Market Live Search (Titanic_) | Alert automatici su lista item personalizzata | ~1 Xanax/mese |
| TornTools | Pulsante "fill max", evidenzia item sotto soglia % | Gratis (Kiwi Browser su mobile Android) |
| Bazaar Listings (Weav3r) | Ripristina vista bazaar dentro torn.com | Free/freemium |
| TornPal subscription | Bot Discord con alert automatici sui deal | A pagamento |
