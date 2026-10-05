from typing import Dict, Any, List, Optional
from config import (
    MIN_PROFIT_PERCENT,
    MIN_PROFIT_VALUE,
    MAX_BUY_BUDGET,
    ITEM_MARKET_FEE_PCT,
    AVOID_ITEMS,
    MADPUP_CRIME_ITEMS,
    MADPUP_EVENT_ITEMS,
    MUG_RISK_THRESHOLD
)
from database import save_deal

class FlippingEngine:
    def __init__(self, min_profit_pct: float = MIN_PROFIT_PERCENT, min_profit_val: int = MIN_PROFIT_VALUE):
        # Madpup: target standard almeno 10%
        self.min_profit_pct = max(min_profit_pct, 10.0)
        self.min_profit_val = min_profit_val

    def is_avoided(self, item_name: str) -> bool:
        """Controlla se l'articolo è tra quelli sconsigliati da Madpup (es. Xanax, EDVD, Sand)."""
        return any(avoid.lower() in item_name.lower() for avoid in AVOID_ITEMS)

    def analyze_item_listings(self, item: dict, market_data: dict) -> List[dict]:
        """
        Analizza le quotazioni di un oggetto (bazaar e item market) e rileva affari:
        1. Rischio zero (prezzo < prezzo di vendita al banco dei pegni/NPC)
        2. Madpup Crime Drops (HPCPU, Bank Statement, Medical Bill svenduti dai noob)
        3. Event Items (Cannabis, Beer, Blood Bags prima degli eventi)
        4. Forte sconto rispetto al market_value medio (>=10%)
        5. Arbitraggio di spread (primo prezzo molto più basso del secondo/terzo)
        """
        item_name = item.get("name", "")
        # Filtro Madpup: salta gli articoli trappola
        if self.is_avoided(item_name):
            return []

        deals = []
        bazaar_listings = market_data.get("bazaar", []) or []
        itemmarket_listings = market_data.get("itemmarket", []) or []
        
        market_val = item.get("market_value", 0)
        pawn_price = item.get("sell_price", 0)
        
        # 1. Analisi Bazaar
        if bazaar_listings:
            # Ordina per costo crescente
            sorted_bazaar = sorted(bazaar_listings, key=lambda x: x.get("cost", float("inf")))
            
            lowest = sorted_bazaar[0]
            buy_cost = lowest.get("cost", 0)
            quantity = lowest.get("quantity", 1)
            player_id = lowest.get("player_id")
            
            is_crime_item = any(ci.lower() in item_name.lower() for ci in MADPUP_CRIME_ITEMS)
            is_event_item = any(ei.lower() in item_name.lower() for ei in MADPUP_EVENT_ITEMS)
            
            total_buy_cost = buy_cost * quantity
            mug_risk = (total_buy_cost >= MUG_RISK_THRESHOLD)
            
            # --- DEAL TIPO 1: ISTANTANEO PAWN SHOP (RISCHIO ZERO) ---
            if pawn_price > 0 and buy_cost < pawn_price:
                profit_per_item = pawn_price - buy_cost
                total_profit = profit_per_item * quantity
                roi = round((profit_per_item / buy_cost) * 100, 1) if buy_cost > 0 else 999.0
                
                deal = {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "deal_type": "ZERO_RISK_PAWN",
                    "buy_source": "Bazaar",
                    "buy_price": buy_cost,
                    "target_sell_price": pawn_price,
                    "quantity_available": quantity,
                    "profit_per_item": profit_per_item,
                    "total_profit": total_profit,
                    "roi_pct": roi,
                    "seller_id": player_id,
                    "mug_risk": mug_risk,
                    "buy_url": f"https://www.torn.com/bazaar.php?userId={player_id}#/p=bazaar&userID={player_id}"
                }
                deals.append(deal)
                save_deal(deal)
                
            # --- DEAL TIPO 2: MADPUP NOOB CRIME DUMP (HPCPU, Bank Statements, ecc.) ---
            elif is_crime_item and market_val > 0 and buy_cost <= (market_val * 0.70):
                target_sell = int(market_val * 0.98)
                profit_per_item = target_sell - buy_cost
                total_profit = profit_per_item * quantity
                roi = round((profit_per_item / buy_cost) * 100, 1) if buy_cost > 0 else 0.0
                
                deal = {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "deal_type": "MADPUP_CRIME_DUMP",
                    "buy_source": "Bazaar",
                    "buy_price": buy_cost,
                    "target_sell_price": target_sell,
                    "quantity_available": quantity,
                    "profit_per_item": profit_per_item,
                    "total_profit": total_profit,
                    "roi_pct": roi,
                    "seller_id": player_id,
                    "mug_risk": mug_risk,
                    "buy_url": f"https://www.torn.com/bazaar.php?userId={player_id}#/p=bazaar&userID={player_id}"
                }
                deals.append(deal)
                save_deal(deal)

            # --- DEAL TIPO 3: EVENT ITEM TARGET (Cannabis, Beer, Blood Bags) ---
            elif is_event_item and market_val > 0 and buy_cost <= (market_val * (1.0 - (self.min_profit_pct / 100.0))):
                target_sell = int(market_val * 0.99)
                profit_per_item = target_sell - buy_cost
                total_profit = profit_per_item * quantity
                roi = round((profit_per_item / buy_cost) * 100, 1) if buy_cost > 0 else 0.0
                
                deal = {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "deal_type": "MADPUP_EVENT_ITEM",
                    "buy_source": "Bazaar",
                    "buy_price": buy_cost,
                    "target_sell_price": target_sell,
                    "quantity_available": quantity,
                    "profit_per_item": profit_per_item,
                    "total_profit": total_profit,
                    "roi_pct": roi,
                    "seller_id": player_id,
                    "mug_risk": mug_risk,
                    "buy_url": f"https://www.torn.com/bazaar.php?userId={player_id}#/p=bazaar&userID={player_id}"
                }
                deals.append(deal)
                save_deal(deal)

            # --- DEAL TIPO 4: SCONTO SIGNIFICATIVO STANDARD (>=10%) ---
            elif market_val > 0 and buy_cost <= (market_val * (1.0 - (self.min_profit_pct / 100.0))):
                target_sell = int(market_val * 0.99)
                profit_per_item = target_sell - buy_cost
                
                if profit_per_item >= self.min_profit_val and (buy_cost * quantity) <= MAX_BUY_BUDGET:
                    total_profit = profit_per_item * quantity
                    roi = round((profit_per_item / buy_cost) * 100, 1) if buy_cost > 0 else 0.0
                    
                    deal = {
                        "item_id": item["id"],
                        "item_name": item["name"],
                        "deal_type": "UNDERPRICED_BAZAAR",
                        "buy_source": "Bazaar",
                        "buy_price": buy_cost,
                        "target_sell_price": target_sell,
                        "quantity_available": quantity,
                        "profit_per_item": profit_per_item,
                        "total_profit": total_profit,
                        "roi_pct": roi,
                        "seller_id": player_id,
                        "mug_risk": mug_risk,
                        "buy_url": f"https://www.torn.com/bazaar.php?userId={player_id}#/p=bazaar&userID={player_id}"
                    }
                    deals.append(deal)
                    save_deal(deal)
                
            # --- DEAL TIPO 2: SCONTO SIGNIFICATIVO RISPETTO AL VALORE DI MERCATO ---
            elif market_val > 0 and buy_cost <= (market_val * (1.0 - (self.min_profit_pct / 100.0))):
                # Se rivendi nel tuo bazaar la fee è 0%, se sull'Item Market è 5%
                target_sell = int(market_val * 0.99) # Prezzo appena sotto il market value per vendita rapida
                profit_per_item = target_sell - buy_cost
                
                if profit_per_item >= self.min_profit_val and (buy_cost * quantity) <= MAX_BUY_BUDGET:
                    total_profit = profit_per_item * quantity
                    roi = round((profit_per_item / buy_cost) * 100, 1) if buy_cost > 0 else 0.0
                    
                    deal = {
                        "item_id": item["id"],
                        "item_name": item["name"],
                        "deal_type": "UNDERPRICED_BAZAAR",
                        "buy_source": "Bazaar",
                        "buy_price": buy_cost,
                        "target_sell_price": target_sell,
                        "quantity_available": quantity,
                        "profit_per_item": profit_per_item,
                        "total_profit": total_profit,
                        "roi_pct": roi,
                        "seller_id": player_id,
                        "buy_url": f"https://www.torn.com/bazaar.php?userId={player_id}#/p=bazaar&userID={player_id}"
                    }
                    deals.append(deal)
                    save_deal(deal)

            # --- DEAL TIPO 3: SPREAD TRA PRIMO E SECONDO/TERZO LISTING ---
            if len(sorted_bazaar) >= 2:
                second = sorted_bazaar[1]
                second_cost = second.get("cost", 0)
                if second_cost > 0 and buy_cost > 0:
                    spread_pct = ((second_cost - buy_cost) / second_cost) * 100.0
                    if spread_pct >= 12.0:
                        target_sell = second_cost - 1
                        profit_per_item = target_sell - buy_cost
                        if profit_per_item >= self.min_profit_val:
                            deal = {
                                "item_id": item["id"],
                                "item_name": item["name"],
                                "deal_type": "SPREAD_ARBITRAGE",
                                "buy_source": "Bazaar",
                                "buy_price": buy_cost,
                                "target_sell_price": target_sell,
                                "quantity_available": quantity,
                                "profit_per_item": profit_per_item,
                                "total_profit": profit_per_item * quantity,
                                "roi_pct": round((profit_per_item / buy_cost) * 100, 1),
                                "seller_id": player_id,
                                "buy_url": f"https://www.torn.com/bazaar.php?userId={player_id}#/p=bazaar&userID={player_id}"
                            }
                            deals.append(deal)
                            save_deal(deal)

        return deals

    def analyze_city_shops(self, shops_data: dict, items_dict: Dict[int, dict]) -> List[dict]:
        """
        Trova oggetti nei negozi ufficiali di Torn (Pharmacy, Sweet Shop, Bits 'n' Bobs)
        che possono essere acquistati a prezzo fisso e rivenduti sul bazaar con alto margine.
        """
        opportunities = []
        for shop_name, shop_items in shops_data.items():
            if not isinstance(shop_items, dict):
                continue
            for item_id_str, details in shop_items.items():
                try:
                    item_id = int(item_id_str)
                except ValueError:
                    continue
                cost = details.get("cost", 0)
                stock = details.get("stock", 0)
                if cost <= 0 or stock <= 0:
                    continue
                
                item_info = items_dict.get(item_id)
                if not item_info:
                    continue
                    
                market_val = item_info.get("market_value", 0)
                if market_val > (cost * 1.25) and (market_val - cost) >= 500:
                    profit_per_item = market_val - cost
                    roi = round((profit_per_item / cost) * 100, 1)
                    opportunities.append({
                        "item_id": item_id,
                        "item_name": item_info.get("name", f"Item #{item_id}"),
                        "shop": shop_name,
                        "shop_price": cost,
                        "market_value": market_val,
                        "profit_per_item": profit_per_item,
                        "stock_available": stock,
                        "roi_pct": roi,
                        "buy_url": "https://www.torn.com/city.php#city-shops"
                    })
                    
        opportunities.sort(key=lambda x: x["profit_per_item"], reverse=True)
        return opportunities
