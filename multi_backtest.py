import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

# All assets from the trading analyzer
ASSETS = {
    "Forex": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "Metals": ["GC=F", "SI=F"], 
    "Indices": ["^GSPC", "^NDX", "^DJI"]
}

results = []

print("Starting Multi-Asset Backtest (2024-2026)...")
print("-" * 50)

for category, tickers in ASSETS.items():
    for ticker in tickers:
        print(f"Testing {ticker} ({category})...")
        try:
            df_1h = yf.download(ticker, period="730d", interval="1h", progress=False, auto_adjust=True)
            df_1d = yf.download(ticker, period="1000d", interval="1d", progress=False, auto_adjust=True)

            if len(df_1h) < 100 or len(df_1d) < 100:
                print(f"  -> Not enough data for {ticker}")
                continue

            if isinstance(df_1h.columns, pd.MultiIndex):
                df_1h.columns = df_1h.columns.get_level_values(0)
            if isinstance(df_1d.columns, pd.MultiIndex):
                df_1d.columns = df_1d.columns.get_level_values(0)

            # Daily (Bias)
            df_1d['SMA50'] = ta.sma(df_1d['Close'], length=50)
            df_1d['SMA200'] = ta.sma(df_1d['Close'], length=200)
            df_1d['Daily_Bias'] = np.where((df_1d['Close'] > df_1d['SMA50']) & (df_1d['Close'] > df_1d['SMA200']), 1, 
                                   np.where((df_1d['Close'] < df_1d['SMA50']) & (df_1d['Close'] < df_1d['SMA200']), -1, 0))

            # 1H (Structure & Entry)
            df_1h['SMA50'] = ta.sma(df_1h['Close'], length=50)
            df_1h['SMA200'] = ta.sma(df_1h['Close'], length=200)
            df_1h['ATR'] = ta.atr(df_1h['High'], df_1h['Low'], df_1h['Close'], length=14)
            df_1h['RSI'] = ta.rsi(df_1h['Close'], length=14)

            df_1d_bias = df_1d[['Daily_Bias']].copy()
            df_1d_bias.index = pd.to_datetime(df_1d_bias.index).tz_localize(None).normalize()
            df_1h_norm = pd.to_datetime(df_1h.index).tz_localize(None).normalize()
            df_1h['Daily_Bias'] = df_1h_norm.map(df_1d_bias['Daily_Bias']).values
            df_1h['Daily_Bias'] = df_1h['Daily_Bias'].ffill()

            df_1h.dropna(inplace=True)

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
                        
                if active_trade:
                    continue

                # Kill zone check (UTC) - Apply to non-crypto
                in_kill_zone = True
                if category != "Crypto":
                    hr = idx.hour
                    mins = hr * 60 + idx.minute
                    in_kill_zone = (7*60 <= mins <= 9*60+30) or (13*60+30 <= mins <= 16*60)
                
                if not in_kill_zone:
                    continue

                bias = row['Daily_Bias']
                price = row['Close']
                sma50 = row['SMA50']
                sma200 = row['SMA200']
                atr = row['ATR']
                rsi = row['RSI']
                
                struct_dir = 1 if price > sma50 and price > sma200 else (-1 if price < sma50 and price < sma200 else 0)
                
                if bias == 0 or struct_dir == 0 or bias != struct_dir:
                    continue
                    
                # Strict RSI Pullback Filter (Only buy when RSI is relatively low in a trend, sell when high)
                if bias == 1 and rsi > 50:
                    continue
                if bias == -1 and rsi < 50:
                    continue
                    
                # High-Accuracy Entry Logic (1:1.5 RR - Securing profits early)
                if bias == 1:
                    entry = price
                    sl_val = entry - (atr * 1.5)  # Wider stop to avoid wicks
                    tp_val = entry + (atr * 2.25) # 1:1.5 ratio
                    active_trade = {'Time': idx, 'Dir': 'Long', 'Entry': entry, 'SL': sl_val, 'TP': tp_val}
                elif bias == -1:
                    entry = price
                    sl_val = entry + (atr * 1.5)
                    tp_val = entry - (atr * 2.25)
                    active_trade = {'Time': idx, 'Dir': 'Short', 'Entry': entry, 'SL': sl_val, 'TP': tp_val}

            wins = len([t for t in trades if t['Result'] == 'Win'])
            losses = len([t for t in trades if t['Result'] == 'Loss'])
            total = wins + losses
            
            if total > 0:
                winrate = (wins / total) * 100
                rr_won = wins * 1.5
                rr_lost = losses * 1.0
                net_r = rr_won - rr_lost
                results.append({
                    "Pair": ticker,
                    "Category": category,
                    "Trades": total,
                    "Win Rate": f"{winrate:.1f}%",
                    "Net R (%)": round(net_r, 2)
                })
            else:
                results.append({
                    "Pair": ticker,
                    "Category": category,
                    "Trades": 0,
                    "Win Rate": "0.0%",
                    "Net R (%)": 0.0
                })
        except Exception as e:
            print(f"  -> Error processing {ticker}: {e}")

print("\n" + "="*70)
print(f"{'Pair':<12} | {'Category':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Net R / % Growth':<15}")
print("-" * 70)
# Sort by Net R descending
results = sorted(results, key=lambda x: x['Net R (%)'], reverse=True)
for r in results:
    growth = f"+{r['Net R (%)']}%" if r['Net R (%)'] > 0 else f"{r['Net R (%)']}%"
    print(f"{r['Pair']:<12} | {r['Category']:<10} | {r['Trades']:<8} | {r['Win Rate']:<10} | {growth}")
print("="*70)
