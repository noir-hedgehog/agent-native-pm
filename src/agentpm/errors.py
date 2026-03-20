class WebhookError(Exception):
    """Base class for webhook processing errors."""


class InvalidSignatureError(WebhookError):
    pass


class InvalidPayloadError(WebhookError):
    pass
