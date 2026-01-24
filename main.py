import os
import time
import asyncio
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from dotenv import load_dotenv
from telegram import Bot

# =========================
# LOAD ENV
# =========================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

# =========================
# SETTINGS
# =========================
PAIRS = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "USDCAD=X"
]

TIMEFRAME = "5m"
LOOKBACK = 50
SCAN_DELAY = 60

# =========================
# FETCH DATA
# =========================
def fetch_data(symbol):
    try:
        df = yf.download(
            symbol,
            period="7d",
            interval=TIMEFRAME,
            progress=False
        )

        if df is None or df.empty:
            return None

        df = df.dropna()
        return df

    except Exception:
        return None

# =========================
# SUPPLY & DEMAND
# =========================
def detect_supply_demand(df):
    try:
        supply = float(df["High"].rolling(LOOKBACK).max().iloc[-1])
        demand = float(df["Low"].rolling(LOOKBACK).min().iloc[-1])
        return supply, demand
    except Exception:
        return None, None

# =========================
# ANALYSIS
# =========================
def analyze_market(symbol, df):
    close = df["Close"].squeeze()  # 🔥 FIX: FORCE 1D

    rsi = RSIIndicator(close=close, window=14).rsi().iloc[-1]
    price = float(close.iloc[-1])

    trend = "UP" if close.iloc[-1] > close.iloc[-20] else "DOWN"

    supply, demand = detect_supply_demand(df)

    signal = "WAIT"
    if rsi < 30 and trend == "UP":
        signal = "BUY"
    elif rsi > 70 and trend == "DOWN":
        signal = "SELL"

    return {
        "symbol": symbol,
        "price": round(price, 5),
        "rsi": round(float(rsi), 2),
        "trend": trend,
        "signal": signal,
        "supply": supply,
        "demand": demand
    }

# =========================
# TELEGRAM
# =========================
async def send_signal(data):
    msg = (
        f"📊 *Pocket Option Signal*\n\n"
        f"💱 Pair: `{data['symbol']}`\n"
        f"💰 Price: {data['price']}\n"
        f"📈 Trend: {data['trend']}\n"
        f"📉 RSI: {data['rsi']}\n"
        f"🚦 Signal: *{data['signal']}*\n"
        f"🔺 Supply: {data['supply']}\n"
        f"🔻 Demand: {data['demand']}"
    )

    await bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )

# =========================
# MAIN LOOP
# =========================
async def run():
    await bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 Pocket Option bot is LIVE"
    )

    while True:
        for pair in PAIRS:
            df = fetch_data(pair)
            if df is None:
                continue

            result = analyze_market(pair, df)

            if result["signal"] != "WAIT":
                await send_signal(result)

        await asyncio.sleep(SCAN_DELAY)

# =========================
# START
# =========================
if __name__ == "__main__":
    asyncio.run(run())
