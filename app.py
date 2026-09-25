import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz

# --- PAGE CONFIG ---
st.set_page_config(page_title="Apex Institutional Analyzer", layout="wide", page_icon="🦅")

# --- CUSTOM CSS FOR SLEEK UI ---
st.markdown("""
<style>
    .opportunity-card {
        background-color: #161A1D;
        padding: 25px;
        border-radius: 12px;
        border-left: 6px solid #00FFAA;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .bearish-card { border-left: 6px solid #FF3366; }
    .neutral-card { border-left: 6px solid #FFCC00; }
    .dead-zone-card { border-left: 6px solid #555555; opacity: 0.8; }
    .metric-value { font-size: 28px; font-weight: bold; margin-top: 5px; }
    .label { color: #888888; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
    .confluence-list { font-size: 15px; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

# --- SESSION LOGIC ---
def get_market_session():
    now_utc = datetime.now(pytz.utc)
    hour = now_utc.hour
    
    session = "Dead Zone / Off Hours"
    has_volume = False
    
    if 12 <= hour < 16:
        session = "London / NY Overlap"
        has_volume = True
    elif 7 <= hour < 12:
        session = "London Session"
        has_volume = True
    elif 16 <= hour < 21:
        session = "New York Session"
        has_volume = True
    elif 23 <= hour or hour < 7:
        session = "Asian Session"
        has_volume = False # Generally lower volume for majors/indices
        
    return session, has_volume, now_utc.strftime("%H:%M UTC")

session_name, has_volume, utc_time = get_market_session()

# --- TOP BAR ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🦅 Apex Institutional Analyzer")
    st.markdown("Abstracting the retail noise. Displaying pure institutional flow and high-probability setups.")
with col2:
    st.markdown(f"""
    <div style="text-align: right; color: #888888; font-size: 12px; margin-top: 20px;">
        MARKET SESSION<br>
        <b style="color: {'#00FFAA' if has_volume else '#FFCC00'}; font-size: 16px;">{session_name}</b><br>
        UTC {utc_time}
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

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
    # Adjust volume flag for Crypto (always active)
    if "Crypto" in selected_asset:
        has_volume = True
        session_name = "Crypto (24/7)"

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

    # Overwrite if session is dead (Time Filter)
    if not has_volume and direction != "NO CLEAR EDGE":
        direction = "SETUP IGNORED (DEAD SESSION)"
        card_class = "opportunity-card dead-zone-card"
        status = f"A++ Setup found, but ignored due to low volume ({session_name})."
        validity = "Wait for London/NY Open"

    news_events = check_fundamentals()
    news_warning = f"⚠️ WARNING: High Impact News Today ({', '.join(news_events)}). Reduce position size." if news_events else "✅ Fundamental overlay clear. No high-impact events."

    # --- UI RENDERING ---
    st.info(news_warning)

    st.markdown(f"""
    <div class="{card_class}">
        <h2 style="margin-top: 0; color: white;">{selected_asset.split('|')[-1].strip()} | {direction}</h2>
        <div style="color: #CCCCCC; margin-bottom: 25px; font-size: 16px;">
            <b>Style:</b> {trade_style} &nbsp;•&nbsp; <b>Status:</b> {status}
        </div>
        
        <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
            <div style="margin-right: 20px;">
                <div class="label">Entry Zone</div>
                <div class="metric-value" style="color: white;">{entry:.4f}</div>
            </div>
            <div style="margin-right: 20px;">
                <div class="label">Target (Liquidity)</div>
                <div class="metric-value" style="color: #00FFAA;">{tp:.4f}</div>
            </div>
            <div>
                <div class="label">Invalidation (SL)</div>
                <div class="metric-value" style="color: #FF3366;">{sl:.4f}</div>
            </div>
        </div>
        
        <hr style="border-color: #444; margin: 25px 0;">
        
        <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
            <div style="margin-right: 20px;">
                <div class="label" style="margin-bottom: 10px;">Confluence Matrix</div>
                <div class="confluence-list" style="color: white;">
                    {'🟢' if direction != 'NO CLEAR EDGE' else '⚪'} Trend & Momentum Alignment<br>
                    {'🟢' if recent_bull_fvg or recent_bear_fvg else '⚪'} Fair Value Gap Detected<br>
                    {'🟢' if recent_bull_ob or recent_bear_ob else '⚪'} Demand/Supply Order Block<br>
                    {'🟢' if has_volume else '🔴'} Market Session Volume
                </div>
            </div>
            <div style="margin-top: 25px;">
                <div class="label">Setup Validity</div>
                <div style="font-size: 18px; color: #888888; margin-top: 5px;">{validity}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("🔍 Developer Mode: View Raw Market Matrix"):
        st.dataframe(df.tail(15))
