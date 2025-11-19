import requests
import pandas as pd
import os
import sys

# --- CONFIGURATION ---
SYMBOL = 'WTI/USD'  # TwelveData uses this format for Crude Oil Spot
INTERVAL = '1h'
RSI_PERIOD = 14

# SECRETS
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY = os.environ.get("API_KEY") # <--- NEW SECRET

if not BOT_TOKEN or not CHAT_ID or not API_KEY:
    print("Error: Missing environment variables (BOT_TOKEN, CHAT_ID, or TWELVE_DATA_API_KEY).")
    sys.exit(1)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed to send message: {e}")

def calculate_rsi(series, period=14):
    """
    Calculates RSI using Wilder's Smoothing Method (Standard for Trading).
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(com=period-1, adjust=False).mean()
    avg_loss = loss.ewm(com=period-1, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_twelvedata_price():
    """
    Fetches OHLC data directly from Twelve Data API using Requests.
    """
    base_url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "apikey": API_KEY,
        "outputsize": 50 # Fetch last 50 candles (enough for RSI)
    }
    
    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if "values" not in data:
            print(f"Error fetching data: {data.get('message', 'Unknown error')}")
            return None

        # 1. Convert JSON list to DataFrame
        df = pd.DataFrame(data['values'])
        
        # 2. Convert columns to numeric (API returns strings)
        cols = ['open', 'high', 'low', 'close']
        df[cols] = df[cols].apply(pd.to_numeric)
        
        # 3. Sort Oldest -> Newest (API returns Newest first, but we need Oldest first for math)
        df = df.iloc[::-1].reset_index(drop=True)
        
        return df

    except Exception as e:
        print(f"API Request Failed: {e}")
        return None

def check_market():
    print(f"Fetching data for {SYMBOL} from TwelveData...")
    
    df = get_twelvedata_price()
    
    if df is None or df.empty:
        print("No data received.")
        return

    # Calculate RSI
    df['rsi'] = calculate_rsi(df['close'], period=RSI_PERIOD)

    # Get last two completed candles
    current_rsi = df['rsi'].iloc[-1]
    prev_rsi = df['rsi'].iloc[-2]
    current_price = df['close'].iloc[-1]

    print(f"Analyzed {SYMBOL}: Prev RSI={prev_rsi:.2f}, Curr RSI={current_rsi:.2f}")

    # LOGIC 1: RSI Recovery (Crossing UP above 30)
    if prev_rsi <= 30 and current_rsi > 30:
        msg = f"🛢 **OIL ALERT (12Data): BUY**\n\n{SYMBOL} ({INTERVAL}) RSI crossed ABOVE 30.\n**RSI:** {current_rsi:.2f}\n**Price:** ${current_price:.2f}"
        send_telegram_message(msg)
        print("Buy Alert Sent")

    # LOGIC 2: RSI Cooldown (Crossing DOWN below 80)
    elif prev_rsi >= 80 and current_rsi < 80:
        msg = f"🔥 **OIL ALERT (12Data): SELL**\n\n{SYMBOL} ({INTERVAL}) RSI crossed BELOW 80.\n**RSI:** {current_rsi:.2f}\n**Price:** ${current_price:.2f}"
        send_telegram_message(msg)
        print("Sell Alert Sent")
    
    else:
        print("No crossover detected.")

if __name__ == "__main__":
    check_market()
