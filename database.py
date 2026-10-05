import sqlite3
import time
from typing import Dict, Any, List, Optional
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
        description TEXT,
        buy_price INTEGER DEFAULT 0,
        sell_price INTEGER DEFAULT 0,
        market_value INTEGER DEFAULT 0,
        circulation INTEGER DEFAULT 0,
        updated_at INTEGER
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        item_name TEXT,
        deal_type TEXT, -- 'INSTANT_PAWN', 'BAZAAR_DISCOUNT', 'TRAVEL_ABROAD', 'SPREAD_FLIP'
        buy_source TEXT,
        buy_price INTEGER,
        target_sell_price INTEGER,
        quantity_available INTEGER DEFAULT 1,
        profit_per_item INTEGER,
        total_profit INTEGER,
        roi_pct REAL,
        seller_id INTEGER,
        buy_url TEXT,
        created_at INTEGER,
        status TEXT DEFAULT 'ACTIVE' -- 'ACTIVE', 'EXPIRED', 'BOUGHT'
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER,
        bazaar_lowest INTEGER,
        im_lowest INTEGER,
        timestamp INTEGER
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        item_id INTEGER PRIMARY KEY,
        target_buy_price INTEGER,
        notes TEXT
    )
    """)
    
    conn.commit()
    conn.close()

def upsert_items(items_dict: Dict[str, Any]):
    """Bulk upsert items from Torn API torn/items"""
    now = int(time.time())
    conn = get_connection()
    cursor = conn.cursor()
    
    records = []
    for item_id_str, data in items_dict.items():
        try:
            item_id = int(item_id_str)
            records.append((
                item_id,
                data.get("name", ""),
                data.get("type", ""),
                data.get("description", ""),
                int(data.get("buy_price", 0) or 0),
                int(data.get("sell_price", 0) or 0),
                int(data.get("market_value", 0) or 0),
                int(data.get("circulation", 0) or 0),
                now
            ))
        except (ValueError, TypeError):
            continue
            
    cursor.executemany("""
    INSERT INTO items (id, name, type, description, buy_price, sell_price, market_value, circulation, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        name=excluded.name,
        type=excluded.type,
        description=excluded.description,
        buy_price=excluded.buy_price,
        sell_price=excluded.sell_price,
        market_value=excluded.market_value,
        circulation=excluded.circulation,
        updated_at=excluded.updated_at
    """, records)
    
    conn.commit()
    conn.close()

def get_item(item_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_items_by_types(types: List[str]) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    placeholders = ",".join("?" for _ in types)
    cursor.execute(f"SELECT * FROM items WHERE type IN ({placeholders}) AND market_value > 0 ORDER BY circulation DESC", types)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_deal(deal: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO deals (
        item_id, item_name, deal_type, buy_source, buy_price, target_sell_price,
        quantity_available, profit_per_item, total_profit, roi_pct, seller_id, buy_url, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        deal["item_id"],
        deal.get("item_name", ""),
        deal["deal_type"],
        deal.get("buy_source", "Bazaar"),
        deal["buy_price"],
        deal["target_sell_price"],
        deal.get("quantity_available", 1),
        deal["profit_per_item"],
        deal["total_profit"],
        deal["roi_pct"],
        deal.get("seller_id"),
        deal.get("buy_url", ""),
        int(time.time())
    ))
    conn.commit()
    conn.close()

def get_recent_deals(limit: int = 30) -> List[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deals WHERE status = 'ACTIVE' ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# Initialize DB on load
init_db()
