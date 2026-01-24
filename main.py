# main.py

import os
import time
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from dotenv import load_dotenv
import requests

# Load Telegram token from .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")  # Example in .env: TELEGRAM_TOKEN=123456:ABC-XYZ
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Example: TELEGRAM_CHAT_ID=123456789

import os
from dotenv import load_dotenv

load_dotenv()

# === SAFE CLOUD CONFIG ===
PAIRS = os.getenv("PAIRS", "EURUSD=X,GBPUSD=X").split(",")
TIMEFRAME = os.getenv("TIMEFRAME", "1m")

print(f"📊 Trading pairs: {PAIRS}")
print(f"⏱️ Timeframe: {TIMEFRAME}")

# Telegram function
def send_telegram_message(message):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        try:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})
        except Exception as e:
            print(f"⚠️ Telegram error: {e}")

# Download data safely
def get_data(pair):
    try:
        period = "7d" if TIMEFRAME == "1m" else "30d"
        data = yf.download(tickers=pair, period=period, interval=TIMEFRAME, progress=False)
        if data.empty:
            print(f"⚠️ No data for {pair} at {TIMEFRAME}. Skipping...")
            return None
        return data
    except Exception as e:
        print(f"⚠️ Error fetching {pair}: {e}")
        return None

# Analyze each market
def analyze_market(pair, data):
    close = data['Close'].squeeze()
    if close.empty:
        return None

    # Indicators
    rsi = RSIIndicator(close, window=14).rsi()
    ema_fast = EMAIndicator(close, window=9).ema_indicator()
    ema_slow = EMAIndicator(close, window=21).ema_indicator()

    try:
        latest_price = float(close.iloc[-1])
        latest_rsi = float(rsi.iloc[-1])
        latest_fast = float(ema_fast.iloc[-1])
        latest_slow = float(ema_slow.iloc[-1])
    except Exception as e:
        print(f"⚠️ Error converting indicators to float for {pair}: {e}")
        return None

    # Trend & Signal
    trend = "UP" if latest_fast > latest_slow else "DOWN"
    signal = "WAIT"
    if trend == "UP" and latest_rsi < 30:
        signal = "BUY"
    elif trend == "DOWN" and latest_rsi > 70:
        signal = "SELL"

    # Supply/Demand & FVG placeholders
    LOOKBACK = 20
    rolling_high = data['High'].rolling(window=LOOKBACK).max()
    rolling_low = data['Low'].rolling(window=LOOKBACK).min()
    supply = float(rolling_high.iloc[-1]) if not rolling_high.empty else None
    demand = float(rolling_low.iloc[-1]) if not rolling_low.empty else None
    fvg = "Neutral"

    return {
        "pair": pair,
        "price": latest_price,
        "trend": trend,
        "rsi": latest_rsi,
        "signal": signal,
        "supply": supply,
        "demand": demand,
        "fvg": fvg
    }

# Main bot loop
def run_bot():
    print("📡 Pocket Option Advanced Signal Bot Started...\n")
    while True:
        messages = []
        for pair in PAIRS:
            pair = pair.strip()
            data = get_data(pair)
            if data is None:
                continue
            result = analyze_market(pair, data)
            if result is None:
                continue

            message = (
                f"===================================\n"
                f"PAIR: {result['pair']}\n"
                f"PRICE: {result['price']}\n"
                f"TREND: {result['trend']}\n"
                f"RSI: {result['rsi']}\n"
                f"SIGNAL: {result['signal']}\n"
                f"SUPPLY: {result['supply']}\n"
                f"DEMAND: {result['demand']}\n"
                f"FVG: {result['fvg']}\n"
                f"==================================="
            )
            print(message)
            messages.append(message)

        # Send combined message to Telegram
        if messages:
            send_telegram_message("\n\n".join(messages))

        # Wait based on timeframe
        if TIMEFRAME.endswith("m"):
            sleep_time = int(TIMEFRAME.replace("m", "")) * 60
        elif TIMEFRAME.endswith("h"):
            sleep_time = int(TIMEFRAME.replace("h", "")) * 3600
        elif TIMEFRAME.endswith("d"):
            sleep_time = int(TIMEFRAME.replace("d", "")) * 86400
        else:
            sleep_time = 60  # default 1 minute

        print(f"⏳ Waiting {sleep_time} seconds until next scan...\n")
        time.sleep(sleep_time)

# Run the bot
if __name__ == "__main__":
    run_bot()
