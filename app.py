import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- MOTORE DI CALCOLO CORE ---
def run_simulation(df, capitale, rr, commissione, slip, algo_type, fast_p=2, slow_p=20):
    balance = capitale
    equity = [capitale]
    pos = None
    wins, losses = 0, 0
    
    # Parametri Asset
    if "XAUUSD" in algo_type:
        STOP_PIPS = 50 
        VALORE_PUNTO = 100.0
        point = 0.01
        SOGLIA_ATR = 1.5
        RISCHIO = 0.001 # 0.1%
    else: # USDJPY
        VALORE_PUNTO = 1000.0
        point = 0.001
        SOGLIA_ATR = 0 # Non usato per Yen Breakout
        RISCHIO = 0.005 # 0.5%

    # Indicatori
    df['ema_fast'] = df['close'].ewm(span=fast_p, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow_p, adjust=False).mean()
    df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=14).mean()

    # Logica specifica per asset
    asia_h, asia_l = 0.0, 9999.0
    session_done = False

    for i in range(20, len(df)):
        # 1. Chiusura Posizioni
        if pos:
            if pos['type'] == 'buy':
                if df['low'].iloc[i] <= pos['sl']:
                    balance -= (pos['risk'] + pos['comm'] + pos['slip']); pos = None; losses += 1
                elif df['high'].iloc[i] >= pos['tp']:
                    balance += (pos['risk'] * rr - pos['comm'] - pos['slip']); pos = None; wins += 1
            elif pos['type'] == 'sell':
                if df['high'].iloc[i] >= pos['sl']:
                    balance -= (pos['risk'] + pos['comm'] + pos['slip']); pos = None; losses += 1
                elif df['low'].iloc[i] <= pos['tp']:
                    balance += (pos['risk'] * rr - pos['comm'] - pos['slip']); pos = None; wins += 1
        
        # 2. Apertura Posizioni
        if not pos:
            if "XAUUSD" in algo_type:
                if df['atr'].iloc[i-1] >= SOGLIA_ATR:
                    sl_dist = STOP_PIPS * 10 * point
                    risk_amt = balance * RISCHIO
                    lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
                    costo_s = slip * point * VALORE_PUNTO * lotti
                    if df['ema_fast'].iloc[i-1] > df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] <= df['ema_slow'].iloc[i-2]:
                        pos = {'type':'buy','sl':df['open'].iloc[i]-sl_dist,'tp':df['open'].iloc[i]+sl_dist*rr,'risk':risk_amt,'comm':lotti*commissione,'slip':costo_s}
                    elif df['ema_fast'].iloc[i-1] < df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] >= df['ema_slow'].iloc[i-2]:
                        pos = {'type':'sell','sl':df['open'].iloc[i]+sl_dist,'tp':df['open'].iloc[i]-sl_dist*rr,'risk':risk_amt,'comm':lotti*commissione,'slip':costo_s}
            
            else: # USDJPY Breakout
                orario = str(df['time'].iloc[i])[:5]
                if orario == '00:00': asia_h, asia_l, session_done = 0.0, 9999.0, False
                if '00:00' <= orario < '08:00':
                    asia_h = max(asia_h, df['high'].iloc[i]); asia_l = min(asia_l, df['low'].iloc[i])
                if orario >= '08:00' and not session_done and asia_h > 0:
                    sl_range = asia_h - asia_l
                    risk_amt = balance * RISCHIO
                    lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2)) if sl_range > 0 else 0.01
                    costo_s = slip * point * VALORE_PUNTO * lotti
                    if df['high'].iloc[i] > asia_h:
                        pos = {'type':'buy','sl':asia_l,'tp':asia_h+sl_range*rr,'risk':risk_amt,'comm':lotti*commissione,'slip':costo_s}; session_done = True
                    elif df['low'].iloc[i] < asia_l:
                        pos = {'type':'sell','sl':asia_h,'tp':asia_l-sl_range*rr,'risk':risk_amt,'comm':lotti*commissione,'slip':costo_s}; session_done = True
        
        equity.append(balance)
    return {"balance": balance, "equity": equity, "wins": wins, "losses": losses}

# --- INTERFACCIA ---
st.set_page_config(page_title="ProQuant SaaS", layout="wide", page_icon="📊")

with st.sidebar:
    st.title("🛡️ ProQuant Lab")
    st.divider()
    asset = st.selectbox("Asset", ["XAUUSD (Oro)", "USDJPY (Yen)"])
    mode = st.radio("Modalità", ["📊 Analisi Singola", "🔥 Mappa di Calore"])
    st.divider()
    capitale = st.number_input("Capitale (€)", value=1000)
    rr = st.slider("Reward/Risk", 1.0, 15.0, 10.0 if "XAU" in asset else 3.0)
    slip = st.number_input("Slippage (Punti)", value=30)
    comm = st.number_input("Comm/Lotto (€)", value=7.0)

st.header(f"{mode} - {asset}")
uploaded_file = st.file_uploader("Carica file CSV (MT5)", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file, sep='\t')
    df_raw.columns = [col.replace('<', '').replace('>', '').lower() for col in df_raw.columns]

    if mode == "📊 Analisi Singola":
        if st.button("LANCIA ANALISI", type="primary", use_container_width=True):
            res = run_simulation(df_raw, capitale, rr, comm, slip, asset)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Bilancio Finale", f"{round(res['balance'], 2)} €", delta=f"{round(res['balance']-capitale, 2)} €")
            c2.metric("Win Rate", f"{round(res['wins']/(res['wins']+res['losses'])*100, 1)}%" if (res['wins']+res['losses'])>0 else "0%")
            c3.metric("Trade Totali", res['wins']+res['losses'])
            
            # Fix Grafico
            st.subheader("Equity Curve")
            st.line_chart(res['equity'])
            
    else: # Mappa di Calore
        st.write("Ottimizzazione AI sulle combinazioni di Medie Mobili (EMA 2-6 vs 10-30)")
        if st.button("GENERA MAPPA DI CALORE", type="primary", use_container_width=True):
            grid = []
            fast_range = range(2, 8, 2)
            slow_range = range(10, 32, 2)
            
            progress = st.progress(0)
            steps = len(fast_range) * len(slow_range)
            curr = 0
            
            for f in fast_range:
                row = []
                for s in slow_range:
                    r = run_simulation(df_raw, capitale, rr, comm, slip, asset, f, s)
                    row.append(round(r['balance'] - capitale, 2))
                    curr += 1
                    progress.progress(curr/steps)
                grid.append(row)
            
            heatmap_df = pd.DataFrame(grid, index=[f"EMA {f}" for f in fast_range], columns=[f"EMA {s}" for s in slow_range])
            st.subheader("Risultati Ottimizzazione (€)")
            st.dataframe(heatmap_df.style.background_gradient(cmap='RdYlGn'))
else:
    st.info("In attesa del file CSV per procedere...")
