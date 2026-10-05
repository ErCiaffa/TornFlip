#!/usr/bin/env python3
import sys
import time
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from config import (
    TORN_API_KEY,
    POLL_INTERVAL_SECONDS,
    PRIORITY_ITEM_TYPES,
    MIN_PROFIT_PERCENT,
    MIN_PROFIT_VALUE
)
from database import (
    get_connection,
    upsert_items,
    get_items_by_types,
    get_recent_deals,
    get_item
)
from torn_api import TornAPIClient
from external_sources import (
    fetch_yata_travel_stocks,
    calculate_travel_arbitrage,
    scrape_weav3r_dollar_bazaars
)
from analyzer import FlippingEngine

console = Console()

def format_money(val: int) -> str:
    return f"${val:,.0f}"

def show_banner():
    banner = Text(
        "╔══════════════════════════════════════════════╗\n"
        "║           TORNFLIP - MARKET ADVISOR          ║\n"
        "║  Arbitrage, Bazaar Flipping & Travel Engine  ║\n"
        "╚══════════════════════════════════════════════╝",
        style="bold cyan"
    )
    console.print(banner)

def cmd_sync(api_client: TornAPIClient):
    """Sincronizza il catalogo di tutti gli oggetti da Torn API"""
    if not api_client.api_key:
        console.print("[bold red][!] Chiave API non impostata in .env![/bold red]")
        console.print("Apri il file [bold yellow].env[/bold yellow] e inserisci la tua [green]TORN_API_KEY[/green].")
        return False
        
    with console.status("[bold green]Scaricamento catalogo completo oggetti Torn (torn/items)..."):
        items = api_client.fetch_items_catalog()
        if not items:
            console.print("[bold red][!] Impossibile scaricare gli oggetti. Controlla la tua API key.[/bold red]")
            return False
        upsert_items(items)
        
    console.print(f"[bold green][✓] Catalogo aggiornato con successo: {len(items)} oggetti memorizzati nel database locale.[/bold green]")
    return True

def cmd_travel():
    """Mostra le opportunità di viaggio (Plushies, Fiori) da YATA live"""
    console.print("[bold cyan]Recupero stock negozi all'estero da YATA (live)...[/bold cyan]")
    stocks = fetch_yata_travel_stocks()
    if not stocks:
        console.print("[bold red][!] Nessun dato ricevuto da YATA.[/bold red]")
        return
        
    # Carica catalogo locale
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, market_value FROM items")
    rows = c.fetchall()
    conn.close()
    
    catalog = {r["id"]: dict(r) for r in rows}
    
    if not catalog:
        console.print("[yellow][!] Catalogo locale vuoto. Esegui prima 'python main.py sync' con la tua API key, oppure uso stime provvisorie.[/yellow]")
        # Mappa provvisoria per plushies/fiori noti
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

    opps = calculate_travel_arbitrage(stocks, catalog, capacity=29)
    
    if not opps:
        console.print("[yellow]Nessun oggetto estero attualmente in stock o con margine positivo.[/yellow]")
        return
        
    table = Table(title="Top Travel Flipping Opportunities (29 items suitcase)", style="cyan")
    table.add_column("Paese", style="yellow")
    table.add_column("Oggetto", style="bold white")
    table.add_column("Costo Estero", justify="right")
    table.add_column("Valore Torn", justify="right", style="green")
    table.add_column("Profitto / Run", justify="right", style="bold green")
    table.add_column("ROI %", justify="right", style="magenta")
    table.add_column("Profitto / Ora", justify="right", style="bold yellow")
    table.add_column("Stock", justify="right")
    
    for o in opps[:15]:
        table.add_row(
            o["country"],
            o["item_name"],
            format_money(o["foreign_cost"]),
            format_money(o["market_value"]),
            format_money(o["trip_profit"]),
            f"{o['roi_pct']}%",
            f"{format_money(o['profit_per_hour'])}/h",
            f"{o['stock_available']:,}"
        )
        
    console.print(table)
    console.print("\n[dim]Nota: I calcoli si basano su 29 slot valigia (Large Suitcase + Airstrip) e tempi standard di volo.[/dim]")

def cmd_scan(api_client: TornAPIClient):
    """Scansiona gli oggetti ad alta liquidità (Plushies, Drugs, Cans, Boosters)"""
    if not api_client.api_key:
        console.print("[bold red][!] Chiave API non impostata in .env![/bold red]")
        return
        
    target_items = get_items_by_types(PRIORITY_ITEM_TYPES)
    if not target_items:
        console.print("[yellow]Database vuoto! Esegui prima 'python main.py sync' per scaricare gli oggetti.[/yellow]")
        return

    console.print(f"[bold cyan]Avvio scansione mercato su {len(target_items)} item prioritari...[/bold cyan]")
    engine = FlippingEngine()
    deals_found = []
    
    # Seleziona i top 40 item più scambiati/in circolazione per restare ben dentro i rate limit
    scan_pool = target_items[:40]
    
    with console.status(f"[bold green]Controllo quotazioni in corso...") as status:
        for idx, item in enumerate(scan_pool, 1):
            status.update(f"Analisi [{idx}/{len(scan_pool)}]: {item['name']}...")
            mkt = api_client.fetch_market_listings(item["id"])
            if not mkt:
                continue
            item_deals = engine.analyze_item_listings(item, mkt)
            if item_deals:
                for d in item_deals:
                    deals_found.append(d)
                    console.print(
                        f"[bold green][AFFARONE TROVATO!][/bold green] {d['item_name']} a [yellow]{format_money(d['buy_price'])}[/yellow] "
                        f"(Target: [green]{format_money(d['target_sell_price'])}[/green]) | Profitto: [bold cyan]{format_money(d['profit_per_item'])}[/bold cyan] ({d['roi_pct']}%)"
                    )

    if not deals_found:
        console.print("[yellow]Nessun affare fuori mercato rilevato al momento tra gli item scansionati.[/yellow]")
    else:
        show_deals_table(deals_found)

def cmd_city(api_client: TornAPIClient):
    """Controlla i negozi cittadini di Torn per acquisti a basso costo con rivendita garantita"""
    if not api_client.api_key:
        console.print("[bold red][!] Chiave API non impostata in .env![/bold red]")
        return
        
    console.print("[bold cyan]Controllo disponibilità stock nei City Shops di Torn...[/bold cyan]")
    shops = api_client.fetch_city_shops()
    if not shops:
        console.print("[yellow]Impossibile ottenere i dati dei City Shops.[/yellow]")
        return
        
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, market_value FROM items")
    rows = c.fetchall()
    conn.close()
    catalog = {r["id"]: dict(r) for r in rows}
    
    engine = FlippingEngine()
    opps = engine.analyze_city_shops(shops, catalog)
    
    if not opps:
        console.print("[yellow]Nessun oggetto con margine nei city shops al momento.[/yellow]")
        return
        
    table = Table(title="City Shops Flipping (Compra dal negozio NPC -> Vendi su Bazaar)", style="green")
    table.add_column("Negozio", style="yellow")
    table.add_column("Oggetto", style="bold white")
    table.add_column("Prezzo Negozio", justify="right")
    table.add_column("Valore Bazaar", justify="right", style="green")
    table.add_column("Profitto / Pezzo", justify="right", style="bold green")
    table.add_column("ROI %", justify="right", style="magenta")
    table.add_column("Stock", justify="right")
    
    for o in opps[:15]:
        table.add_row(
            o["shop"],
            o["item_name"],
            format_money(o["shop_price"]),
            format_money(o["market_value"]),
            format_money(o["profit_per_item"]),
            f"{o['roi_pct']}%",
            f"{o['stock_available']:,}"
        )
    console.print(table)

def show_deals_table(deals):
    table = Table(title="🔥 Affari di Mercato Rilevati 🔥", style="bold green")
    table.add_column("Tipo", style="yellow")
    table.add_column("Oggetto", style="bold white")
    table.add_column("Prezzo Acquisto", justify="right", style="red")
    table.add_column("Target Rivendita", justify="right", style="green")
    table.add_column("Profitto Totale", justify="right", style="bold yellow")
    table.add_column("ROI %", justify="right", style="magenta")
    table.add_column("Link Acquisto", style="blue")
    
    for d in deals:
        table.add_row(
            d.get("deal_type", "FLIP"),
            d.get("item_name", ""),
            format_money(d.get("buy_price", 0)),
            format_money(d.get("target_sell_price", 0)),
            format_money(d.get("total_profit", 0)),
            f"{d.get('roi_pct', 0)}%",
            d.get("buy_url", "https://www.torn.com")
        )
    console.print(table)

def cmd_monitor(api_client: TornAPIClient):
    """Loop continuo di monitoraggio del mercato"""
    if not api_client.api_key:
        console.print("[bold red][!] Chiave API non impostata in .env![/bold red]")
        return
        
    console.print(f"[bold green]Avvio monitoraggio automatico continuo (intervallo: {POLL_INTERVAL_SECONDS}s). Premere Ctrl+C per fermare.[/bold green]")
    try:
        while True:
            console.print(f"\n[cyan][{time.strftime('%H:%M:%S')}] Scansione periodica in corso...[/cyan]")
            cmd_scan(api_client)
            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoraggio interrotto dall'utente.[/yellow]")

def cmd_status():
    """Verifica lo stato del sistema e del database"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM items")
    item_count = c.fetchone()["count"]
    c.execute("SELECT COUNT(*) as count FROM deals")
    deal_count = c.fetchone()["count"]
    conn.close()
    
    key_status = "[bold green]CONFIGURATA[/bold green]" if TORN_API_KEY else "[bold red]NON CONFIGURATA[/bold red]"
    
    panel = Panel(
        f"[bold]Torn API Key:[/bold] {key_status}\n"
        f"[bold]Oggetti nel DB locale:[/bold] {item_count}\n"
        f"[bold]Affari registrati nel DB:[/bold] {deal_count}\n"
        f"[bold]Soglia Minima Guadagno:[/bold] {format_money(MIN_PROFIT_VALUE)} / {MIN_PROFIT_PERCENT}%\n"
        f"[bold]Fonti Esterne Attive:[/bold] YATA live travel, weav3r.dev monitor",
        title="Stato Sistema TornFlip",
        style="cyan"
    )
    console.print(panel)

def main():
    show_banner()
    
    parser = argparse.ArgumentParser(description="TornFlip - Personal Market Flipping Assistant")
    parser.add_argument("command", nargs="?", default="status", choices=["sync", "scan", "travel", "city", "monitor", "status", "deals"],
                        help="Comando da eseguire")
    args = parser.parse_args()
    
    api_client = TornAPIClient(TORN_API_KEY)
    
    if args.command == "status":
        cmd_status()
        console.print("\n[dim]Comandi disponibili:[/dim]")
        console.print("  [bold cyan]python main.py travel[/bold cyan]   -> Opportunità di flipping estero (Plushies/Fiori) con YATA live")
        console.print("  [bold cyan]python main.py sync[/bold cyan]     -> Sincronizza il catalogo oggetti con Torn API")
        console.print("  [bold cyan]python main.py scan[/bold cyan]     -> Scansiona bazaar e trova sconti/errori di prezzo")
        console.print("  [bold cyan]python main.py city[/bold cyan]     -> Controlla negozi della città per arbitraggio")
        console.print("  [bold cyan]python main.py monitor[/bold cyan]  -> Monitoraggio continuo in tempo reale")
        console.print("  [bold cyan]python main.py deals[/bold cyan]    -> Mostra gli affari recenti registrati")
    elif args.command == "sync":
        cmd_sync(api_client)
    elif args.command == "travel":
        cmd_travel()
    elif args.command == "scan":
        cmd_scan(api_client)
    elif args.command == "city":
        cmd_city(api_client)
    elif args.command == "monitor":
        cmd_monitor(api_client)
    elif args.command == "deals":
        deals = get_recent_deals(20)
        if deals:
            show_deals_table(deals)
        else:
            console.print("[yellow]Nessun affare recente salvato nel database.[/yellow]")

if __name__ == "__main__":
    main()
