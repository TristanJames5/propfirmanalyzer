import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Apex Institutional Analyzer", layout="wide", page_icon="🦅")

# --- CUSTOM CSS FOR SLEEK UI ---
st.markdown("""
<style>
    .opportunity-card {
        background-color: #1E1E1E;
        padding: 25px;
        border-radius: 12px;
        border-left: 6px solid #00FFAA;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .bearish-card { border-left: 6px solid #FF3366; }
    .neutral-card { border-left: 6px solid #FFCC00; }
    .metric-value { font-size: 28px; font-weight: bold; margin-top: 5px; }
    .label { color: #888888; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
    .confluence-list { font-size: 15px; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

st.title("🦅 Apex Institutional Analyzer")
st.markdown("Abstracting the retail noise. Displaying pure institutional flow, liquidity grabs, and high-probability setups.")

# --- ASSETS ---
tickers = {
    "Forex | EUR/USD": "EURUSD=X", "Forex | GBP/USD": "GBPUSD=X", "Forex | USD/JPY": "JPY=X", 
    "Forex | AUD/USD": "AUDUSD=X", "Forex | USD/CAD": "CAD=X", "Forex | USD/CHF": "CHF=X",
    "Index | Nasdaq 100": "NQ=F", "Index | S&P 500": "ES=F", "Index | Dow Jones": "YM=F", "Index | DAX": "^GDAXI",
    "Metal | Gold (XAU/USD)": "GC=F", "Metal | Silver (XAG/USD)": "SI=F",
    "Crypto | Bitcoin": "BTC-USD", "Crypto | Ethereum": "ETH-USD", "Crypto | Solana": "SOL-USD"
}

# --- SIDEBAR ---
with st.sidebar:
    st.header("Trade Terminal")
    selected_asset = st.selectbox("Select Market", list(tickers.keys()))
    ticker_symbol = tickers[selected_asset]
    
    trade_style = st.selectbox("Trading Style", ["Scalping (15m)", "Day Trading (1H)", "Swing (4H)", "Positional (1D)"], index=1)
    
    timeframe_map = {"Scalping (15m)": "15m", "Day Trading (1H)": "1h", "Swing (4H)": "4h", "Positional (1D)": "1d"}
    tf = timeframe_map[trade_style]
    period_map = {"15m": "5d", "1h": "1mo", "4h": "1mo", "1d": "1y"}
    period = period_map[tf]

# --- ALGORITHMIC ENGINE ---
@st.cache_data(ttl=300)
def load_and_analyze(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    if df.empty: return df
    
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    
    df.ta.sma(length=50, append=True)
    df.ta.sma(length=200, append=True)
    df.ta.atr(length=14, append=True)
    
    df['FVG_Bull'] = False
    df['FVG_Bear'] = False
    df['Bull_OB'] = False
    df['Bear_OB'] = False
    
    for i in range(2, len(df)):
        if df['Low'].iloc[i] > df['High'].iloc[i-2] and df['Close'].iloc[i-1] > df['Open'].iloc[i-1]:
            df.iat[i, df.columns.get_loc('FVG_Bull')] = True
        if df['High'].iloc[i] < df['Low'].iloc[i-2] and df['Close'].iloc[i-1] < df['Open'].iloc[i-1]:
            df.iat[i, df.columns.get_loc('FVG_Bear')] = True
            
        if i >= 3:
            atr = df['ATRr_14'].iloc[i-1]
            body_curr = abs(df['Close'].iloc[i] - df['Open'].iloc[i])
            if df['Close'].iloc[i-1] < df['Open'].iloc[i-1] and df['Close'].iloc[i] > df['Open'].iloc[i] and body_curr > atr:
                df.iat[i-1, df.columns.get_loc('Bull_OB')] = True
            if df['Close'].iloc[i-1] > df['Open'].iloc[i-1] and df['Close'].iloc[i] < df['Open'].iloc[i] and body_curr > atr:
                df.iat[i-1, df.columns.get_loc('Bear_OB')] = True

    return df

@st.cache_data(ttl=3600)
def check_fundamentals():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.content)
        today = datetime.now().strftime("%m-%d-%Y")
        high_impact = [child.find('title').text for child in root.findall('event') if child.find('impact').text == "High" and child.find('date').text == today]
        return high_impact
    except:
        return []

# --- EXECUTION LOGIC ---
df = load_and_analyze(ticker_symbol, period, tf)

if df.empty:
    st.error("Market data unavailable. Please try another asset or timeframe.")
else:
    current_price = float(df['Close'].iloc[-1])
    atr = float(df['ATRr_14'].iloc[-1])
    sma50 = float(df['SMA_50'].iloc[-1])
    sma200 = float(df['SMA_200'].iloc[-1])
    
    recent_bull_fvg = df['FVG_Bull'].iloc[-15:].any()
    recent_bear_fvg = df['FVG_Bear'].iloc[-15:].any()
    recent_bull_ob = df['Bull_OB'].iloc[-15:].any()
    recent_bear_ob = df['Bear_OB'].iloc[-15:].any()
    
    direction = "NO CLEAR EDGE"
    card_class = "neutral-card"
    status = "Sitting on hands. Waiting for liquidity sweep."
    entry = current_price
    sl = 0.0
    tp = 0.0
    validity = "N/A"
    
    if current_price > sma50 and current_price > sma200:
        if recent_bull_fvg or recent_bull_ob:
            direction = "HIGH PROBABILITY LONG (BUY)"
            card_class = "opportunity-card"
            status = "Setup Validated. Awaiting Entry Trigger."
            entry = current_price - (atr * 0.4) 
            sl = entry - (atr * 1.5) 
            tp = entry + (atr * 3.0) 
            validity = f"Invalidated if price breaks {sl:.4f}"
            
    elif current_price < sma50 and current_price < sma200:
        if recent_bear_fvg or recent_bear_ob:
            direction = "HIGH PROBABILITY SHORT (SELL)"
            card_class = "opportunity-card bearish-card"
            status = "Setup Validated. Awaiting Entry Trigger."
            entry = current_price + (atr * 0.4)
            sl = entry + (atr * 1.5)
            tp = entry - (atr * 3.0)
            validity = f"Invalidated if price breaks {sl:.4f}"

    news_events = check_fundamentals()
    news_warning = f"⚠️ WARNING: High Impact News Today ({', '.join(news_events)}). Reduce position size." if news_events else "✅ Clear Fundamentals. No red-folder news expected today."

    # --- UI RENDERING ---
    st.markdown(f"""
    <div class="{card_class}">
        <h2 style="margin-top: 0; color: white;">{selected_asset.split('|')[-1].strip()} | {direction}</h2>
        <div style="color: #CCCCCC; margin-bottom: 25px; font-size: 16px;">
            <b>Style:</b> {trade_style} &nbsp;•&nbsp; <b>Status:</b> {status}
        </div>
        
        <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
            <div style="margin-right: 20px;">
                <div class="label">Optimal Entry Zone</div>
                <div class="metric-value" style="color: white;">{entry:.4f}</div>
            </div>
            <div style="margin-right: 20px;">
                <div class="label">Target (Liquidity Pool)</div>
                <div class="metric-value" style="color: #00FFAA;">{tp:.4f}</div>
            </div>
            <div>
                <div class="label">Stop Loss (Invalidation)</div>
                <div class="metric-value" style="color: #FF3366;">{sl:.4f}</div>
            </div>
        </div>
        
        <hr style="border-color: #444; margin: 25px 0;">
        
        <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
            <div style="margin-right: 20px;">
                <div class="label" style="margin-bottom: 10px;">Institutional Confluences</div>
                <div class="confluence-list" style="color: white;">
                    {'🟢' if direction != 'NO CLEAR EDGE' else '⚪'} Trend & Momentum Alignment<br>
                    {'🟢' if recent_bull_fvg or recent_bear_fvg else '⚪'} Fair Value Gap (Imbalance)<br>
                    {'🟢' if recent_bull_ob or recent_bear_ob else '⚪'} Supply/Demand Block<br>
                    {'🔴' if news_events else '🟢'} Fundamental Clearance
                </div>
            </div>
            <div style="margin-top: 25px;">
                <div class="label">Trade Expiry / Validity</div>
                <div style="font-size: 18px; color: #FFCC00; font-weight: bold; margin-top: 5px;">{validity}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.info(news_warning)
    
    with st.expander("🔍 Developer Mode: View Raw Market Matrix"):
        st.dataframe(df.tail(15))
