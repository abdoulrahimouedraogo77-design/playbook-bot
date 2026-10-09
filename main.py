import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "VOTRE_TOKEN_ICI")

def scanner_playbook():
    """Scanne les tokens Solana respectant le Playbook Reversal"""
    url = "https://api.dexscreener.com/latest/dex/tokens/solana"
    # Requête de recherche sur les paires récentes actives
    search_url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
    
    try:
        response = requests.get(search_url, timeout=10)
        data = response.json()
        pairs = data.get('pairs', [])
        
        candidats = []
        for pair in pairs:
            if pair.get('chainId') != 'solana':
                continue
            
            mc = pair.get('fdv', 0) or pair.get('marketCap', 0)
            created_at = pair.get('pairCreatedAt', 0)
            
            if not created_at or not mc:
                continue
            
            # Calcul de l'âge en heures
            import time
            age_heures = (time.time() - (created_at / 1000)) / 3600
            
            # RÈGLE DU PLAYBOOK :
            # 1. Âge entre 24h et 96h (1 à 4 jours)
            # 2. Market Cap actuel en zone de Dip : 80K$ à 350K$
            if 24 <= age_heures <= 96 and 80_000 <= mc <= 350_000:
                candidats.append(pair)
                if len(candidats) >= 3:
                    break
        return candidats
    except Exception as e:
        logging.error(f"Erreur scan : {e}")
        return []

async def scan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Analyse Playbook en cours : recherche de runners 1-4 jours en plein dip...")
    
    tokens = scanner_playbook()
    
    if not tokens:
        await update.message.reply_text("Aucun token ne remplit actuellement les critères stricts (1-4 jours, MC 100K-300K). Réessayez dans un instant.")
        return
    
    for token in tokens:
        ca = token.get('baseToken', {}).get('address', 'N/A')
        symbol = token.get('baseToken', {}).get('symbol', 'N/A')
        mc = int(token.get('fdv', 0) or token.get('marketCap', 0))
        volume = int(token.get('volume', {}).get('h24', 0))
        
        texte = (
            f"🎯 **RUNNER DÉTECTÉ (Playbook Dip)**\n\n"
            f"🪙 **Token :** ${symbol}\n"
            f"📍 **CA :** `{ca}`\n"
            f"📊 **Market Cap actuel :** ${mc:,}\n"
            f"💧 **Volume 24h :** ${volume:,}\n\n"
            f"⚠️ *Vérifiez les Top Holders sur GMGN et l'activité X avant d'entrer !*"
        )
        
        boutons = [
            [
                InlineKeyboardButton("🟧 GMGN Sniper", url=f"https://gmgn.ai/sol/token/{ca}"),
                InlineKeyboardButton("⚡ Photon SOL", url=f"https://photon-sol.tinyastro.io/en/r/@playbook/{ca}")
            ],
            [
                InlineKeyboardButton("🤖 Trojan Bot", url=f"https://t.me/solana_trojanbot?start=r-{ca}"),
                InlineKeyboardButton("📊 DexScreener", url=f"https://dexscreener.com/solana/{ca}")
            ]
        ]
        
        await update.message.reply_text(
            texte,
            reply_markup=InlineKeyboardMarkup(boutons),
            parse_mode="Markdown"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Playbook prêt. Envoyez 's' pour scanner.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Répond à la commande /start ou au simple message 's'
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.Regex('^(s|S|/scan)$'), scan_handler))
    
    application.run_polling()
    
