import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import os
import json
import requests

# ---------------- SETTINGS ----------------
st.set_page_config(layout="centered")
st.title("📉 Dip Alert AI")

PORTFOLIO_FILE = "portfolio.json"

# ---------------- TELEGRAM ----------------
TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# ---------------- UI STYLE ----------------
st.markdown("""
<style>
.grid {display:grid;grid-template-columns:1fr 1fr;gap:15px;}
.card {background:#111827;padding:18px;border-radius:16px;box-shadow:0 4px 12px rgba(0,0,0,0.4);}
.card-title {font-size:16px;font-weight:600;margin-bottom:10px;}
.signal-badge {text-align:center;font-size:26px;font-weight:bold;animation:pulse 1.5s infinite;}
@keyframes pulse {0%{opacity:1;}50%{opacity:0.6;}100%{opacity:1;}}
.green{color:#22c55e;} .red{color:#ef4444;} .orange{color:#f59e0b;}
.bar{height:10px;border-radius:5px;}
</style>
""", unsafe_allow_html=True)

# ---------------- HELPERS ----------------

def clean_close(df):
    return df['Close'].iloc[:,0] if isinstance(df.columns,pd.MultiIndex) else df['Close']

def calculate_rsi(series,period=14):
    delta=series.diff()
    gain=delta.clip(lower=0)
    loss=-delta.clip(upper=0)
    rs=gain.rolling(period).mean()/loss.rolling(period).mean()
    return 100-(100/(1+rs))

def get_data(ticker,period="6mo"):
    return yf.download(ticker,period=period,interval="1d",auto_adjust=True)

def get_weekly_rsi(close):
    return calculate_rsi(close.resample('W').last()).iloc[-1]

def check_new_low(close):
    last3=close.tail(3)
    return last3.iloc[-1]<=last3.min()

def vix_trend(v):
    if len(v)<3: return "unknown"
    return "rising" if v.iloc[-1]>v.iloc[-2]>v.iloc[-3] else "stabilizing"

# ---------------- DATA ----------------

nifty=get_data("^NSEI")
vix_df=get_data("^INDIAVIX")

close=clean_close(nifty)
vix_close=clean_close(vix_df)

rsi=get_weekly_rsi(close)
vix=float(vix_close.dropna().iloc[-1])
new_low=check_new_low(close)
vix_state=vix_trend(vix_close)

# ---------------- SIGNAL ----------------

if rsi<40 and vix>25:
    signal="STRONG DIP ZONE" if not new_low else "WATCH"
else:
    signal="NO SIGNAL"

color="red" if signal=="STRONG DIP ZONE" else "orange" if signal=="WATCH" else "green"
msg="Accumulate gradually" if signal=="STRONG DIP ZONE" else "Wait" if signal=="WATCH" else "Normal"

score=5 if signal=="STRONG DIP ZONE" else 3

# 🔔 TELEGRAM ALERT
if signal=="STRONG DIP ZONE":
    send_telegram(f"🚨 STRONG DIP ALERT\nRSI:{rsi:.2f} VIX:{vix:.2f}")

# ---------------- SIGNAL CARD ----------------

st.markdown(f"""
<div class="card">
<div class="card-title">Market Status</div>
<div class="signal-badge {color}">{signal}</div>
<p style="text-align:center;">{msg}</p>
</div>
""",unsafe_allow_html=True)

# ---------------- GRID ----------------

st.markdown('<div class="grid">',unsafe_allow_html=True)

st.markdown(f"""
<div class="card">
<div class="card-title">Market Data</div>
<p>RSI: {rsi:.2f}</p>
<p>VIX: {vix:.2f}</p>
<p>Trend: {vix_state}</p>
</div>
""",unsafe_allow_html=True)

alloc="High (60–70%)" if score>=4 else "Moderate (~40%)"

st.markdown(f"""
<div class="card">
<div class="card-title">Action</div>
<p>{msg}</p>
<hr>
<p><b>Allocation:</b> {alloc}</p>
</div>
""",unsafe_allow_html=True)

st.markdown('</div>',unsafe_allow_html=True)

# ---------------- CAPITAL ALLOCATION ----------------

st.markdown('<div class="card"><div class="card-title">💰 Capital Allocation</div>', unsafe_allow_html=True)

total_capital = st.number_input("Total Capital (₹)", value=100000.0)

alloc_pct = 0.7 if score>=4 else 0.4
deploy_amount = total_capital * alloc_pct

st.write(f"Deploy: ₹{deploy_amount:,.0f}")

# ---------------- RISK CONTROL ----------------

st.markdown("### ⚠️ Risk Control")

risk_pct = st.slider("Risk per Trade (%)", 1, 10, 2)
risk_amount = total_capital * (risk_pct / 100)

st.write(f"Max Risk per Trade: ₹{risk_amount:,.0f}")

# ---------------- STOCKS + RANKING ----------------

stocks={
"HDFC Bank":"HDFCBANK.NS",
"Reliance":"RELIANCE.NS",
"TCS":"TCS.NS",
"Infosys":"INFY.NS",
"ICICI Bank":"ICICIBANK.NS"
}

ranking=[]
for name,ticker in stocks.items():
    df=get_data(ticker)
    c=clean_close(df)

    wrsi=get_weekly_rsi(c)
    nl=check_new_low(c)

    score_s=0
    if wrsi<40: score_s+=1
    if wrsi<35: score_s+=1
    if not nl: score_s+=1
    if vix>25: score_s+=1

    ranking.append((name,score_s))

ranking.sort(key=lambda x:x[1],reverse=True)

# ---------------- SMART ALLOCATION ----------------

st.markdown("### 📊 Suggested Allocation")

total_score=sum([s for _,s in ranking if s>0])

if total_score>0:
    for name,s in ranking:
        if s>0:
            weight=s/total_score
            max_per_stock = risk_amount * 5
            amount=min(deploy_amount*weight,max_per_stock)

            st.write(f"{name} → ₹{amount:,.0f}")

# ---------------- QUANTITY CALCULATOR ----------------

st.markdown("### 🧮 Quantity Calculator")

for name,s in ranking:
    if s>0:
        ticker=stocks[name]
        df=get_data(ticker,"5d")
        price=float(clean_close(df).iloc[-1])

        weight=s/total_score if total_score>0 else 0
        max_per_stock = risk_amount * 5
        amount=min(deploy_amount*weight,max_per_stock)

        qty=int(amount//price)

        st.write(f"{name}")
        st.write(f"Price: ₹{price:.0f} | Invest: ₹{amount:,.0f} → Qty: {qty}")
        st.markdown("---")

st.markdown('</div>',unsafe_allow_html=True)

# ---------------- BACKTEST ----------------

st.markdown('<div class="card"><div class="card-title">📊 Strategy Backtest</div>', unsafe_allow_html=True)

def backtest_strategy(close_series, vix_series):
    results=[]
    for i in range(30,len(close_series)-5):
        try:
            rsi_val=calculate_rsi(close_series[:i]).iloc[-1]
            vix_val=vix_series.iloc[min(i,len(vix_series)-1)]
            if rsi_val<40 and vix_val>25:
                entry=close_series.iloc[i]
                exit_price=close_series.iloc[i+5]
                results.append((exit_price-entry)/entry*100)
        except:
            continue
    return results

bt=backtest_strategy(close,vix_close)

if bt:
    st.write(f"Avg Return: {np.mean(bt):.2f}%")
    st.write(f"Win Rate: {sum(r>0 for r in bt)/len(bt)*100:.1f}%")
    st.write(f"Signals: {len(bt)}")

st.markdown('</div>',unsafe_allow_html=True)

# ---------------- PORTFOLIO ----------------

def load_p():
    return json.load(open(PORTFOLIO_FILE)) if os.path.exists(PORTFOLIO_FILE) else []

def save_p(p): json.dump(p,open(PORTFOLIO_FILE,"w"))

portfolio=load_p()

st.markdown('<div class="card"><div class="card-title">Portfolio</div>',unsafe_allow_html=True)

name=st.selectbox("Stock",list(stocks.keys()))
qty=st.number_input("Qty",min_value=1)
price_input=st.number_input("Buy Price")

if st.button("Add"):
    portfolio.append({"name":name,"ticker":stocks[name],"qty":qty,"buy_price":price_input})
    save_p(portfolio)

for p in portfolio:
    df=get_data(p["ticker"],"5d")
    cp=float(clean_close(df).iloc[-1])
    pnl=(p["qty"]*cp)-(p["qty"]*p["buy_price"])
    st.write(f"{p['name']} → ₹{pnl:.0f}")

st.markdown('</div>',unsafe_allow_html=True)