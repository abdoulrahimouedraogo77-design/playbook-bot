import os
import sys
import types
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

if 'imghdr' not in sys.modules:
    dummy_imghdr = types.ModuleType('imghdr')
    dummy_imghdr.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = dummy_imghdr

logging.basicConfig(level=logging.INFO)

TOKEN = "8657135601:AAG-iKsu73uJ45g3UvWBz9fJV_3xCo0dTnM"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"PLAYBOOK_SCANNER_OK")

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def fetch_solana_pairs():
    """Interroge plusieurs endpoints DexScreener pour maximiser la couverture."""
    endpoints = [
        "https://api.dexscreener.com/latest/dex/search?q=SOL",
        "https://api.dexscreener.com/latest/dex/search?q=pump",
        "https://api.dexscreener.com/latest/dex/search?q=raydium"
    ]
    seen_addresses = set()
    all_pairs = []

    for url in endpoints:
        try:
            res = requests.get(url, timeout=8)
            if res.status_code == 200:
                data = res.json().get('pairs', [])
                for p in data:
                    addr = p.get('pairAddress')
                    if addr and addr not in seen_addresses and p.get('chainId') == 'solana':
                        seen_addresses.add(addr)
                        all_pairs.append(p)
        except Exception:
            continue
    return all_pairs

def format_card(category_title, pair, age_hours, mc, liquidity):
    base = pair.get('baseToken', {})
    name = base.get('name', 'Inconnu')
    symbol = base.get('symbol', 'UNKNOWN')
    address = base.get('address', '')
    price = str(pair.get('priceUsd', '0'))
    
    txns5m = pair.get('txns', {}).get('m5', {})
    buys5m = txns5m.get('buys', 0)
    sells5m = txns5m.get('sells', 0)
    vol24h = pair.get('volume', {}).get('h24', 0)

    age_str = f"{age_hours:.1f}h ({age_hours/24:.1f}j)" if age_hours >= 24 else f"{age_hours:.1f}h"

    return (
        f"{category_title}\n\n"
        f"🪙 **{name}** (`${symbol}`)\n"
        f"⏱ **Âge :** {age_str}\n"
        f"💰 **MC :** ${mc:,.0f} \vert{} **Prix :**${price}\n"
        f"💧 **Liquidité :** ${liquidity:,.0f} \vert{} **Vol 24h :**${vol24h:,.0f}\n"
        f"⚡ **Tape (5m) :** 🟢 {buys5m} buys | 🔴 {sells5m} sells\n\n"
        f"📋 **CA :**\n`{address}`\n\n"
        f"🔍 [DexScreener]({pair.get('url', '')}) | [Inspecter sur GMGN](https://gmgn.ai/sol/token/{address})"
    )

def execute_playbook_scan():
    pairs = fetch_solana_pairs()
    if not pairs:
        return "⚠️ Impossible de synchroniser les flux de paires Solana."

    now = time.time() * 1000
    dips_cards = []
    midcaps_cards = []
    fresh_runners_cards = []

    for pair in pairs:
        created_at = pair.get('pairCreatedAt', 0)
        if not created_at:
            continue

        age_hours = (now - created_at) / (1000 * 3600)
        mc = pair.get('marketCap') or pair.get('fdv') or 0
        liquidity = pair.get('liquidity', {}).get('usd', 0)

        # Filtre anti-scam de base
        if liquidity < 8000:
            continue

        # FILTRE 1 : Dip Runner (1-4 jours, MC 100k$- 350k$)
        if (24 <= age_hours <= 96) and (100000 <= mc <= 350000):
            if len(dips_cards) < 2:
                dips_cards.append(format_card("🎯 **PROFIL 1 : DIP RUNNER (1-4j | Rebound)**", pair, age_hours, mc, liquidity))

        # FILTRE 2 : Noms Établis (7+ jours, MC < 25M$, Entrées 5M$-10M$)
        elif (age_hours >= 168) and (mc <= 25000000) and (liquidity >= 100000):
            if len(midcaps_cards) < 2:
                midcaps_cards.append(format_card("💎 **PROFIL 2 : RUNNER ÉTABLI (7+ jours | Setup 50M+)**", pair, age_hours, mc, liquidity))

        # FILTRE 3 : Lancements Frais avec Volume (< 7j, MC > 500k$)
        elif (age_hours < 168) and (mc >= 500000) and (liquidity >= 30000):
            if len(fresh_runners_cards) < 2:
                fresh_runners_cards.append(format_card("🚀 **PROFIL 3 : FRESH RUNNER (< 7j | Obj 10M-20M)**", pair, age_hours, mc, liquidity))

    total_results = dips_cards + midcaps_cards + fresh_runners_cards

    if not total_results:
        return (
            "📡 **SCAN PLAYBOOK EXÉCUTÉ**\n\n"
            "Aucun token ne rentre dans les 3 configurations cibles pour le moment.\n"
            "• Profil 1 : 24h-96h & MC 100k-350k\n"
            "• Profil 2 : > 7j & MC < 25M\n"
            "• Profil 3 : < 7j & MC > 500k\n\n"
            "Renvoyez `s` dans quelques minutes pour réanalyser le flux."
        )

    return "\n\n━━━━━━━━━━━━━━━\n\n".join(total_results)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ **Playbook Scanner Solana Actif**\n\n"
        "• Profil 1 : Dips post-dump (1-4 jours | 100k-350k MC)\n"
        "• Profil 2 : Runners établis (> 7 jours | < 25M MC)\n"
        "• Profil 3 : Fresh Runners (< 7 jours | > 500k MC)\n\n"
        "Tapez **s** pour scanner instantanément."
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip().lower()
    if text == 's':
        await update.message.reply_text("🔎 Analyse du marché selon les 3 règles du Playbook...")
        rapport = execute_playbook_scan()
        await update.message.reply_text(rapport, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    print("Bot Playbook multi-profils prêt.")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
    
