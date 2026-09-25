import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz

# ─────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(page_title="Apex Institutional Analyzer", layout="wide",
                   page_icon="🔺", initial_sidebar_state="expanded")

# ── Sidebar CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif!important;background:#0D0F10;color:#E8E8E8;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding:0!important;max-width:100%!important;}
section[data-testid="stSidebar"]{background:#111416!important;border-right:1px solid #1E2426;}
section[data-testid="stSidebar"]>div{padding:0!important;}
::-webkit-scrollbar{width:4px;}::-webkit-scrollbar-track{background:#0D0F10;}::-webkit-scrollbar-thumb{background:#2A3035;border-radius:4px;}
.sidebar-logo{display:flex;align-items:center;gap:12px;padding:28px 22px 22px;border-bottom:1px solid #1E2426;margin-bottom:10px;}
.logo-icon{width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#00D68F,#00A86B);display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;color:#0D0F10;flex-shrink:0;}
.logo-text h1{margin:0;font-size:16px;font-weight:700;color:#fff;letter-spacing:0.5px;}
.logo-text p{margin:2px 0 0;font-size:9px;color:#5A6872;letter-spacing:2px;text-transform:uppercase;}
.nav-item{display:flex;align-items:center;gap:12px;padding:12px 22px;font-size:14px;font-weight:500;color:#6B7B8A;position:relative;}
.nav-item.active{background:#161B1F;color:#fff;}
.nav-item.active::before{content:'';position:absolute;left:0;top:50%;transform:translateY(-50%);width:3px;height:22px;background:#00D68F;border-radius:0 3px 3px 0;}
.nav-dot{width:6px;height:6px;border-radius:50%;background:#00D68F;margin-left:auto;}
.nav-section-label{padding:18px 22px 8px;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#3A4A55;font-weight:600;}
div[data-testid="stSelectbox"]>div>div{background:#1A1F23!important;border:1px solid #252C32!important;border-radius:8px!important;color:#E8E8E8!important;font-size:13px!important;}
div[data-testid="stNumberInput"] input{background:#1A1F23!important;border:1px solid #252C32!important;border-radius:8px!important;color:#E8E8E8!important;}
div[data-testid="stNumberInput"] button{background:#1A1F23!important;border-color:#252C32!important;color:#E8E8E8!important;}
.stButton>button{border-radius:8px!important;font-family:'Inter',sans-serif!important;font-size:11px!important;font-weight:600!important;}
.stButton>button[kind="primary"]{background:#0A2E1F!important;border:1px solid #00D68F!important;color:#00D68F!important;}
.stButton>button[kind="secondary"]{background:#161B1F!important;border:1px solid #252C32!important;color:#6B7B8A!important;}
.sys-status{display:flex;align-items:center;gap:8px;padding:16px 22px;border-top:1px solid #1E2426;}
.status-dot{width:8px;height:8px;border-radius:50%;background:#00D68F;animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.status-text p{margin:0;font-size:12px;color:#fff;font-weight:500;}
.status-text span{font-size:10px;color:#5A6872;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
#  SESSION LOGIC
# ─────────────────────────────────────────
def get_market_session():
    now = datetime.now(pytz.utc)
    h, m = now.hour, now.minute
    mins = h * 60 + m
    # Precise kill zones
    if 7*60 <= mins <= 9*60+30:   return "London Open Kill Zone",   True, now.strftime("%H:%M:%S")
    if 13*60+30 <= mins <= 16*60: return "NY Open Kill Zone",       True, now.strftime("%H:%M:%S")
    if 12*60 <= mins < 13*60+30:  return "London / NY Transition",  True, now.strftime("%H:%M:%S")
    if 9*60+30 <= mins < 12*60:   return "London Mid (Lower Vol)",  False, now.strftime("%H:%M:%S")
    if 16*60 < mins <= 21*60:     return "New York Session",        False, now.strftime("%H:%M:%S")
    if 23*60 <= mins or mins < 7*60: return "Asian Session / Off",  False, now.strftime("%H:%M:%S")
    return "Dead Zone", False, now.strftime("%H:%M:%S")

session_name, in_kill_zone, utc_time = get_market_session()

# ─────────────────────────────────────────
#  ASSETS
# ─────────────────────────────────────────
ASSET_GROUPS = {
    "Forex majors": {"EUR/USD":"EURUSD=X","GBP/USD":"GBPUSD=X","USD/JPY":"JPY=X",
                     "AUD/USD":"AUDUSD=X","USD/CAD":"CAD=X","USD/CHF":"CHF=X"},
    "Indices":      {"Nasdaq 100":"NQ=F","S&P 500":"ES=F","Dow Jones":"YM=F","DAX":"^GDAXI"},
    "Metals":       {"Gold (XAU/USD)":"GC=F","Silver (XAG/USD)":"SI=F"},
    "Crypto":       {"Bitcoin (BTC)":"BTC-USD","Ethereum (ETH)":"ETH-USD","Solana (SOL)":"SOL-USD"},
}
ASSET_ICONS = {
    "EUR/USD":"E","GBP/USD":"G","USD/JPY":"J","AUD/USD":"A","USD/CAD":"C","USD/CHF":"S",
    "Nasdaq 100":"N","S&P 500":"S","Dow Jones":"D","DAX":"D",
    "Gold (XAU/USD)":"Au","Silver (XAG/USD)":"Ag",
    "Bitcoin (BTC)":"₿","Ethereum (ETH)":"Ξ","Solana (SOL)":"◎",
}

# ─────────────────────────────────────────
#  MTF CONFIG — User-Specified Framework
#  Bias → Structure → Entry
# ─────────────────────────────────────────
MTF_CONFIG = {
    "Scalp": {
        "bias":   {"tf": "15m", "period": "5d"},
        "struct": {"tf": "5m",  "period": "2d"},
        "entry":  {"tf": "1m",  "period": "1d"},
        "names":  ("15M · Bias", "5M · Structure", "1M · Entry"),
        "short":  ("15M", "5M", "1M"),
        "label":  "Scalp",   "btn_tf": "1M",
    },
    "Day": {
        "bias":   {"tf": "1h",  "period": "30d"},
        "struct": {"tf": "15m", "period": "5d"},
        "entry":  {"tf": "5m",  "period": "2d"},
        "names":  ("1H · Bias", "15M · Structure", "5M · Entry"),
        "short":  ("1H", "15M", "5M"),
        "label":  "Day Trading", "btn_tf": "5M",
    },
    "Swing": {
        "bias":   {"tf": "1d",  "period": "90d"},
        "struct": {"tf": "4h",  "period": "60d"},
        "entry":  {"tf": "15m", "period": "5d"},
        "names":  ("1D · Bias", "4H · Structure", "15M · Entry"),
        "short":  ("1D", "4H", "15M"),
        "label":  "Swing",   "btn_tf": "15M",
    },
    "Position": {
        "bias":   {"tf": "1wk", "period": "2y"},
        "struct": {"tf": "1d",  "period": "6mo"},
        "entry":  {"tf": "4h",  "period": "60d"},
        "names":  ("1W · Bias", "1D · Structure", "4H · Entry"),
        "short":  ("1W", "1D", "4H"),
        "label":  "Position", "btn_tf": "4H",
    },
}

# ─────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────
for k, v in [("market_group","Forex majors"),("asset","EUR/USD"),("style","Day"),
             ("account_size",25000.0),("risk_pct",1.0)]:
    if k not in st.session_state: st.session_state[k] = v

# ─────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <div class="logo-icon">A</div>
        <div class="logo-text"><h1>APEX</h1><p>Institutional Analyzer</p></div>
    </div>
    <div class="nav-item active"><span>📊</span> Signal desk <span class="nav-dot"></span></div>
    <div class="nav-item"><span>🗺️</span> Market map</div>
    <div class="nav-item"><span>📈</span> Trade journal</div>
    <div class="nav-section-label">Market</div>
    """, unsafe_allow_html=True)

    group_options = list(ASSET_GROUPS.keys())
    selected_group = st.selectbox("Market group", group_options,
        index=group_options.index(st.session_state.market_group),
        key="group_sel", label_visibility="collapsed")
    st.session_state.market_group = selected_group

    asset_options = list(ASSET_GROUPS[selected_group].keys())
    if st.session_state.asset not in asset_options:
        st.session_state.asset = asset_options[0]
    selected_asset_name = st.selectbox("Asset", asset_options,
        index=asset_options.index(st.session_state.asset),
        key="asset_sel", label_visibility="collapsed")
    st.session_state.asset = selected_asset_name
    ticker_symbol = ASSET_GROUPS[selected_group][selected_asset_name]

    # Style selector with MTF info
    st.markdown('<div class="nav-section-label">Trade Style</div>', unsafe_allow_html=True)
    style_keys = list(MTF_CONFIG.keys())
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    grid = [c1, c2, c3, c4]
    for i, s in enumerate(style_keys):
        cfg_s = MTF_CONFIG[s]
        with grid[i]:
            if st.button(f"{s}\n{cfg_s['btn_tf']}", key=f"sty_{s}", width="stretch",
                         type="primary" if st.session_state.style == s else "secondary"):
                st.session_state.style = s; st.rerun()

    # Show current MTF chain
    cur_cfg = MTF_CONFIG[st.session_state.style]
    sn = cur_cfg["short"]
    st.markdown(f"""
    <div style="background:#0D1A14;border:1px solid #1A3A28;border-radius:8px;padding:10px 14px;margin:8px 14px;">
        <div style="font-size:9px;color:#5A6872;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">Active MTF Chain</div>
        <div style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;">
            <span style="background:#0A2E1F;color:#00D68F;padding:3px 8px;border-radius:4px;">{sn[0]}</span>
            <span style="color:#3A4A55;">→</span>
            <span style="background:#162030;color:#5A9AE0;padding:3px 8px;border-radius:4px;">{sn[1]}</span>
            <span style="color:#3A4A55;">→</span>
            <span style="background:#2E1A00;color:#F5A742;padding:3px 8px;border-radius:4px;">{sn[2]}</span>
        </div>
        <div style="font-size:10px;color:#5A6872;margin-top:5px;">Bias → Structure → Entry</div>
    </div>
    """, unsafe_allow_html=True)

    # Risk Calculator
    st.markdown('<div class="nav-section-label">Risk Calculator</div>', unsafe_allow_html=True)
    ca, cb = st.columns(2)
    with ca:
        st.markdown('<div style="font-size:10px;color:#5A6872;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Account</div>', unsafe_allow_html=True)
        acct = st.number_input("acct", value=st.session_state.account_size, min_value=100.0,
                               step=1000.0, label_visibility="collapsed", key="acct_in", format="%.0f")
        st.session_state.account_size = acct
    with cb:
        st.markdown('<div style="font-size:10px;color:#5A6872;text-transform:uppercase;letter-spacing:1px;margin-bottom:2px;">Risk %</div>', unsafe_allow_html=True)
        risk_pct = st.number_input("risk", value=st.session_state.risk_pct, min_value=0.1,
                                   max_value=5.0, step=0.1, label_visibility="collapsed",
                                   key="risk_in", format="%.1f")
        st.session_state.risk_pct = risk_pct

    max_exp = acct * (risk_pct / 100)
    st.markdown(f'<div style="padding:8px 0 12px;"><div style="font-size:10px;color:#5A6872;text-transform:uppercase;letter-spacing:1px;">Max Exposure</div><div style="font-size:26px;font-weight:700;color:#00D68F;margin-top:4px;">${max_exp:,.0f}</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="sys-status"><div class="status-dot"></div><div class="status-text"><p>Systems operational</p><span>MTF Engine v2.0</span></div></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────
#  DATA ENGINE
# ─────────────────────────────────────────
@st.cache_data(ttl=180)
def load_tf(ticker, period, interval):
    """Download + compute indicators for one timeframe. Returns None on failure."""
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is None or df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        required = ['Open','High','Low','Close','Volume']
        if not all(c in df.columns for c in required): return None
        df = df[required].copy().dropna()
        if len(df) < 5: return None

        # Indicators — wrap each in try/except for robustness
        try: df.ta.sma(length=min(50, len(df)//2), append=True)
        except: pass
        try: df.ta.sma(length=min(200, len(df)//2), append=True)
        except: pass
        try: df.ta.ema(length=min(21, len(df)//2), append=True)
        except: pass
        try: df.ta.rsi(length=min(14, len(df)//3), append=True)
        except: pass
        try: df.ta.atr(length=min(14, len(df)//3), append=True)
        except: pass
        try:
            if len(df) >= 35: df.ta.macd(append=True)
        except: pass
        return df
    except Exception:
        return None


def analyze_tf(df):
    """Extract direction + key metrics from a single TF dataframe."""
    if df is None or len(df) < 5:
        return {"direction": "neutral", "fvg": False, "ob": False,
                "rsi": 50.0, "macd_bull": False, "atr": 0.0,
                "price": 0.0, "swing_high": 0.0, "swing_low": 0.0,
                "mid_range": 0.0, "in_discount": False, "in_premium": False,
                "zone_pct": 50.0, "ok": False}

    price = float(df['Close'].iloc[-1])
    out = {"direction":"neutral","fvg":False,"ob":False,"rsi":50.0,"macd_bull":False,
           "atr":0.0,"price":price,"swing_high":price,"swing_low":price,
           "mid_range":price,"in_discount":False,"in_premium":False,"zone_pct":50.0,"ok":True}

    # Trend via SMA
    sma50_col  = [c for c in df.columns if c.startswith("SMA_5")]
    sma200_col = [c for c in df.columns if c.startswith("SMA_2")]
    if sma50_col and sma200_col:
        s50  = float(df[sma50_col[0]].iloc[-1])
        s200 = float(df[sma200_col[0]].iloc[-1])
        if not (pd.isna(s50) or pd.isna(s200)):
            if price > s50 and price > s200:   out["direction"] = "long"
            elif price < s50 and price < s200: out["direction"] = "short"

    # RSI
    rsi_col = [c for c in df.columns if c.startswith("RSI_")]
    if rsi_col:
        v = float(df[rsi_col[0]].iloc[-1])
        if not pd.isna(v): out["rsi"] = v

    # ATR
    atr_col = [c for c in df.columns if c.startswith("ATRr_")]
    if atr_col:
        v = float(df[atr_col[0]].iloc[-1])
        if not pd.isna(v): out["atr"] = v

    # MACD
    macd_c = [c for c in df.columns if "MACD_" in c and "MACDs_" not in c and "MACDh_" not in c]
    macds_c= [c for c in df.columns if "MACDs_" in c]
    if macd_c and macds_c:
        mv = float(df[macd_c[0]].iloc[-1]); sv = float(df[macds_c[0]].iloc[-1])
        if not (pd.isna(mv) or pd.isna(sv)): out["macd_bull"] = mv > sv

    # FVG detection (last 10 candles, direction-aware)
    n = min(len(df)-2, 12)
    for i in range(1, n):
        lo_i = float(df['Low'].iloc[-i]); hi_i2 = float(df['High'].iloc[-i-2])
        hi_i = float(df['High'].iloc[-i]); lo_i2 = float(df['Low'].iloc[-i-2])
        c_prev = float(df['Close'].iloc[-i-1]); o_prev = float(df['Open'].iloc[-i-1])
        if lo_i > hi_i2 and c_prev > o_prev:  out["fvg"] = True; break
        if hi_i < lo_i2 and c_prev < o_prev:  out["fvg"] = True; break

    # OB detection (impulsive reversal)
    for i in range(1, min(n, 10)):
        if out["atr"] > 0:
            body = abs(float(df['Close'].iloc[-i]) - float(df['Open'].iloc[-i]))
            prev_dir_bear = float(df['Close'].iloc[-i-1]) < float(df['Open'].iloc[-i-1])
            curr_dir_bull = float(df['Close'].iloc[-i]) > float(df['Open'].iloc[-i])
            if prev_dir_bear and curr_dir_bull and body > out["atr"]:
                out["ob"] = True; break
            prev_dir_bull2 = float(df['Close'].iloc[-i-1]) > float(df['Open'].iloc[-i-1])
            curr_dir_bear2 = float(df['Close'].iloc[-i]) < float(df['Open'].iloc[-i])
            if prev_dir_bull2 and curr_dir_bear2 and body > out["atr"]:
                out["ob"] = True; break

    # Premium / Discount (50% Fibonacci of last 50 candles)
    lb = min(50, len(df))
    sh = float(df['High'].iloc[-lb:].max())
    sl = float(df['Low'].iloc[-lb:].min())
    out["swing_high"] = sh; out["swing_low"] = sl
    rng = sh - sl
    if rng > 0:
        out["mid_range"]   = (sh + sl) / 2
        out["zone_pct"]    = (price - sl) / rng * 100
        out["in_discount"] = price < out["mid_range"]
        out["in_premium"]  = price > out["mid_range"]

    return out


@st.cache_data(ttl=3600)
def check_fundamentals():
    try:
        root = ET.fromstring(requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.xml", timeout=5).content)
        today = datetime.now().strftime("%m-%d-%Y")
        return [c.find('title').text for c in root.findall('event')
                if c.find('impact').text == "High" and c.find('date').text == today]
    except: return []

# ─────────────────────────────────────────
#  LOAD ALL 3 TIMEFRAMES
# ─────────────────────────────────────────
style_cfg = MTF_CONFIG[st.session_state.style]
is_crypto = selected_group == "Crypto"

with st.spinner(f"Loading {style_cfg['short'][0]} / {style_cfg['short'][1]} / {style_cfg['short'][2]} data..."):
    df_bias   = load_tf(ticker_symbol, style_cfg["bias"]["period"],   style_cfg["bias"]["tf"])
    df_struct = load_tf(ticker_symbol, style_cfg["struct"]["period"], style_cfg["struct"]["tf"])
    df_entry  = load_tf(ticker_symbol, style_cfg["entry"]["period"],  style_cfg["entry"]["tf"])

bias_r   = analyze_tf(df_bias)
struct_r = analyze_tf(df_struct)
entry_r  = analyze_tf(df_entry)

# PDH / PDL — always from daily
df_daily = load_tf(ticker_symbol, "10d", "1d")
pdh = pdl = None
if df_daily is not None and len(df_daily) >= 2:
    pdh = float(df_daily['High'].iloc[-2])
    pdl = float(df_daily['Low'].iloc[-2])
    pwh = float(df_daily['High'].iloc[-5:].max()) if len(df_daily) >= 5 else pdh
    pwl = float(df_daily['Low'].iloc[-5:].min())  if len(df_daily) >= 5 else pdl
else:
    pwh = pwl = None

news_events = check_fundamentals()
news_clear  = len(news_events) == 0

# ─────────────────────────────────────────
#  MTF SIGNAL ENGINE
#  All 3 TFs must agree for a valid signal
# ─────────────────────────────────────────
b_dir = bias_r["direction"]
s_dir = struct_r["direction"]
e_dir = entry_r["direction"]

# Kill zone filter
has_volume = in_kill_zone or is_crypto

# Count aligned TFs
def count_aligned(d): return sum(1 for x in [b_dir, s_dir, e_dir] if x == d)
long_aligned  = count_aligned("long")
short_aligned = count_aligned("short")

direction_key = "wait"
entry_price = tp = sl = 0.0
validity_text = "No MTF alignment. All 3 timeframes must agree on direction."
validity_sub  = f"Currently: {style_cfg['short'][0]} {b_dir.upper()} · {style_cfg['short'][1]} {s_dir.upper()} · {style_cfg['short'][2]} {e_dir.upper()}"

# All 3 must agree + premium/discount filter
if long_aligned == 3 and struct_r["in_discount"]:
    direction_key = "long"
elif short_aligned == 3 and struct_r["in_premium"]:
    direction_key = "short"
elif long_aligned == 3 and not struct_r["in_discount"]:
    validity_text = "All 3 TFs bullish but price in PREMIUM zone — wait for pullback."
    validity_sub  = f"Entry zone: below {struct_r['mid_range']:.4f} (50% level)"
elif short_aligned == 3 and not struct_r["in_premium"]:
    validity_text = "All 3 TFs bearish but price in DISCOUNT zone — wait for bounce."
    validity_sub  = f"Entry zone: above {struct_r['mid_range']:.4f} (50% level)"

# Session / kill zone filter
if not has_volume and direction_key != "wait":
    direction_key = "wait"
    validity_text = f"A+ Setup found but outside kill zone ({session_name})."
    validity_sub  = "Wait for London Open (07:00) or NY Open (13:30) UTC."

# News filter
if not news_clear and direction_key != "wait":
    direction_key = "wait"
    validity_text = f"High-impact news active. Setup paused: {', '.join(news_events[:2])}."
    validity_sub  = "Resume after news event clears."

# Entry / SL / TP using entry TF ATR (tighter, more precise)
atr = entry_r["atr"] or struct_r["atr"] or 0.001
price = entry_r["price"] or (float(df_entry['Close'].iloc[-1]) if df_entry is not None and len(df_entry) > 0 else 0)

if direction_key == "long" and price:
    entry_price = price - (atr * 0.3)
    sl          = entry_price - (atr * 1.2)       # tighter SL = surgical entry
    tp          = entry_price + (atr * 4.0)       # 1:3.3 R:R minimum
    validity_text = f"Invalidated if price closes below {sl:.4f} on {style_cfg['short'][2]} chart."
    validity_sub  = ""
elif direction_key == "short" and price:
    entry_price = price + (atr * 0.3)
    sl          = entry_price + (atr * 1.2)
    tp          = entry_price - (atr * 4.0)
    validity_text = f"Invalidated if price breaks above {sl:.4f} on {style_cfg['short'][2]} chart."
    validity_sub  = ""

# ─────────────────────────────────────────
#  CONFIDENCE SCORING (Weighted MTF Model)
# ─────────────────────────────────────────
def calc_confidence():
    if direction_key == "wait": return 0
    score = 0
    # Timeframe alignment (60 pts max — core of the system)
    tf_match = sum(1 for d in [b_dir, s_dir, e_dir] if d == direction_key)
    score += tf_match * 20          # 60 max — all 3 aligned
    # Premium/Discount (10 pts)
    if direction_key == "long"  and struct_r["in_discount"]: score += 10
    if direction_key == "short" and struct_r["in_premium"]:  score += 10
    # Structure signals on structural TF (15 pts)
    if struct_r["fvg"]: score += 8
    if struct_r["ob"]:  score += 7
    # Kill zone (10 pts)
    if in_kill_zone: score += 10
    # Entry TF momentum (10 pts)
    rsi = entry_r["rsi"]
    if direction_key == "long"  and entry_r["macd_bull"] and 40 < rsi < 68: score += 10
    if direction_key == "short" and not entry_r["macd_bull"] and 32 < rsi < 60: score += 10
    # News clear (5 pts)
    if news_clear: score += 5
    return min(score, 100)

confidence = calc_confidence()

# R:R calculation
pip_divisor = 100 if "JPY" in selected_asset_name else 10000
pips_tp = abs(tp - entry_price) * pip_divisor if tp and entry_price else 0
pips_sl = abs(sl - entry_price) * pip_divisor if sl and entry_price else 0
rr_ratio = pips_tp / pips_sl if pips_sl > 0 else 0

# Confluence items (updated for MTF)
cf_items = [
    (f"Bias TF ({style_cfg['short'][0]}) aligned",     b_dir == direction_key and direction_key != "wait", "B1"),
    (f"Structure TF ({style_cfg['short'][1]}) aligned", s_dir == direction_key and direction_key != "wait", "B2"),
    (f"Entry TF ({style_cfg['short'][2]}) aligned",     e_dir == direction_key and direction_key != "wait", "B3"),
    ("Price in correct zone (Premium/Discount)",
        (direction_key=="long" and struct_r["in_discount"]) or
        (direction_key=="short" and struct_r["in_premium"]),             "B4"),
    ("FVG or OB on Structure TF",       struct_r["fvg"] or struct_r["ob"],     "B5"),
    ("Kill zone active",                in_kill_zone or is_crypto,              "B6"),
    ("Fundamental overlay clear",       news_clear,                             "B7"),
]
cf_confirmed = sum(1 for _,v,_ in cf_items if v)

# ─────────────────────────────────────────
#  BUILD HTML VARIABLES
# ─────────────────────────────────────────
session_dot   = "#00D68F" if in_kill_zone or is_crypto else "#F5C142"
card_bar      = {"long":"#00D68F","short":"#FF3A5C","wait":"#2A3A45"}.get(direction_key,"#2A3A45")
badge_cls     = {"long":"badge-long","short":"badge-short","wait":"badge-wait"}.get(direction_key,"badge-wait")
badge_txt     = {"long":"LONG","short":"SHORT","wait":"NO SIGNAL"}.get(direction_key,"NO SIGNAL")
asset_sub     = "High-probability MTF-confirmed setup." if direction_key in ("long","short") else "Waiting for full MTF alignment."
asset_icon    = ASSET_ICONS.get(selected_asset_name, selected_asset_name[0])

pill_long  = "background:#0A2E1F;border-color:#00D68F;color:#00D68F;" if direction_key=="long"  else ""
pill_short = "background:#2E0A13;border-color:#FF3A5C;color:#FF3A5C;" if direction_key=="short" else ""
pill_wait  = "background:#2E280A;border-color:#F5C142;color:#F5C142;" if direction_key=="wait"  else ""

if not news_clear:
    fund_style = "background:#2E0A13;border:1px solid #5A1A22;"
    fund_title = "High Impact News Active"
    fund_sub   = f"Events: {', '.join(news_events[:3])}. System paused."
    fund_badge_cls, fund_badge_txt = "high", "HIGH RISK"
else:
    fund_style = ""
    fund_title = "Fundamental overlay clear"
    fund_sub   = "No high-impact events detected. System active."
    fund_badge_cls, fund_badge_txt = "low", "LOW RISK"

# Entry range display
if entry_price and direction_key == "long":
    entry_range = f"{entry_price:.4f} &ndash; {(entry_price + atr*0.1):.4f}"
elif entry_price and direction_key == "short":
    entry_range = f"{(entry_price - atr*0.1):.4f} &ndash; {entry_price:.4f}"
else:
    entry_range = "&mdash;"

tp_str = f"{tp:.4f}" if tp else "&mdash;"
sl_str = f"{sl:.4f}" if sl else "&mdash;"
pips_tp_str = f"+{pips_tp:.1f} pips" if pips_tp else ""
pips_sl_str = f"-{pips_sl:.1f} pips" if pips_sl else ""
rr_str  = f"1 : {rr_ratio:.1f}" if rr_ratio > 0 else "—"
tp_css  = "#00D68F" if direction_key=="long" else ("#FF3A5C" if direction_key=="short" else "#666")
sl_css  = "#FF3A5C" if direction_key=="long" else ("#00D68F" if direction_key=="short" else "#666")

# MTF direction styling
def tf_style(d, target):
    if d == "long":    return "#00D68F", "▲ BULLISH", "#0A2E1F", "1px solid #1A4030"
    if d == "short":   return "#FF3A5C", "▼ BEARISH", "#2E0A13", "1px solid #4A1020"
    return "#F5C142", "— NEUTRAL", "#1A1500", "1px solid #3A2E00"

b_col, b_lbl, b_bg, b_bdr = tf_style(b_dir, direction_key)
s_col, s_lbl, s_bg, s_bdr = tf_style(s_dir, direction_key)
e_col, e_lbl, e_bg, e_bdr = tf_style(e_dir, direction_key)

# Alignment badge
all_aligned = long_aligned == 3 or short_aligned == 3
if all_aligned and direction_key != "wait":
    align_bg  = "#0A2316"; align_bdr = "1px solid #1A4030"; align_col = "#00D68F"
    align_txt = "&#10003; ALL 3 TIMEFRAMES ALIGNED &mdash; HIGH CONVICTION SIGNAL"
elif long_aligned == 2 or short_aligned == 2:
    align_bg  = "#1A1500"; align_bdr = "1px solid #3A2E00"; align_col = "#F5C142"
    align_txt = "&#9888; 2 / 3 TIMEFRAMES ALIGNED &mdash; WAIT FOR FULL CONFIRMATION"
else:
    align_bg  = "#1A1A1A"; align_bdr = "1px solid #2A2A2A"; align_col = "#5A6872"
    align_txt = "&#10005; TIMEFRAMES CONFLICTED &mdash; NO TRADE"

# Zone indicator
zone_pct = struct_r["zone_pct"]
zone_label = f"DISCOUNT ({zone_pct:.0f}%)" if zone_pct < 50 else f"PREMIUM ({zone_pct:.0f}%)"
zone_col   = "#00D68F" if zone_pct < 50 else "#FF3A5C"
zone_ok    = (direction_key=="long" and zone_pct<50) or (direction_key=="short" and zone_pct>50)

# PDH/PDL
pdh_str = f"{pdh:.4f}" if pdh else "N/A"
pdl_str = f"{pdl:.4f}" if pdl else "N/A"
pwh_str = f"{pwh:.4f}" if pwh else "N/A"
pwl_str = f"{pwl:.4f}" if pwl else "N/A"

# Confidence bar
conf_col = "#00D68F" if confidence >= 75 else ("#F5C142" if confidence >= 50 else "#FF3A5C")
conf_gate = "FIRE" if confidence >= 75 else ("MARGINAL" if confidence >= 50 else "BLOCKED")

# Confluence rows
cf_rows = ""
for cf_text, cf_val, cf_num in cf_items:
    chk   = "&#10003;" if cf_val else "&#10005;"
    chk_c = "#00D68F"  if cf_val else "#FF3A5C"
    txt_c = "#E8E8E8"  if cf_val else "#5A6872"
    cf_rows += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #151A1D;">
            <span style="color:{chk_c};font-size:13px;font-weight:700;width:16px;text-align:center;">{chk}</span>
            <span style="font-size:13px;color:{txt_c};flex:1;">{cf_text}</span>
            <span style="font-size:10px;color:#3A4A55;font-weight:600;">{cf_num}</span>
        </div>"""

val_sub_html = f'<p style="font-size:12px;color:#5A6872;margin:6px 0 0;line-height:1.5;">{validity_sub}</p>' if validity_sub else ""
val_bg  = "#001A0D" if direction_key in ("long","short") else "#0F0F0F"
val_bdr = "1px solid #003A1A" if direction_key in ("long","short") else "1px solid #1E2426"
updated = datetime.now(pytz.utc).strftime('%H:%M UTC')

# ─────────────────────────────────────────
#  RENDER — components.html (no sanitization)
# ─────────────────────────────────────────
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Inter',sans-serif;background:#0D0F10;color:#E8E8E8;font-size:14px;}}

.top-bar{{display:flex;align-items:center;justify-content:flex-end;padding:14px 36px;border-bottom:1px solid #1A1F23;}}
.sess-pill{{display:flex;align-items:center;gap:10px;padding:8px 18px;border-right:1px solid #1A1F23;}}
.sess-lbl{{font-size:9px;letter-spacing:2px;color:#5A6872;text-transform:uppercase;}}
.sess-val{{font-size:13px;font-weight:600;color:#fff;margin-top:2px;}}
.clock-pill{{display:flex;align-items:center;gap:8px;padding:8px 18px;font-size:13px;font-weight:600;color:#fff;}}

.page-hdr{{padding:26px 36px 0;}}
.page-sub{{font-size:10px;letter-spacing:2px;color:#5A6872;text-transform:uppercase;display:flex;align-items:center;gap:8px;margin-bottom:8px;}}
.live-badge{{background:#0A2E1F;border:1px solid #00D68F;border-radius:20px;padding:2px 10px;font-size:10px;color:#00D68F;letter-spacing:1px;}}
.page-title{{font-size:38px;font-weight:700;color:#fff;letter-spacing:-0.5px;margin-bottom:4px;}}
.page-desc{{font-size:13px;color:#6B7B8A;}}
.dir-pills{{display:flex;gap:6px;}}
.dir-pill{{padding:7px 18px;border-radius:8px;font-size:12px;font-weight:600;border:1px solid #252C32;color:#6B7B8A;background:#161B1F;}}
.hdr-row{{display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;}}

/* MTF Panel */
.mtf-panel{{margin:20px 36px 0;background:#0D1410;border:1px solid #1A2C20;border-radius:14px;padding:20px 24px;}}
.mtf-label{{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#5A6872;font-weight:600;margin-bottom:14px;}}
.mtf-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px;}}
.mtf-tf-box{{border-radius:10px;padding:14px;}}
.mtf-tf-name{{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;font-weight:600;margin-bottom:6px;opacity:0.7;}}
.mtf-tf-dir{{font-size:14px;font-weight:700;}}
.mtf-align{{border-radius:8px;padding:10px 16px;font-size:12px;font-weight:600;letter-spacing:0.5px;}}
.mtf-zone-row{{display:flex;align-items:center;justify-content:space-between;margin-top:10px;flex-wrap:wrap;gap:8px;}}
.zone-badge{{font-size:11px;font-weight:700;padding:4px 12px;border-radius:20px;}}
.key-levels{{display:flex;gap:16px;}}
.kl-item{{font-size:11px;color:#5A6872;}}
.kl-val{{font-weight:600;color:#E8E8E8;}}

/* Fund banner */
.fund-banner{{margin:16px 36px 0;display:flex;align-items:center;justify-content:space-between;background:#0A2316;border:1px solid #1A4030;border-radius:12px;padding:12px 18px;}}
.fund-left{{display:flex;align-items:center;gap:10px;}}
.fund-title{{font-size:13px;font-weight:600;color:#fff;margin-bottom:1px;}}
.fund-sub{{font-size:11px;color:#5A8A70;}}
.fund-badge{{font-size:10px;font-weight:700;letter-spacing:1px;padding:4px 12px;border-radius:20px;}}
.fund-badge.low{{background:#0A2316;border:1px solid #00D68F;color:#00D68F;}}
.fund-badge.high{{background:#2E0A13;border:1px solid #FF3A5C;color:#FF3A5C;}}

/* Signal card */
.signal-card{{margin:14px 36px 36px;background:#111416;border:1px solid #1E2426;border-radius:16px;overflow:hidden;}}
.card-inner{{display:flex;}}
.card-bar{{width:4px;flex-shrink:0;}}
.card-body{{flex:1;min-width:0;}}
.card-top{{display:flex;align-items:center;gap:14px;padding:20px 24px 0;}}
.asset-icon{{width:40px;height:40px;border-radius:10px;background:#1E2426;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:700;color:#fff;flex-shrink:0;}}
.asset-name{{font-size:20px;font-weight:700;color:#fff;}}
.asset-badge{{padding:3px 10px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:0.5px;}}
.badge-long{{background:#0A2E1F;color:#00D68F;}}
.badge-short{{background:#2E0A13;color:#FF3A5C;}}
.badge-wait{{background:#1A1F23;color:#5A6872;}}
.asset-sub{{font-size:12px;color:#6B7B8A;margin-top:2px;}}
.ap-label{{font-size:9px;color:#5A6872;letter-spacing:1px;text-transform:uppercase;}}
.ap-value{{font-size:14px;font-weight:700;color:#fff;margin-top:2px;}}

/* Metrics */
.metrics-row{{display:flex;padding:20px 24px;border-bottom:1px solid #1A1F23;gap:0;}}
.metric-col{{flex:1;}}
.metric-col+.metric-col{{border-left:1px solid #1A1F23;padding-left:20px;}}
.m-label{{font-size:9px;letter-spacing:2px;text-transform:uppercase;color:#5A6872;margin-bottom:5px;}}
.m-val{{font-size:24px;font-weight:700;color:#fff;letter-spacing:-0.5px;}}
.m-sub{{font-size:11px;color:#5A6872;margin-top:3px;}}
.rr-badge{{display:inline-block;background:#0A2316;border:1px solid #1A4030;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700;color:#00D68F;margin-top:4px;}}

/* Confidence bar */
.conf-bar-wrap{{padding:0 24px 16px;}}
.conf-bar-row{{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}}
.conf-bar-lbl{{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#5A6872;font-weight:600;}}
.conf-gate{{font-size:10px;font-weight:700;letter-spacing:1px;padding:2px 10px;border-radius:12px;}}
.conf-bar-bg{{background:#1A1F23;border-radius:4px;height:6px;overflow:hidden;}}
.conf-bar-fill{{height:6px;border-radius:4px;transition:width 0.3s;}}

/* Bottom */
.card-bottom{{display:flex;border-top:1px solid #1A1F23;}}
.conf-col{{flex:1;padding:18px 24px;border-right:1px solid #1A1F23;}}
.valid-col{{width:290px;flex-shrink:0;padding:18px 24px;}}
.cf-head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:12px;}}
.cf-title{{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#5A6872;font-weight:600;}}
.vb-label{{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#5A6872;font-weight:600;margin-bottom:10px;}}
.vb-text{{font-size:12px;color:#C8C8C8;line-height:1.6;}}
.vb-box{{border-radius:10px;padding:14px;margin-bottom:12px;}}
.conf-row{{display:flex;align-items:baseline;justify-content:space-between;margin-top:6px;}}
.conf-lbl2{{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:#5A6872;}}
.conf-val{{font-size:30px;font-weight:700;}}

/* Footer */
.card-footer{{display:flex;justify-content:space-between;align-items:center;padding:10px 24px;border-top:1px solid #1A1F23;font-size:10px;color:#3A4A55;}}
</style>
</head>
<body>

<!-- TOP BAR -->
<div class="top-bar">
    <div class="sess-pill">
        <div style="width:8px;height:8px;border-radius:50%;background:{session_dot};flex-shrink:0;"></div>
        <div>
            <div class="sess-lbl">Market Session</div>
            <div class="sess-val">{session_name}</div>
        </div>
    </div>
    <div class="clock-pill">&#128336; UTC &nbsp; {utc_time}</div>
</div>

<!-- PAGE HEADER -->
<div class="page-hdr">
    <div class="page-sub">Institutional Signal Engine &nbsp;<span class="live-badge">LIVE</span></div>
    <div class="hdr-row">
        <div>
            <h1 class="page-title">Market Opportunity</h1>
            <p class="page-desc">MTF analysis &mdash; {style_cfg['short'][0]} bias &middot; {style_cfg['short'][1]} structure &middot; {style_cfg['short'][2]} entry</p>
        </div>
        <div class="dir-pills">
            <div class="dir-pill" style="{pill_long}">Long</div>
            <div class="dir-pill" style="{pill_short}">Short</div>
            <div class="dir-pill" style="{pill_wait}">Waiting</div>
        </div>
    </div>
</div>

<!-- MTF ALIGNMENT PANEL -->
<div class="mtf-panel">
    <div class="mtf-label">Multi-Timeframe Analysis &mdash; {style_cfg['label']}</div>
    <div class="mtf-grid">
        <div class="mtf-tf-box" style="background:{b_bg};border:{b_bdr};">
            <div class="mtf-tf-name" style="color:{b_col};">{style_cfg['names'][0]}</div>
            <div class="mtf-tf-dir" style="color:{b_col};">{b_lbl}</div>
        </div>
        <div class="mtf-tf-box" style="background:{s_bg};border:{s_bdr};">
            <div class="mtf-tf-name" style="color:{s_col};">{style_cfg['names'][1]}</div>
            <div class="mtf-tf-dir" style="color:{s_col};">{s_lbl}</div>
        </div>
        <div class="mtf-tf-box" style="background:{e_bg};border:{e_bdr};">
            <div class="mtf-tf-name" style="color:{e_col};">{style_cfg['names'][2]}</div>
            <div class="mtf-tf-dir" style="color:{e_col};">{e_lbl}</div>
        </div>
    </div>
    <div class="mtf-align" style="background:{align_bg};border:{align_bdr};color:{align_col};">{align_txt}</div>
    <div class="mtf-zone-row">
        <div style="display:flex;align-items:center;gap:10px;">
            <span class="zone-badge" style="background:{'#0A2316' if zone_pct<50 else '#2E0A13'};border:1px solid {zone_col};color:{zone_col};">{zone_label}</span>
            <span style="font-size:11px;color:#5A6872;">{'&#10003; Correct zone for ' + direction_key if zone_ok else '&#9888; Wrong zone — avoid entry'}</span>
        </div>
        <div class="key-levels">
            <div class="kl-item">PDH <span class="kl-val">{pdh_str}</span></div>
            <div class="kl-item">PDL <span class="kl-val">{pdl_str}</span></div>
            <div class="kl-item">PWH <span class="kl-val">{pwh_str}</span></div>
            <div class="kl-item">PWL <span class="kl-val">{pwl_str}</span></div>
        </div>
    </div>
</div>

<!-- FUNDAMENTAL BANNER -->
<div class="fund-banner" style="{fund_style}">
    <div class="fund-left">
        <span style="font-size:16px;">&#128737;</span>
        <div>
            <div class="fund-title">{fund_title}</div>
            <div class="fund-sub">{fund_sub}</div>
        </div>
    </div>
    <span class="fund-badge {fund_badge_cls}">{fund_badge_txt}</span>
</div>

<!-- SIGNAL CARD -->
<div class="signal-card">
    <div class="card-inner">
        <div class="card-bar" style="background:{card_bar};"></div>
        <div class="card-body">

            <!-- CARD TOP -->
            <div class="card-top">
                <div class="asset-icon">{asset_icon}</div>
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:2px;">
                        <span class="asset-name">{selected_asset_name}</span>
                        <span class="asset-badge {badge_cls}">{badge_txt}</span>
                    </div>
                    <p class="asset-sub">{asset_sub}</p>
                </div>
                <div style="margin-left:auto;text-align:right;">
                    <div class="ap-label">Analysis Profile</div>
                    <div class="ap-value">{style_cfg['label']} &middot; {style_cfg['short'][2]} Entry</div>
                </div>
            </div>

            <!-- METRICS -->
            <div class="metrics-row">
                <div class="metric-col">
                    <div class="m-label">Entry Zone ({style_cfg['short'][2]})</div>
                    <div class="m-val">{entry_range}</div>
                    <div class="m-sub">LIMIT ORDER RANGE</div>
                </div>
                <div class="metric-col">
                    <div class="m-label">Target (Liquidity)</div>
                    <div class="m-val" style="color:{tp_css};">{tp_str}</div>
                    <div class="m-sub" style="color:{tp_css};">{pips_tp_str}</div>
                </div>
                <div class="metric-col">
                    <div class="m-label">Invalidation (SL)</div>
                    <div class="m-val" style="color:{sl_css};">{sl_str}</div>
                    <div class="m-sub" style="color:{sl_css};">{pips_sl_str}</div>
                </div>
                <div class="metric-col">
                    <div class="m-label">Risk : Reward</div>
                    <div class="m-val" style="color:#E8E8E8;">{rr_str}</div>
                    <div class="rr-badge" style="{'display:none' if not rr_ratio else ''}">{'VALID' if rr_ratio >= 3 else 'LOW RR'}</div>
                </div>
            </div>

            <!-- CONFIDENCE BAR -->
            <div class="conf-bar-wrap" style="padding-top:14px;">
                <div class="conf-bar-row">
                    <span class="conf-bar-lbl">Signal Confidence</span>
                    <span class="conf-gate" style="background:{'#0A2316' if confidence>=75 else ('#1A1500' if confidence>=50 else '#2E0A13')};color:{conf_col};">{conf_gate} &mdash; {confidence}%</span>
                </div>
                <div class="conf-bar-bg">
                    <div class="conf-bar-fill" style="width:{confidence}%;background:{conf_col};"></div>
                </div>
            </div>

            <!-- BOTTOM -->
            <div class="card-bottom">
                <div class="conf-col">
                    <div class="cf-head">
                        <span class="cf-title">Confluence Matrix</span>
                        <span style="font-size:12px;font-weight:600;color:{'#00D68F' if cf_confirmed>=5 else ('#F5C142' if cf_confirmed>=3 else '#FF3A5C')};">{cf_confirmed} / {len(cf_items)} CONFIRMED</span>
                    </div>
                    <div>{cf_rows}</div>
                </div>

                <div class="valid-col">
                    <div class="vb-label">Setup Validity</div>
                    <div class="vb-box" style="background:{val_bg};border:{val_bdr};">
                        <p class="vb-text">{validity_text}</p>
                        {val_sub_html}
                    </div>
                    <div class="conf-row">
                        <span class="conf-lbl2">Model Confidence</span>
                        <span class="conf-val" style="color:{conf_col};">{confidence}%</span>
                    </div>
                    <div style="font-size:10px;color:#5A6872;margin-top:4px;">
                        {'&#10003; CLEAR TO TRADE' if confidence >= 75 and direction_key != 'wait' else '&#9888; WAIT — threshold not met (75%)'}
                    </div>
                </div>
            </div>

            <!-- FOOTER -->
            <div class="card-footer">
                <span>APEX MTF ENGINE v2.0</span>
                <span>Decision support only. Always manage your risk.</span>
                <span>UPDATED {updated}</span>
            </div>

        </div>
    </div>
</div>

</body>
</html>"""

components.html(html, height=1020, scrolling=False)

with st.expander("🔍 Developer Mode — Raw MTF Data"):
    t1, t2, t3 = st.tabs([
        f"Bias ({style_cfg['short'][0]})",
        f"Structure ({style_cfg['short'][1]})",
        f"Entry ({style_cfg['short'][2]})"
    ])
    with t1: st.dataframe(df_bias.tail(15) if df_bias is not None else pd.DataFrame(), width="stretch")
    with t2: st.dataframe(df_struct.tail(15) if df_struct is not None else pd.DataFrame(), width="stretch")
    with t3: st.dataframe(df_entry.tail(15) if df_entry is not None else pd.DataFrame(), width="stretch")
