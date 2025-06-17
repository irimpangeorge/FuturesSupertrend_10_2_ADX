import ssl
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import certifi
import urllib.request
import pandas as pd
import pandas_ta as ta
import requests
from io import StringIO
import json
import os
import time
import threading
from datetime import datetime, timedelta

# ---------------------- CONFIG ----------------------
API_TOKEN_TEMP = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzUwODQxMTA5LCJ0b2tlbkNvbnN1bWVyVHlwZSI6IlNFTEYiLCJ3ZWJob29rVXJsIjoiIiwiZGhhbkNsaWVudElkIjoiMTAwMDU4MjkxMiJ9.tVR7IUXhoG556v731fv-t4DXweJy6M-8T3ZgCbm1osyOzQY5Fm4-nW04KVCuPyRB5q66DQywMl6glroWkB7klQ"
CLIENT_ID_TEMP= "1000582912"
API_HISTORY_URL = "https://api.dhan.co/v2/charts/intraday"
API_CURR_POSITIONS = "https://api.dhan.co/v2/positions"
API_POST_ORDERS = "https://api.dhan.co/v2/orders"


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
    "NSE_NIFTY-I": {"Id": 1, "securityID": "0", "nextOrder": "", "segment": "NSE_FNO","instrumentID":"FUTIDX", "atr_period":10, "multiplier":2, "time_frame":5, "quantity":750, "expiry": "2025-04-24"},
    "NSE_NIFTYBANK-I": {"Id": 2, "securityID": "0", "nextOrder": "", "segment": "NSE_FNO","instrumentID":"FUTIDX", "atr_period":10, "multiplier":2, "time_frame":5, "quantity":750, "expiry": "2025-04-24"},
    "MCX_GOLDM-I": {"Id": 3, "securityID": "0", "nextOrder": "", "segment": "MCX_COMM","instrumentID":"FUTCOM", "atr_period":10, "multiplier":2, "time_frame":5, "quantity":750, "expiry": "2025-05-05"},
    "MCX_SILVERM-I": {"Id": 4, "securityID": "0", "nextOrder": "", "segment": "MCX_COMM","instrumentID":"FUTCOM", "atr_period":10, "multiplier":2, "time_frame":5, "quantity":750, "expiry": "2025-04-30"},
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

def get_last_signal(df, column):
   return df[column].tail(2000).dropna().iloc[-1] if not df[column].tail(2000).dropna().empty else "No signal"

def refresh_page():
    # Setup session state
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()

    # Check if 5 minutes (300s) have passed
    now = time.time()
    elapsed = now - st.session_state.last_refresh

    st.write(f"Elapsed time: {int(elapsed)} seconds")

    if elapsed >= 120:  # 5 minutes
        st.session_state.last_refresh = now
        st.experimental_rerun()

    
def place_all_orders(dhan_api):

    get_instrument_details()
    for instrument_key in instruments:

        instrument = instruments[instrument_key]

        if is_mcx_tender_period(instrument):
            st.warning("🚫 MCX trade skipped due to tender period (5 days before expiry).\nPlease use roll over option to place next order")
            continue
    
        if is_option_tender_period_expired(instrument):
            st.warning("🚫 Option trade skipped due to tender period.\nPlease use roll over option to place next order")
            continue

        df = fetch_data(instrument, instrument["time_frame"], dhan_api)

        if not df.empty:
            
            df = apply_indicators(df, instrument["atr_period"], instrument["multiplier"] )
            df = generate_signals(df)

            df = df[["close", "supertrend", "di_plus", "di_minus", "entry", "exit"]].tail(2000)

            currorder, next_contract, positionType = fetch_current_orders(dhan_api, instrument)

            latest_exit_signal = get_last_signal(df, "exit")
            latest_entry_signal = get_last_signal(df, "entry")
            if(positionType != latest_entry_signal): 
                place_orders(str(instrument["securityID"]), instrument["quantity"], latest_entry_signal, latest_exit_signal, currorder, str(instrument["segment"]))

    
def fetch_and_displaydata(instrument, atrperiod, multiplier, timeframe, quantity, dhan_api):
    
    df = fetch_data(instrument, timeframe, dhan_api)

    if not df.empty:
        df = apply_indicators(df, atrperiod, multiplier )
        df = generate_signals(df)

        st.subheader("📊 Signals Table")
        df = df[["close", "supertrend", "di_plus", "di_minus", "entry", "exit"]].tail(2000)
        styled_df  = df.style.apply(highlight_row, axis=1)
        st.dataframe(styled_df )

       
        st.subheader("📦 Current Orders")
        currorder, next_contract, positionType = fetch_current_orders(dhan_api, instrument)
        st.success(f"📝  Current contract: {currorder}")
        st.subheader("📍 Last Signal")
        latest_entry_signal = get_last_signal(df, "entry")
        st.success(f"🔔 Last Signal: {latest_entry_signal}")
        return currorder, next_contract

def get_instrument_details(count = 0):
    ssl_context = ssl.create_default_context(cafile=certifi.where())

# Step 2: Download the file manually
    url = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(url, context=context) as response:
        csv_data = response.read().decode("utf-8")

    for instrument_key in instruments:
        instrument = instruments[instrument_key]
    # Step 3: Load into DataFrame
        scrip_master = pd.read_csv(StringIO(csv_data))
        if(instrument["Id"] == 1):
            securityid = scrip_master[
                (scrip_master["INSTRUMENT"] == "FUTIDX") &
                (scrip_master["UNDERLYING_SYMBOL"]=="NIFTY") &
                (scrip_master["EXCH_ID"] == "NSE")
                ].copy()
        elif(instrument["Id"] == 2): 
            securityid = scrip_master[
                (scrip_master["INSTRUMENT"] == "FUTIDX") &
                (scrip_master["UNDERLYING_SYMBOL"]=="BANKNIFTY") &
                (scrip_master["EXCH_ID"] == "NSE")
                ].copy()   
        elif(instrument["Id"] == 3): 
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
        latest_securityid = securityid["SECURITY_ID"].iloc[count]
        latest_expirydate = securityid["SM_EXPIRY_DATE"].iloc[count]
        next_order = securityid["SYMBOL_NAME"].iloc[count]
        instrument["securityID"] = latest_securityid
        instrument["expiry"] = latest_expirydate
        instrument["nextOrder"] = next_order
    
    return 

def get_next_order(instrument, count=0):
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
    next_order = securityid["SYMBOL_NAME"].iloc[count]

    return next_order

def is_mcx_tender_period(instrument_key):

    ts = pd.Timestamp(instrument_key["expiry"])
    expiry = ts.date() #datetime.strptime(expirydate, "%Y-%m-%d")
    tender_start = expiry - timedelta(days=6)
    return datetime.now().date() >= tender_start and instrument_key["segment"] == "MCX_COMM"

def is_option_tender_period_expired(instrument_key): 

    ts = pd.Timestamp(instrument_key["expiry"])
    expiry = ts.date() #datetime.strptime(expirydate, "%Y-%m-%d")
    tender_start = expiry - timedelta(days = 0)
    return datetime.now().date() > tender_start and instrument_key["segment"] == "NSE_FNO"

def fetch_data(instrument, timeframe, dhan_api):
    today = datetime.today()
    from_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    if dhan_api=="api token" or not dhan_api:
        st.warning("Enter a valid api token and try again")
        return pd.DataFrame()
        
    payload = {
            "securityId": str(instrument["securityID"]),
            "exchangeSegment": str(instrument["segment"]),
            "instrument": str(instrument["instrumentID"]),
            "interval": str(1),
            "fromDate": str(from_date),
            "toDate": str(to_date)
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

def prevent_rerun(trigger_key="run_logic"):
    """Call this function to control rerun behavior."""
    if trigger_key not in st.session_state:
        st.session_state[trigger_key] = False

def place_orders(securityid, quantity, entrysignal, exitsignal, currentorder, segment):

    headers = {
        "access-token": API_TOKEN_TEMP,
        "Content-Type": "application/json",
	"Accept": "application/json"
    }

    if str(currentorder) != "No Contract":
        if exitsignal == "None":
            return
        elif exitsignal == "SELL":
            type = "SELL"
        else:
            type = "BUY"

        payload = {
                "dhanClientId": CLIENT_ID_TEMP,
                "transactionType": type,
                "exchangeSegment": segment,
                "productType": "MARGIN",
                "orderType": "MARKET",
                "validity": "DAY",
                "securityId": str(securityid),
                "quantity": quantity,
                "afterMarketOrder": "false",
            }
        res = requests.post(API_POST_ORDERS, json = payload, headers = headers)

    if entrysignal == "None":
        return
    elif entrysignal == "BUY":
         type = "BUY"
    else:
        type = "SELL"

    payload = {
                "dhanClientId": CLIENT_ID_TEMP,
                "transactionType": type,
                "exchangeSegment": segment,
                "productType": "MARGIN",
                "orderType": "MARKET",
                "validity": "DAY",
                "securityId": str(securityid),
                "quantity": quantity,
                "afterMarketOrder": "false",
            }
    res = requests.post(API_POST_ORDERS, json = payload, headers = headers)
    if res.status_code != 200:
        st.error(f"Failed to fetch data: {res.status_code} - {res.text}")

def fetch_current_orders(dhan_api, instrument):
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
    if(instrument["Id"] == 1):
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("NIFTY", na=False)] & ~df["tradingSymbol"].str.contains("BANKNIFTY", na=False)
    elif(instrument["Id"] == 2): 
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("BANKNIFTY", na=False)]
    elif(instrument["Id"] == 3): 
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("GOLDM", na=False)]
    else:
        fut_df = fut_df[fut_df["tradingSymbol"].str.contains("SILVERM", na=False)]
    fut_df[["tradingSymbol", "positionType", "exchangeSegment", "productType"]].tail(2000)
    latest_contract = fut_df["tradingSymbol"].dropna().iloc[-1] if not fut_df["tradingSymbol"].dropna().empty else "No Contract"
    positiontype = fut_df["positionType"].dropna().iloc[-1] if not fut_df["positionType"].dropna().empty else "None"
    if latest_contract != "No Contract":
        next_contract =  get_next_order(instrument, 1)
    else:
        next_contract =  get_next_order(instrument, 0)
    return latest_contract, next_contract, positiontype

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

   
    common_settings = load_common_settings()
    refreshtime = 0
    for instrument_key in instruments:
        instrument_settings = load_instrument_settings(instrument_key)
        settings = load_instrument_settings(instrument_key)
        instrument = instruments[instrument_key]
        if instrument["Id"] == 1:
            instrument["atr_period"] = int(settings["atr_period"])
            instrument["multiplier"] = int(settings["multiplier"])
            instrument["time_frame"] = int(settings["time_frame"])
            instrument["quantity"] = int(settings["quantity"])
        elif instrument["Id"] == 2:
            instrument["atr_period"] = int(settings["atr_period"])
            instrument["multiplier"] = int(settings["multiplier"])
            instrument["time_frame"] = int(settings["time_frame"])
            instrument["quantity"] = int(settings["quantity"])
        elif instrument["Id"] == 3:
            instrument["atr_period"] = int(settings["atr_period"])
            instrument["multiplier"] = int(settings["multiplier"])
            instrument["time_frame"] = int(settings["time_frame"])
            instrument["quantity"] = int(settings["quantity"])
        else:
            instrument["atr_period"] = int(settings["atr_period"])
            instrument["multiplier"] = int(settings["multiplier"])
            instrument["time_frame"] = int(settings["time_frame"])
            instrument["quantity"] = int(settings["quantity"])

        if refreshtime == 0: refreshtime = instrument["time_frame"]
        elif refreshtime > instrument["time_frame"]: refreshtime = instrument["time_frame"]


    instrument = instruments[instrument_name]
    st.sidebar.header("Parameters")

    dhan_api_token = st.sidebar.text_input("Api Token", value = common_settings.get("dhan_api_token",""))
    dhan_client_id = st.sidebar.text_input("Client ID", value = common_settings.get("dhan_client_id",""))
    nf_atr_period = st.sidebar.number_input("ATR Period", min_value = 0, max_value = None, value = instrument["atr_period"], step = 1)
    nf_multiplier = st.sidebar.number_input("Multiplier", min_value = 0, max_value = None, value = instrument["multiplier"], step = 1)
    nf_timeframe = st.sidebar.number_input("Time Frame", min_value = 0, max_value = None, value = instrument["time_frame"], step = 1)
    nf_quantity = st.sidebar.number_input("Quantity", min_value = 0, max_value = None, value = instrument["quantity"], step = 1)

    place_all_orders(dhan_api_token)
    currorder, next_contract = fetch_and_displaydata(instrument, nf_atr_period, nf_multiplier, nf_timeframe, nf_quantity, dhan_api_token)
    st_autorefresh(interval= refreshtime * 60 * 1000, limit=None, key="auto_refresh")

    col1, col2 = st.sidebar.columns([1, 1]) 

    with col2:
        if st.button("Roll Over"):
            latest_contract = currorder["tradingSymbol"].dropna().iloc[-1] if not currorder["tradingSymbol"].dropna().empty else "No Contract"
            if latest_contract != "No Contract":
                st.write("Current contract is:" +latest_contract+ ".\nAre you sure you want to roll over to " + next_contract + "?")
                answer = st.radio("", ["Yes", "No"], label_visibility="collapsed" )
                if st.button("Submit"):
                    st.write(f"You selected: {answer}")
            else:
                st.write("Currently no contract. Do you want to roll over to " + next_contract + "?")
                answer = st.radio("", ["Yes", "No"], label_visibility="collapsed" )
                if st.button("Submit"):
                    st.write(f"You selected: {answer}")
    with col1:
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

    st.query_params["auth"] = "1"

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
        exit = 0
        if current_pos == "short" and df["short_exit"].iloc[i]:
            df.at[df.index[i], "exit"] = "COVER"
            df.at[df.index[i], "entry"] = "None"
            exit = 1
            current_pos = None
            
        if current_pos == "long" and df["long_exit"].iloc[i]:
            df.at[df.index[i], "exit"] = "SELL"
            df.at[df.index[i], "entry"] = "None"
            exit = 1
            current_pos = None

        if current_pos == None and df["long_entry"].iloc[i]:
            df.at[df.index[i], "entry"] = "BUY"
            if exit == 0:
                df.at[df.index[i], "exit"] = "None"
            current_pos = "long"
            
        if current_pos == None and df["short_entry"].iloc[i]:
            df.at[df.index[i], "entry"] = "SHORT"
            if exit == 0:
                df.at[df.index[i], "exit"] = "None"
            current_pos = "short"
       
    return df

def highlight_row(row):
    if row['entry'] == "SHORT":
        return ['background-color: lightcoral'] * len(row)
    elif row['entry'] == "BUY":
        return ['background-color: lightcoral'] * len(row)
    elif row['exit'] == "COVER":
        return ['background-color: lightcoral'] * len(row)
    elif row['exit'] == "SELL":
        return ['background-color: lightcoral'] * len(row)
    else:
        return [''] * len(row)

def main():

    if st.query_params.get("auth") == "1":
        st.session_state.logged_in = True

    if st.session_state.logged_in:
        display_supertrend()
    else:
        login()

def load_instrument_settings(instrument_key):

    instrument = instruments[instrument_key]

    if(instrument["Id"] == 1):
        settingsfile = SETTINGS_NIFTY_FILE
    elif(instrument["Id"] == 2): 
        settingsfile = SETTINGS_BNF_FILE
    elif(instrument["Id"] == 3): 
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
   











