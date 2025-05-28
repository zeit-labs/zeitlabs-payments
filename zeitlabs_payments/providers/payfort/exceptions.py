from zeitlabs_payments.exceptions import GatewayError


class PayFortException(GatewayError):
    """PayFort exception."""


class PayFortBadSignatureException(PayFortException):
    """PayFort bad signature exception."""
