import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- MOTORE QUANTITATIVO ---

def run_backtest(df, capitale, rr, comm, slip, asset, fast=2, slow=20):
    balance = capitale
    equity = [capitale]
    peak = capitale
    max_dd = 0.0
    gross_wins = 0.0
    gross_losses = 0.0

    pos_type = None
    pos_sl = 0.0
    pos_tp = 0.0
    pos_risk = 0.0
    pos_comm = 0.0
    pos_slip = 0.0
    wins, losses = 0, 0

    if "XAUUSD" in asset:
        STOP_PIPS, VALORE_PUNTO, point, SOGLIA_ATR, RISCHIO = 50, 100.0, 0.01, 1.5, 0.001
    else:
        VALORE_PUNTO, point, SOGLIA_ATR, RISCHIO = 1000.0, 0.001, 0, 0.005

    df = df.copy()
    df['ema_fast'] = df['close'].ewm(span=fast, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=slow, adjust=False).mean()
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(window=14).mean()

    asia_h, asia_l, session_done = 0.0, 9999.0, False

    for i in range(20, len(df)):
        # 1. Chiusura posizioni
        if pos_type is not None:
            if pos_type == 'buy':
                if df['low'].iloc[i] <= pos_sl:
                    loss = pos_risk + pos_comm + pos_slip
                    balance -= loss
                    gross_losses += loss
                    pos_type = None
                    losses += 1
                elif df['high'].iloc[i] >= pos_tp:
                    gain = pos_risk * rr - pos_comm - pos_slip
                    balance += gain
                    gross_wins += gain
                    pos_type = None
                    wins += 1
            elif pos_type == 'sell':
                if df['high'].iloc[i] >= pos_sl:
                    loss = pos_risk + pos_comm + pos_slip
                    balance -= loss
                    gross_losses += loss
                    pos_type = None
                    losses += 1
                elif df['low'].iloc[i] <= pos_tp:
                    gain = pos_risk * rr - pos_comm - pos_slip
                    balance += gain
                    gross_wins += gain
                    pos_type = None
                    wins += 1

        # Aggiorna equity e drawdown ad ogni candela
        equity.append(balance)
        peak = max(peak, balance)
        drawdown = (peak - balance) / peak * 100 if peak > 0 else 0
        max_dd = max(max_dd, drawdown)

        # 2. Apertura posizioni
        if pos_type is None:
            if "XAUUSD" in asset:
                if df['atr'].iloc[i - 1] >= SOGLIA_ATR:
                    sl_dist = STOP_PIPS * 10 * point
                    risk_amt = balance * RISCHIO
                    lotti = max(0.01, round(risk_amt / (sl_dist * VALORE_PUNTO), 2))
                    c_slip = slip * point * VALORE_PUNTO * lotti
                    if (df['ema_fast'].iloc[i - 1] > df['ema_slow'].iloc[i - 1] and
                            df['ema_fast'].iloc[i - 2] <= df['ema_slow'].iloc[i - 2]):
                        pos_type = 'buy'
                        pos_sl = df['open'].iloc[i] - sl_dist
                        pos_tp = df['open'].iloc[i] + sl_dist * rr
                        pos_risk, pos_comm, pos_slip = risk_amt, lotti * comm, c_slip
                    elif (df['ema_fast'].iloc[i - 1] < df['ema_slow'].iloc[i - 1] and
                          df['ema_fast'].iloc[i - 2] >= df['ema_slow'].iloc[i - 2]):
                        pos_type = 'sell'
                        pos_sl = df['open'].iloc[i] + sl_dist
                        pos_tp = df['open'].iloc[i] - sl_dist * rr
                        pos_risk, pos_comm, pos_slip = risk_amt, lotti * comm, c_slip
            else:
                orario = str(df['time'].iloc[i])[:5]
                if orario == '00:00':
                    asia_h, asia_l, session_done = 0.0, 9999.0, False
                if '00:00' <= orario < '08:00':
                    asia_h = max(asia_h, df['high'].iloc[i])
                    asia_l = min(asia_l, df['low'].iloc[i])
                if orario >= '08:00' and not session_done and asia_h > 0:
                    sl_range = asia_h - asia_l
                    risk_amt = balance * RISCHIO
                    lotti = max(0.01, round(risk_amt / (sl_range * VALORE_PUNTO), 2)) if sl_range > 0 else 0.01
                    c_slip = slip * point * VALORE_PUNTO * lotti
                    if df['high'].iloc[i] > asia_h:
                        pos_type = 'buy'
                        pos_sl = asia_l
                        pos_tp = asia_h + sl_range * rr
                        pos_risk, pos_comm, pos_slip = risk_amt, lotti * comm, c_slip
                        session_done = True
                    elif df['low'].iloc[i] < asia_l:
                        pos_type = 'sell'
                        pos_sl = asia_h
                        pos_tp = asia_l - sl_range * rr
                        pos_risk, pos_comm, pos_slip = risk_amt, lotti * comm, c_slip
                        session_done = True

    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else float('inf')

    return {
        "balance": balance,
        "equity": equity,
        "wins": wins,
        "losses": losses,
        "max_drawdown": round(max_dd, 2),
        "profit_factor": profit_factor,
        "gross_wins": round(gross_wins, 2),
        "gross_losses": round(gross_losses, 2),
    }


# --- INTERFACCIA ---

st.set_page_config(page_title="ProQuant SaaS", layout="wide", page_icon="🏦")

with st.sidebar:
    st.title("🏦 ProQuant Lab")
    st.divider()
    asset = st.selectbox("Seleziona Asset", ["XAUUSD (Oro)", "USDJPY (Yen)"])
    capitale = st.number_input("Capitale Iniziale (€)", value=1000)
    rr = st.slider("Reward/Risk Ratio", 1.0, 15.0, 10.0 if "XAU" in asset else 3.0)
    slip = st.number_input("Slippage Simulato (Punti)", value=30)
    comm = st.number_input("Commissione/Lotto (€)", value=7.0)
    st.divider()
    st.caption("v3.0 - Walk-Forward + Metriche Complete")

st.title("🛡️ Piattaforma di Validazione Quantitativa")

uploaded_file = st.file_uploader("Trascina qui lo storico CSV di MetaTrader 5", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file, sep='\t')
    df_raw.columns = [str(col).replace('<', '').replace('>', '').lower().strip() for col in df_raw.columns]

    tab1, tab2, tab3 = st.tabs(["📊 Analisi Singola", "🔲 Grid Search EMA", "🔬 Walk-Forward Validation"])

    # --- TAB 1: Analisi Singola ---
    with tab1:
        if st.button("ESEGUI BACKTEST", type="primary", use_container_width=True):
            with st.spinner("Calcolo in corso..."):
                res = run_backtest(df_raw, capitale, rr, comm, slip, asset)

            profit = res['balance'] - capitale
            total_t = res['wins'] + res['losses']
            wr = (res['wins'] / total_t * 100) if total_t > 0 else 0

            # Metriche complete: 6 colonne
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Profitto Netto", f"{round(profit, 2)} €", delta=f"{round(profit, 2)} €")
            m2.metric("Saldo Finale", f"{round(res['balance'], 2)} €")
            m3.metric("Win Rate", f"{round(wr, 1)} %")
            m4.metric("Trade Totali", total_t)
            m5.metric(
                "Max Drawdown",
                f"{res['max_drawdown']} %",
                delta=f"-{res['max_drawdown']} %",
                delta_color="inverse"
            )
            pf = res['profit_factor']
            m6.metric(
                "Profit Factor",
                f"{pf}" if pf != float('inf') else "∞",
                delta="buono" if pf >= 1.5 else "basso",
                delta_color="normal" if pf >= 1.5 else "inverse"
            )

            # Interpretazione automatica
            st.divider()
            if pf >= 1.5 and res['max_drawdown'] < 20:
                st.success("✅ Strategia robusta: Profit Factor solido e drawdown contenuto.")
            elif pf >= 1.0 and res['max_drawdown'] < 30:
                st.warning("⚠️ Strategia marginale: profittevole ma con margini stretti. Ottimizza i parametri.")
            else:
                st.error("❌ Strategia debole: profit factor basso o drawdown eccessivo. Non operare live.")

            # Equity Curve
            st.subheader("Equity Curve")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=res['equity'],
                mode='lines',
                name='Equity',
                line=dict(color='#2ecc71', width=2),
                fill='tozeroy',
                fillcolor='rgba(46,204,113,0.08)'
            ))
            fig.update_layout(
                xaxis_title='Candele',
                yaxis_title='Saldo (€)',
                template="plotly_dark",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)

    # --- TAB 2: Grid Search ---
    with tab2:
        st.subheader("Grid Search — Ottimizzazione Parametri EMA")
        st.write("Testa 25 combinazioni di EMA per identificare le configurazioni più robuste.")
        st.caption("⚠️ Nota: questo test usa l'intero dataset. Per una validazione corretta usa il Walk-Forward.")

        if st.button("AVVIA GRID SEARCH", use_container_width=True):
            fast_r = [2, 4, 6, 8, 10]
            slow_r = [10, 15, 20, 25, 30]
            grid_profit = []
            grid_pf = []

            bar = st.progress(0)
            total_steps = len(fast_r) * len(slow_r)
            step = 0

            for f in fast_r:
                row_profit = []
                row_pf = []
                for s in slow_r:
                    r = run_backtest(df_raw, capitale, rr, comm, slip, asset, f, s)
                    row_profit.append(round(r['balance'] - capitale, 2))
                    row_pf.append(r['profit_factor'] if r['profit_factor'] != float('inf') else 99.0)
                    step += 1
                    bar.progress(step / total_steps)
                grid_profit.append(row_profit)
                grid_pf.append(row_pf)

            col1, col2 = st.columns(2)
            with col1:
                st.write("**Profitto Netto (€)**")
                df_profit = pd.DataFrame(
                    grid_profit,
                    index=[f"EMA Fast {f}" for f in fast_r],
                    columns=[f"EMA Slow {s}" for s in slow_r]
                )
                st.dataframe(df_profit.style.background_gradient(cmap='RdYlGn'), use_container_width=True)

            with col2:
                st.write("**Profit Factor**")
                df_pf = pd.DataFrame(
                    grid_pf,
                    index=[f"EMA Fast {f}" for f in fast_r],
                    columns=[f"EMA Slow {s}" for s in slow_r]
                )
                st.dataframe(df_pf.style.background_gradient(cmap='RdYlGn'), use_container_width=True)

    # --- TAB 3: Walk-Forward ---
    with tab3:
        st.subheader("Walk-Forward Validation")
        st.write(
            "Ottimizza i parametri su dati passati (training), poi valida su dati futuri mai visti (test). "
            "Questo è il vero test di robustezza: se la strategia funziona solo sul training, è overfittata."
        )

        split = st.slider("% dati usati per il training", 50, 80, 70,
                          help="Il restante % viene usato come test out-of-sample")
        split_idx = int(len(df_raw) * split / 100)

        col_info1, col_info2 = st.columns(2)
        col_info1.info(f"📚 Training: {split_idx} candele ({split}%)")
        col_info2.info(f"🔬 Test: {len(df_raw) - split_idx} candele ({100 - split}%)")

        if st.button("ESEGUI WALK-FORWARD", type="primary", use_container_width=True):
            df_train = df_raw.iloc[:split_idx].copy()
            df_test = df_raw.iloc[split_idx:].copy()

            # Ottimizzazione su training
            best_profit = -float('inf')
            best_params = (2, 20)
            best_pf = 0.0

            fast_r = [2, 4, 6, 8, 10]
            slow_r = [10, 15, 20, 25, 30]

            bar = st.progress(0)
            total = len(fast_r) * len(slow_r)
            step = 0

            with st.spinner("Ottimizzazione su dati di training..."):
                for f in fast_r:
                    for s in slow_r:
                        r = run_backtest(df_train, capitale, rr, comm, slip, asset, f, s)
                        p = r['balance'] - capitale
                        if p > best_profit:
                            best_profit = p
                            best_params = (f, s)
                            best_pf = r['profit_factor']
                        step += 1
                        bar.progress(step / total)

            # Validazione su test
            with st.spinner("Validazione su dati out-of-sample..."):
                res_test = run_backtest(df_test, capitale, rr, comm, slip, asset, *best_params)
                test_profit = res_test['balance'] - capitale

            st.divider()
            st.markdown(f"### Parametri ottimali trovati: EMA Fast **{best_params[0]}** / EMA Slow **{best_params[1]}**")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Profitto Training", f"{round(best_profit, 2)} €")
            c2.metric("Profit Factor Training", f"{best_pf if best_pf != float('inf') else '∞'}")
            c3.metric(
                "Profitto Test (out-of-sample)",
                f"{round(test_profit, 2)} €",
                delta=f"{round(test_profit, 2)} €"
            )
            c4.metric("Max Drawdown Test", f"{res_test['max_drawdown']} %")

            st.divider()

            # Verdetto
            if test_profit > 0 and res_test['profit_factor'] >= 1.2:
                st.success(
                    f"✅ Strategia ROBUSTA: profittevole anche su {100 - split}% di dati mai visti. "
                    f"Profit Factor out-of-sample: {res_test['profit_factor']}"
                )
            elif test_profit > 0:
                st.warning(
                    "⚠️ Strategia MARGINALE: profittevole in test ma con Profit Factor basso. "
                    "Procedi con cautela e position sizing conservativo."
                )
            else:
                st.error(
                    "❌ OVERFITTING RILEVATO: la strategia è profittevole in training ma perdente in test. "
                    "Non operare live con questi parametri."
                )

            # Equity curve test
            st.subheader("Equity Curve — Periodo di Test (out-of-sample)")
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(
                y=res_test['equity'],
                mode='lines',
                name='Equity Test',
                line=dict(color='#3498db', width=2),
                fill='tozeroy',
                fillcolor='rgba(52,152,219,0.08)'
            ))
            fig2.update_layout(
                xaxis_title='Candele',
                yaxis_title='Saldo (€)',
                template="plotly_dark",
                height=350
            )
            st.plotly_chart(fig2, use_container_width=True)

else:
    st.info("⚠️ Carica un file CSV esportato da MetaTrader 5 per sbloccare le funzionalità di analisi.")
