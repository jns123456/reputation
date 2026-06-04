"""Attach a request ID for log correlation (production operations)."""

import uuid

from config.request_context import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (
            request.headers.get(REQUEST_ID_HEADER)
            or request.META.get("HTTP_X_REQUEST_ID")
            or uuid.uuid4().hex
        )
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
