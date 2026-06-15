"""Map domain exceptions to DRF responses."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from accounts import abuse_services
from accounts.write_guard import ContentRejected, write_guard_user_message


def api_exception_handler(exc, context):
    if isinstance(exc, abuse_services.RateLimitExceeded):
        return Response(
            {"detail": write_guard_user_message(exc)},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if isinstance(exc, ContentRejected):
        return Response(
            {"detail": write_guard_user_message(exc), "reasons": exc.reasons},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, ValueError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, PermissionError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)

    from django.core.exceptions import ValidationError

    if isinstance(exc, ValidationError):
        if hasattr(exc, "message_dict"):
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(exc, "messages"):
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    return None
