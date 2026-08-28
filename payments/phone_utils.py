"""
Phone number utilities for M-Pesa payments.
"""
import re


def normalize_phone_number(phone):
    """
    Normalize Kenyan phone numbers to international format.
    
    Examples:
        0708319101 -> 254708319101
        +254708319101 -> 254708319101
        254708319101 -> 254708319101
    
    Returns the normalized number or raises ValueError if invalid.
    """
    if not phone or not isinstance(phone, str):
        raise ValueError("Phone number must be a non-empty string")
    
    # Remove spaces and common formatting
    phone = phone.strip().replace(" ", "").replace("-", "")
    
    # If it starts with +254, remove the +
    if phone.startswith("+254"):
        phone = "254" + phone[4:]
    # If it starts with 254, keep as is
    elif phone.startswith("254"):
        pass
    # If it starts with 0, replace with 254
    elif phone.startswith("0"):
        phone = "254" + phone[1:]
    else:
        raise ValueError("Invalid phone number format")
    
    # Validate the format: 254 + 9 digits (Kenyan number)
    if not re.match(r"^254[0-9]{9}$", phone):
        raise ValueError("Invalid Kenyan phone number format")
    
    # Validate it's a Safaricom number (starts with 0700-0799, 0701-0701)
    # 254700-254799 is Safaricom
    next_two = phone[3:5]
    if next_two not in {"70", "71", "72", "74", "75", "76", "79"}:
        raise ValueError("Phone number must be a supported Safaricom number")
    
    return phone
