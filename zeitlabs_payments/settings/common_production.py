"""Common Settings"""
from typing import Any


def plugin_settings(settings: Any) -> None:
    """
    plugin settings
    """
    settings.PAYFORT_SETTINGS = {
        'access_code': 'm6ScifP9737ykbx31Z7i',
        'merchant_identifier': '14c025eb',
        'request_sha_phrase': '91W.WiIGZa0FN3wtp6ALqs?@',
        'response_sha_phrase': '26UzSCZTEBIdirrrNNuakx!#',
        'sha_method': 'SHA-256',
        'redirect_url': 'https://sbcheckout.payfort.com/FortAPI/paymentPage'
    }
    settings.ECOMMERCE_BASE_URL = 'https://f62a-2406-5a00-a20d-cc00-30af-50c9-cda6-2def.ngrok-free.app'
