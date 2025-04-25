import ssl
import streamlit as st
import certifi
import urllib.request
import pandas as pd
import pandas_ta as ta
import requests
from io import StringIO
from datetime import datetime, timedelta

# ---------------------- CONFIG ----------------------
API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzQ3OTAxNjU5LCJ0b2tlbkNvbnN1bWVyVHlwZSI6IlNFTEYiLCJ3ZWJob29rVXJsIjoiIiwiZGhhbkNsaWVudElkIjoiMTEwNDEwODg5MyJ9.Bg1TsNnNTRd6znWPQNgcBB4OAW8I0zjQmwjDcs-o2k3dJJlvGDPnmVgYFb82ID1sur6wN7lNtSh-tnH1L6dGyg"  # Replace with your Dhan access token
API_URL = "https://api.dhan.co/v2/charts/intraday"

# List of instruments with mock securityIds (replace with actuals)
instruments = {
    "NSE_NIFTY-I": {"Id": "1", "segment": "NSE_FNO","instrumentID":"FUTIDX", "timeframe": 75, "expiry": "2025-04-24"},
    "NSE_NIFTYBANK-I": {"Id": "2", "segment": "NSE_FNO","instrumentID":"FUTIDX", "timeframe": 75, "expiry": "2025-04-24"},
    "MCX_GOLDM-I": {"Id": "3", "segment": "MCX_COMM","instrumentID":"FUTCOM", "timeframe": 60, "expiry": "2025-05-05"},
    "MCX_SILVERM-I": {"Id": "4", "segment": "MCX_COMM","instrumentID":"FUTCOM", "timeframe": 60, "expiry": "2025-04-30"},
}

# ---------------------- FUNCTIONS ----------------------
def get_security_id(instrument):
    ssl_context = ssl.create_default_context(cafile=certifi.where())

# Step 2: Download the file manually
    url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, context=context) as response:
        csv_data = response.read().decode("utf-8")

# Step 3: Load into DataFrame
    scrip_master = pd.read_csv(StringIO(csv_data))
    if(instrument["Id"] == "1"):
        securityid = scrip_master[
            (scrip_master["INSTRUMENT"] == "FUTIDX") &
            (scrip_master["UNDERLYING_SYMBOL"]=="NIFTY") &
            (scrip_master["EXCH_ID"] == "NSE")
            ].copy()
    elif(instrument["Id"] == "2"): 
        securityid = scrip_master[
            (scrip_master["INSTRUMENT"] == "FUTIDX") &
            (scrip_master["UNDERLYING_SYMBOL"]=="BANKNIFTY") &
            (scrip_master["EXCH_ID"] == "NSE")
            ].copy()   
    elif(instrument["Id"] == "3"): 
        securityid = scrip_master[
            (scrip_master["INSTRUMENT"] == "FUTCOM") &
            (scrip_master["UNDERLYING_SYMBOL"]=="GOLDM") &
            (scrip_master["EXCH_ID"] == "MCX")
            ].copy()   
    else:
        securityid = scrip_master[
            (scrip_master["INSTRUMENT"] == "FUTCOM") &
            (scrip_master["UNDERLYING_SYMBOL"]=="SILVERM") &
            (scrip_master["EXCH_ID"] == "MCX")
            ].copy()   

    securityid["SM_EXPIRY_DATE"] = pd.to_datetime(securityid["SM_EXPIRY_DATE"], errors="coerce")
    securityid = securityid.sort_values("SM_EXPIRY_DATE")

# Get the latest expiry
    latest_securityid = securityid["SECURITY_ID"].iloc[0]
    
    return latest_securityid

def is_mcx_tender_period(instrument):
    expiry = datetime.strptime(instrument["expiry"], "%Y-%m-%d")
    tender_start = expiry - timedelta(days=3)
    return datetime.now().date() >= tender_start.date() and instrument["segment"] == "MCX_COMM"

def fetch_data(instrument):
    today = datetime.today()
    from_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    securityid=get_security_id(instrument)
    if(instrument["segment"] == "MCX_COMM"):
        payload = {
            "securityId": str(securityid),
            "exchangeSegment": instrument["segment"],
            "instrument": instrument["instrumentID"],
            "interval": 60,
            "fromDate": from_date,
            "toDate": to_date
        }
    else:
         payload = {
            "securityId": str(securityid),
            "exchangeSegment": instrument["segment"],
            "instrument": instrument["instrumentID"],
            "interval": 1,
            "fromDate": from_date,
            "toDate": to_date
        }

    headers = {
        "access-token": API_TOKEN,
        "Content-Type": "application/json",
	"Accept": "application/json"

    }

    res = requests.post(API_URL, json=payload, headers=headers)
    if res.status_code != 200:
        st.error(f"Failed to fetch data: {res.status_code} - {res.text}")
        return pd.DataFrame()

    data = res.json()
    if not data:
        st.warning("No data returned.")
        return pd.DataFrame()
        
    if(instrument["segment"] != "MCX_COMM"):
        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s', errors='coerce')
        df.set_index("timestamp", inplace=True)
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert("Asia/Kolkata")
        df = df.between_time("09:15", "15:30") 
        return df.resample("75min").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()

    else:

        df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s', errors='coerce')

        # Drop rows with bad or missing timestamps
        df.dropna(subset=["timestamp"], inplace=True)
        df.set_index("timestamp", inplace=True)
        df.index = df.index.tz_localize("UTC")
        df.index = df.index.tz_convert("Asia/Kolkata")
        df = df.between_time("10.00", "23.00") 
        return df

def apply_indicators(df):
    st_indicator = ta.supertrend(df["high"], df["low"], df["close"], length=10, multiplier=2)
    df["supertrend"] = st_indicator["SUPERT_10_2.0"]

    adx = ta.adx(df["high"], df["low"], df["close"])
    df["di_plus"] = adx["DMP_14"]
    df["di_minus"] = adx["DMN_14"]
    df["adx"] = adx["ADX_14"]

    return df

def generate_signals(df):
    df["long_entry"] = (df["close"] > df["supertrend"]) & (df["di_plus"] > df["di_minus"])
    df["short_entry"] = (df["close"] < df["supertrend"]) & (df["di_minus"] > df["di_plus"])
    df["signal"] = None

    current_pos = None

    for i in range(len(df)):
        if current_pos != "long" and df["long_entry"].iloc[i]:
            df.at[df.index[i], "signal"] = "BUY"
            current_pos = "long"
        elif current_pos != "short" and df["short_entry"].iloc[i]:
            df.at[df.index[i], "signal"] = "SELL"
            current_pos = "short"
        else:
            df.at[df.index[i], "signal"] = None

    return df

# ---------------------- STREAMLIT UI ----------------------

st.title("📈 Futures Supertrend(10,2)-ADX")

instrument_name = st.selectbox("Select Instrument", list(instruments.keys()))
instrument = instruments[instrument_name]

if is_mcx_tender_period(instrument):
    st.warning("🚫 MCX trade skipped due to tender period (3 days before expiry).")
else:
    df = fetch_data(instrument)

    if not df.empty:
        df = apply_indicators(df)
        df = generate_signals(df)

        st.subheader("📊 Signals Table")
        st.dataframe(df[["close", "supertrend", "di_plus", "di_minus", "signal"]].tail(2000))

        st.subheader("📉 Price vs Supertrend")
        st.line_chart(df[["close", "supertrend"]])

        st.subheader("📍 Last Signal")
        latest_signal = df["signal"].dropna().iloc[-1] if not df["signal"].dropna().empty else "No signal"
        st.success(f"🔔 Last Signal: {latest_signal}")
