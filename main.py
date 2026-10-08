import os
import time
import requests
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Critères Playbook : Reversal sain (ATH 1M-3M$, Drop 40-60%)
MIN_AGE_HOURS = 24
MAX_AGE_HOURS = 96
MIN_ATH_MCAP = 1000000
MAX_ATH_MCAP = 3000000
MIN_DROP_PCT = 40.0
MAX_DROP_PCT = 60.0
MIN_VOLUME_1H = 8000

def find_playbook_token():
    url = "https://api.dexscreener.com/latest/dex/search?q=SOL"
    try:
        res = requests.get(url, timeout=12).json()
        pairs = res.get("pairs", [])
    except Exception as e:
        print(f"Erreur API: {e}")
        return None

    now_ms = time.time() * 1000

    for pair in pairs:
        if pair.get("chainId") != "solana":
            continue

        created_at = pair.get("pairCreatedAt", 0)
        if not created_at:
            continue

        age_hours = (now_ms - created_at) / (1000 * 3600)
        if not (MIN_AGE_HOURS <= age_hours <= MAX_AGE_HOURS):
            continue

        current_mc = pair.get("fdv") or pair.get("marketCap") or 0
        price_drop_24h = pair.get("priceChange", {}).get("h24", 0)

        if not (-MAX_DROP_PCT <= price_drop_24h <= -MIN_DROP_PCT):
            continue

        ath_estimate = current_mc / (1 + (price_drop_24h / 100))
        if not (MIN_ATH_MCAP <= ath_estimate <= MAX_ATH_MCAP):
            continue

        vol_1h = pair.get("volume", {}).get("h1", 0)
        if vol_1h < MIN_VOLUME_1H:
            continue

        ca = pair.get("baseToken", {}).get("address")
        symbol = pair.get("baseToken", {}).get("symbol")
        name = pair.get("baseToken", {}).get("name")
        pair_url = pair.get("url")

        return {
            "name": name,
            "symbol": symbol,
            "ca": ca,
            "age_days": age_hours / 24,
            "ath": ath_estimate,
            "mc": current_mc,
            "drop": abs(price_drop_24h),
            "vol1h": vol_1h,
            "url": pair_url
        }
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()

    if text == "s" or text == "/scan":
        status_msg = await update.message.reply_text("🔎 Analyse du marché en cours (Playbook : ATH 1M-3M$, Retracement 40-60%)...")
        
        token = find_playbook_token()
        
        if not token:
            await status_msg.edit_text("⏳ Aucun token ne correspond exactement aux filtres stricts à cet instant. Réessayez dans quelques minutes avec `s`.")
            return

        ca = token["ca"]
        symbol = token["symbol"]
        
        ct_query = urllib.parse.quote(f"${symbol} OR {ca}")
        x_url = f"https://x.com/search?q={ct_query}&f=live"
        trojan_url = f"https://t.me/solana_trojanbot?start=r-abdoul_ravgh12a-{ca}"

        message = (
            f"🎯 *PLAYBOOK REVERSAL VALIDÉ*\n\n"
            f"🪙 *Token :* {token['name']} (`${symbol}`)\n"
            f"⏳ *Âge :* {token['age_days']:.1f} jours\n"
            f"🏔️ *Pic ATH :* `${token['ath']:,.0f}`\n"
            f"📉 *Correction :* `-{token['drop']:.1f}%` (Zone saine)\n"
            f"💰 *Market Cap :* `${token['mc']:,.0f}`\n"
            f"💧 *Volume 1h :* `${token['vol1h']:,.0f}`\n\n"
            f"📋 *CA :*\n`{ca}`\n\n"
            f"⚡ *Règle :* Vérifiez X (CT) et les holders avant d'entrer !"
        )

        keyboard = [
            [
                InlineKeyboardButton("🐦 Vérifier sur X (CT)", url=x_url),
                InlineKeyboardButton("📊 DexScreener", url=token["url"])
            ],
            [
                InlineKeyboardButton("🚀 Acheter sur Trojan", url=trojan_url)
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await status_msg.delete()
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("Erreur: TELEGRAM_BOT_TOKEN manquant !")
        exit(1)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(CommandHandler("scan", handle_message))

    print("Scanner Playbook opérationnel...")
    app.run_polling()
