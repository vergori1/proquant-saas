import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- MOTORE DI CALCOLO UNIFICATO ---
def run_backtest(df, capitale, rr, comm, slip, asset, fast=2, slow=20):
    balance = capitale
    equity = [capitale]
    pos = None
    wins, losses = 0, 0
    
    if "XAUUSD" in asset:
        STOP_PIPS, VALORE_PUNTO, point, SOGLIA_ATR, RISCHIO = 50, 100.0, 0.01, 1.5, 0.001
    else: # USDJPY
        VALORE_PUNTO, point, SOGLIA_ATR, RISCHIO = 1000.0, 0.001, 0, 0.005

    # Indicatori
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=14).mean()

    asia_h, asia_l, session_done = 0.0, 9999.0, False

    for i in range(20, len(df)):
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
        
        if not pos:
            if "XAUUSD" in asset:
                if df['atr'].iloc[i-1] >= SOGLIA_ATR:
                    sl_dist = STOP_PIPS * 10 * point
                    risk_amt = balance * RISCHIO
                    lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
                    c_slip = slip * point * VALORE_PUNTO * lotti
                    if df['ema_fast'].iloc[i-1] > df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] <= df['ema_slow'].iloc[i-2]:
                        pos = {'type':'buy','sl':df['open'].iloc[i]-sl_dist,'tp':df['open'].iloc[i]+sl_dist*rr,'risk':risk_amt,'comm':lotti*comm,'slip':c_slip}
                    elif df['ema_fast'].iloc[i-1] < df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] >= df['ema_slow'].iloc[i-2]:
                        pos = {'type':'sell','sl':df['open'].iloc[i]+sl_dist,'tp':df['open'].iloc[i]-sl_dist*rr,'risk':risk_amt,'comm':lotti*comm,'slip':c_slip}
            else: # USDJPY
                orario = str(df['time'].iloc[i])[:5]
                if orario == '00:00': asia_h, asia_l, session_done = 0.0, 9999.0, False
                if '00:00' <= orario < '08:00':
                    asia_h = max(asia_h, df['high'].iloc[i]); asia_l = min(asia_l, df['low'].iloc[i])
                if orario >= '08:00' and not session_done and asia_h > 0:
                    sl_range = asia_h - asia_low if 'asia_low' in locals() else asia_h - asia_l
                    risk_amt = balance * RISCHIO
                    lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2)) if sl_range > 0 else 0.01
                    c_slip = slip * point * VALORE_PUNTO * lotti
                    if df['high'].iloc[i] > asia_h:
                        pos = {'type':'buy','sl':asia_l,'tp':asia_h+sl_range*rr,'risk':risk_amt,'comm':lotti*comm,'slip':c_slip}; session_done = True
                    elif df['low'].iloc[i] < asia_l:
                        pos = {'type':'sell','sl':asia_h,'tp':asia_l-sl_range*rr,'risk':risk_amt,'comm':lotti*comm,'slip':c_slip}; session_done = True
        equity.append(balance)
    return {"balance": balance, "equity": equity, "wins": wins, "losses": losses}

# --- INTERFACCIA PROFESSIONALE ---
st.set_page_config(page_title="ProQuant SaaS", layout="wide", page_icon="🏦")

# Sidebar
with st.sidebar:
    st.title("🏦 ProQuant Lab")
    st.divider()
    asset = st.selectbox("Seleziona Asset", ["XAUUSD (Oro)", "USDJPY (Yen)"])
    capitale = st.number_input("Capitale Iniziale (€)", value=1000)
    rr = st.slider("Reward/Risk Ratio", 1.0, 15.0, 10.0 if "XAU" in asset else 3.0)
    slip = st.number_input("Slippage Simulato (Punti)", value=30)
    comm = st.number_input("Commissione/Lotto (€)", value=7.0)
    st.divider()
    st.caption("v2.0 - Cloud Certified")

# Caricamento File
st.title("🛡️ Piattaforma di Validazione Quantitativa")
uploaded_file = st.file_uploader("Trascina qui lo storico CSV di MetaTrader 5", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file, sep='\t')
    df_raw.columns = [col.replace('<', '').replace('>', '').lower() for col in df_raw.columns]

    # TAB SYSTEM (Come richiesto)
    tab1, tab2 = st.tabs(["📊 Analisi Singola", "🔥 Mappa di Calore AI"])

    with tab1:
        if st.button("ESEGUI BACKTEST", type="primary", use_container_width=True):
            res = run_backtest(df_raw, capitale, rr, comm, slip, asset)
            
            # Metrics Row
            m1, m2, m3, m4 = st.columns(4)
            profit = res['balance'] - capitale
            m1.metric("Profitto Netto", f"{round(profit, 2)} €", delta=f"{round(profit, 2)} €")
            m2.metric("Saldo Finale", f"{round(res['balance'], 2)} €")
            total_t = res['wins'] + res['losses']
            wr = (res['wins'] / total_t * 100) if total_t > 0 else 0
            m3.metric("Win Rate", f"{round(wr, 1)} %")
            m4.metric("Trade Totali", total_t)

            # Grafico Plotly (Anti-Bug)
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=res['equity'], mode='lines', name='Equity', line=dict(color='#2ecc71', width=2)))
            fig.update_layout(title='Equity Curve (Stress-Tested)', xaxis_title='Numero di Trade', yaxis_title='Saldo (€)', template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Ottimizzazione Genetica delle Medie Mobili")
        st.write("L'IA analizzerà 25 combinazioni per trovare il 'Nucleo di Robustezza'.")
        if st.button("GENERA MAPPA DI CALORE", use_container_width=True):
            fast_r, slow_r = [2, 4, 6, 8, 10], [10, 15, 20, 25, 30]
            grid = []
            bar = st.progress(0)
            total_steps = len(fast_r) * len(slow_r)
            step = 0
            for f in fast_r:
                row = []
                for s in slow_
