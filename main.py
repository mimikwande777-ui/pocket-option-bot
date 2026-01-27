# main.py
import os
import asyncio
import time
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator
from telegram import Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from tradingview_ta import TA_Handler, Interval, Exchange

load_dotenv()

# === Environment / Settings ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")
PAIRS = [p.strip().upper() for p in os.getenv("PAIRS", "EURUSD,GBPUSD").split(",")]
TIMEFRAME = os.getenv("TIMEFRAME", "1m")  # '1m','5m','15m','30m','60m'
TOP_SIGNALS = int(os.getenv("TOP_SIGNALS", "5"))
LOOKBACK = int(os.getenv("LOOKBACK", "20"))

bot = Bot(token=TELEGRAM_TOKEN)

# === TradingView mapping ===
TV_SYMBOL_MAP = {p: p for p in PAIRS}  # simple map, can adjust if needed
TV_INTERVAL_MAP = {
    "1m": Interval.INTERVAL_1_MIN,
    "5m": Interval.INTERVAL_5_MIN,
    "15m": Interval.INTERVAL_15_MIN,
    "30m": Interval.INTERVAL_30_MIN,
    "60m": Interval.INTERVAL_1_HOUR,
}

# === Helpers ===
def alpha_interval_to_av(timeframe: str):
    mapping = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "60m": "60min", "1h": "60min"}
    return mapping.get(timeframe, "5min")

def fetch_alpha_fx(from_sym: str, to_sym: str, interval: str, outputsize="compact"):
    if not ALPHA_KEY:
        return None
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "FX_INTRADAY",
        "from_symbol": from_sym,
        "to_symbol": to_sym,
        "interval": alpha_interval_to_av(interval),
        "outputsize": outputsize,
        "apikey": ALPHA_KEY
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        js = r.json()
        key = next((k for k in js if "Time Series" in k), None)
        if key is None: return None
        df = pd.DataFrame.from_dict(js[key], orient="index").astype(float)
        df.index = pd.to_datetime(df.index)
        df = df.rename(columns=lambda c: c.split(" ")[1].capitalize())
        df = df[["Open","High","Low","Close"]].sort_index()
        return df
    except Exception:
        return None

def fetch_yfinance(symbol: str, timeframe: str):
    import yfinance as yf
    try:
        period = "7d" if timeframe == "1m" else "30d"
        df = yf.download(symbol if symbol.endswith("=X") else symbol+"=X", period=period, interval=timeframe, progress=False)
        df.dropna(inplace=True)
        return df
    except Exception:
        return None

def get_ohlc_for_pair(pair: str):
    s = pair.upper().replace("/","").replace("-","")
    try:
        if ALPHA_KEY and len(s)>=6:
            base, quote = s[:3], s[3:6]
            df = fetch_alpha_fx(base, quote, TIMEFRAME)
            if df is not None and len(df)>=LOOKBACK: return df
    except: pass
    for sym in [s+"=X", s]:
        df = fetch_yfinance(sym, TIMEFRAME)
        if df is not None and len(df)>=LOOKBACK: return df
    return None

# === Signal logic ===
def detect_fvg(df):
    try:
        if len(df)<3: return "Neutral"
        h1,h2,h3 = df["High"].iloc[-3:]
        l1,l2,l3 = df["Low"].iloc[-3:]
        c2,c3 = df["Close"].iloc[-2:]
        if l2>h1 and c3>c2: return "Bullish"
        if h2<l1 and c3<c2: return "Bearish"
        return "Neutral"
    except: return "Neutral"

def detect_supply_demand(df, lookback=LOOKBACK):
    try:
        rolling_high = df["High"].rolling(window=lookback).max()
        rolling_low = df["Low"].rolling(window=lookback).min()
        supply = float(rolling_high.iloc[-1]) if not rolling_high.empty else None
        demand = float(rolling_low.iloc[-1]) if not rolling_low.empty else None
        return supply, demand
    except: return None,None

def tradingview_confirmation(pair):
    try:
        tv_symbol = TV_SYMBOL_MAP.get(pair, pair)
        tv_interval = TV_INTERVAL_MAP.get(TIMEFRAME, Interval.INTERVAL_5_MIN)
        handler = TA_Handler(
            symbol=tv_symbol,
            screener="forex",
            exchange="FX_IDC",
            interval=tv_interval
        )
        analysis = handler.get_analysis()
        summary = analysis.summary["RECOMMENDATION"]  # BUY/SELL/NEUTRAL
        return summary
    except Exception:
        return "Neutral"

def analyze_df(df, pair):
    try:
        close = df["Close"].squeeze()
        if hasattr(close,"iloc")==False: close=pd.Series(close).squeeze()
        rsi_series = RSIIndicator(close, window=14).rsi()
        ema_fast = EMAIndicator(close, window=9).ema_indicator()
        ema_slow = EMAIndicator(close, window=21).ema_indicator()
        latest_rsi = float(rsi_series.iloc[-1])
        latest_fast = float(ema_fast.iloc[-1])
        latest_slow = float(ema_slow.iloc[-1])
        latest_price = float(close.iloc[-1])
        trend = "UP" if latest_fast>latest_slow else "DOWN"
        signal = None
        score=0
        if trend=="UP" and latest_rsi<35: signal="BUY"; score=100-latest_rsi
        elif trend=="DOWN" and latest_rsi>65: signal="SELL"; score=latest_rsi
        supply,demand=detect_supply_demand(df)
        fvg=detect_fvg(df)
        tv_confirm = tradingview_confirmation(pair)
        # Only send signal if TV doesn't contradict
        if signal=="BUY" and tv_confirm=="SELL": signal=None
        if signal=="SELL" and tv_confirm=="BUY": signal=None
        return {"pair":pair,"price":round(latest_price,5),"rsi":round(latest_rsi,2),
                "trend":trend,"signal":signal,"score":score,"supply":supply,"demand":demand,
                "fvg":fvg,"tv":tv_confirm}
    except: return None

async def get_top_signals():
    results=[]
    for pair in PAIRS:
        df = get_ohlc_for_pair(pair)
        if df is None: continue
        res=analyze_df(df,pair)
        if res and res["signal"]: results.append(res)
        await asyncio.sleep(1.2)  # respect free API
    return sorted(results,key=lambda x:x["score"],reverse=True)[:TOP_SIGNALS]

def format_message(signals):
    if not signals: return "⏳ No strong BUY/SELL signals right now."
    msg = "📊 Top Signals (with TradingView confirmation)\n\n"
    for s in signals:
        msg+=f"{s['pair']} | {s['signal']} | Price: {s['price']} | RSI: {s['rsi']} | FVG:{s['fvg']} | TV:{s['tv']}\n"
    return msg

# === Telegram handlers ===
async def cmd_signals(update: "Update", context: "ContextTypes"):
    top = await get_top_signals()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=format_message(top))

async def periodic_sender(app):
    while True:
        top = await get_top_signals()
        if top: await app.bot.send_message(chat_id=CHAT_ID, text=format_message(top))
        await asyncio.sleep(max(60,60))  # adjust as needed

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("signals", cmd_signals))
    asyncio.create_task(periodic_sender(app))
    await app.run_polling()

if __name__=="__main__":
    asyncio.run(main())
