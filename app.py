import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ==============================================================
# --- MOTORE QUANTITATIVO (Completamente Dinamico) ---
# ==============================================================

def run_backtest(df, asset, config):
    # Parametri Comuni
    capitale = config.get("capitale", 1000)
    comm = config.get("comm", 7.0)
    slip = config.get("slip", 30)

    balance = capitale
    equity = [capitale]
    peak = capitale
    max_dd = 0.0
    gross_wins, gross_losses = 0.0, 0.0
    wins, losses = 0, 0

    df = df.copy()

    # --------------------------------------------------------------
    # 1. LOGICA XAUUSD (EMA Cross + Filtro ATR)
    # --------------------------------------------------------------
    if "XAUUSD" in asset:
        fast = config.get("ema_fast", 2)
        slow = config.get("ema_slow", 20)
        rr = config.get("rr", 6.0)
        soglia_atr = config.get("atr_thresh", 1.5)
        stop_pips = config.get("stop_pips", 50)
        rischio_pct = config.get("risk_pct", 0.1) / 100.0

        VALORE_PUNTO, point = 100.0, 0.01
        pos_type, pos_sl, pos_tp = None, 0.0, 0.0
        pos_risk, pos_comm, pos_slip = 0.0, 0.0, 0.0

        df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
        df['tr'] = np.maximum(df['high'] - df['low'], np.maximum(abs(df['high'] - df['close'].shift(1)), abs(df['low'] - df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(window=14).mean()

        for i in range(20, len(df)):
            # Chiusura
            if pos_type is not None:
                if pos_type == 'buy':
                    if df['low'].iloc[i] <= pos_sl:
                        loss = pos_risk + pos_comm + pos_slip
                        balance -= loss; gross_losses += loss; pos_type = None; losses += 1
                    elif df['high'].iloc[i] >= pos_tp:
                        gain = pos_risk * rr - pos_comm - pos_slip
                        balance += gain; gross_wins += gain; pos_type = None; wins += 1
                elif pos_type == 'sell':
                    if df['high'].iloc[i] >= pos_sl:
                        loss = pos_risk + pos_comm + pos_slip
                        balance -= loss; gross_losses += loss; pos_type = None; losses += 1
                    elif df['low'].iloc[i] <= pos_tp:
                        gain = pos_risk * rr - pos_comm - pos_slip
                        balance += gain; gross_wins += gain; pos_type = None; wins += 1

            equity.append(balance)
            peak = max(peak, balance)
            drawdown = (peak - balance) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

            # Apertura
            if pos_type is None and df['atr'].iloc[i - 1] >= soglia_atr:
                sl_dist = stop_pips * 10 * point
                risk_amt = balance * rischio_pct
                lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
                c_slip = slip * point * VALORE_PUNTO * lotti
                
                if df['ema_fast'].iloc[i - 1] > df['ema_slow'].iloc[i - 1] and df['ema_fast'].iloc[i - 2] <= df['ema_slow'].iloc[i - 2]:
                    pos_type, pos_sl, pos_tp = 'buy', df['open'].iloc[i] - sl_dist, df['open'].iloc[i] + sl_dist * rr
                    pos_risk, pos_comm, pos_slip = risk_amt, lotti * comm, c_slip
                elif df['ema_fast'].iloc[i - 1] < df['ema_slow'].iloc[i - 1] and df['ema_fast'].iloc[i - 2] >= df['ema_slow'].iloc[i - 2]:
                    pos_type, pos_sl, pos_tp = 'sell', df['open'].iloc[i] + sl_dist, df['open'].iloc[i] - sl_dist * rr
                    pos_risk, pos_comm, pos_slip = risk_amt, lotti * comm, c_slip

    # --------------------------------------------------------------
    # 2. LOGICA USDJPY (Breakout Asiatico MQL5 Clone)
    # --------------------------------------------------------------
    else:
        start_h = config.get("start_h", 3)
        end_h = config.get("end_h", 6)
        exit_h = config.get("exit_h", 18)
        sl_ratio = config.get("sl_ratio", 0.2)
        rischio_pct = config.get("risk_pct", 0.4) / 100.0

        VALORE_PUNTO, point = 1000.0, 0.001
        
        pos_type, pos_entry, pos_sl = None, 0.0, 0.0
        pos_comm, pos_slip, pos_lots = 0.0, 0.0, 0.0
        
        asia_h, asia_l = 0.0, 9999.0
        session_done = False
        current_day = -1

        for i in range(20, len(df)):
            # Utilizziamo la colonna time_dt corretta creata in fase di lettura
            cur_dt = df['time_dt'].iloc[i]
            h, dow, month = cur_dt.hour, cur_dt.dayofweek, cur_dt.month

            if cur_dt.day != current_day:
                asia_h, asia_l = 0.0, 9999.0
                session_done = False
                current_day = cur_dt.day

            # Chiusura
            if pos_type is not None:
                if h >= exit_h: 
                    exit_price = df['open'].iloc[i]
                    pips_made = (exit_price - pos_entry)/point if pos_type == 'buy' else (pos_entry - exit_price)/point
                    gain = (pips_made * point * VALORE_PUNTO * pos_lots) - pos_comm - pos_slip
                    balance += gain
                    if gain > 0: gross_wins += gain; wins += 1
                    else: gross_losses += abs(gain); losses += 1
                    pos_type = None
                else: 
                    if pos_type == 'buy' and df['low'].iloc[i] <= pos_sl:
                        pips_made = (pos_sl - pos_entry) / point
                        gain = (pips_made * point * VALORE_PUNTO * pos_lots) - pos_comm - pos_slip
                        balance += gain; gross_losses += abs(gain); losses += 1
                        pos_type = None
                    elif pos_type == 'sell' and df['high'].iloc[i] >= pos_sl:
                        pips_made = (pos_entry - pos_sl) / point
                        gain = (pips_made * point * VALORE_PUNTO * pos_lots) - pos_comm - pos_slip
                        balance += gain; gross_losses += abs(gain); losses += 1
                        pos_type = None

            equity.append(balance)
            peak = max(peak, balance)
            drawdown = (peak - balance) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

            # Calcolo Range Asiatico
            if start_h <= h < end_h:
                asia_h = max(asia_h, df['high'].iloc[i])
                asia_l = min(asia_l, df['low'].iloc[i])

            # Apertura Breakout (esatta replica logica MQL5)
            if pos_type is None and end_h <= h < exit_h and not session_done:
                # Python dow: 2=Mer, 3=Gio, 4=Ven
                if month in [3, 5, 6, 7, 8, 9, 10, 11, 12] and dow in [2, 3, 4]:
                    if asia_h > 0 and asia_l < 9999.0:
                        range_hl = asia_h - asia_l

                        if df['high'].iloc[i] >= asia_h:
                            pos_type = 'buy'
                            pos_entry = max(df['open'].iloc[i], asia_h)
                            pos_sl = asia_l + (range_hl * sl_ratio) 
                            sl_dist = (pos_entry - pos_sl) / point
                            risk_amt = balance * rischio_pct 
                            pos_lots = max(0.01, round(risk_amt / (sl_dist * point * VALORE_PUNTO), 2)) if sl_dist > 0 else 0.01
                            pos_comm, pos_slip = pos_lots * comm, slip * point * VALORE_PUNTO * pos_lots
                            session_done = True
                            
                        elif df['low'].iloc[i] <= asia_l:
                            pos_type = 'sell'
                            pos_entry = min(df['open'].iloc[i], asia_l)
                            pos_sl = asia_h - (range_hl * sl_ratio) 
                            sl_dist = (pos_sl - pos_entry) / point
                            risk_amt = balance * rischio_pct 
                            pos_lots = max(0.01, round(risk_amt / (sl_dist * point * VALORE_PUNTO), 2)) if sl_dist > 0 else 0.01
                            pos_comm, pos_slip = pos_lots * comm, slip * point * VALORE_PUNTO * pos_lots
                            session_done = True

    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else float('inf')

    return {
        "balance": balance, "equity": equity, "wins": wins, "losses": losses,
        "max_drawdown": round(max_dd, 2), "profit_factor": profit_factor,
        "gross_wins": round(gross_wins, 2), "gross_losses": round(gross_losses, 2)
    }

# ==============================================================
# --- INTERFACCIA VETRINA (Streamlit) ---
# ==============================================================

st.set_page_config(page_title="ProQuant SaaS", layout="wide", page_icon="🏦")

# Costruzione Configurazione Dinamica
config = {}

with st.sidebar:
    st.title("🏦 ProQuant Lab")
    asset = st.selectbox("Seleziona Asset", ["XAUUSD (Oro)", "USDJPY (Yen)"])
    
    st.divider()
    st.subheader("⚙️ Setup Globale")
    config["capitale"] = st.number_input("Capitale Iniziale (€)", value=1000)
    config["slip"] = st.number_input("Slippage (Punti)", value=30)
    config["comm"] = st.number_input("Commissione/Lotto (€)", value=7.0)
    st.divider()

    if "XAUUSD" in asset:
        st.subheader("🎯 Calibrazione Oro")
        config["rr"] = st.slider("Reward/Risk Ratio", 1.0, 15.0, 10.0)
        config["ema_fast"] = st.number_input("EMA Veloce", value=2)
        config["ema_slow"] = st.number_input("EMA Lenta", value=20)
        config["atr_thresh"] = st.number_input("Soglia ATR (Volatilità)", value=1.5, step=0.1)
        config["stop_pips"] = st.number_input("Stop Loss (Pips)", value=50)
        config["risk_pct"] = st.number_input("Rischio per Trade (%)", value=0.1, step=0.1)
    else:
        st.subheader("⛩️ Calibrazione Yen")
        config["start_h"] = st.number_input("Ora Inizio Range", value=3, min_value=0, max_value=23)
        config["end_h"] = st.number_input("Ora Fine Range", value=6, min_value=0, max_value=23)
        config["exit_h"] = st.number_input("Ora Chiusura Forzata", value=18, min_value=0, max_value=23)
        config["sl_ratio"] = st.slider("SL Ratio (Restringimento Box)", 0.0, 1.0, 0.2, step=0.05)
        config["risk_pct"] = st.number_input("Rischio per Trade (%)", value=0.4, step=0.1)

    st.caption("v5.1 - Date Parser Fix + Dynamic Injection")

# Corpo Centrale
st.title("🛡️ Piattaforma di Validazione Quantitativa")
uploaded_file = st.file_uploader("Trascina qui lo storico CSV di MetaTrader 5", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file, sep='\t')
    df_raw.columns = [str(col).replace('<', '').replace('>', '').lower().strip() for col in df_raw.columns]

    # SOLUZIONE AL BUG DEL PARSER DATE/TIME
    if 'date' in df_raw.columns and 'time' in df_raw.columns:
        df_raw['time_dt'] = pd.to_datetime(df_raw['date'] + ' ' + df_raw['time'])
    elif 'time' in df_raw.columns:
        df_raw['time_dt'] = pd.to_datetime(df_raw['time'])
    else:
        st.error("Formato data/ora non riconosciuto. Assicurati che il CSV esportato da MT5 abbia le colonne DATE e TIME.")
        st.stop()

    tab1, tab2 = st.tabs(["📊 Analisi Singola", "🔬 Avanzate (Presto Disponibili)"])

    with tab1:
        if st.button("ESEGUI BACKTEST", type="primary", use_container_width=True):
            with st.spinner("Calcolo in corso..."):
                res = run_backtest(df_raw, asset, config)

            profit = res['balance'] - config["capitale"]
            total_t = res['wins'] + res['losses']
            wr = (res['wins'] / total_t * 100) if total_t > 0 else 0

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Profitto Netto", f"{round(profit, 2)} €", delta=f"{round(profit, 2)} €")
            m2.metric("Saldo Finale", f"{round(res['balance'], 2)} €")
            m3.metric("Win Rate", f"{round(wr, 1)} %")
            m4.metric("Trade Totali", total_t)
            m5.metric("Max Drawdown", f"{res['max_drawdown']} %", delta=f"-{res['max_drawdown']} %", delta_color="inverse")
            
            pf = res['profit_factor']
            m6.metric("Profit Factor", f"{pf}" if pf != float('inf') else "∞", delta="buono" if pf >= 1.5 else "basso", delta_color="normal" if pf >= 1.5 else "inverse")

            fig = go.Figure()
            fig.add_trace(go.Scatter(y=res['equity'], mode='lines', name='Equity', line=dict(color='#2ecc71', width=2), fill='tozeroy', fillcolor='rgba(46,204,113,0.08)'))
            fig.update_layout(xaxis_title='Candele', yaxis_title='Saldo (€)', template="plotly_dark", height=400)
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("⚠️ Carica un file CSV esportato da MetaTrader 5 per sbloccare le funzionalità di analisi.")
