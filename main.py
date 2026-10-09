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

TOKEN = "8646433044:AAGlwrPeXXbnL-EGCKJBFPpZkEIJzWBRUuY"

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def scanner_playbook():
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            return "Impossible de récupérer les données."
        data = res.json()
        pairs = data.get('pairs', [])
        resultats = []
        now = time.time() * 1000

        for pair in pairs:
            if pair.get('chainId') != 'solana':
                continue
            created_at = pair.get('pairCreatedAt', 0)
            if not created_at:
                continue
            age_hours = (now - created_at) / (1000 * 3600)
            if not (24 <= age_hours <= 96):
                continue
            mc = pair.get('marketCap') or pair.get('fdv') or 0
            if not (100000 <= mc <= 350000):
                continue

            base = pair.get('baseToken', {})
            name = base.get('name', 'Inconnu')
            symbol = base.get('symbol', 'UNKNOWN')
            address = base.get('address', '')
            price = str(pair.get('priceUsd', '0'))
            liquidity = pair.get('liquidity', {}).get('usd', 0)
            txns5m = pair.get('txns', {}).get('m5', {})
            buys = txns5m.get('buys', 0)
            sells = txns5m.get('sells', 0)

            msg = (
                "🎯 MEMECOIN PLAYBOOK VALIDÉ\n\n"
                + "🪙 " + str(name) + " ($" + str(symbol) + ")\n"
                + "⏱ Âge : " + str(round(age_hours, 1)) + "h (" + str(round(age_hours/24, 1)) + "j)\n"
                + "💰 MC : $" + str(round(mc)) + " | Prix : $" + price + "\n"
                + "💧 Liquidité : $" + str(round(liquidity)) + "\n"
                + "🟢 Achats : " + str(buys) + " vs 🔴 Ventes : " + str(sells) + "\n\n"
                + "📋 CA :\n" + str(address)
            )
            resultats.append(msg)
            if len(resultats) >= 3:
                break

        if not resultats:
            return "📡 SCAN EN DIRECT : Aucun token ne valide actuellement tous les critères stricts (Âge 24h-96h, MC 100k-350k)."
        return "\n\n---\n\n".join(resultats)
    except Exception as e:
        return "Erreur lors du scan : " + str(e)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Scanner Actif !\nEnvoyez la lettre s pour lancer le scan.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt == 's':
        await update.message.reply_text("🔎 Scan en cours...")
        res = scanner_playbook()
        await update.message.reply_text(res)

def main():
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    print("Bot démarré avec succès !")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
    
