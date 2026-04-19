import streamlit as st
import pandas as pd
import numpy as np

# --- LOGICA DI CALCOLO (MOTORI) ---
def calculate_xauusd(df, capitale, rr, commissione, slippage_punti):
    RISCHIO_PERCENT = 0.1 / 100.0
    STOP_PIPS = 50  
    VALORE_PUNTO = 100.0
    point = 0.01
    sl_dist = STOP_PIPS * 10 * point
    costo_slip = slippage_punti * point * VALORE_PUNTO
    
    df['ema_fast'] = df['close'].ewm(span=2, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=20, adjust=False).mean()
    df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    balance = capitale
    equity = [capitale]
    pos = None
    wins, losses = 0, 0

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
        
        if not pos and df['atr'].iloc[i-1] >= 1.5:
            risk_amt = balance * RISCHIO_PERCENT
            lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
            if df['ema_fast'].iloc[i-1] > df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] <= df['ema_slow'].iloc[i-2]:
                pos = {'type': 'buy', 'sl': df['open'].iloc[i] - sl_dist, 'tp': df['open'].iloc[i] + sl_dist*rr, 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
            elif df['ema_fast'].iloc[i-1] < df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] >= df['ema_slow'].iloc[i-2]:
                pos = {'type': 'sell', 'sl': df['open'].iloc[i] + sl_dist, 'tp': df['open'].iloc[i] - sl_dist*rr, 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
        equity.append(balance)
    return {"balance": balance, "equity": equity, "wins": wins, "losses": losses}

def calculate_usdjpy(df, capitale, rr, commissione, slippage_punti):
    RISCHIO_PERCENT = 0.5 / 100.0
    VALORE_PUNTO = 1000.0
    point = 0.001
    costo_slip = slippage_punti * point * VALORE_PUNTO
    balance = capitale
    equity = [capitale]
    pos = None
    asia_high, asia_low = 0.0, 9999.0
    session_calculated = False
    wins, losses = 0, 0

    for i in range(1, len(df)):
        orario = str(df['time'].iloc[i])[:5]
        if orario == '00:00': asia_high, asia_low = 0.0, 9999.0; session_calculated = False
        if '00:00' <= orario < '08:00':
            if df['high'].iloc[i] > asia_high: asia_high = df['high'].iloc[i]
            if df['low'].iloc[i] < asia_low: asia_low = df['low'].iloc[i]
        if orario >= '08:00' and not session_calculated and asia_high > 0:
            sl_range = asia_high - asia_low
            if df['high'].iloc[i] > asia_high:
                risk_amt = balance * RISCHIO_PERCENT
                lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2))
                pos = {'type': 'buy', 'sl': asia_low, 'tp': asia_high + (sl_range * rr), 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
                session_calculated = True
            elif df['low'].iloc[i] < asia_low:
                risk_amt = balance * RISCHIO_PERCENT
                lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2))
                pos = {'type': 'sell', 'sl': asia_high, 'tp': asia_low - (sl_range * rr), 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
                session_calculated = True
        if pos:
            if pos['type'] == 'buy':
                if df['low'].iloc[i] <= pos['sl']: balance -= (pos['risk'] + pos['comm'] + pos['slip']); pos = None; losses += 1
                elif df['high'].iloc[i] >= pos['tp']: balance += (pos['risk'] * rr - pos['comm'] - pos['slip']); pos = None; wins += 1
            elif pos['type'] == 'sell':
                if df['high'].iloc[i] >= pos['sl']: balance -= (pos['risk'] + pos['comm'] + pos['slip']); pos = None; losses += 1
                elif df['low'].iloc[i] <= pos['tp']: balance += (pos['risk'] * rr - pos['comm'] - pos['slip']); pos = None; wins += 1
        equity.append(balance)
    return {"balance": balance, "equity": equity, "wins": wins, "losses": losses}

# --- INTERFACCIA STREAMLIT MIGLIORATA ---
st.set_page_config(page_title="ProQuant SaaS", layout="wide", page_icon="📈")

# Sidebar con design pulito
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2621/2621814.png", width=80)
    st.title("ProQuant Lab")
    st.divider()
    algo = st.radio("Seleziona Algoritmo", ["XAUUSD Sniper", "USDJPY Breakout"])
    st.divider()
    st.info("Configura i parametri del mercato reale per uno stress test accurato.")

# Main Layout
st.title(f"🚀 Dashboard Analisi: {algo}")

col_input1, col_input2 = st.columns([1, 1])
with col_input1:
    capitale = st.number_input("Capitale (€)", value=1000, step=100)
    rr = st.slider("Reward/Risk Ratio", 1.0, 15.0, 10.0 if "XAUUSD" in algo else 3.0)
with col_input2:
    slip = st.number_input("Slippage (Punti)", value=30)
    comm = st.number_input("Commissione/Lotto (€)", value=7.0)

uploaded_file = st.file_uploader("Carica file CSV da MetaTrader 5", type="csv")

# Il Bottone "Mancante" ora è centrale e visibile
st.divider()
btn_run = st.button("📊 AVVIA BACKTEST PROFESSIONALE", use_container_width=True, type="primary")

if uploaded_file and btn_run:
    df = pd.read_csv(uploaded_file, sep='\t')
    df.columns = [col.replace('<', '').replace('>', '').lower() for col in df.columns]
    
    with st.status("Elaborazione dati in corso...", expanded=True) as status:
        st.write("Analizzando le matrici temporali...")
        res = calculate_xauusd(df, capitale, rr, comm, slip) if "XAUUSD" in algo else calculate_usdjpy(df, capitale, rr, comm, slip)
        status.update(label="Analisi Completata!", state="complete", expanded=False)

    # Visualizzazione Risultati Professionali
    m1, m2, m3 = st.columns(3)
    profitto_netto = res['balance'] - capitale
    m1.metric("Profitto Netto", f"{round(profitto_netto, 2)} €", delta=f"{round(profitto_netto, 2)} €")
    m2.metric("Saldo Finale", f"{round(res['balance'], 2)} €")
    wr = (res['wins'] / (res['wins'] + res['losses']) * 100) if (res['wins'] + res['losses']) > 0 else 0
    m3.metric("Win Rate", f"{round(wr, 2)} %")

    st.subheader("Curva di Equity (Stress-Tested)")
    st.line_chart(res['equity'], use_container_width=True)
    
    with st.expander("Vedi Dettagli Operatività"):
        st.write(f"Trade Vincenti: {res['wins']}")
        st.write(f"Trade Perdenti: {res['losses']}")
        st.write(f"Slippage totale applicato: {slip} punti per trade")
else:
    st.warning("Carica un file CSV e clicca sul bottone per vedere i risultati.")
