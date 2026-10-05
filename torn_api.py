import time
import requests
from typing import Dict, Any, Optional
from config import TORN_API_KEY, TORN_API_URL, MAX_REQUESTS_PER_MINUTE

class TornAPIClient:
    def __init__(self, api_key: str = TORN_API_KEY):
        self.api_key = api_key
        self.last_request_time = 0.0
        self.min_interval = 60.0 / MAX_REQUESTS_PER_MINUTE  # ~0.7 seconds between calls
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "TornFlip-Bot/1.0"
        })

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def get(self, section: str, entity_id: str = "", selections: str = "") -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
            
        self._rate_limit()
        
        url = f"{TORN_API_URL}/{section}/{entity_id}" if entity_id else f"{TORN_API_URL}/{section}/"
        params = {
            "selections": selections,
            "key": self.api_key
        }
        
        try:
            resp = self.session.get(url, params=params, timeout=12)
            if resp.status_code != 200:
                print(f"[!] Errore HTTP {resp.status_code} su {url}")
                return None
                
            data = resp.json()
            if "error" in data:
                err = data["error"]
                code = err.get("code")
                msg = err.get("error")
                print(f"[!] Errore Torn API [Code {code}]: {msg}")
                if code == 5:
                    # Rate limit exceeded: sleep 15s
                    time.sleep(15)
                return None
                
            return data
        except Exception as e:
            print(f"[!] Eccezione durante richiesta API: {e}")
            return None

    def fetch_items_catalog(self) -> Optional[Dict[str, Any]]:
        """Recupera l'intero catalogo degli oggetti da torn/items"""
        res = self.get("torn", selections="items")
        if res and "items" in res:
            return res["items"]
        return None

    def fetch_market_listings(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Recupera le quotazioni di bazaar e item market per un singolo item"""
        return self.get("market", str(item_id), selections="bazaar,itemmarket")

    def fetch_city_shops(self) -> Optional[Dict[str, Any]]:
        """Recupera lo stock e i prezzi dei negozi della città"""
        res = self.get("torn", selections="cityshops")
        if res and "cityshops" in res:
            return res["cityshops"]
        return None
