#!/usr/bin/env python3

import smtplib
from email.message import EmailMessage
import requests
import json
import re
from datetime import date, datetime
import os

# --- Configuration for assets to monitor ---
ASSETS = {
    "ETH": {
        "slug_template": "ethereum-up-or-down-on-july-{}",
        "binance_symbol": "ETHUSDT"
    },
    "BTC": {
        "slug_template": "bitcoin-up-or-down-on-july-{}",
        "binance_symbol": "BTCUSDT"
    },
    "XRP": {
        "slug_template": "xrp-up-or-down-on-july-{}",
        "binance_symbol": "XRPUSDT"
    },
    "SOL": {
        "slug_template": "solana-up-or-down-on-july-{}",
        "binance_symbol": "SOLUSDT"
    }
}

yes_price = float
percent_change = float


def load_alert_state(asset_name):
    """Load the previous alert state for a specific asset from file"""
    try:
        with open('alert_state.json', 'r') as f:
            full_state = json.load(f)
            return full_state.get(asset_name, {
                "last_high_alert": False,
                "last_low_alert": False,
                "last_price": None
            })
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "last_high_alert": False,
            "last_low_alert": False,
            "last_price": None
        }


def save_alert_state(asset_name, state):
    """Save the current alert state for a specific asset to file"""
    try:
        with open('alert_state.json', 'r') as f:
            full_state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        full_state = {}

    full_state[asset_name] = state

    with open('alert_state.json', 'w') as f:
        json.dump(full_state, f, indent=4)


def alert_user(asset_name, yes_price, percent_change):
    formated_percent_change = "{:.2f}".format(percent_change)

    # Load previous state for the specific asset
    state = load_alert_state(asset_name)
    asset_display_name = asset_name.upper()

    alerts_sent = []

    # High price alerts (above 80%)
    if yes_price > 0.8:
        if not state["last_high_alert"]:
            print(f"🚨 {asset_display_name} ALERT: Price crossed above 80%!")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current {asset_display_name} change: {formated_percent_change}%")
            send_email(asset_display_name, yes_price, formated_percent_change, f"🚨 HIGH ALERT: {asset_display_name} Price above 80%")
            state["last_high_alert"] = True
            alerts_sent.append("high_alert")
    else:
        # Check if we should send a "falling" alert
        if state["last_high_alert"] and yes_price <= 0.6:
            print(f"📉 {asset_display_name} ALERT: Price falling! Dropped to 60% or below")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current {asset_display_name} change: {formated_percent_change}%")
            send_email(asset_display_name, yes_price, formated_percent_change, f"📉 FALLING ALERT: {asset_display_name} Price dropped to 60% or below")
            state["last_high_alert"] = False
            alerts_sent.append("falling_alert")

    # Low price alerts (below 20%)
    if yes_price < 0.2:
        if not state["last_low_alert"]:
            print(f"🚨 {asset_display_name} ALERT: Price crossed below 20%!")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current {asset_display_name} change: {formated_percent_change}%")
            send_email(asset_display_name, yes_price, formated_percent_change, f"🚨 LOW ALERT: {asset_display_name} Price below 20%")
            state["last_low_alert"] = True
            alerts_sent.append("low_alert")
    else:
        # Check if we should send a "rising" alert
        if state["last_low_alert"] and yes_price >= 0.4:
            print(f"📈 {asset_display_name} ALERT: Price rising! Climbed to 40% or above")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current {asset_display_name} change: {formated_percent_change}%")
            send_email(asset_display_name, yes_price, formated_percent_change, f"📈 RISING ALERT: {asset_display_name} Price climbed to 40% or above")
            state["last_low_alert"] = False
            alerts_sent.append("rising_alert")

    # Update state with current price
    state["last_price"] = yes_price

    # Save state for the specific asset
    save_alert_state(asset_name, state)

    if not alerts_sent:
        print(f"No alerts needed for {asset_display_name}. Price: {yes_price:.2f}c, Change: {formated_percent_change}%")
        print(f"State: High alert active: {state['last_high_alert']}, Low alert active: {state['last_low_alert']}")


def send_email(asset_name, yes_price, formated_percent_change, alert_type):
    email_body = f"""
        POLYMARKET PRICE ALERT

        {alert_type}

        CURRENT YES PRICE: {yes_price:.2f} cents

        Current {asset_name} position: {formated_percent_change}% 

        Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """

    from_email = os.environ.get('EMAIL_FROM')
    app_password = os.environ.get('EMAIL_APP_PASSWORD')
    to_email = os.environ.get('EMAIL_TO')

    if not from_email or not app_password:
        print("ERROR: Email credentials not found in environment variables")
        return

    msg = EmailMessage()
    msg['subject'] = f"PolyMarket Alert: {alert_type}"
    msg['from'] = from_email
    msg['to'] = to_email
    msg.set_content(email_body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_email, app_password)
            server.send_message(msg)
            print(f"Email for {asset_name} sent successfully!")
    except smtplib.SMTPException as e:
        print(f"Failed to send email for {asset_name}: {e}")


def get_binance_prices(symbol):
    current_price_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
    klines_url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit=1"

    try:
        # --- Get the current price ---
        current_price_response = requests.get(current_price_url)
        current_price_response.raise_for_status()
        current_price_data = current_price_response.json()
        current_price = float(current_price_data.get('price'))

        # --- Get the daily open price ---
        klines_response = requests.get(klines_url)
        klines_response.raise_for_status()
        klines_data = klines_response.json()

        open_price = None
        if klines_data:
            open_price = float(klines_data[0][1])

        return {
            "open_price": open_price,
            "current_price": current_price
        }

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while communicating with the Binance API for {symbol}: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        print(f"An error occurred while parsing the API response for {symbol}: {e}")
        return None


def extract_slug_from_url(url):
    match = re.search(r'polymarket\.com/event/([^/?&#]+)', url)
    if not match:
        raise ValueError("Invalid Polymarket URL format")
    return match.group(1)


def get_market_data(url):
    """Fetch market data from Polymarket API"""
    slug = extract_slug_from_url(url)
    base_url = 'https://gamma-api.polymarket.com'

    # Get event by slug
    event_response = requests.get(f"{base_url}/events?slug={slug}")
    event_response.raise_for_status()
    event_data = event_response.json()

    if not isinstance(event_data, list) or len(event_data) == 0:
        raise ValueError(f"No event found for slug '{slug}'")

    event = event_data[0]

    # Get markets for the event
    markets = []
    if isinstance(event.get('markets'), list) and len(event['markets']) > 0:
        markets = event['markets']
    else:
        markets_response = requests.get(f"{base_url}/markets?event_id={event['id']}&active=true")
        markets_response.raise_for_status()
        markets = markets_response.json()

    if not markets:
        raise ValueError("No markets found")

    # Process first market
    market = markets[0]
    if not market.get('tokens') and not market.get('outcomes'):
        detail_response = requests.get(f"{base_url}/markets/{market['id']}")
        detail_response.raise_for_status()
        market = detail_response.json()

    # Extract token IDs
    token_ids = extract_token_ids(market)
    if len(token_ids) >= 2:
        market['token_ids'] = token_ids
        return market
    else:
        raise ValueError("No valid token pairs found")


def extract_token_ids(market):
    """Extract token IDs from market data"""
    # Try tokens array
    if isinstance(market.get('tokens'), list) and len(market['tokens']) >= 2:
        token_ids = [t['token_id'] for t in market['tokens'] if t.get('token_id')]
        if len(token_ids) >= 2:
            return token_ids[:2]

    # Try outcomes array
    if isinstance(market.get('outcomes'), list) and len(market['outcomes']) >= 2:
        token_ids = [o['token_id'] for o in market['outcomes'] if o.get('token_id')]
        if len(token_ids) >= 2:
            return token_ids[:2]

    # Try clobTokenIds
    if isinstance(market.get('clobTokenIds'), str):
        try:
            parsed = json.loads(market['clobTokenIds'])
            if isinstance(parsed, list) and len(parsed) >= 2:
                return parsed[:2]
        except json.JSONDecodeError:
            pass

    if isinstance(market.get('clobTokenIds'), list) and len(market['clobTokenIds']) >= 2:
        return market['clobTokenIds'][:2]

    return []


def get_token_price(token_id):
    """Get current price for a specific token"""
    try:
        # Get buy and sell prices
        buy_response = requests.get(f"https://clob.polymarket.com/price?token_id={token_id}&side=buy")
        buy_response.raise_for_status()
        buy_data = buy_response.json()

        sell_response = requests.get(f"https://clob.polymarket.com/price?token_id={token_id}&side=sell")
        sell_response.raise_for_status()
        sell_data = sell_response.json()

        buy_price = float(buy_data.get('price', 0))
        sell_price = float(sell_data.get('price', 0))

        # Return midpoint price
        if buy_price > 0 and sell_price > 0:
            return (buy_price + sell_price) / 2
        elif buy_price > 0:
            return buy_price
        elif sell_price > 0:
            return sell_price
        else:
            return None

    except Exception as e:
        print(f"Failed to fetch price for token {token_id}: {e}")
        return None


def process_market(asset_name, asset_config):
    """Main logic for processing a single asset market."""
    current_date = date.today()
    current_day = current_date.day
    print(f"\n--- Checking {asset_name.upper()} prices for day {current_day} ---")

    slug = asset_config["slug_template"].format(current_day)
    url = f"https://polymarket.com/event/{slug}"

    try:
        market = get_market_data(url)
        token_ids = market.get('token_ids', [])

        if len(token_ids) >= 2:
            yes_price = get_token_price(token_ids[0])

            if yes_price is not None:
                print(f"YES Price: ${yes_price:.4f}")
            else:
                print("Unable to fetch YES price")
                return
        else:
            print("No valid token IDs found")
            return

    except Exception as e:
        print(f"Error fetching market data for {asset_name}: {e}")
        return

    print(f"Getting {asset_name.upper()} price from Binance...")
    price_data = get_binance_prices(asset_config["binance_symbol"])

    if price_data:
        print(f"Today's Open Price (UTC): ${price_data['open_price']:,.2f}")
        print(f"Current Price:            ${price_data['current_price']:,.2f}")

        if price_data['open_price'] is not None:
            change = price_data['current_price'] - price_data['open_price']
            percent_change = (change / price_data['open_price']) * 100

            if change >= 0:
                print(f"Day's Change:             +${change:,.2f} ({percent_change:+.2f}%)")
            else:
                print(f"Day's Change:             -${abs(change):,.2f} ({percent_change:.2f}%)")

            # Check for alerts
            alert_user(asset_name, yes_price, percent_change)
        else:
            print(f"Could not calculate {asset_name.upper()} price change")
    else:
        print(f"Failed to fetch {asset_name.upper()} price data")


def main():
    """Iterate over all configured assets and process them."""
    for asset_name, asset_config in ASSETS.items():
        process_market(asset_name, asset_config)


if __name__ == "__main__":
    main()