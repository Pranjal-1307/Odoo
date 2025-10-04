from typing import Optional, Tuple
import re
import numpy as np
import cv2
import pytesseract
from PIL import Image

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "₹": "INR",
    "¥": "JPY",
    "₩": "KRW",
    "₽": "RUB",
    "R$": "BRL",
    "C$": "CAD",
    "A$": "AUD",
    "NZ$": "NZD",
    "CHF": "CHF",
}

ISO_CODES = {"USD","EUR","GBP","INR","JPY","KRW","RUB","BRL","CAD","AUD","NZD","CHF","SGD","HKD","ZAR","AED","SAR","NOK","SEK","DKK"}

TOTAL_HINTS = ["total", "amount due", "grand total", "balance due", "amount", "sum"]

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    # Convert to OpenCV
    arr = np.array(img)
    if arr.ndim == 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    else:
        gray = arr
    # Adaptive threshold to boost contrast
    th = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY, 31, 10)
    # Slight dilation to connect broken digits
    kernel = np.ones((1,1), np.uint8)
    proc = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    return Image.fromarray(proc)

def ocr_text(img: Image.Image) -> str:
    proc = preprocess_for_ocr(img)
    # Configure tesseract to look for numbers + currency symbols predominantly
    config = "--oem 3 --psm 6"
    text = pytesseract.image_to_string(proc, config=config)
    return text

def detect_currency_and_amount(text: str) -> Tuple[Optional[str], Optional[float]]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # 1) Find currency symbol / ISO
    currency = None
    for line in lines:
        # symbol variants like R$, A$, C$ must be checked first
        for sym in ["R$", "A$", "C$", "NZ$"]:
            if sym in line:
                currency = CURRENCY_SYMBOLS.get(sym)
                break
        if currency:
            break
        # common single-char symbols
        for sym in ["₹","$","€","£","¥","₩","₽"]:
            if sym in line:
                currency = CURRENCY_SYMBOLS.get(sym)
                break
        if currency:
            break
        # ISO codes
        iso_match = re.findall(r"\b([A-Z]{{3}})\b", line)
        for iso in iso_match:
            if iso in ISO_CODES:
                currency = iso
                break
        if currency:
            break

    # 2) Look for amounts, prioritizing lines with TOTAL hints
    amount = None
    money_regex = re.compile(r"(?<!\d)(\d{{1,3}}(?:[\,\s]\d{{3}})*|\d+)([\.,]\d{{2}})?")
    scored_candidates = []

    for idx, line in enumerate(lines):
        # Normalize decimals: remove spaces in thousands
        candidates = money_regex.findall(line)
        if not candidates:
            continue
        score = 0
        lcline = line.lower()
        if any(h in lcline for h in TOTAL_HINTS):
            score += 5
        if currency and (currency in line):
            score += 3
        for num, dec in candidates:
            raw = (num.replace(" ", "").replace(",", "")) + (dec if dec else "")
            try:
                val = float(raw.replace(",", ""))
                scored_candidates.append((score, idx, val, line))
            except:
                continue

    if scored_candidates:
        # Highest score; tie-break by later lines (often totals at end)
        scored_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        amount = scored_candidates[0][2]

    return currency, amount
