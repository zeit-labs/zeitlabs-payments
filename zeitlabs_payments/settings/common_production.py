"""Common Settings"""
from typing import Any


def plugin_settings(settings: Any) -> None:
    """
    plugin settings
    """
    settings.PAYFORT = {
        'access_code': 'm6ScifP9737ykbx31Z7i',
        'merchant_identifier': '14c025eb',
        'request_sha_phrase': '91W.WiIGZa0FN3wtp6ALqs?@',
        'response_sha_phrase': '26UzSCZTEBIdirrrNNuakx!#',
        'sha_method': 'SHA-256',
        'redirect_url': 'https://sbcheckout.payfort.com/FortAPI/paymentPage'
    }
    settings.BASE_URL = 'https://67c5-2406-5a00-a2ab-7100-d24c-b2d9-587c-aa71.ngrok-free.app'
