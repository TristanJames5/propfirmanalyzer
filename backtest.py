import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

print("Downloading Historical Data (2024-2026)...")
# yfinance limits 1h data to max 730 days (approx 2 years)
df_1h = yf.download("BTC-USD", period="730d", interval="1h", progress=False, auto_adjust=True)
df_1d = yf.download("BTC-USD", period="1000d", interval="1d", progress=False, auto_adjust=True)

if isinstance(df_1h.columns, pd.MultiIndex):
    df_1h.columns = df_1h.columns.get_level_values(0)
if isinstance(df_1d.columns, pd.MultiIndex):
    df_1d.columns = df_1d.columns.get_level_values(0)

print("Calculating Indicators...")
# Daily (Bias)
df_1d['SMA50'] = ta.sma(df_1d['Close'], length=50)
df_1d['SMA200'] = ta.sma(df_1d['Close'], length=200)
df_1d['Daily_Bias'] = np.where((df_1d['Close'] > df_1d['SMA50']) & (df_1d['Close'] > df_1d['SMA200']), 1, 
                       np.where((df_1d['Close'] < df_1d['SMA50']) & (df_1d['Close'] < df_1d['SMA200']), -1, 0))

# 1H (Structure & Entry)
df_1h['SMA50'] = ta.sma(df_1h['Close'], length=50)
df_1h['SMA200'] = ta.sma(df_1h['Close'], length=200)
df_1h['ATR'] = ta.atr(df_1h['High'], df_1h['Low'], df_1h['Close'], length=14)

# Map Daily bias to 1H dataframe
df_1d_bias = df_1d[['Daily_Bias']].copy()
if df_1d_bias.index.tz is not None:
    df_1d_bias.index = df_1d_bias.index.tz_localize(None)
    
bias_series = pd.Series(df_1h.index.normalize().map(df_1d_bias['Daily_Bias']), index=df_1h.index)
df_1h['Daily_Bias'] = bias_series.ffill()

df_1h.dropna(inplace=True)

print("Running Simulation...")
trades = []
active_trade = None

for i in range(50, len(df_1h)):
    row = df_1h.iloc[i]
    idx = df_1h.index[i]
    
    # Manage active trade
    if active_trade:
        if row['High'] >= active_trade['TP'] and active_trade['Dir'] == 'Long':
            active_trade['Result'] = 'Win'
            trades.append(active_trade)
            active_trade = None
        elif row['Low'] <= active_trade['SL'] and active_trade['Dir'] == 'Long':
            active_trade['Result'] = 'Loss'
            trades.append(active_trade)
            active_trade = None
        elif row['Low'] <= active_trade['TP'] and active_trade['Dir'] == 'Short':
            active_trade['Result'] = 'Win'
            trades.append(active_trade)
            active_trade = None
        elif row['High'] >= active_trade['SL'] and active_trade['Dir'] == 'Short':
            active_trade['Result'] = 'Loss'
            trades.append(active_trade)
            active_trade = None
        continue

    # Kill zone check (UTC)
    hr = idx.hour
    mins = hr * 60 + idx.minute
    in_kill_zone = (7*60 <= mins <= 9*60+30) or (13*60+30 <= mins <= 16*60)
    
    # Bypass kill zone for crypto
    # if not in_kill_zone:
    #     continue

    bias = row['Daily_Bias']
    price = row['Close']
    sma50 = row['SMA50']
    sma200 = row['SMA200']
    atr = row['ATR']
    
    struct_dir = 1 if price > sma50 and price > sma200 else (-1 if price < sma50 and price < sma200 else 0)
    
    if bias == 0 or struct_dir == 0 or bias != struct_dir:
        continue
        
    # Premium / Discount
    window = df_1h.iloc[i-50:i]
    sh = window['High'].max()
    sl = window['Low'].min()
    mid = (sh + sl) / 2
    
    in_discount = price < mid
    in_premium = price > mid
    
    # Very basic FVG approximation for speed (just checking if gap exists in last 3 candles)
    fvg = False
    for j in range(1, 4):
        if i-j-2 < 0: continue
        prev_hi = df_1h['High'].iloc[i-j-2]
        curr_lo = df_1h['Low'].iloc[i-j]
        prev_lo = df_1h['Low'].iloc[i-j-2]
        curr_hi = df_1h['High'].iloc[i-j]
        if bias == 1 and curr_lo > prev_hi: fvg = True
        if bias == -1 and curr_hi < prev_lo: fvg = True
        
    # Entry Logic (1:3.3 RR)
    if bias == 1:
        entry = price - (atr * 0.3)
        sl_val = entry - (atr * 1.2)
        tp_val = entry + (atr * 4.0)
        active_trade = {'Time': idx, 'Dir': 'Long', 'Entry': entry, 'SL': sl_val, 'TP': tp_val}
    elif bias == -1:
        entry = price + (atr * 0.3)
        sl_val = entry + (atr * 1.2)
        tp_val = entry - (atr * 4.0)
        active_trade = {'Time': idx, 'Dir': 'Short', 'Entry': entry, 'SL': sl_val, 'TP': tp_val}

wins = len([t for t in trades if t['Result'] == 'Win'])
losses = len([t for t in trades if t['Result'] == 'Loss'])
total = wins + losses

print("-" * 40)
print(f"BACKTEST RESULTS: BTC-USD (2024-2026)")
print(f"Strategy: Sniper MTF (Daily Bias + 1H Structure/Entry)")
print(f"Total Signals Fired: {total}")
if total > 0:
    winrate = (wins / total) * 100
    print(f"Wins: {wins} | Losses: {losses}")
    print(f"Win Rate: {winrate:.2f}%")
    print(f"Average R:R per trade: 1 : 3.3")
    rr_won = wins * 3.33
    rr_lost = losses * 1.0
    net_r = rr_won - rr_lost
    print(f"Net Return in R: +{net_r:.2f}R")
    print(f"Estimated Account Growth (1% risk): +{net_r:.2f}%")
else:
    print("No trades taken. System constraints were too tight for this dataset.")
print("-" * 40)
