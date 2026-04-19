import streamlit as st
import pandas as pd
import numpy as np

# --- MOTORE 1: XAUUSD (EMA + ATR Sniper) ---
def calculate_xauusd(df, capitale, rr, commissione, slippage_punti):
    RISCHIO_PERCENT = 0.1 / 100.0
    STOP_PIPS = 50  
    VALORE_PUNTO = 100.0
    point = 0.01
    sl_dist = STOP_PIPS * 10 * point
    costo_slip = slippage_punti * point * VALORE_PUNTO
    
    df['ema_fast'] = df['close'].ewm(span=2, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=20, adjust=False).mean()
    
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

        if not pos and df['atr'].iloc[i-1] >= SOGLIA_ATR:
            risk_amt = balance * RISCHIO_PERCENT
            lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
            if df['ema_fast'].iloc[i-1] > df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] <= df['ema_slow'].iloc[i-2]:
                pos = {'type': 'buy', 'sl': df['open'].iloc[i] - sl_dist, 'tp': df['open'].iloc[i] + sl_dist*rr, 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
            elif df['ema_fast'].iloc[i-1] < df['ema_slow'].iloc[i-1] and df['ema_fast'].iloc[i-2] >= df['ema_slow'].iloc[i-2]:
                pos = {'type': 'sell', 'sl': df['open'].iloc[i] + sl_dist, 'tp': df['open'].iloc[i] - sl_dist*rr, 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}

    return {"balance": balance, "equity": equity}

# --- MOTORE 2: USDJPY (Asian Breakout) ---
def calculate_usdjpy(df, capitale, rr, commissione, slippage_punti):
    RISCHIO_PERCENT = 0.5 / 100.0  # Rischio leggermente maggiore sulle valute
    VALORE_PUNTO = 1000.0
    point = 0.001
    costo_slip = slippage_punti * point * VALORE_PUNTO
    
    balance = capitale
    equity = [capitale]
    pos = None
    
    asia_high = 0.0
    asia_low = 9999.0
    session_calculated = False

    for i in range(1, len(df)):
        # Estrai l'orario dalla colonna 'time' (formato HH:MM:SS)
        orario = str(df['time'].iloc[i])[:5] 
        
        # Reset a mezzanotte
        if orario == '00:00':
            asia_high = 0.0
            asia_low = 9999.0
            session_calculated = False
            
        # Calcolo Range Asiatico
        if '00:00' <= orario < '08:00':
            if df['high'].iloc[i] > asia_high: asia_high = df['high'].iloc[i]
            if df['low'].iloc[i] < asia_low: asia_low = df['low'].iloc[i]
            
        # Breakout Trading (Dopo le 08:00)
        if orario >= '08:00' and not session_calculated and asia_high > 0:
            sl_range = asia_high - asia_low
            
            if df['high'].iloc[i] > asia_high and not pos:
                risk_amt = balance * RISCHIO_PERCENT
                lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2)) if sl_range > 0 else 0.01
                pos = {'type': 'buy', 'sl': asia_low, 'tp': asia_high + (sl_range * rr), 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
                session_calculated = True
                
            elif df['low'].iloc[i] < asia_low and not pos:
                risk_amt = balance * RISCHIO_PERCENT
                lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2)) if sl_range > 0 else 0.01
                pos = {'type': 'sell', 'sl': asia_high, 'tp': asia_low - (sl_range * rr), 'risk': risk_amt, 'comm': lotti*commissione, 'slip': lotti*costo_slip}
                session_calculated = True

        # Gestione Uscite
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

    return {"balance": balance, "equity": equity}

# --- INTERFACCIA GRAFICA E SIDEBAR ---
st.set_page_config(page_title="ProQuant SaaS", layout="wide")

# Sidebar
st.sidebar.title("⚙️ Pannello di Controllo")
st.sidebar.markdown("Seleziona l'algoritmo da analizzare:")
algoritmo = st.sidebar.radio("Strategia Attiva:", ("XAUUSD (Oro) - EMA Sniper", "USDJPY (Yen) - Asian Breakout"))

st.sidebar.markdown("---")
st.sidebar.info("Carica il file CSV corretto esportato da MetaTrader 5 in base all'algoritmo selezionato.")

# Main Page
st.title("☁️ ProQuant Strategy Analyzer")
st.markdown(f"**Algoritmo selezionato:** {algoritmo}")

uploaded_file = st.file_uploader("Carica lo storico CSV (M15 richiesto)", type="csv")

# Parametri dinamici basati sull'algoritmo
col1, col2 = st.columns(2)
with col1:
    capitale = st.number_input("Capitale Iniziale (€)", value=1000)
    # Lo Yen usa un RR di 3, l'Oro un RR di 10
    default_rr = 10.0 if "XAUUSD" in algoritmo else 3.0
    rr = st.slider("Reward/Risk Ratio", 1.0, 15.0, default_rr)
with col2:
    slip = st.number_input("Slippage Simulato (Punti)", value=30)
    comm = st.number_input("Commissione per Lotto (€)", value=7.0)

if uploaded_file and st.button("Avvia Analisi Quantitativa"):
    df = pd.read_csv(uploaded_file, sep='\t')
    df.columns = [col.replace('<', '').replace('>', '').lower() for col in df.columns]
    
    with st.spinner("Calcolo delle matrici in corso..."):
        if "XAUUSD" in algoritmo:
            res = calculate_xauusd(df, capitale, rr, comm, slip)
        else:
            res = calculate_usdjpy(df, capitale, rr, comm, slip)
    
    st.success(f"📈 Profitto Netto Finale: {round(res['balance'] - capitale, 2)} €")
    st.metric(label="Saldo Conto", value=f"{round(res['balance'], 2)} €")
    st.line_chart(res['equity'])
