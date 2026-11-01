from decimal import Decimal, ROUND_HALF_UP
import requests

def historical_usd_rate(currency, date):
    if currency == "USD": return Decimal("1.00000000"), date, "USD"
    try:
        response = requests.get(f"https://api.frankfurter.app/{date.isoformat()}", params={"from": currency, "to": "USD"}, timeout=5)
        response.raise_for_status()
        payload = response.json()
        rate = payload.get("rates", {}).get("USD")
        if rate is not None: return Decimal(str(rate)), date.fromisoformat(payload.get("date", date.isoformat())), "Frankfurter.app"
    except (requests.RequestException, ValueError, TypeError): pass
    return None, None, None

def usd_value(amount, rate):
    return (Decimal(amount) * Decimal(rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
