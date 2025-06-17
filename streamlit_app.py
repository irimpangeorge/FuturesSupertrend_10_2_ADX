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
import PlaceOrders
from datetime import datetime, timedelta

# ---------------------- CONFIG ----------------------

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

    PlaceOrders.get_instrument_details()

    df = PlaceOrders.fetch_data(instrument, timeframe, dhan_api)

    if not df.empty:
        df = PlaceOrders.apply_indicators(df, atrperiod, multiplier )
        df = PlaceOrders.generate_signals(df)

        st.subheader("📊 Signals Table")
        df = df[["close", "supertrend", "di_plus", "di_minus", "entry", "exit"]].tail(2000)
        styled_df  = df.style.apply(highlight_row, axis=1)
        st.dataframe(styled_df )

       
        st.subheader("📦 Current Orders")
        currorder, next_contract, positionType = PlaceOrders.fetch_current_orders(dhan_api, instrument)
        st.success(f"📝  Current contract: {currorder}")
        st.subheader("📍 Last Signal")
        latest_entry_signal = PlaceOrders.get_last_signal(df, "entry")
        st.success(f"🔔 Last Signal: {latest_entry_signal}")
        return currorder, next_contract

def prevent_rerun(trigger_key="run_logic"):
    """Call this function to control rerun behavior."""
    if trigger_key not in st.session_state:
        st.session_state[trigger_key] = False

def display_supertrend():

    col1, col2, col3 = st.columns([6, 1, 1]) 
    with col3:
        if st.button("Logout"):
            st.query_params["auth"] = "0"
            st.session_state.logged_in = False
            st.rerun()


    st.title("📈 Futures Supertrend(10,2)-ADX")

    instrument_name = st.selectbox("Select Instrument", list(PlaceOrders.instruments.keys()))

   
    common_settings = PlaceOrders.load_common_settings()
    refreshtime = 0
    for instrument_key in PlaceOrders.instruments:
        #instrument_settings = load_instrument_settings(instrument_key)
        settings = PlaceOrders.load_instrument_settings(instrument_key)
        instrument = PlaceOrders.instruments[instrument_key]
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


    instrument = PlaceOrders.instruments[instrument_name]
    st.sidebar.header("Parameters")

    dhan_api_token = st.sidebar.text_input("Api Token", value = common_settings.get("dhan_api_token",""))
    dhan_client_id = st.sidebar.text_input("Client ID", value = common_settings.get("dhan_client_id",""))
    nf_atr_period = st.sidebar.number_input("ATR Period", min_value = 0, max_value = None, value = instrument["atr_period"], step = 1)
    nf_multiplier = st.sidebar.number_input("Multiplier", min_value = 0, max_value = None, value = instrument["multiplier"], step = 1)
    nf_timeframe = st.sidebar.number_input("Time Frame", min_value = 0, max_value = None, value = instrument["time_frame"], step = 1)
    nf_quantity = st.sidebar.number_input("Quantity", min_value = 0, max_value = None, value = instrument["quantity"], step = 1)

    #PlaceOrders.place_all_orders(dhan_api_token)
    currorder, next_contract = fetch_and_displaydata(instrument, nf_atr_period, nf_multiplier, nf_timeframe, nf_quantity, dhan_api_token)
    #st_autorefresh(interval= refreshtime * 60 * 1000, limit=None, key="auto_refresh")

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
   











