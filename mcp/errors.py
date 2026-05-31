"""Structured MCP error type."""


class McpError(Exception):
    """An MCP tool/resource error with a stable machine-readable code."""

    def __init__(self, code, message, *, http_status=400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)

    def to_dict(self):
        return {"code": self.code, "message": self.message}
