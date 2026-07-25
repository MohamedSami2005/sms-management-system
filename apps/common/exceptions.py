class SMSGatewayException(Exception):
    """Base exception for all SMS Gateway integration errors."""
    def __init__(self, message: str, status_code: int = None, response_raw: str = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_raw = response_raw

    def __str__(self):
        return f"{self.message} (HTTP Status: {self.status_code})" if self.status_code else self.message


class SMSGatewayTimeoutException(SMSGatewayException):
    """Raised when the HTTP request to the SMS gateway times out."""
    pass


class SMSGatewayAuthException(SMSGatewayException):
    """Raised when gateway authentication fails (HTTP 401/403 or invalid API Key)."""
    pass


class SMSGatewayValidationException(SMSGatewayException):
    """Raised when mobile number, DLT Template ID, or parameters fail validation."""
    pass


class SMSGatewayHTTPException(SMSGatewayException):
    """Raised when the SMS Gateway returns a non-200 HTTP status code."""
    pass
