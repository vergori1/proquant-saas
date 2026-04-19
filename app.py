import streamlit as st
import pandas as pd
import numpy as np


# --- MOTORE QUANTITATIVO (Il Cervello) ---
def calculate_xauusd(df, capitale, rr, commissione, slippage_punti):
    RISCHIO_PERCENT = 0.1 / 100.0
    STOP_PIPS = 50  # Lo stop loss strutturale validato
    VALORE_PUNTO = 100.0
    point = 0.01
    sl_dist = STOP_PIPS * 10 * point
    costo_slip = slippage_punti * point * VALORE_PUNTO

    # Calcolo Medie
    df['ema_fast'] = df['close'].ewm(span=2, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=20, adjust=False).mean()

    # Calcolo ATR (Pacemaker)
    df['tr'] = np.maximum(df['high'] - df['low'],
                          np.maximum(abs(df['high'] - df['close'].shift(1)),
                                     abs(df['low'] - df['close'].shift(1))))
    df['atr'] = df['tr'].rolling(window=14).mean()

    balance = capitale
    equity = [capitale]
    pos = None
    SOGLIA_ATR = 1.5

    for i in range(20, len(df)):
        if pos:
            if pos['type'] == 'buy':
                if df['low'].iloc[i] <= pos['sl']:
                    balance -= (pos['risk'] + pos['comm'] + pos['slip'])
                    pos = None
                elif df['high'].iloc[i] >= pos['tp']:
                    balance += (pos['risk'] * rr - pos['comm'] - pos['slip'])
                    pos = None
            elif pos['type'] == 'sell':
                if df['high'].iloc[i] >= pos['sl']:
                    balance -= (pos['risk'] + pos['comm'] + pos['slip'])
                    pos = None
                elif df['low'].iloc[i] <= pos['tp']:
                    balance += (pos['risk'] * rr - pos['comm'] - pos['slip'])
                    pos = None
            equity.append(balance)
        else:
            equity.append(balance)

        if not pos and df['atr'].iloc[i - 1] >= SOGLIA_ATR:
            risk_amt = balance * RISCHIO_PERCENT
            lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
            if df['ema_fast'].iloc[i - 1] > df['ema_slow'].iloc[i - 1] and df['ema_fast'].iloc[i - 2] <= \
                    df['ema_slow'].iloc[i - 2]:
                pos = {'type': 'buy', 'sl': df['open'].iloc[i] - sl_dist, 'tp': df['open'].iloc[i] + sl_dist * rr,
                       'risk': risk_amt, 'comm': lotti * commissione, 'slip': lotti * costo_slip}
            elif df['ema_fast'].iloc[i - 1] < df['ema_slow'].iloc[i - 1] and df['ema_fast'].iloc[i - 2] >= \
                    df['ema_slow'].iloc[i - 2]:
                pos = {'type': 'sell', 'sl': df['open'].iloc[i] + sl_dist, 'tp': df['open'].iloc[i] - sl_dist * rr,
                       'risk': risk_amt, 'comm': lotti * commissione, 'slip': lotti * costo_slip}

    return {"balance": balance, "equity": equity}


# --- INTERFACCIA GRAFICA (La Vetrina) ---
st.set_page_config(page_title="ProQuant SaaS", layout="wide")
st.title("☁️ ProQuant Strategy Analyzer (Cloud Version)")
st.markdown("Piattaforma Istituzionale per validazione Algo-Trading")

uploaded_file = st.file_uploader("Carica lo storico CSV (es. XAUUSD M15)", type="csv")

col1, col2 = st.columns(2)
with col1:
    capitale = st.number_input("Capitale Iniziale (€)", value=1000)
    rr = st.slider("Reward/Risk Ratio", 1.0, 15.0, 10.0)
with col2:
    slip = st.number_input("Slippage Simulato (Punti)", value=30)
    comm = st.number_input("Commissione per Lotto (€)", value=7.0)

if uploaded_file and st.button("Avvia Analisi Quantitativa"):
    # Leggiamo il file CSV
    # Sep='\t' gestisce il formato di esportazione di MetaTrader
    df = pd.read_csv(uploaded_file, sep='\t')
    df.columns = [col.replace('<', '').replace('>', '').lower() for col in df.columns]

    with st.spinner("Calcolo delle matrici in corso..."):
        res = calculate_xauusd(df, capitale, rr, comm, slip)

    st.success(f"📈 Profitto Netto Finale: {round(res['balance'] - capitale, 2)} €")
    st.metric(label="Saldo Conto", value=f"{round(res['balance'], 2)} €")
    st.line_chart(res['equity'])