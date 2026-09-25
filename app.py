import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

st.set_page_config(page_title="Prop Firm Analyzer", layout="wide")

st.title("📈 Prop Firm Trading Analyzer")
st.markdown("Free Technical & Fundamental Overview for Forex, Indices, and Crypto")

# Sidebar for inputs
st.sidebar.header("Settings")
tickers = {
    "EUR/USD": "EURUSD=X",
    "Gold": "GC=F",
    "Nasdaq 100": "NQ=F",
    "Bitcoin": "BTC-USD"
}
selected_asset = st.sidebar.selectbox("Select Asset", list(tickers.keys()))
ticker_symbol = tickers[selected_asset]

timeframe = st.sidebar.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=3)
period = st.sidebar.selectbox("Lookback Period", ["5d", "1mo", "3mo", "1y"], index=1)

# Fetch Data
@st.cache_data(ttl=300) # Cache for 5 minutes
def load_data(ticker, period, interval):
    data = yf.download(ticker, period=period, interval=interval, progress=False)
    if not data.empty:
        # Calculate some basic indicators using pandas_ta
        # We handle multi-index columns from yfinance by flattening if needed, 
        # or just accessing the standard OHLCV columns.
        
        # Flatten yfinance multi-index if it exists (for newer yfinance versions)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        # Ensure column names are standard for pandas-ta
        data = data[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        # Calculate indicators
        data.ta.sma(length=20, append=True)
        data.ta.sma(length=50, append=True)
        data.ta.rsi(length=14, append=True)
    return data

st.write(f"### Fetching data for {selected_asset} ({ticker_symbol})")

try:
    df = load_data(ticker_symbol, period, timeframe)
    
    if df.empty:
        st.error("No data found for this asset and timeframe combination.")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.write("#### Recent Price Action")
            st.dataframe(df.tail(10))
            
        with col2:
            st.write("#### Bias Analysis")
            # Very basic bias calculation
            current_price = df['Close'].iloc[-1]
            sma_20 = df['SMA_20'].iloc[-1]
            sma_50 = df['SMA_50'].iloc[-1]
            
            bias = "Neutral"
            if current_price > sma_20 and sma_20 > sma_50:
                bias = "Bullish 🟢"
            elif current_price < sma_20 and sma_20 < sma_50:
                bias = "Bearish 🔴"
                
            st.metric(label="Current Trend Bias (20/50 SMA)", value=bias)
            st.metric(label="Current Price", value=f"{current_price:.4f}")
            st.metric(label="RSI (14)", value=f"{df['RSI_14'].iloc[-1]:.2f}")
        
        st.info("🚧 In the next iterations, we will add Order Blocks, Fair Value Gaps, Volume Profile, and Fundamental News parsing here.")
except Exception as e:
    st.error(f"Error loading data: {e}")
