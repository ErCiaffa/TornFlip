#!/usr/bin/env python3
import os
import time
import json
import threading
from flask import Flask, jsonify, request, render_template_string
from config import (
    BASE_DIR,
    TORN_API_KEY,
    MIN_PROFIT_PERCENT,
    MIN_PROFIT_VALUE,
    MAX_BUY_BUDGET,
    POLL_INTERVAL_SECONDS,
    PRIORITY_ITEM_TYPES,
    ENV_PATH
)
from database import (
    get_connection,
    upsert_items,
    get_items_by_types,
    get_recent_deals,
    get_item
)
from torn_api import TornAPIClient
from external_sources import fetch_yata_travel_stocks, calculate_travel_arbitrage
from analyzer import FlippingEngine

app = Flask(__name__)

# In-memory background scanner state
scanner_state = {
    "is_running": False,
    "last_scan_time": 0,
    "last_scan_result": "",
    "items_scanned": 0,
    "deals_found_last_scan": 0
}

def update_env_file(key: str, value: str):
    """Aggiorna una chiave nel file .env"""
    lines = []
    found = False
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
            
    if not found:
        new_lines.append(f"{key}={value}\n")
        
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.environ[key] = value

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/status")
def get_status():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM items")
    item_count = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) as count FROM deals")
    deal_count = c.fetchone()["count"]
    conn.close()
    
    current_key = os.getenv("TORN_API_KEY", TORN_API_KEY)
    masked_key = f"{current_key[:4]}...{current_key[-4:]}" if len(current_key) >= 8 else ("Configurata" if current_key else "Non configurata")
    
    return jsonify({
        "has_api_key": bool(current_key),
        "api_key_masked": masked_key,
        "items_in_catalog": item_count,
        "deals_recorded": deal_count,
        "min_profit_pct": float(os.getenv("MIN_PROFIT_PERCENT", MIN_PROFIT_PERCENT)),
        "min_profit_val": int(os.getenv("MIN_PROFIT_VALUE", MIN_PROFIT_VALUE)),
        "max_buy_budget": int(os.getenv("MAX_BUY_BUDGET", MAX_BUY_BUDGET)),
        "scanner_state": scanner_state
    })

@app.route("/api/settings", methods=["POST"])
def save_settings():
    data = request.json or {}
    if "api_key" in data and data["api_key"].strip():
        update_env_file("TORN_API_KEY", data["api_key"].strip())
    if "min_profit_pct" in data:
        update_env_file("MIN_PROFIT_PERCENT", str(data["min_profit_pct"]))
    if "min_profit_val" in data:
        update_env_file("MIN_PROFIT_VALUE", str(data["min_profit_val"]))
    if "max_buy_budget" in data:
        update_env_file("MAX_BUY_BUDGET", str(data["max_buy_budget"]))
        
    return jsonify({"success": True, "message": "Impostazioni salvate con successo!"})

@app.route("/api/sync", methods=["POST"])
def sync_catalog():
    key = os.getenv("TORN_API_KEY", TORN_API_KEY)
    if not key:
        return jsonify({"success": False, "error": "API Key mancante"}), 400
        
    client = TornAPIClient(key)
    items = client.fetch_items_catalog()
    if not items:
        return jsonify({"success": False, "error": "Impossibile contattare Torn API. Verifica la chiave."}), 502
        
    upsert_items(items)
    return jsonify({
        "success": True,
        "message": f"Catalogo aggiornato con {len(items)} oggetti.",
        "count": len(items)
    })

@app.route("/api/deals")
def list_deals():
    limit = int(request.args.get("limit", 50))
    deals = get_recent_deals(limit)
    return jsonify(deals)

@app.route("/api/scan", methods=["POST"])
def run_scan():
    key = os.getenv("TORN_API_KEY", TORN_API_KEY)
    if not key:
        return jsonify({"success": False, "error": "API Key mancante. Inseriscila nelle impostazioni."}), 400
        
    target_items = get_items_by_types(PRIORITY_ITEM_TYPES)
    if not target_items:
        return jsonify({"success": False, "error": "Catalogo vuoto. Esegui prima la sincronizzazione (Sync)."}), 400
        
    client = TornAPIClient(key)
    min_pct = float(os.getenv("MIN_PROFIT_PERCENT", MIN_PROFIT_PERCENT))
    min_val = int(os.getenv("MIN_PROFIT_VALUE", MIN_PROFIT_VALUE))
    engine = FlippingEngine(min_profit_pct=min_pct, min_profit_val=min_val)
    
    # Costruisci lo scan pool con priorità assoluta per gli oggetti della guida Madpup
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Crime Drops (HPCPU, Medical Bills, Bank Statements)
    crime_items = []
    from config import MADPUP_CRIME_ITEMS, MADPUP_EVENT_ITEMS, AVOID_ITEMS
    for ci in MADPUP_CRIME_ITEMS:
        c.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 2", (f"%{ci}%",))
        crime_items.extend([dict(r) for r in c.fetchall()])
        
    # 2. Event Timed Items (Cannabis, Beers, Blood Bags, Chocolates)
    event_items = []
    for ei in MADPUP_EVENT_ITEMS:
        c.execute("SELECT * FROM items WHERE name LIKE ? LIMIT 2", (f"%{ei}%",))
        event_items.extend([dict(r) for r in c.fetchall()])
    conn.close()
    
    # Filtra ed unisci evitando duplicati e AVOID_ITEMS
    seen_ids = set()
    scan_pool = []
    
    for item in crime_items + event_items + target_items:
        if item["id"] in seen_ids:
            continue
        if engine.is_avoided(item["name"]):
            continue
        seen_ids.add(item["id"])
        scan_pool.append(item)
        if len(scan_pool) >= 40:
            break
            
    deals_found = []
    
    for item in scan_pool:
        mkt = client.fetch_market_listings(item["id"])
        if not mkt:
            continue
        deals = engine.analyze_item_listings(item, mkt)
        deals_found.extend(deals)
        
    scanner_state["last_scan_time"] = int(time.time())
    scanner_state["items_scanned"] = len(scan_pool)
    scanner_state["deals_found_last_scan"] = len(deals_found)
    
    return jsonify({
        "success": True,
        "scanned_items": len(scan_pool),
        "deals_found": len(deals_found),
        "deals": deals_found
    })

@app.route("/api/travel")
def travel_deals():
    capacity = int(request.args.get("capacity", 29))
    stocks = fetch_yata_travel_stocks()
    if not stocks:
        return jsonify([])
        
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, market_value FROM items")
    rows = c.fetchall()
    conn.close()
    
    catalog = {r["id"]: dict(r) for r in rows}
    if not catalog:
        # Fallback default stime
        catalog = {
            268: {"market_value": 45000, "name": "Jaguar Plushie"},
            266: {"market_value": 44000, "name": "Nessie Plushie"},
            269: {"market_value": 46000, "name": "Monkey Plushie"},
            273: {"market_value": 47000, "name": "Chamois Plushie"},
            274: {"market_value": 72000, "name": "Panda Plushie"},
            384: {"market_value": 90000, "name": "Camel Plushie"},
            261: {"market_value": 46000, "name": "Ceibo Flower"},
            267: {"market_value": 48000, "name": "Edelweiss Flower"},
            263: {"market_value": 52000, "name": "Crocus Flower"},
            264: {"market_value": 65000, "name": "Heather Flower"},
            282: {"market_value": 73000, "name": "Cherry Blossom"}
        }
        
    opportunities = calculate_travel_arbitrage(stocks, catalog, capacity=capacity)
    return jsonify(opportunities)

@app.route("/api/city-shops")
def city_shops():
    key = os.getenv("TORN_API_KEY", TORN_API_KEY)
    if not key:
        return jsonify({"success": False, "error": "API Key mancante"}), 400
        
    client = TornAPIClient(key)
    shops = client.fetch_city_shops()
    if not shops:
        return jsonify([])
        
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, market_value FROM items")
    rows = c.fetchall()
    conn.close()
    catalog = {r["id"]: dict(r) for r in rows}
    
    engine = FlippingEngine()
    opps = engine.analyze_city_shops(shops, catalog)
    return jsonify(opps)

@app.route("/api/items")
def search_items():
    query = request.args.get("q", "").strip()
    conn = get_connection()
    c = conn.cursor()
    if query:
        c.execute("SELECT id, name, type, buy_price, sell_price, market_value FROM items WHERE name LIKE ? ORDER BY market_value DESC LIMIT 25", (f"%{query}%",))
    else:
        c.execute("SELECT id, name, type, buy_price, sell_price, market_value FROM items ORDER BY circulation DESC LIMIT 25")
    rows = c.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# Single Page Application HTML Template (Tailwind CSS, Lucide icons, Inter font, Dark Mode)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="it" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TornFlip — Professional Market Advisor</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#ecfdf5', 500: '#10b981', 600: '#059669', 700: '#047857' },
            torn: { 800: '#131b26', 900: '#0b1118', 950: '#060a0f' }
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; background-color: #080d13; color: #e2e8f0; }
    .mono { font-family: 'JetBrains Mono', monospace; }
    .glow-green { box-shadow: 0 0 25px rgba(16, 185, 129, 0.2); }
    .table-row-hover:hover { background-color: rgba(255, 255, 255, 0.03); }
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased">
  
  <!-- Header Bar -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
          <i data-lucide="trending-up" class="w-5 h-5"></i>
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <span class="font-extrabold text-lg tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">TornFlip</span>
            <span class="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">v1.2 Pro</span>
          </div>
          <p class="text-[11px] text-slate-400 leading-tight">Live Arbitrage & Market Intelligence</p>
        </div>
      </div>

      <!-- Quick stats & tabs -->
      <nav class="hidden md:flex space-x-1 p-1 bg-slate-900 border border-slate-800 rounded-xl">
        <button onclick="switchTab('deals')" id="tab-deals" class="tab-btn px-4 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500 text-slate-950 shadow">
          <i data-lucide="zap" class="w-3.5 h-3.5 inline mr-1"></i> Radar Affari
        </button>
        <button onclick="switchTab('madpup')" id="tab-madpup" class="tab-btn px-4 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/60 transition">
          <i data-lucide="sparkles" class="w-3.5 h-3.5 inline mr-1 text-amber-400"></i> Metodo Madpup
        </button>
        <button onclick="switchTab('travel')" id="tab-travel" class="tab-btn px-4 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/60 transition">
          <i data-lucide="plane" class="w-3.5 h-3.5 inline mr-1"></i> Travel Flipping
        </button>
        <button onclick="switchTab('city')" id="tab-city" class="tab-btn px-4 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/60 transition">
          <i data-lucide="store" class="w-3.5 h-3.5 inline mr-1"></i> City Shops
        </button>
        <button onclick="switchTab('calculator')" id="tab-calculator" class="tab-btn px-4 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/60 transition">
          <i data-lucide="calculator" class="w-3.5 h-3.5 inline mr-1"></i> Calcolatore
        </button>
        <button onclick="switchTab('settings')" id="tab-settings" class="tab-btn px-4 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white hover:bg-slate-800/60 transition">
          <i data-lucide="settings" class="w-3.5 h-3.5 inline mr-1"></i> Impostazioni
        </button>
      </nav>

      <!-- Right Action Bar -->
      <div class="flex items-center space-x-3">
        <div id="key-badge" class="hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium border bg-slate-900 text-slate-400 border-slate-800">
          <span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span>
          <span id="key-label">Verifica chiave...</span>
        </div>
        <button onclick="triggerScan()" id="btn-scan" class="flex items-center space-x-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-3.5 py-2 rounded-lg transition shadow-lg shadow-emerald-950/50">
          <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
          <span>Scansiona Ora</span>
        </button>
      </div>
    </div>
  </header>

  <!-- Mobile Bottom Nav -->
  <div class="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-slate-950 border-t border-slate-800 flex justify-around p-2">
    <button onclick="switchTab('deals')" class="flex flex-col items-center text-xs text-emerald-400"><i data-lucide="zap" class="w-5 h-5"></i><span>Radar</span></button>
    <button onclick="switchTab('madpup')" class="flex flex-col items-center text-xs text-amber-400"><i data-lucide="sparkles" class="w-5 h-5"></i><span>Madpup</span></button>
    <button onclick="switchTab('travel')" class="flex flex-col items-center text-xs text-slate-400"><i data-lucide="plane" class="w-5 h-5"></i><span>Travel</span></button>
    <button onclick="switchTab('city')" class="flex flex-col items-center text-xs text-slate-400"><i data-lucide="store" class="w-5 h-5"></i><span>City</span></button>
    <button onclick="switchTab('calculator')" class="flex flex-col items-center text-xs text-slate-400"><i data-lucide="calculator" class="w-5 h-5"></i><span>Calc</span></button>
    <button onclick="switchTab('settings')" class="flex flex-col items-center text-xs text-slate-400"><i data-lucide="settings" class="w-5 h-5"></i><span>Setup</span></button>
  </div>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-20 md:pb-6">
    
    <!-- Top Stats Row -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>Catalogo Oggetti</span>
          <i data-lucide="database" class="w-4 h-4 text-emerald-400"></i>
        </div>
        <div class="text-2xl font-bold mono text-white" id="stat-catalog">-</div>
        <div class="text-[11px] text-slate-500 mt-1">Memorizzati in tornflip.db</div>
      </div>

      <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>Affari Rilevati</span>
          <i data-lucide="target" class="w-4 h-4 text-cyan-400"></i>
        </div>
        <div class="text-2xl font-bold mono text-cyan-400" id="stat-deals">-</div>
        <div class="text-[11px] text-slate-500 mt-1">Margine minimo &ge; 10%</div>
      </div>

      <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>Top Travel ROI</span>
          <i data-lucide="plane-takeoff" class="w-4 h-4 text-amber-400"></i>
        </div>
        <div class="text-2xl font-bold mono text-amber-400" id="stat-top-travel">-</div>
        <div class="text-[11px] text-slate-500 mt-1" id="stat-top-travel-sub">Live da YATA</div>
      </div>

      <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800">
        <div class="flex items-center justify-between text-slate-400 text-xs mb-1">
          <span>Protezione Mugging</span>
          <i data-lucide="shield-alert" class="w-4 h-4 text-rose-400"></i>
        </div>
        <div class="text-sm font-bold mono text-rose-300 mt-1">&le; $10M / Item</div>
        <div class="text-[11px] text-slate-500 mt-1">Regola Madpup IM 2.0</div>
      </div>
    </div>

    <!-- TAB 1: RADAR AFFARI (DEALS) -->
    <section id="pane-deals" class="tab-pane">
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div class="p-4 sm:p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 class="text-base font-bold text-white flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Live Flipping Radar
            </h2>
            <p class="text-xs text-slate-400">Affari rilevati nei bazaar dei player con profitto immediato e arbitraggio</p>
          </div>
          <div class="flex items-center space-x-2">
            <span class="text-xs text-slate-400">Filtro:</span>
            <select id="deal-filter" onchange="renderDealsTable()" class="bg-slate-950 border border-slate-700 text-xs rounded-lg px-2.5 py-1.5 text-slate-200">
              <option value="ALL">Tutti gli affari</option>
              <option value="MADPUP_CRIME_DUMP">🎯 Noob Crime Dumps (HPCPU/Estratti)</option>
              <option value="MADPUP_EVENT_ITEM">🎉 Event Items (Beer/Blood/420)</option>
              <option value="ZERO_RISK_PAWN">🛡️ Zero-Risk Pawn (NPC)</option>
              <option value="UNDERPRICED_BAZAAR">🏷️ Sotto Mercato (&ge;10%)</option>
              <option value="SPREAD_ARBITRAGE">📊 Arbitraggio Spread</option>
            </select>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="border-b border-slate-800 text-slate-400 uppercase font-semibold tracking-wider bg-slate-950/40">
                <th class="py-3 px-4">Strategia</th>
                <th class="py-3 px-4">Oggetto</th>
                <th class="py-3 px-4 text-right">Prezzo Acquisto</th>
                <th class="py-3 px-4 text-right">Target Rivendita</th>
                <th class="py-3 px-4 text-right">Profitto Singolo</th>
                <th class="py-3 px-4 text-right">Profitto Totale</th>
                <th class="py-3 px-4 text-right">ROI %</th>
                <th class="py-3 px-4 text-center">Azione</th>
              </tr>
            </thead>
            <tbody id="deals-tbody" class="divide-y divide-slate-800/60 font-medium">
              <tr>
                <td colspan="8" class="text-center py-10 text-slate-500">
                  <i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-400"></i>
                  Caricamento affari di mercato in corso...
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB: METODO MADPUP (CRIME DROPS, EVENTS & ANTI-MUG) -->
    <section id="pane-madpup" class="tab-pane hidden">
      <div class="space-y-6">
        
        <!-- Hero Card Madpup -->
        <div class="bg-gradient-to-r from-amber-950/40 via-slate-900/80 to-slate-900/60 border border-amber-500/30 rounded-2xl p-6 shadow-xl relative overflow-hidden">
          <div class="max-w-3xl">
            <div class="flex items-center space-x-2 text-amber-400 font-bold text-xs uppercase tracking-wider mb-2">
              <i data-lucide="award" class="w-4 h-4"></i>
              <span>Strategia Testata sul Campo: 2 Miliardi $ in 95 Giorni</span>
            </div>
            <h2 class="text-xl font-extrabold text-white tracking-tight mb-2">Il Metodo Madpup per il Flipping</h2>
            <p class="text-xs text-slate-300 leading-relaxed">
              Il vero profitto nel flipping non viene solo dagli errori di battitura, ma dallo <strong>studio dei cicli, degli eventi e dei crimini</strong>. I principianti svendono oggetti rari credendoli spazzatura, mentre gli eventi stagionali creano picchi di domanda prevedibili.
            </p>
          </div>
        </div>

        <!-- 3 Strategy Pillars -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <!-- Pillar 1 -->
          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 hover:border-amber-500/40 transition">
            <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 mb-4">
              <i data-lucide="crosshair" class="w-5 h-5"></i>
            </div>
            <h3 class="text-sm font-bold text-white mb-1">1. "Search for Cash" & Crimini</h3>
            <p class="text-xs text-slate-400 leading-relaxed mb-3">
              Oggetti come <strong>HPCPU, estratti conto bancari (Bank Statements) e fatture mediche</strong> vengono svenduti dai noob per poche centinaia di dollari. Rivendibili a <strong>$100k - $1M+</strong>.
            </p>
            <div class="text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2.5 py-1 rounded-lg border border-amber-800/40">
              Focus: HPCPU, Medical Bills, Bank Statements
            </div>
          </div>

          <!-- Pillar 2 -->
          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 hover:border-cyan-500/40 transition">
            <div class="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 mb-4">
              <i data-lucide="calendar" class="w-5 h-5"></i>
            </div>
            <h3 class="text-sm font-bold text-white mb-1">2. Mercati Cronometrati (Eventi)</h3>
            <p class="text-xs text-slate-400 leading-relaxed mb-3">
              Accumula settimane prima del picco e vendi al momento di massima foga: <strong>Cannabis (420 Day)</strong>, <strong>Beer (Beer Day)</strong>, <strong>Blood Bags (Blood Day)</strong> e <strong>Big Box of Chocolates</strong>.
            </p>
            <div class="text-[11px] font-mono text-cyan-400 bg-cyan-950/40 px-2.5 py-1 rounded-lg border border-cyan-800/40">
              Target: +15% a +35% durante l'evento
            </div>
          </div>

          <!-- Pillar 3 -->
          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 hover:border-rose-500/40 transition">
            <div class="w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-rose-400 mb-4">
              <i data-lucide="shield-check" class="w-5 h-5"></i>
            </div>
            <h3 class="text-sm font-bold text-white mb-1">3. Protocollo Anti-Mugging</h3>
            <p class="text-xs text-slate-400 leading-relaxed mb-3">
              Dopo Item Market 2.0, non tenere mai in vendita singoli item sopra i <strong>$10M</strong> nel bazaar. Parcheggia il contante in <strong>azioni SYM</strong> (0.1% fee + Drug Pack settimanale) o vola all'estero.
            </p>
            <div class="text-[11px] font-mono text-rose-400 bg-rose-950/40 px-2.5 py-1 rounded-lg border border-rose-800/40">
              Regola: Safe storage in SYM stock o Flight
            </div>
          </div>
        </div>

        <!-- Avoid List vs Target List -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5">
            <h4 class="text-xs font-bold text-rose-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <i data-lucide="slash" class="w-4 h-4"></i>
              Articoli Esclusi da Madpup (Falsi Affari)
            </h4>
            <ul class="space-y-2 text-xs text-slate-300">
              <li class="flex items-start gap-2">
                <span class="text-rose-400 font-bold">•</span>
                <div><strong>Xanax:</strong> Troppa concorrenza di bot e spread &lt;1%. Margine bruciato dalle oscillazioni.</div>
              </li>
              <li class="flex items-start gap-2">
                <span class="text-rose-400 font-bold">•</span>
                <div><strong>Erotic DVD (EDVD):</strong> Prezzo ultra-stabile, rotazione lenta, zero volatilità per fare flip veloci.</div>
              </li>
              <li class="flex items-start gap-2">
                <span class="text-rose-400 font-bold">•</span>
                <div><strong>Sand e Luxury Rarities (&gt;$25M):</strong> Mercato piccolissimo, capitale bloccato per settimane.</div>
              </li>
            </ul>
          </div>

          <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-5">
            <h4 class="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-3 flex items-center gap-1.5">
              <i data-lucide="check-circle" class="w-4 h-4"></i>
              Regole d'Oro per l'Esecuzione
            </h4>
            <ul class="space-y-2 text-xs text-slate-300">
              <li class="flex items-start gap-2">
                <span class="text-emerald-400 font-bold">•</span>
                <div><strong>Margine minimo 10%:</strong> Se il profitto netto scende sotto il 10%, smetti di comprare e attendi.</div>
              </li>
              <li class="flex items-start gap-2">
                <span class="text-emerald-400 font-bold">•</span>
                <div><strong>Usa il tuo Bazaar (250 pts):</strong> Ha 0% tasse rispetto al 3-5% dell'Item Market (Torn Tax).</div>
              </li>
              <li class="flex items-start gap-2">
                <span class="text-emerald-400 font-bold">•</span>
                <div><strong>I rapinatori sono clienti:</strong> Non bloccarli, spesso tornano a comprare per recuperare il denaro speso.</div>
              </li>
            </ul>
          </div>
        </div>

      </div>
    </section>

    <!-- TAB 2: TRAVEL FLIPPING (YATA) -->
    <section id="pane-travel" class="tab-pane hidden">
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div class="p-4 sm:p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 class="text-base font-bold text-white flex items-center gap-2">
              <i data-lucide="plane" class="w-4 h-4 text-cyan-400"></i>
              Travel Flipping Arbitrage (Live YATA Crowdsource)
            </h2>
            <p class="text-xs text-slate-400">Calcolo profitto netto per run e all'ora basato su stock effettivo all'estero</p>
          </div>
          <div class="flex items-center space-x-3">
            <label class="text-xs text-slate-400">Capienza Valigia:</label>
            <div class="flex items-center space-x-2">
              <input type="range" id="suitcase-cap" min="5" max="29" value="29" oninput="updateSuitcaseDisplay(this.value)" onchange="fetchTravelDeals()" class="w-24 accent-emerald-500">
              <span id="suitcase-val" class="text-xs mono font-bold text-emerald-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">29</span>
            </div>
            <button onclick="fetchTravelDeals()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs rounded-lg transition font-medium">
              <i data-lucide="rotate-cw" class="w-3.5 h-3.5 inline mr-1"></i> Aggiorna
            </button>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="border-b border-slate-800 text-slate-400 uppercase font-semibold tracking-wider bg-slate-950/40">
                <th class="py-3 px-4">Destinazione</th>
                <th class="py-3 px-4">Oggetto Estero</th>
                <th class="py-3 px-4 text-right">Costo Estero</th>
                <th class="py-3 px-4 text-right">Valore a Torn</th>
                <th class="py-3 px-4 text-right">Guadagno / Run</th>
                <th class="py-3 px-4 text-right">Profitto Orario ($/hr)</th>
                <th class="py-3 px-4 text-right">ROI %</th>
                <th class="py-3 px-4 text-right">Stock</th>
                <th class="py-3 px-4 text-center">Volo</th>
              </tr>
            </thead>
            <tbody id="travel-tbody" class="divide-y divide-slate-800/60 font-medium">
              <!-- Filled via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 3: CITY SHOPS -->
    <section id="pane-city" class="tab-pane hidden">
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div class="p-4 sm:p-5 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 class="text-base font-bold text-white flex items-center gap-2">
              <i data-lucide="store" class="w-4 h-4 text-amber-400"></i>
              Negozi Ufficiali Torn (Pharmacy, Sweet Shop, Bits 'n' Bobs)
            </h2>
            <p class="text-xs text-slate-400">Compra direttamente dagli NPC a prezzo regolato e rivendi sul tuo Bazaar</p>
          </div>
          <button onclick="fetchCityShops()" class="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs rounded-lg transition font-medium">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5 inline mr-1"></i> Ricarica
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left border-collapse text-xs">
            <thead>
              <tr class="border-b border-slate-800 text-slate-400 uppercase font-semibold tracking-wider bg-slate-950/40">
                <th class="py-3 px-4">Negozio</th>
                <th class="py-3 px-4">Articolo</th>
                <th class="py-3 px-4 text-right">Prezzo Negozio</th>
                <th class="py-3 px-4 text-right">Valore Bazaar</th>
                <th class="py-3 px-4 text-right">Profitto / Pezzo</th>
                <th class="py-3 px-4 text-right">ROI %</th>
                <th class="py-3 px-4 text-right">Stock Disponibile</th>
                <th class="py-3 px-4 text-center">Azione</th>
              </tr>
            </thead>
            <tbody id="city-tbody" class="divide-y divide-slate-800/60 font-medium">
              <!-- Filled via JS -->
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- TAB 4: CALCULATOR -->
    <section id="pane-calculator" class="tab-pane hidden">
      <div class="max-w-2xl mx-auto bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h2 class="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="calculator" class="w-5 h-5 text-emerald-400"></i>
          Calcolatore Margine e Tasse Flip
        </h2>
        <p class="text-xs text-slate-400 mb-6">Simula l'acquisto e la rivendita considerando le commissioni dell'Item Market (5%) o Bazaar (0%).</p>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Prezzo di Acquisto ($)</label>
            <input type="number" id="calc-buy" value="85000" oninput="recalc()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm mono text-white focus:border-emerald-500 outline-none">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Prezzo Target di Rivendita ($)</label>
            <input type="number" id="calc-sell" value="100000" oninput="recalc()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm mono text-white focus:border-emerald-500 outline-none">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Quantità</label>
            <input type="number" id="calc-qty" value="10" oninput="recalc()" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm mono text-white focus:border-emerald-500 outline-none">
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Canale di Vendita</label>
            <div class="grid grid-cols-2 gap-3">
              <label class="flex items-center space-x-2 p-3 rounded-xl border border-slate-800 bg-slate-950/60 cursor-pointer">
                <input type="radio" name="calc-channel" value="bazaar" checked onchange="recalc()" class="accent-emerald-500">
                <span class="text-xs font-medium text-slate-200">Mio Bazaar (0% Tasse)</span>
              </label>
              <label class="flex items-center space-x-2 p-3 rounded-xl border border-slate-800 bg-slate-950/60 cursor-pointer">
                <input type="radio" name="calc-channel" value="im" onchange="recalc()" class="accent-emerald-500">
                <span class="text-xs font-medium text-slate-200">Item Market (5% Tasse)</span>
              </label>
            </div>
          </div>

          <div class="mt-6 p-4 rounded-xl bg-slate-950 border border-slate-800 grid grid-cols-3 gap-3 text-center">
            <div>
              <div class="text-[11px] text-slate-400">Spesa Totale</div>
              <div id="calc-res-cost" class="text-sm font-bold mono text-white mt-1">$850,000</div>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Ricavo Netto</div>
              <div id="calc-res-rev" class="text-sm font-bold mono text-emerald-400 mt-1">$1,000,000</div>
            </div>
            <div>
              <div class="text-[11px] text-slate-400">Profitto Netto (ROI)</div>
              <div id="calc-res-profit" class="text-sm font-bold mono text-amber-400 mt-1">+$150,000 (17.6%)</div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 5: SETTINGS -->
    <section id="pane-settings" class="tab-pane hidden">
      <div class="max-w-2xl mx-auto bg-slate-900/70 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h2 class="text-lg font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="settings" class="w-5 h-5 text-emerald-400"></i>
          Impostazioni Motore TornFlip
        </h2>
        <p class="text-xs text-slate-400 mb-6">Configura la tua API key di Torn e le soglie di rilevamento affari.</p>

        <form id="settings-form" onsubmit="saveSettings(event)" class="space-y-5">
          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Torn API Key (Public o Limited)</label>
            <div class="flex space-x-2">
              <input type="password" id="set-api-key" placeholder="Incolla la tua chiave API di Torn" class="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm mono text-white focus:border-emerald-500 outline-none">
              <button type="button" onclick="syncCatalogNow()" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded-xl transition text-slate-200">
                <i data-lucide="download-cloud" class="w-4 h-4 inline mr-1"></i> Sync DB
              </button>
            </div>
            <p class="text-[11px] text-slate-500 mt-1">Puoi generarla su <a href="https://www.torn.com/preferences.php#tab=api" target="_blank" class="text-emerald-400 underline">Torn.com > Preferences > API</a>.</p>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Sconto Minimo (%)</label>
              <input type="number" id="set-min-pct" step="0.5" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm mono text-white focus:border-emerald-500 outline-none">
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Profitto Minimo per Oggetto ($)</label>
              <input type="number" id="set-min-val" step="1000" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm mono text-white focus:border-emerald-500 outline-none">
            </div>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-300 mb-1">Budget Massimo per Transazione ($)</label>
            <input type="number" id="set-budget" step="1000000" class="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-2 text-sm mono text-white focus:border-emerald-500 outline-none">
          </div>

          <div class="pt-4 border-t border-slate-800 flex items-center justify-between">
            <span id="save-msg" class="text-xs font-medium text-emerald-400"></span>
            <button type="submit" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs rounded-xl shadow-lg transition">
              Salva Impostazioni
            </button>
          </div>
        </form>
      </div>
    </section>

  </main>

  <script>
    let globalDeals = [];

    function formatMoney(val) {
      return '$' + Number(val || 0).toLocaleString('en-US');
    }

    function switchTab(tabName) {
      document.querySelectorAll('.tab-pane').forEach(el => el.classList.add('hidden'));
      document.getElementById('pane-' + tabName).classList.remove('hidden');

      document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('bg-emerald-500', 'text-slate-950', 'shadow');
        btn.classList.add('text-slate-300');
      });
      const activeBtn = document.getElementById('tab-' + tabName);
      if (activeBtn) {
        activeBtn.classList.add('bg-emerald-500', 'text-slate-950', 'shadow');
        activeBtn.classList.remove('text-slate-300');
      }

      if (tabName === 'travel') fetchTravelDeals();
      if (tabName === 'city') fetchCityShops();
      lucide.createIcons();
    }

    async function loadStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('stat-catalog').innerText = data.items_in_catalog.toLocaleString();
        document.getElementById('stat-deals').innerText = data.deals_recorded.toLocaleString();
        
        const badge = document.getElementById('key-badge');
        const label = document.getElementById('key-label');
        if (data.has_api_key) {
          badge.className = 'hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium border bg-emerald-950/40 text-emerald-400 border-emerald-800/50';
          badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400"></span><span>API Key: ${data.api_key_masked}</span>`;
        } else {
          badge.className = 'hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium border bg-amber-950/40 text-amber-400 border-amber-800/50';
          badge.innerHTML = `<span class="w-2 h-2 rounded-full bg-amber-400 animate-pulse"></span><span>API Key Mancante</span>`;
        }

        document.getElementById('set-min-pct').value = data.min_profit_pct;
        document.getElementById('set-min-val').value = data.min_profit_val;
        document.getElementById('set-budget').value = data.max_buy_budget;
      } catch (e) {
        console.error("Errore fetch status:", e);
      }
    }

    async function fetchDeals() {
      try {
        const res = await fetch('/api/deals?limit=40');
        globalDeals = await res.json();
        renderDealsTable();
      } catch (e) {
        console.error(e);
      }
    }

    function renderDealsTable() {
      const tbody = document.getElementById('deals-tbody');
      const filter = document.getElementById('deal-filter').value;
      const filtered = filter === 'ALL' ? globalDeals : globalDeals.filter(d => d.deal_type === filter);

      if (!filtered.length) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-12 text-slate-500">
          <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
          Nessun affare rilevato con i filtri attuali. Clicca <strong>Scansiona Ora</strong> in alto per aggiornare.
        </td></tr>`;
        lucide.createIcons();
        return;
      }

      tbody.innerHTML = filtered.map(d => {
        let badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">FLIP</span>';
        if (d.deal_type === 'ZERO_RISK_PAWN') {
          badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">🛡️ ZERO-RISK PAWN</span>';
        } else if (d.deal_type === 'MADPUP_CRIME_DUMP') {
          badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 font-bold">🎯 NOOB CRIME DUMP</span>';
        } else if (d.deal_type === 'MADPUP_EVENT_ITEM') {
          badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/30 font-bold">🎉 EVENT PUMP ITEM</span>';
        } else if (d.deal_type === 'UNDERPRICED_BAZAAR') {
          badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">🏷️ SOTTO MERCATO</span>';
        } else if (d.deal_type === 'SPREAD_ARBITRAGE') {
          badge = '<span class="px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-400 border border-purple-500/30">📊 SPREAD GAP</span>';
        }

        const mugAlert = d.mug_risk 
          ? `<span class="inline-flex items-center gap-1 text-[10px] text-rose-400 bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-800 ml-1 font-semibold" title="Transazione >$10M: rischia mugging! Parcheggia subito in azioni SYM o vola!">⚠️ >$10M Mug Risk</span>` 
          : '';

        return `
          <tr class="table-row-hover transition">
            <td class="py-3 px-4">${badge}</td>
            <td class="py-3 px-4 font-semibold text-white">
              <div class="flex items-center">${d.item_name} ${mugAlert}</div>
              <div class="text-[10px] text-slate-500 font-normal">Disponibili: ${d.quantity_available || 1} pz</div>
            </td>
            <td class="py-3 px-4 text-right mono text-rose-400">${formatMoney(d.buy_price)}</td>
            <td class="py-3 px-4 text-right mono text-slate-300">${formatMoney(d.target_sell_price)}</td>
            <td class="py-3 px-4 text-right mono text-emerald-400 font-bold">+${formatMoney(d.profit_per_item)}</td>
            <td class="py-3 px-4 text-right mono text-amber-400 font-bold">+${formatMoney(d.total_profit)}</td>
            <td class="py-3 px-4 text-right mono font-bold text-emerald-400">${d.roi_pct}%</td>
            <td class="py-3 px-4 text-center">
              <a href="${d.buy_url}" target="_blank" class="inline-flex items-center space-x-1 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow transition">
                <span>Compra</span>
                <i data-lucide="external-link" class="w-3 h-3"></i>
              </a>
            </td>
          </tr>
        `;
      }).join('');
      lucide.createIcons();
    }

    async function triggerScan() {
      const btn = document.getElementById('btn-scan');
      btn.disabled = true;
      btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Scansione in corso...</span>`;
      lucide.createIcons();

      try {
        const res = await fetch('/api/scan', { method: 'POST' });
        const data = await res.json();
        if (!data.success) {
          alert(data.error || "Errore durante la scansione");
        } else {
          await fetchDeals();
          await loadStatus();
        }
      } catch (e) {
        alert("Errore di rete durante la scansione");
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i><span>Scansiona Ora</span>`;
        lucide.createIcons();
      }
    }

    function updateSuitcaseDisplay(val) {
      document.getElementById('suitcase-val').innerText = val;
    }

    async function fetchTravelDeals() {
      const tbody = document.getElementById('travel-tbody');
      tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-slate-500"><i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-1 text-cyan-400"></i> Interrogazione live YATA in corso...</td></tr>`;
      lucide.createIcons();

      try {
        const cap = document.getElementById('suitcase-cap').value;
        const res = await fetch('/api/travel?capacity=' + cap);
        const data = await res.json();

        if (data.length > 0) {
          document.getElementById('stat-top-travel').innerText = formatMoney(data[0].profit_per_hour) + '/h';
          document.getElementById('stat-top-travel-sub').innerText = `${data[0].item_name} (${data[0].country})`;
        }

        tbody.innerHTML = data.map(o => `
          <tr class="table-row-hover transition">
            <td class="py-3 px-4 font-semibold text-amber-400">${o.country}</td>
            <td class="py-3 px-4 font-bold text-white">${o.item_name}</td>
            <td class="py-3 px-4 text-right mono text-slate-300">${formatMoney(o.foreign_cost)}</td>
            <td class="py-3 px-4 text-right mono text-slate-400">${formatMoney(o.market_value)}</td>
            <td class="py-3 px-4 text-right mono text-emerald-400 font-bold">+${formatMoney(o.trip_profit)}</td>
            <td class="py-3 px-4 text-right mono text-amber-400 font-bold">${formatMoney(o.profit_per_hour)}/h</td>
            <td class="py-3 px-4 text-right mono text-cyan-400">${o.roi_pct}%</td>
            <td class="py-3 px-4 text-right mono text-slate-400">${o.stock_available.toLocaleString()}</td>
            <td class="py-3 px-4 text-center">
              <a href="https://www.torn.com/travelagency.php" target="_blank" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs transition inline-flex items-center gap-1">
                <span>Vola</span>
                <i data-lucide="external-link" class="w-3 h-3"></i>
              </a>
            </td>
          </tr>
        `).join('');
        lucide.createIcons();
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-6 text-rose-400">Errore nel caricamento stock YATA</td></tr>`;
      }
    }

    async function fetchCityShops() {
      const tbody = document.getElementById('city-tbody');
      tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-slate-500"><i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-1 text-amber-400"></i> Controllo stock negozi Torn...</td></tr>`;
      lucide.createIcons();

      try {
        const res = await fetch('/api/city-shops');
        const data = await res.json();
        if (data.error) {
          tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-amber-400">${data.error}</td></tr>`;
          return;
        }

        tbody.innerHTML = data.map(o => `
          <tr class="table-row-hover transition">
            <td class="py-3 px-4 text-amber-400 font-semibold">${o.shop}</td>
            <td class="py-3 px-4 text-white font-bold">${o.item_name}</td>
            <td class="py-3 px-4 text-right mono text-slate-300">${formatMoney(o.shop_price)}</td>
            <td class="py-3 px-4 text-right mono text-slate-400">${formatMoney(o.market_value)}</td>
            <td class="py-3 px-4 text-right mono text-emerald-400 font-bold">+${formatMoney(o.profit_per_item)}</td>
            <td class="py-3 px-4 text-right mono text-cyan-400">${o.roi_pct}%</td>
            <td class="py-3 px-4 text-right mono text-slate-400">${o.stock_available.toLocaleString()}</td>
            <td class="py-3 px-4 text-center">
              <a href="${o.buy_url}" target="_blank" class="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs transition inline-flex items-center gap-1">
                <span>Negozio</span>
                <i data-lucide="external-link" class="w-3 h-3"></i>
              </a>
            </td>
          </tr>
        `).join('');
        lucide.createIcons();
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Errore caricamento negozi</td></tr>`;
      }
    }

    function recalc() {
      const buy = parseFloat(document.getElementById('calc-buy').value) || 0;
      const sell = parseFloat(document.getElementById('calc-sell').value) || 0;
      const qty = parseInt(document.getElementById('calc-qty').value) || 1;
      const channel = document.querySelector('input[name="calc-channel"]:checked').value;

      const totalCost = buy * qty;
      const feePct = channel === 'im' ? 0.05 : 0.0;
      const netSellEach = sell * (1.0 - feePct);
      const totalRev = netSellEach * qty;
      const profit = totalRev - totalCost;
      const roi = totalCost > 0 ? ((profit / totalCost) * 100).toFixed(1) : 0;

      document.getElementById('calc-res-cost').innerText = formatMoney(totalCost);
      document.getElementById('calc-res-rev').innerText = formatMoney(totalRev);
      document.getElementById('calc-res-profit').innerText = (profit >= 0 ? '+' : '') + formatMoney(profit) + ` (${roi}%)`;
      document.getElementById('calc-res-profit').className = profit >= 0 ? 'text-sm font-bold mono text-emerald-400 mt-1' : 'text-sm font-bold mono text-rose-400 mt-1';
    }

    async function saveSettings(e) {
      e.preventDefault();
      const payload = {
        api_key: document.getElementById('set-api-key').value,
        min_profit_pct: parseFloat(document.getElementById('set-min-pct').value),
        min_profit_val: parseInt(document.getElementById('set-min-val').value),
        max_buy_budget: parseInt(document.getElementById('set-budget').value)
      };

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        document.getElementById('save-msg').innerText = data.message;
        setTimeout(() => document.getElementById('save-msg').innerText = '', 3000);
        await loadStatus();
      } catch (err) {
        alert("Errore salvataggio");
      }
    }

    async function syncCatalogNow() {
      const key = document.getElementById('set-api-key').value;
      if (!key) {
        alert("Inserisci prima l'API Key nel campo!");
        return;
      }
      await saveSettings({ preventDefault: () => {} });
      
      const msg = document.getElementById('save-msg');
      msg.innerText = "Sincronizzazione catalogo in corso...";
      try {
        const res = await fetch('/api/sync', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          msg.innerText = data.message;
          await loadStatus();
        } else {
          alert(data.error);
        }
      } catch (err) {
        alert("Errore durante sync");
      }
    }

    // Auto-init
    window.addEventListener('DOMContentLoaded', async () => {
      lucide.createIcons();
      await loadStatus();
      await fetchDeals();
      await fetchTravelDeals();
      recalc();
    });
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"[*] TornFlip Web Server avviato su http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
