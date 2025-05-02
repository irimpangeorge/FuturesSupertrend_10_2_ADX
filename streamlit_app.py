import ssl
import streamlit as st
import certifi
import urllib.request
import pandas as pd
import pandas_ta as ta
import requests
from io import StringIO
import json
import os
from datetime import datetime, timedelta

# ---------------------- CONFIG ----------------------
#API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzQ3OTAxNjU5LCJ0b2tlbkNvbnN1bWVyVHlwZSI6IlNFTEYiLCJ3ZWJob29rVXJsIjoiIiwiZGhhbkNsaWVudElkIjoiMTEwNDEwODg5MyJ9.Bg1TsNnNTRd6znWPQNgcBB4OAW8I0zjQmwjDcs-o2k3dJJlvGDPnmVgYFb82ID1sur6wN7lNtSh-tnH1L6dGyg"  # Replace with your Dhan access token
API_HISTORY_URL = "https://api.dhan.co/v2/charts/intraday"
API_CURR_POSITIONS = "https://api.dhan.co/v2/positions"


USERNAME = "admin"
PASSWORD = "password123"
SETTINGS_FILE = "settings.json"
SETTINGS_NIFTY_FILE = "nifty_settings.json"
SETTINGS_BNF_FILE = "bnf_settings.json"
SETTINGS_GOLDM_FILE = "goldm_settings.json"
SETTINGS_SILVERM_FILE = "silverm_settings.json"
# ---------------------- Sessions ----------------------
if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

# List of instruments with mock securityIds (replace with actuals)
instruments = {
    "NSE_NIFTY-I": {"Id": "1", "segment": "NSE_FNO","instrumentID":"FUTIDX", "timeframe": 75, "expiry": "2025-04-24"},
    "NSE_NIFTYBANK-I": {"Id": "2", "segment": "NSE_FNO","instrumentID":"FUTIDX", "timeframe": 75, "expiry": "2025-04-24"},
    "MCX_GOLDM-I": {"Id": "3", "segment": "MCX_COMM","instrumentID":"FUTCOM", "timeframe": 60, "expiry": "2025-05-05"},
    "MCX_SILVERM-I": {"Id": "4", "segment": "MCX_COMM","instrumentID":"FUTCOM", "timeframe": 60, "expiry": "2025-04-30"},
}

# ---------------------- FUNCTIONS ----------------------
def login():
    password_holder = st.empty()

    with password_holder.container():
        st.title("🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if username == USERNAME and password == PASSWORD:
                st.session_state["logged_in"] = True
                st.success("Login successful!")
                st.query_params["auth"] = "1"
                password_holder.empty()
                st.rerun()
                st.stop()
            else:
                st.error("Invalid username or password")

def fetch_and_displaydata(instrument, atrperiod, multiplier, timeframe, quantity, dhan_api):
    if is_mcx_tender_period(instrument):
        st.warning("🚫 MCX trade skipped due to tender period (3 days before expiry).")
    else:
        df = fetch_data(instrument, timeframe, dhan_api)

        if not df.empty:
            df = apply_indicators(df, atrperiod, multiplier )
            df = generate_signals(df)

            st.subheader("📊 Signals Table")
            st.dataframe(df[["close", "supertrend", "di_plus", "di_minus", "entry", "exit"]].tail(2000))

            st.subheader("📍 Last Signal")
            latest_signal = df["entry"].dropna().iloc[-1] if not df["entry"].dropna().empty else "No signal"
            st.success(f"🔔 Last Signal: {latest_signal}")
        return

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
    latest_expirydate = securityid["SM_EXPIRY_DATE"].iloc[0]
    
    return latest_securityid, latest_expirydate

def is_mcx_tender_period(instrument):
    securityid, expirydate = get_security_id(instrument)
    ts = pd.Timestamp(expirydate)
    expiry = ts.date() #datetime.strptime(expirydate, "%Y-%m-%d")
    tender_start = expiry - timedelta(days=3)
    return datetime.now().date() >= tender_start and instrument["segment"] == "MCX_COMM"

def fetch_data(instrument, timeframe, dhan_api):
    today = datetime.today()
    from_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    if dhan_api=="api token" or not dhan_api:
        st.warning("Enter a valid api token and try again")
        return pd.DataFrame()
        
    securityid, expirydate = get_security_id(instrument)
    payload = {
            "securityId": str(securityid),
            "exchangeSegment": instrument["segment"],
            "instrument": instrument["instrumentID"],
            "interval": 1,
            "fromDate": from_date,
            "toDate": to_date
            }

    headers = {
        "access-token": dhan_api,
        "Content-Type": "application/json",
	"Accept": "application/json"

    }

    res = requests.post(API_HISTORY_URL, json=payload, headers=headers)
    if res.status_code != 200:
        st.error(f"Failed to fetch data: {res.status_code} - {res.text}")
        return pd.DataFrame()

    data = res.json()
    if not data:
        st.warning("No data returned.")
        return pd.DataFrame()
        
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='s', errors='coerce')
    df.set_index("timestamp", inplace=True)
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("Asia/Kolkata")
    if(instrument["segment"] != "MCX_COMM"):
        df = df.between_time("09:15", "15:30") 
    else:
        df = df.between_time("10.00", "23.00") 

    resample_timeframe = f"{timeframe}min"
    return df.resample(resample_timeframe).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()

def fetch_current_orders(dhan_api,instrument):
    st.subheader("📦 Current Orders")
    headers = {
        "access-token": dhan_api,
	"Accept": "application/json"
    }

    res = requests.get(API_CURR_POSITIONS, headers=headers)

    if res.status_code != 200:
        st.error(f"Failed to fetch data: {res.status_code} - {res.text}")
        return pd.DataFrame()

    data = res.json()
    if not data:
        st.warning("No data returned.")
        return pd.DataFrame()
    
    df = pd.DataFrame(data, columns=["tradingSymbol", "positionType", "exchangeSegment", "productType"])
    fut_df = df[df["tradingSymbol"].str.contains("FUT", na=False)]
    fut_df = fut_df[fut_df["productType"].str.contains("MARGIN", na=False)]
    if(instrument["Id"] == "1"):
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("NIFTY", na=False)] & ~df["tradingSymbol"].str.contains("BANKNIFTY", na=False)
    elif(instrument["Id"] == "2"): 
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("BANKNIFTY", na=False)]
    elif(instrument["Id"] == "3"): 
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("GOLDM", na=False)]
    else:
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("SILVERM", na=False)]
    st.dataframe(fut_df[["tradingSymbol", "positionType", "exchangeSegment", "productType"]].tail(2000))

def apply_indicators(df, atr_period, multipliers):
    st_indicator = ta.supertrend(df["high"], df["low"], df["close"], length = atr_period, multiplier = multipliers)
    trend = f"SUPERT_{atr_period}_{float(multipliers)}"
    df["supertrend"] = st_indicator[trend]

    adx = ta.adx(df["high"], df["low"], df["close"])
    df["di_plus"] = adx["DMP_14"]
    df["di_minus"] = adx["DMN_14"]
    df["adx"] = adx["ADX_14"]

    return df

def display_supertrend():

    col1, col2, col3 = st.columns([6, 1, 1]) 
    with col3:
        if st.button("Logout"):
            st.query_params["auth"] = "0"
            st.session_state.logged_in = False
            st.rerun()

    st.title("📈 Futures Supertrend(10,2)-ADX")

    instrument_name = st.selectbox("Select Instrument", list(instruments.keys()))
    instrument = instruments[instrument_name]

    instrument_settings = load_instrument_settings(instrument)
    common_settings = load_common_settings()

    st.sidebar.header("Parameters")

    dhan_api_token = st.sidebar.text_input("Api Token", value = common_settings.get("dhan_api_token",""))
    dhan_client_id = st.sidebar.text_input("Client ID", value = common_settings.get("dhan_client_id",""))
    nf_atr_period = st.sidebar.number_input("ATR Period", min_value = 0, max_value = None, value = int(instrument_settings["atr_period"]), step = 1)
    nf_multiplier = st.sidebar.number_input("Multiplier", min_value = 0, max_value = None, value = int(instrument_settings["multiplier"]), step = 1)
    nf_timeframe = st.sidebar.number_input("Time Frame", min_value = 0, max_value = None, value = int(instrument_settings["time_frame"]), step = 1)
    nf_quantity = st.sidebar.number_input("Quantity", min_value = 0, max_value = None, value = int(instrument_settings["quantity"]), step = 1)

    sidecol1, sidecol2 = st.sidebar.columns([1, 1]) 
    with sidecol1:
        if st.button("💾 Save"):
            instrument_settings = {
                "atr_period": nf_atr_period,
                "multiplier": nf_multiplier,
                "time_frame": nf_timeframe,
                "quantity": nf_quantity
                }
            common_settings = {
                "dhan_client_id": dhan_client_id,
                "dhan_api_token": dhan_api_token
            }
            save_settings(instrument_settings, common_settings, instrument)
            st.success("✅ Settings saved permanently!")
            st.rerun()  # Optional: to reflect updated values immediately
    
    with sidecol2:
        st.button("Roll Over")

    st.query_params["auth"] = "1"
    fetch_and_displaydata(instrument,nf_atr_period,nf_multiplier,nf_timeframe,nf_multiplier,dhan_api_token)
    fetch_current_orders(dhan_api_token, instrument)

def generate_signals(df):
    df["long_entry"] = (df["close"] > df["supertrend"]) & (df["di_plus"] > df["di_minus"])
    df["long_exit"] = (df["close"] < df["supertrend"])
    df["short_entry"] = (df["close"] < df["supertrend"]) & (df["di_plus"] > df["di_minus"])
    df["short_exit"] = (df["close"] > df["supertrend"])
    df["entry"] = None
    df["exit"] = None

    current_pos = None

    for i in range(len(df)):
        df.at[df.index[i], "exit"] = None
        df.at[df.index[i], "entry"] = None
        if current_pos == "short" and df["short_exit"].iloc[i]:
            df.at[df.index[i], "exit"] = "COVER"
            df.at[df.index[i], "entry"] = "None"
            current_pos = None
        if current_pos == "long" and df["long_exit"].iloc[i]:
            df.at[df.index[i], "exit"] = "SELL"
            df.at[df.index[i], "entry"] = "None"
            current_pos = None
        if current_pos == None and df["long_entry"].iloc[i]:
            df.at[df.index[i], "entry"] = "BUY"
            current_pos = "long"
        if current_pos == None and df["short_entry"].iloc[i]:
            df.at[df.index[i], "entry"] = "SHORT"
            current_pos = "short"
    return df

def main():
    if st.query_params.get("auth") == "1":
        st.session_state.logged_in = True

    if st.session_state.logged_in:
        display_supertrend()
    else:
        login()

def load_instrument_settings(instrument):
    if(instrument["Id"] == "1"):
        settingsfile = SETTINGS_NIFTY_FILE
    elif(instrument["Id"] == "2"): 
        settingsfile = SETTINGS_BNF_FILE
    elif(instrument["Id"] == "3"): 
        settingsfile = SETTINGS_GOLDM_FILE
    else:
        settingsfile = SETTINGS_SILVERM_FILE

    if os.path.exists(settingsfile):
        with open(settingsfile, "r") as f:
            return json.load(f)
    else:
        # Default settings
        return {
         "atr_period":10,
         "multiplier":2,
         "time_frame":5,
         "quantity":750
        }

def load_common_settings():
        
    settingsfile = SETTINGS_FILE

    if os.path.exists(settingsfile):
        with open(settingsfile, "r") as f:
            return json.load(f)
    else:
        # Default settings
        return {
         "dhan_api_token": "api token",
        }
    
def save_settings(instru_settings, common_settings, instrument):
    if(instrument["Id"] == "1"):
        settingsfile = SETTINGS_NIFTY_FILE
    elif(instrument["Id"] == "2"): 
        settingsfile = SETTINGS_BNF_FILE
    elif(instrument["Id"] == "3"): 
        settingsfile = SETTINGS_GOLDM_FILE
    else:
        settingsfile = SETTINGS_SILVERM_FILE

    with open(settingsfile, "w") as f:
        json.dump(instru_settings, f, indent=2)
    
    settingsfile = SETTINGS_FILE
    with open(settingsfile, "w") as f:
        json.dump(common_settings, f, indent=2)
# ---------------------- STREAMLIT UI ----------------------

if __name__ == "__main__":
    main()
   











