import requests
from typing import Dict, Optional

def get_company_currency_for_country(country_code: str) -> Optional[str]:
    # Query restcountries to map country -> currency
    try:
        url = "https://restcountries.com/v3.1/all?fields=name,currencies,cca2"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for c in data:
            if c.get("cca2") == country_code.upper():
                currencies = c.get("currencies", {})
                if currencies:
                    # Pick the first currency code
                    return list(currencies.keys())[0]
        return None
    except Exception:
        return None

def fetch_rates(base: str) -> Dict[str, float]:
    url = f"https://api.exchangerate-api.com/v4/latest/{base.upper()}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("rates", {})

def convert(amount: float, from_ccy: str, to_ccy: str) -> float:
    if from_ccy.upper() == to_ccy.upper():
        return float(amount)
    # Get rates with base = from_ccy and read rate to to_ccy
    rates = fetch_rates(from_ccy)
    rate = rates.get(to_ccy.upper())
    if not rate:
        # Fallback: try base = to_ccy (invert)
        rates2 = fetch_rates(to_ccy)
        back = rates2.get(from_ccy.upper())
        if not back:
            raise ValueError("Conversion rate not available")
        rate = 1.0 / back
    return float(amount) * float(rate)
