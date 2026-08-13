from datetime import datetime

MIN_STOCK_THRESHOLD = 5

def calculate_stock_status(quantity: float, minimum_stock: float = None) -> str:
    """
    Calculates stock status based on current quantity and minimum stock threshold.
    - OUT OF STOCK: quantity <= 0
    - LOW STOCK: 0 < quantity <= minimum_stock
    - IN STOCK: quantity > minimum_stock
    """
    if minimum_stock is None:
        minimum_stock = MIN_STOCK_THRESHOLD
    if quantity <= 0:
        return "OUT OF STOCK"
    elif quantity <= minimum_stock:
        return "LOW STOCK"
    else:
        return "IN STOCK"

def get_status_badge_class(status: str) -> str:
    """Returns CSS badge class for status display."""
    if status == "IN STOCK":
        return "badge-success"
    elif status == "LOW STOCK":
        return "badge-warning"
    elif status == "OUT OF STOCK":
        return "badge-danger"
    return "badge-secondary"

def format_currency(value) -> str:
    """
    Formats float/number to Indian Rupee currency format (e.g. ₹1,50,000.00).
    Uses standard Indian number system formatting (Lakhs and Crores).
    """
    try:
        val = float(value)
        is_negative = val < 0
        val = abs(val)
        
        s, decimal = f"{val:.2f}".split(".")
        
        if len(s) <= 3:
            formatted = s
        else:
            last_three = s[-3:]
            remaining = s[:-3]
            groups = []
            while remaining:
                groups.append(remaining[-2:])
                remaining = remaining[:-2]
            groups.reverse()
            formatted = ",".join(groups) + "," + last_three
            
        sign = "-" if is_negative else ""
        return f"{sign}₹{formatted}.{decimal}"
    except (ValueError, TypeError):
        return "₹0.00"

def format_datetime(dt) -> str:
    """Formats datetime object to standard human readable string."""
    if isinstance(dt, datetime):
        return dt.strftime("%b %d, %Y %I:%M %p")
    return str(dt) if dt else "N/A"

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

def _two_digits(num: int) -> str:
    if num < 20:
        return _ONES[num]
    return (_TENS[num // 10] + (" " + _ONES[num % 10] if num % 10 else "")).strip()

def _three_digits(num: int) -> str:
    if num < 100:
        return _two_digits(num)
    return (_ONES[num // 100] + " Hundred" + (" " + _two_digits(num % 100) if num % 100 else "")).strip()

def amount_in_words(value) -> str:
    """
    Converts an amount into Indian English words (Rupees/Paise, Lakh/Crore).
    Example: 12345.50 -> 'Twelve Thousand Three Hundred Forty-Five Rupees and Fifty Paise Only'
    """
    try:
        val = abs(float(value))
        rupees = int(val)
        paise = int(round((val - rupees) * 100))

        parts = []
        crore = rupees // 10000000
        lakh = (rupees // 100000) % 100
        thousand = (rupees // 1000) % 100
        hundred = rupees % 1000

        if crore:
            parts.append(_two_digits(crore) + " Crore")
        if lakh:
            parts.append(_two_digits(lakh) + " Lakh")
        if thousand:
            parts.append(_two_digits(thousand) + " Thousand")
        if hundred:
            parts.append(_three_digits(hundred))
        if not parts:
            parts.append("Zero")

        words = " ".join(parts) + " Rupees"
        if paise:
            words += " and " + _two_digits(paise) + " Paise"
        words += " Only"
        return words
    except (ValueError, TypeError):
        return "Zero Rupees Only"
