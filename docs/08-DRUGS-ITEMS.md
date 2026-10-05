# Drugs, Items, Boosters & Consumables — Reference Esteso

Riferimenti: [Drug Wiki](https://wiki.torn.com/wiki/Drug),
[Item Cooldowns](https://wiki.torn.com/wiki/Item_Cooldowns),
[Enhancer](https://wiki.torn.com/wiki/Enhancer),
[Temporary](https://wiki.torn.com/wiki/Temporary),
[Ammo](https://wiki.torn.com/wiki/Ammo).

## 1. Sistema dei 3 cooldown indipendenti

Torn ha **3 timer cooldown** separati. L'API `user/cooldowns` ritorna
`{ drug, booster, medical }` in **secondi residui**.

| CD | Item categoria | Esempi |
|----|----------------|--------|
| **Drug** | Drug items | Cannabis, Xanax, LSD, Ecstasy, PCP, Vicodin, Shroom, Speed, Opium, Ketamine, Love Juice |
| **Booster** | Alcolici, dolci, energy drink, books, statboost | Munster, X-Mas Cracker, Bottle of Beer, Wine, Erotic DVD, Book of Boosts |
| **Medical** | Cure life/hospital | First Aid Kit, Small First Aid Kit, Blood Bag, Morphine, Empty Blood Bag, Ipecac Syrup, Neutralizer |

> Un item triggera **solo** il cooldown della sua categoria, ma alcuni
> item raggruppano i 3 effetti (rari) — caso-per-caso.

## 2. Drugs — tabella numerica completa

| Drug | CD base | OD chance | Addiction % | Effetti chiave | Note |
|------|--------:|----------:|------------:|----------------|------|
| Cannabis | ~1h | bassissima | 0.2% | +happy, +modesti effetti misc | Rilassante |
| Vicodin | ~3h | ~3% | 3.3% | +happy, +damage reduction, riduce dolore | Analgesic |
| Xanax | 6-8h | ~3% | **11.2%** | **+250 energy, +75 happy** | Workhorse |
| Ketamine | ~5h | bassa | 1.9% | +stat passive temp, dissociativo | OD = CD esteso |
| LSD | 6.5-7.5h | ~7% | 6.25% | +misc, hallucinations | High addiction |
| Opium | ~6h | **0%** (no OD) | 2.8% | **rimuove hospital time** (tranne radiation) | Uniche con LJ |
| PCP | ~6h | ~7% | 7.6% | +stat passive, anger | Può ridurre stat permanente low-level |
| Shroom | ~5h | ~6% | 1.6% | +intelligence, hallucinations | Soft drug |
| Speed | ~5h | ~9% | 4.2% | +speed, +energy | Può ridurre stat low-level |
| Ecstasy | ~4h | ~12% | 3.0% | +happy molto | Alto OD risk |
| Love Juice | event | **0%** | 0% | +revive bonus, +event misc | Solo Valentine |

### Overdose

- Effetti OD = **2-5x** normal addiction gain di quella dose.
- OD = CD esteso (Xanax e Ketamine sono le **uniche** con OD esteso documentato).
- OD inflitta hospital + log pubblico.
- Solo Opium e Love Juice **non possono overdosare**.

### Sistema addiction

L'addiction è una **percentuale 0-100%** che cresce ad ogni dose e
decresce con il tempo (decay lento).

| Range | Effetti |
|-------|---------|
| 0-25% | Nessun effetto |
| 25-50% | Lievi malus battle stats (~-1 a -5%) |
| 50-75% | Malus battle stats medi, riduzione efficienza azienda |
| 75-100% | Malus pesanti, **lock Sports Science Gym**, lock gain edu |

**Trigger speciali**:
- **Xanax + Ecstasy > 150 totali** lifetime = lock Sports Science Gym permanente (richiede rehab).
- **Speed + PCP** possono **ridurre stat permanentemente** se preso a low level.

### Rehab

- **Local** (City Hospital): paghi $ proporzionali al livello addiction.
- **Private** (PI Medical Facility): più rapido + economico.
- Decay naturale: ~0.2-0.5% al giorno (varia con perks Toleration).
- Merit "Addiction Mitigation": -2%/level effetti negativi (max 10 level).

## 3. Booster items (alcolici, dolci, energy drink)

Triggerano il **Booster CD**.

| Categoria | Esempi tipici | Effetto base |
|-----------|----------------|--------------|
| Alcohol | Bottle of Beer (+10E +10H), Wine, Vodka, Whiskey, Champagne (+50E) | +energy/+happy |
| Energy Drink | Munster (+50E), X-Mas Cracker (+25E), Bottle of Mind Goblin | +energy boost |
| Candy | Lollipop (+25H), Box of Chocolates, Chocolate Bar | +happy |
| Plushie | Sheep Plushie, Teddy Bear, Stingray, Wolverine | +happy molto |
| Flower | Rose, Tulip, Crocus, Heather, Cherry Blossom, Edelweiss, Peony, Banana Orchid, Ceibo Flower, Orchid, African Violet, Dahlia | +happy + gift PI |
| Book Booster | Sun Tzu's Art of War, Trojan Horse, Self Control Is For Losers, Book of Boosts | Buff durata 31g |
| Stat Enhancer | Stat Enhancement Strength/Defense/Speed/Dex | Permanent stat boost |
| Needles (Injection) | Serotonin, Tyrosine, Epinephrine, Melatonin | Stat buff temp (richiede BIO3420) |

### Books famosi

- **Sun Tzu: The Art of War**: +25% combat skill per 31g.
- **Trojan Horse**: +50% computer crime per 31g.
- **Self Control Is For Losers**: -50% booster CD per 31g.
- **Book of Boosts**: +10% gym gain per 31g.
- **Personal Stylist**: +50% pickpocketing per 31g.
- **Sword Mastery**: +25% melee critical per 31g.

## 4. Medical items

Triggerano il **Medical CD**.

| Item | Life restore | Hospital reduction | Note |
|------|-------------:|--------------------:|------|
| First Aid Kit | +50 life | -30 min hosp | Standard |
| Small First Aid Kit | +25 life | -15 min hosp | Cheap |
| Blood Bag (standard) | +25 life | -10 min hosp | |
| Blood Bag : Type A+ / B+ / O+ / AB+ | +50 life | -varia | |
| Blood Bag : Irradiated | speciale | speciale | rare |
| Empty Blood Bag | 0 | 0 | Component crafting |
| Morphine | +100 life | -all hosp | Strong |
| Ipecac Syrup | 0 | 0 | **Rimuove drug CD** (rischio reverse) |
| Neutralizer | 0 | 0 | Rimuove poison/status |
| Anti-radiation Pill | 0 | rimuove rad. poison | Event |

## 5. Temporary weapons (one-shot)

Triggerano il **Booster CD** per i non-damage (Flash/Smoke/Tear Gas/
Pepper) e niente CD per damage one-use, ma il vincolo è "1 uso per
fight" (a meno di Snowball/Brick che stackano).

### Damage temp (campione)

| Item | Damage | Accuracy | Note |
|------|-------:|---------:|------|
| Brick | ~85 | 110 | Stack 2 |
| Snowball | ~30 | 100 | Stack alto (event) |
| Sand | ~35 | 100 | Stack 1 |
| Throwing Knife | ~70 | 108 | |
| Trout | ~55 | 100 | Joke item, ottime stats |
| Bottle Rocket | ~85 | 105 | Event |
| Fireworks | ~90 | 105 | Event |
| Molotov Cocktail | ~95 | 104 | Standard temp |
| Stick Grenade | ~98 | 105 | |
| Grenade | **~100.80** | **106** | Common |
| HEG (High Explosive Grenade) | **~116.26** | **116** | Top tier |
| Ninja Stars | ~95 | 110 | |
| Claymore Mine | ~150+ | 110 | Heavy |
| Nail Bomb | **~174.34** | **106** | Highest damage temp |

### Utility temp (no damage)

| Item | Effetto | Accuracy |
|------|---------|---------:|
| Flash Grenade | Stun next turn | 200 (always hit) |
| Smoke Grenade | Cover, +stealth | 200 |
| Tear Gas | Reduces enemy accuracy | 200 |
| Pepper Spray | Stun + accuracy reduction | 200 |

## 6. Ammo system

Ogni weapon damage usa ammo (anche se nascosto). 6 tipi di ammo speciale
acquistabili al **Shooting Range**:

| Ammo type | Effetto | Slot |
|-----------|---------|------|
| **Standard** (default) | nessun bonus | gratis |
| **Tracer** | +accuracy, riduce stealth | costoso |
| **Piercing** | bypass parziale armor | medio |
| **Incendiary** | +crit chance | medio |
| **Hollow Point** | +damage no armor | medio |
| **Special** | Mission rewards only | rare |

Solo **uno** tipo speciale può essere caricato per arma per fight.

## 7. Enhancer items

### Crime Enhancer (Crimes 2.0: +5% XP/skill)

| Crime | Enhancer item |
|-------|---------------|
| Search For Cash | Metal Detector |
| Shoplifting | Duffel Bag |
| Pickpocketing | Cut-Throat Razor |
| Burglary | Lock Pick |
| Scamming | Burner Phone |
| Card Skimming | Skimming Device |
| Hustling (Pool) | Marked Cue |
| Hustling (Cards) | Marked Deck |
| Hustling (Darts) | Custom Darts |
| Hustling (Slots) | Loaded Coin |
| Forgery | Forgery Kit |
| Dealing | (varia per drug) |
| Disposal | Cleaning Kit |
| Cracking | Wire Stripper |
| Auto Theft | Master Key Set |

### Gym Enhancer

| Item | Bonus | Durata |
|------|-------|--------|
| Hairbrush | +5% gym gain | 1 train |
| Pre-Workout Supplement | +X% gym | 1 day |
| Sports Drink | +X% energy | 1 train |

### Stat Enhancer (one-time permanent)

| Item | Effetto |
|------|---------|
| Stat Enhancement Strength | +stat permanent STR |
| Stat Enhancement Defense | +stat permanent DEF |
| Stat Enhancement Speed | +stat permanent SPD |
| Stat Enhancement Dexterity | +stat permanent DEX |

Sono **molto rari**, mercato altamente volatile.

### Travel Enhancer

- Increase foreign item capacity slots (rare).

## 8. Item categorie da `torn/items`

| Categoria | Note |
|-----------|------|
| Primary | Pistole, fucili, machine gun (slot 1) |
| Secondary | Pistole secondarie, SMG (slot 2) |
| Melee | Coltelli, mazze, spade |
| Temporary | One-use weapons |
| Defensive | Armor (helmet, body, pants, boots, gloves) |
| Drug | Drug items |
| Medical | Medical items |
| Booster | Booster items |
| Energy Drink | Sotto-Booster |
| Alcohol | Sotto-Booster |
| Candy | Sotto-Booster |
| Flower | Sotto-Booster + gift PI |
| Plushie | Sotto-Booster + collection |
| Supplement | Sotto-Booster |
| Enhancer | Crime/Gym/Stat |
| Special | Item rari (Christmas Cracker, Halloween Candy) |
| Collectible | Item da collezione (Trading Cards, etc.) |
| Material | Materiali OC2, crafting |
| Clothing | Cosmetic |
| Car | Auto da racing |
| Jewelry | Anelli, collane (gift, marriage) |
| Book | Booster libri |
| Virus | Computer virus (cyber cafe crime) |
| Artifact | Reliquie (event, rare) |
| Other | Misc |

## 9. API & polling consigliato

| Selection | Frequenza | Uso |
|-----------|-----------|-----|
| `user/inventory` | 5m + invalidate on event | Conta item |
| `user/cooldowns` | 30s | 3 timer drug/booster/medical |
| `user/refills` | 1h | Stato refill energy/nerve/medical |
| `user/perks` | 1d | Bonus permanenti |
| `user/criminalrecord` | 6h | Drugs/Xanax/Ecstasy/LSD/etc. counts |
| `torn/items` | 1d | Catalogo (~1.500 item) |
| `torn/itemstats` | 1d | Damage/accuracy weapons |
| `torn/cityshops` | 5m | Restock + alarm |

## 10. Feature TornCiaffa (Drugs/Items)

| Feature | Logica |
|---------|--------|
| **3-CD HUD** | Live timer drug/booster/medical con ETA push |
| **Xanax Stack Planner** | Schedule dosi/24h tenendo addiction sotto soglia personalizzata |
| **OD Risk Bar** | Mostra rischio OD per ogni dose; alert > 5% |
| **Rehab Planner** | Costo locale vs PI Medical, tempo rehab atteso |
| **Sports Sci Lock Watcher** | Xanax+Ecstasy lifetime counter con alert 140/150 |
| **Drink Reminder** | Notif push "Munster ready" |
| **Medical Stock Alert** | Soglia minima BB/FAK/Morphine in inventario |
| **Temp Loadout Picker** | Suggerisce 1-3 temp ideali per target weight class |
| **Enhancer Inventory Tracker** | Mancanti per ogni crime (con prezzo bazaar/market) |
| **Ammo Picker** | Suggerisce ammo speciale per loadout (e quando consumarla) |
| **Stat Enhancer Market Watch** | Prezzo storico, alert deviation > X% |
| **Rare Item Restock** | Push su pawn shop / city shop / foreign restock |
| **Crit Hit Calc** | Sommatoria crit chance (base + edu + merit + laser + expose) |
