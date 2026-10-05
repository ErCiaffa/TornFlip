import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tornflip.db"
ENV_PATH = BASE_DIR / ".env"

def load_env():
    """Simple parser for .env without external dotenv dependency."""
    if not ENV_PATH.exists():
        return
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

load_env()

# Config values
TORN_API_KEY = os.getenv("TORN_API_KEY", "").strip()
MIN_PROFIT_PERCENT = float(os.getenv("MIN_PROFIT_PERCENT", "10.0"))  # Regola Madpup: minimo 10%
MIN_PROFIT_VALUE = int(os.getenv("MIN_PROFIT_VALUE", "15000"))
MAX_BUY_BUDGET = int(os.getenv("MAX_BUY_BUDGET", "100000000"))
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
MUG_RISK_THRESHOLD = 10000000  # $10M: Oltre questa cifra scatta l'allerta mugging!

# Market Fees
ITEM_MARKET_FEE_PCT = 0.05  # 5% tax when sold on Item Market (Torn Tax post-IM 2.0)
BAZAAR_FEE_PCT = 0.00       # 0% tax when sold on own Bazaar

# API Limits
TORN_API_URL = "https://api.torn.com"
MAX_REQUESTS_PER_MINUTE = 85  # Torn limit is 100/min; safe threshold is 85

# Madpup: Articoli da EVITARE (spread minuscoli o capitale bloccato)
AVOID_ITEMS = [
    "Xanax",        # Troppa concorrenza bot, spread <1%
    "Erotic DVD",   # Prezzo ultra-stabile, rotazione lenta
    "Sand"          # Troppo costoso ($25M+), mercato quasi inesistente
]

# Madpup: Articoli ad Alto Rendimento da monitorare attivamente
# 1. Search for cash & Forgery (i noob li svendono a pochi dollari credendoli spazzatura)
MADPUP_CRIME_ITEMS = [
    "HPCPU",
    "Bank Statement",
    "Medical Bill",
    "Blank Credit Card",
    "Certificate of Authenticity",
    "Bond Certificate",
    "Microchip",
    "Fluorescent Light Tube"
]

# 2. Event Timed Items & High Volatility Boosters
MADPUP_EVENT_ITEMS = [
    "Cannabis",                 # 420 Day (20 Aprile)
    "Bottle of Beer",           # International Beer Day
    "Empty Blood Bag",          # World Blood Day
    "Blood Bag : O+",
    "Blood Bag : A+",
    "Big Box of Chocolates",    # Happy Jumps & Wall Buyouts
    "Box of Chocolates"
]

# High-liquidity item types prioritized for flipping
PRIORITY_ITEM_TYPES = [
    "Plushie",
    "Flower",
    "Drug",
    "Booster",
    "Energy Drink",
    "Candy",
    "Alcohol",
    "Medical",
    "Enhancer",
    "Supply Pack"
]

# Round-trip flight times (minutes) for travel arbitrage
# Standard roundtrip times without business class / airstrip
TRAVEL_ROUNDTRIP_MINUTES = {
    "mex": 36,     # Mexico
    "cay": 50,     # Cayman Islands
    "can": 58,     # Canada
    "haw": 188,    # Hawaii
    "uni": 222,    # United Kingdom
    "arg": 234,    # Argentina
    "swi": 246,    # Switzerland
    "jap": 316,    # Japan
    "chi": 338,    # China
    "uae": 462,    # UAE
    "sou": 476,    # South Africa
}

