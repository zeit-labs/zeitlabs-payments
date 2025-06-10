"""Zeitlasb payments generic exceptions."""


class GatewayError(Exception):
    """Custom exception for payment gateway related errors."""


class CartFulfillmentError(Exception):
    """Custom exception raised when cart fulfillment fails."""


class InavlidCartError(Exception):
    """Custom exception raised when cart is invalid."""
