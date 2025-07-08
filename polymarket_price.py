#!/usr/bin/env python3

import smtplib
from email.message import EmailMessage
import requests
import json
import re
from datetime import date, datetime, time
import os

yes_price = float
percent_change = float


def load_alert_state():
    """Load the previous alert state from file"""
    try:
        with open('alert_state.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "last_high_alert": False,
            "last_low_alert": False,
            "last_price": None
        }


def save_alert_state(state):
    """Save the current alert state to file"""
    with open('alert_state.json', 'w') as f:
        json.dump(state, f)


def alert_user(yes_price, percent_change):
    formated_percent_change = "{:.2f}".format(percent_change)

    # Load previous state
    state = load_alert_state()

    alerts_sent = []

    # High price alerts (above 80%)
    if yes_price > 0.8:
        if not state["last_high_alert"]:
            # First time crossing above 80%
            print("🚨 ALERT: Price crossed above 80%!")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current Eth change: {formated_percent_change}%")
            send_email(yes_price, formated_percent_change, "🚨 HIGH ALERT: Price above 80%")
            state["last_high_alert"] = True
            alerts_sent.append("high_alert")
    else:
        # Check if we should send a "falling" alert
        if state["last_high_alert"] and yes_price <= 0.6:
            print("📉 ALERT: Price falling! Dropped to 60% or below")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current Eth change: {formated_percent_change}%")
            send_email(yes_price, formated_percent_change, "📉 FALLING ALERT: Price dropped to 60% or below")
            state["last_high_alert"] = False
            alerts_sent.append("falling_alert")

    # Low price alerts (below 20%)
    if yes_price < 0.2:
        if not state["last_low_alert"]:
            # First time crossing below 20%
            print("🚨 ALERT: Price crossed below 20%!")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current Eth change: {formated_percent_change}%")
            send_email(yes_price, formated_percent_change, "🚨 LOW ALERT: Price below 20%")
            state["last_low_alert"] = True
            alerts_sent.append("low_alert")
    else:
        # Check if we should send a "rising" alert
        if state["last_low_alert"] and yes_price >= 0.4:
            print("📈 ALERT: Price rising! Climbed to 40% or above")
            print(f"PolyMarket YES Token @ {yes_price:.2f}c")
            print(f"Current Eth change: {formated_percent_change}%")
            send_email(yes_price, formated_percent_change, "📈 RISING ALERT: Price climbed to 40% or above")
            state["last_low_alert"] = False
            alerts_sent.append("rising_alert")

    # Update state with current price
    state["last_price"] = yes_price

    # Save state
    save_alert_state(state)

    if not alerts_sent:
        print(f"No alerts needed. Price: {yes_price:.2f}c, ETH: {formated_percent_change}%")
        print(f"State: High alert active: {state['last_high_alert']}, Low alert active: {state['last_low_alert']}")


def send_email(yes_price, formated_percent_change, alert_type):
    email_body = f"""
        POLYMARKET PRICE ALERT

        {alert_type}

        CURRENT YES PRICE: {yes_price:.2f} cents

        Current Eth position: {formated_percent_change}% 

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
            print("Email sent successfully!")
    except smtplib.SMTPException as e:
        print(f"Failed to send email: {e}")



def get_ethereum_prices_binance():
    # The trading pair for Ethereum and Tether USD
    symbol = 'ETHUSDT'

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
        print(f"An error occurred while communicating with the Binance API: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        print(f"An error occurred while parsing the API response: {e}")
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


def main():
    current_date = date.today()
    current_day = current_date.day
    print(f"Checking prices for day {current_day}")

    url = f"https://polymarket.com/event/ethereum-up-or-down-on-july-{current_day}?tid=1751853495589"

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
        print(f"Error fetching market data: {e}")
        return

    print("Getting ETH price...")
    eth_price = get_ethereum_prices_binance()

    if eth_price:
        print(f"\nToday's Open Price (UTC): ${eth_price['open_price']:,.2f}")
        print(f"Current Price:            ${eth_price['current_price']:,.2f}")

        if eth_price['open_price'] is not None:
            change = eth_price['current_price'] - eth_price['open_price']
            percent_change = (change / eth_price['open_price']) * 100

            if change >= 0:
                print(f"Day's Change:             +${change:,.2f} ({percent_change:+.2f}%)")
            else:
                print(f"Day's Change:             -${abs(change):,.2f} ({percent_change:.2f}%)")

            # Check for alerts
            alert_user(yes_price, percent_change)
        else:
            print("Could not calculate ETH price change")
    else:
        print("Failed to fetch ETH price data")


if __name__ == "__main__":
    main()