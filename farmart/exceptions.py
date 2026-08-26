from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    DRF's default error shape is {"detail": "..."}. The frontend expects
    {"message": "..."} on every error response, so this normalizes it.
    """
    response = exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data:
        response.data = {"message": str(response.data["detail"])}
    return response