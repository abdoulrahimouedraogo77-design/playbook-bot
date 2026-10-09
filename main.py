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

# Correction de compatibilité Python 3.11/3.14 pour imghdr
if 'imghdr' not in sys.modules:
    dummy_imghdr = types.ModuleType('imghdr')
    dummy_imghdr.what = lambda *args, **kwargs: None
    sys.modules['imghdr'] = dummy_imghdr

logging.basicConfig(level=logging.INFO)

# Votre nouveau token révoqué propre
TOKEN = "8657135601:AAG-iKsu73uJ45g3UvWBz9fJV_3xCo0dTnM"

# Serveur de santé pour Render Web Service
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"PLAYBOOK_BOT_ONLINE")

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

def scanner_playbook():
    try:
        url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
        res = requests.get(url, timeout=12)
        if res.status_code != 200:
            return "⚠️ Erreur API DexScreener : Impossible de joindre les serveurs."
        
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
            
            # RÈGLE 1 : Âge entre 24h et 96h (1 à 4 jours après le run initial)
            age_hours = (now - created_at) / (1000 * 3600)
            if not (24 <= age_hours <= 96):
                continue
            
            # RÈGLE 2 : Zone de rechargement dip (MC entre 100K$et 350K$)
            mc = pair.get('marketCap') or pair.get('fdv') or 0
            if not (100000 <= mc <= 350000):
                continue

            # RÈGLE 3 : Liquidité minimale pour éviter les traps
            liquidity = pair.get('liquidity', {}).get('usd', 0)
            if liquidity < 15000:
                continue

            base = pair.get('baseToken', {})
            name = base.get('name', 'Inconnu')
            symbol = base.get('symbol', 'UNKNOWN')
            address = base.get('address', '')
            price = str(pair.get('priceUsd', '0'))
            
            # Données de flux (Tape analysis)
            txns5m = pair.get('txns', {}).get('m5', {})
            buys5m = txns5m.get('buys', 0)
            sells5m = txns5m.get('sells', 0)
            vol24h = pair.get('volume', {}).get('h24', 0)

            fiche = (
                "🎯 **DIP RUNNER DÉTECTÉ (1-4j)**\n\n"
                f"🪙 **Token :** {name} (`${symbol}`)\n"
                f"⏱ **Âge :** {age_hours:.1f}h ({age_hours/24:.1f} jours)\n"
                f"💰 **Market Cap :** ${mc:,.0f}\n"
                f"💧 **Liquidité :** ${liquidity:,.0f}\n"
                f"📊 **Volume 24h :** ${vol24h:,.0f}\n"
                f"⚡ **Flux 5m :** 🟢 {buys5m} achats | 🔴 {sells5m} ventes\n\n"
                f"📋 **CA :**\n`{address}`\n\n"
                f"🔗 [Voir sur DexScreener]({pair.get('url', '')}) | [GMGN](https://gmgn.ai/sol/token/{address})"
            )
            resultats.append(fiche)
            
            if len(resultats) >= 3:
                break

        if not resultats:
            return (
                "📡 **SCAN DU PLAYBOOK TERMINÉ**\n\n"
                "Aucun token ne coche actuellement 100% des critères :\n"
                "• Réseau : Solana\n"
                "• Âge : 24h à 96h (post-dump initial)\n"
                "• MC actuel : 100k$- 350k$\n"
                "• Liquidité > 15 000$\n\n"
                "Réessayez dans quelques minutes avec `s`."
            )
        
        return "\n\n━━━━━━━━━━━━━━━\n\n".join(resultats)

    except Exception as e:
        return f"Erreur d'analyse : {str(e)}"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚡ **Playbook Runner Scanner v2**\n\n"
        "Critères appliqués :\n"
        "1. Âge 24h - 96h (Pas de FOMO sur lancements frais)\n"
        "2. Range 100k$- 350k$ MC (Dip d'accumulation)\n"
        "3. Filtre de liquidité actif\n\n"
        "Envoyez **s** à tout moment pour lancer une recherche."
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip().lower()
    if text == 's':
        await update.message.reply_text("🔎 Analyse du marché en cours via le Playbook...")
        rapport = scanner_playbook()
        await update.message.reply_text(rapport, parse_mode="Markdown", disable_web_page_preview=True)

def main():
    threading.Thread(target=start_health_server, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), message_handler))
    print("Bot Playbook démarré avec succès !")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
