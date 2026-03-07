import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default exception handler to produce consistent
    error responses across the entire API.

    Standard error shape:
    {
        "error": {
            "code": "validation_error",
            "message": "...",
            "details": { ... }   # field-level errors if applicable
        }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_payload = {
            "error": {
                "code": _get_error_code(response.status_code),
                "message": _extract_message(response.data),
                "details": response.data if isinstance(response.data, dict) else {},
            }
        }
        response.data = error_payload
    else:
        # Unhandled exception — log it and return 500
        logger.exception("Unhandled exception: %s", exc)
        response = Response(
            {
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                    "details": {},
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return response


def _get_error_code(status_code: int) -> str:
    codes = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        429: "rate_limit_exceeded",
        500: "internal_server_error",
    }
    return codes.get(status_code, "error")


def _extract_message(data) -> str:
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        # Return first field error as the top-level message
        first_key = next(iter(data))
        first_val = data[first_key]
        if isinstance(first_val, list):
            return str(first_val[0])
        return str(first_val)
    if isinstance(data, list):
        return str(data[0])
    return str(data)