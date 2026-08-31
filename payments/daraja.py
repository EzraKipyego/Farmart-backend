"""
Daraja (M-Pesa) STK Push integration.

Requires MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE,
MPESA_PASSKEY, and MPESA_CALLBACK_URL to be set in .env.
"""
import base64
import logging
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SANDBOX_BASE_URL = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE_URL = "https://api.safaricom.co.ke"


class DarajaResponseError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or {}


class DarajaGatewayError(Exception):
    def __init__(self, message, details=None, status_code=504):
        super().__init__(message)
        self.details = details or {}
        self.status_code = status_code


def _base_url():
    env = getattr(settings, "DARAJA_ENV", getattr(settings, "MPESA_ENVIRONMENT", "sandbox"))
    env = str(env).strip().lower()
    return PRODUCTION_BASE_URL if env == "production" else SANDBOX_BASE_URL


def _credentials_configured():
    return bool(
        getattr(settings, "DARAJA_CONSUMER_KEY", None)
        and getattr(settings, "DARAJA_CONSUMER_SECRET", None)
        and getattr(settings, "DARAJA_SHORTCODE", None)
        and getattr(settings, "DARAJA_PASSKEY", None)
        and getattr(settings, "DARAJA_CALLBACK_URL", None)
    )


def get_access_token():
    """Obtain OAuth access token from Daraja."""
    try:
        response = requests.get(
            f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials",
            auth=(settings.DARAJA_CONSUMER_KEY, settings.DARAJA_CONSUMER_SECRET),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as error:
        response = getattr(error, "response", None)
        logger.error(
            "[Daraja] OAuth request failed: %s response_status=%s response_body=%s",
            error,
            response.status_code if response is not None else None,
            response.text if response is not None else None,
        )
        raise DarajaGatewayError(
            "Payment gateway timeout. Please try again.",
            {"error": str(error), "response_status": response.status_code if response is not None else None},
            504 if isinstance(error, requests.exceptions.Timeout) else 502,
        ) from error
    except Exception as error:
        logger.error("[Daraja] Failed to obtain access token: %s", error)
        raise DarajaGatewayError("Payment gateway unavailable. Please try again.", {"error": str(error)}, 502) from error


def initiate_stk_push(phone, amount, account_reference):
    """
    Initiate an M-Pesa STK push to the given phone number.
    
    Returns:
        (checkout_request_id, merchant_request_id) on success
    
    Raises:
        Exception if credentials not configured or API call fails
    """
    if not _credentials_configured():
        raise ValueError("Daraja credentials are not properly configured")
    callback_url = str(
        getattr(
            settings,
            "DARAJA_CALLBACK_URL",
            "https://farmart-backend-02tq.onrender.com/api/payments/callback/",
        )
    ).strip()
    if not callback_url.startswith("https://"):
        raise ValueError("MPESA_CALLBACK_URL must be a public HTTPS URL")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}".encode()
    ).decode()

    try:
        token = get_access_token()
    except Exception as e:
        logger.error(f"[Daraja] Could not get access token: {e}")
        raise

    daraja_amount = int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if daraja_amount <= 0:
        raise ValueError("STK amount must be a positive whole number")

    payload = {
        "BusinessShortCode": settings.DARAJA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": daraja_amount,
        "PartyA": phone,
        "PartyB": settings.DARAJA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": "Farmart order payment",
    }

    try:
        response = requests.post(
            f"{_base_url()}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        try:
            data = response.json()
        except ValueError:
            data = {"raw_response": response.text[:1000]}

        logger.info("[Daraja] raw STK response status=%s body=%s", response.status_code, data)

        logger.info(
            "[Daraja] STK response code=%s merchant_request_id=%s checkout_request_id=%s customer_message=%s",
            data.get("ResponseCode"), data.get("MerchantRequestID"),
            data.get("CheckoutRequestID"), data.get("CustomerMessage"),
        )
        if str(data.get("ResponseCode")) != "0":
            raise DarajaResponseError(
                data.get("ResponseDescription") or data.get("CustomerMessage") or "Daraja rejected the STK request",
                {
                    "response_code": data.get("ResponseCode"),
                    "response_description": data.get("ResponseDescription"),
                    "customer_message": data.get("CustomerMessage"),
                },
            )

        checkout_id = data.get("CheckoutRequestID")
        merchant_id = data.get("MerchantRequestID")

        if not checkout_id or not merchant_id:
            logger.error(f"[Daraja] Missing IDs in response: {data}")
            raise ValueError("Missing CheckoutRequestID or MerchantRequestID in response")

        logger.info(f"[Daraja] STK push initiated: {checkout_id} for {phone}")
        return checkout_id, merchant_id
    except requests.exceptions.RequestException as error:
        response = getattr(error, "response", None)
        logger.error(
            "[Daraja] Safaricom request failed: %s response_status=%s response_body=%s",
            error,
            response.status_code if response is not None else None,
            response.text if response is not None else None,
        )
        raise DarajaGatewayError(
            "Payment gateway timeout. Please try again.",
            {"error": str(error), "response_status": response.status_code if response is not None else None},
            504 if isinstance(error, requests.exceptions.Timeout) else 502,
        ) from error
    except Exception as error:
        logger.error("[Daraja] Error initiating STK push: %s", error)
        raise DarajaGatewayError("Payment gateway unavailable. Please try again.", {"error": str(error)}, 502) from error


def query_stk_push_status(checkout_request_id):
    """Poll Daraja to verify the final status of an STK Push transaction."""
    if not _credentials_configured():
        raise ValueError("Daraja credentials are not properly configured")
    if not checkout_request_id:
        raise ValueError("CheckoutRequestID is required")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}".encode()
    ).decode()

    token = get_access_token()
    payload = {
        "BusinessShortCode": settings.DARAJA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    try:
        response = requests.post(
            f"{_base_url()}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("[Daraja] STK query response for %s: %s", checkout_request_id, data)

        result_code = data.get("ResultCode")
        result_description = data.get("ResultDesc") or data.get("ResponseDescription") or "M-Pesa status query response"
        if str(result_code) == "0":
            return {"status": "COMPLETED", "message": result_description, "raw": data}
        if result_code in ("10200", "1032", "1037"):
            return {"status": "PENDING", "message": result_description, "raw": data}
        return {"status": "FAILED", "message": result_description, "raw": data}
    except requests.exceptions.RequestException as error:
        response = getattr(error, "response", None)
        logger.error(
            "[Daraja] STK query request failed: %s response_status=%s response_body=%s",
            error,
            response.status_code if response is not None else None,
            response.text if response is not None else None,
        )
        raise DarajaGatewayError(
            "Payment gateway timeout. Please try again.",
            {"error": str(error), "response_status": response.status_code if response is not None else None},
            504 if isinstance(error, requests.exceptions.Timeout) else 502,
        ) from error
    except ValueError as error:
        logger.error("[Daraja] STK query returned malformed JSON: %s", error)
        raise DarajaGatewayError("Payment gateway unavailable. Please try again.", {"error": str(error)}, 502) from error
