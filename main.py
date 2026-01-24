import os
import time
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
# SETTINGS (NO input())
# =========================
PAIRS = [
    "EURUSD=X",
    "GBPUSD=X",
    "USDJPY=X",
    "AUDUSD=X",
    "USDCAD=X"
]

TIMEFRAME = "5m"
INTERVAL_SECONDS = 60
LOOKBACK = 50

# =========================
# DATA FETCH
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

        df.dropna(inplace=True)
        return df
    except Exception:
        return None

# =========================
# SUPPLY / DEMAND (FIXED)
# =========================
def detect_supply_demand(df):
    try:
        high_series = df["High"].rolling(LOOKBACK).max()
        low_series = df["Low"].rolling(LOOKBACK).min()

        supply = float(high_series.iloc[-1])
        demand = float(low_series.iloc[-1])

        return supply, demand
    except Exception:
        return None, None

# =========================
# ANALYSIS
# =========================
def analyze_market(symbol, df):
    close = df["Close"]

    rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
    price = float(close.iloc[-1])

    supply, demand = detect_supply_demand(df)

    trend = "UP" if close.iloc[-1] > close.iloc[-20] else "DOWN"

    signal = "WAIT"
    if rsi < 30 and trend == "UP":
        signal = "BUY"
    elif rsi > 70 and trend == "DOWN":
        signal = "SELL"

    return {
        "symbol": symbol,
        "price": price,
        "rsi": round(rsi, 2),
        "trend": trend,
        "signal": signal,
        "supply": supply,
        "demand": demand
    }

# =========================
# TELEGRAM
# =========================
def send_signal(data):
    msg = (
        f"📊 *Pocket Option Signal*\n\n"
        f"💱 Pair: `{data['symbol']}`\n"
        f"💰 Price: {data['price']}\n"
        f"📈 Trend: {data['trend']}\n"
        f"📉 RSI: {data['rsi']}\n"
        f"🟢 Signal: *{data['signal']}*\n"
        f"🔺 Supply: {data['supply']}\n"
        f"🔻 Demand: {data['demand']}"
    )

    bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )

# =========================
# MAIN LOOP
# =========================
def run():
    bot.send_message(chat_id=CHAT_ID, text="🚀 Signal bot started")

    while True:
        for pair in PAIRS:
            df = fetch_data(pair)
            if df is None:
                continue

            result = analyze_market(pair, df)

            if result["signal"] != "WAIT":
                send_signal(result)

        time.sleep(INTERVAL_SECONDS)

# =========================
# START
# =========================
if __name__ == "__main__":
    run()
