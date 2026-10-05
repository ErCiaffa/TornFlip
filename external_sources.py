import re
import json
import requests
from typing import Dict, Any, List, Optional
from config import TRAVEL_ROUNDTRIP_MINUTES

YATA_TRAVEL_URL = "https://yata.yt/api/v1/travel/export/"
WEAV3R_BASE_URL = "https://weav3r.dev"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def fetch_yata_travel_stocks() -> Dict[str, Any]:
    """
    Recupera i dati live sullo stock dei negozi all'estero da YATA (no auth necessaria).
    Ritorna per ogni paese: item, quantity, cost all'estero.
    """
    try:
        resp = requests.get(YATA_TRAVEL_URL, headers=BROWSER_HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("stocks", {})
    except Exception as e:
        print(f"[!] Errore nel recupero stock YATA: {e}")
    return {}

def calculate_travel_arbitrage(yata_stocks: Dict[str, Any], items_catalog: Dict[int, dict], capacity: int = 29) -> List[dict]:
    """
    Calcola le migliori opportunità di flipping estero (plushies, fiori, ecc.):
    Profitto per item, per volo (capacity) e all'ora ($/hr).
    """
    opportunities = []
    
    country_names = {
        "mex": "Mexico",
        "cay": "Cayman Islands",
        "can": "Canada",
        "haw": "Hawaii",
        "uni": "United Kingdom",
        "arg": "Argentina",
        "swi": "Switzerland",
        "jap": "Japan",
        "chi": "China",
        "uae": "UAE",
        "sou": "South Africa",
    }
    
    for country_code, country_info in yata_stocks.items():
        c_name = country_names.get(country_code, country_code.upper())
        rt_minutes = TRAVEL_ROUNDTRIP_MINUTES.get(country_code, 120)
        
        for stock_item in country_info.get("stocks", []):
            item_id = stock_item.get("id")
            name = stock_item.get("name")
            quantity = stock_item.get("quantity", 0)
            cost = stock_item.get("cost", 0)
            
            if quantity <= 0 or cost <= 0:
                continue
                
            # Trova market value su Torn
            item_info = items_catalog.get(item_id)
            if not item_info:
                continue
                
            market_val = item_info.get("market_value", 0)
            if market_val <= cost:
                continue
                
            profit_per_item = market_val - cost
            # Consideriamo la capienza valigia (es. 29 con Large Suitcase + Airstrip)
            units = min(quantity, capacity)
            trip_profit = profit_per_item * units
            
            # Calcolo $/ora
            hours = rt_minutes / 60.0
            profit_per_hour = int(trip_profit / hours) if hours > 0 else 0
            roi_pct = round((profit_per_item / cost) * 100, 1)
            
            opportunities.append({
                "item_id": item_id,
                "item_name": name,
                "country": c_name,
                "country_code": country_code,
                "foreign_cost": cost,
                "market_value": market_val,
                "profit_per_item": profit_per_item,
                "stock_available": quantity,
                "trip_profit": trip_profit,
                "roi_pct": roi_pct,
                "roundtrip_min": rt_minutes,
                "profit_per_hour": profit_per_hour
            })
            
    # Ordina per profitto orario decrescente
    opportunities.sort(key=lambda x: x["profit_per_hour"], reverse=True)
    return opportunities

def scrape_weav3r_dollar_bazaars() -> List[dict]:
    """
    Tenta di estrarre listing da https://weav3r.dev/dollar-bazaars se accessibile.
    Cerca pattern JSON o listing nel payload Next.js.
    """
    deals = []
    try:
        url = f"{WEAV3R_BASE_URL}/dollar-bazaars"
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=12)
        if resp.status_code == 200:
            # Match item listings from next.js JSON stream
            text = resp.text
            # Cerca blocchi tipo {"id":..., "name":..., "price":1, "market_value":...}
            matches = re.findall(r'\{[^{}]*"name"\s*:\s*"([^"]+)"[^{}]*"price"\s*:\s*([0-9]+)[^{}]*\}', text)
            for m in matches:
                deals.append({
                    "name": m[0],
                    "price": int(m[1]),
                    "source": "weav3r.dev/dollar-bazaars"
                })
    except Exception as e:
        print(f"[!] Info weav3r scraper: {e}")
    return deals
