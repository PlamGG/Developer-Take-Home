class SplitBillException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BusinessRuleError(SplitBillException):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=422)


class AuthenticationError(SplitBillException):
    def __init__(self, message: str = "Invalid or missing X-User"):
        super().__init__(code="unauthorized", message=message, status_code=401)


class NotFoundError(SplitBillException):
    def __init__(self, code: str, message: str):
        super().__init__(code=code, message=message, status_code=404)


class ForbiddenError(SplitBillException):
    def __init__(self, code: str = "not_a_member", message: str = "Not a member of this group"):
        super().__init__(code=code, message=message, status_code=403)
