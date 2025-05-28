"""
zeitlabs_payments Django application initialization.
"""

from django.apps import AppConfig


class ZeitlabsPaymentsConfig(AppConfig):
    """
    Configuration for the zeitlabs_payments Django application.
    """

    name = 'zeitlabs_payments'

    # pylint: disable=duplicate-code
    plugin_app = {
        'settings_config': {
            'lms.djangoapp': {
                'production': {
                    'relative_path': 'settings.common_production',
                }
            }
        },

        'url_config': {
            'lms.djangoapp': {
                'namespace': 'zeitlabs_payments',
            },
        },
    }
    # pylint: enable=duplicate-code
