import os
import sys
import types

# Fix pour compatibilité Python (imghdr)
if 'imghdr' not in sys.modules:
    dummy_imghdr = types.ModuleType('imghdr')
    dummy_imghdr.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = dummy_imghdr

import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = '8646433044:AAGlwrPeXXbnL-EGCKJBFPpZkEIJzWBRUuY'

# Petit serveur pour satisfaire Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot en ligne !")

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def scanner_playbook():
    """Scanne les tokens Solana respectant le Playbook Reversal"""
    search_url = 'https://api.dexscreener.com/latest/dex/search?q=SOL'
    try:
        response = requests.get(search_url, timeout=10)
        if response.status_code != 200:
            return "Impossible de récupérer les données du marché."
        data = response.json()
        pairs = data.get('pairs', [])
        resultats = []
        import time
        now = time.time() * 1000
        for pair in pairs:
            if pair.get('chainId') != 'solana':
                continue
            created_at = pair.get('pairCreatedAt', 0)
            if not created_at:
                continue
            age_hours = (now - created_at) / (1000 * 3600)
            # Critère 1 : Âge entre 24h et 96h (1 à 4 jours)
            if not (24 <= age_hours <= 96):
                continue
            # Critère 2 : Market Cap entre 100k et 350k
            mc = pair.get('marketCap') or pair.get('fdv') or 0
            if not (100000 <= mc <= 350000):
                continue
            base = pair.get('baseToken', {})
            name = base.get('name', 'Inconnu')
            symbol = base.get('symbol', 'UNKNOWN')
            address = base.get('address', '')
            price = pair.get('priceUsd', '0')
            liquidity = pair.get('liquidity', {}).get('usd', 0)
            txns5m = pair.get('txns', {}).get('m5', {})
            buys = txns5m.get('buys', 0)
            sells = txns5m.get('sells', 0)
            ratio = (buys / sells) if sells > 0 else buys

            text = (
                f"🎯 *MEMECOIN PLAYBOOK VALIDÉ*\n\n"
                f"🪙 *{name} (${symbol})*\n"
                f"⏱ Âge : {age_hours:.1f}h ({age_hours/24:.1f}j)\n"
                f"💰 MC : ${mc:,.0f} \vert{} Prix :${price}\n"
                f"💧 Liquidité : ${liquidity:,.0f}\n"
                f"🟢 {buys} Achats vs 🔴 {sells} Ventes (Ratio {ratio:.1f}x)\n"
                f"📋 CA :\n`{address}`"
            )
            resultats.append(text)
            if len(resultats) >= 3:
                break
        if not resultats:
            return "📡 *SCAN EN DIRECT :* Aucun token ne valide actuellement tous les critères stricts (Âge 24h-96h, MC 100k-350k)."
        return "\n\n---\n\n".join(resultats)
    except Exception as e:
        return f"Erreur lors du scan : {e}"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "🤖 *Bot Scanner Actif !*\n\nEnvoyez la lettre *s* pour lancer le scan."
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip().lower()
    if user_text == 's':
        await update.message.reply_text("🔎 Scan en cours...")
        res = scanner_playbook()
        await update.message.reply_text(res, parse_mode='Markdown')

def main():
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    app = ApplicationBuilder().token(
            
