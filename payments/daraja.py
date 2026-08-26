"""
Daraja (M-Pesa) STK Push integration.

Requires DARAJA_CONSUMER_KEY, DARAJA_CONSUMER_SECRET, DARAJA_SHORTCODE,
DARAJA_PASSKEY, and DARAJA_CALLBACK_URL to be set in .env. Until then,
initiate_stk_push() below returns a simulated response so the payment
flow still works end to end during development.
"""
import base64
import requests
from datetime import datetime
from django.conf import settings

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE_URL = "https://api.safaricom.co.ke"


def _base_url():
    return PRODUCTION_BASE_URL if settings.DARAJA_ENV == "production" else SANDBOX_BASE_URL


def _credentials_configured():
    return bool(
        settings.DARAJA_CONSUMER_KEY
        and settings.DARAJA_CONSUMER_SECRET
        and settings.DARAJA_SHORTCODE
        and settings.DARAJA_PASSKEY
    )


def get_access_token():
    response = requests.get(
        f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials",
        auth=(settings.DARAJA_CONSUMER_KEY, settings.DARAJA_CONSUMER_SECRET),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def initiate_stk_push(phone, amount, account_reference):
    """
    Returns (checkout_request_id, simulated: bool).
    Falls back to a simulated request if Daraja credentials aren't set.
    """
    if not _credentials_configured():
        return f"sim_{int(datetime.utcnow().timestamp() * 1000)}", True

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}".encode()
    ).decode()

    token = get_access_token()

    payload = {
        "BusinessShortCode": settings.DARAJA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": settings.DARAJA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": settings.DARAJA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": "Farmart order payment",
    }

    response = requests.post(
        f"{_base_url()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["CheckoutRequestID"], False