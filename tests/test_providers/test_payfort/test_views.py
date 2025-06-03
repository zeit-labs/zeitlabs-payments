"""Test views for the zeitlabs_payment payfort provider"""
from unittest.mock import patch

import pytest
from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.test import RequestFactory, TestCase
from django.urls import reverse

from zeitlabs_payments.models import Cart, CatalogueItem, Transaction
from zeitlabs_payments.providers.payfort.exceptions import PayFortException
from zeitlabs_payments.providers.payfort.views import PayfortFeedbackView

User = get_user_model()


@pytest.mark.usefixtures('base_data')
class PayfortFeedbackTestView(TestCase):
    """Payfort feedback test case."""

    def setUp(self) -> None:
        """
        Set up test data for the Payfort feedback tests.

        :return: None
        """
        self.user = User.objects.get(id=3)
        self.cart = Cart.objects.create(user=self.user, status=Cart.Status.PROCESSING)
        self.course_mode = CourseMode.objects.get(sku='custom-sku-1')
        self.course_item = CatalogueItem.objects.get(sku='custom-sku-1')
        self.cart.items.create(
            catalogue_item=self.course_item,
            original_price=self.course_item.price,
            final_price=self.course_item.price,
        )
        self.site = Site.objects.create(name='test.com', domain='test.com')
        self.provider = 'payfort'
        self.url = reverse('zeitlabs_payments:payfort-feedback')

        self.valid_response = {
            'amount': '150',
            'response_code': '14000',
            'acquirer_response_message': 'Success',
            'card_number': '411111******1111',
            'card_holder_name': 'Tehreem',
            'signature': '141ae3d36be4f7f50cefbb966b26c8ee073a84dd32d99eec3084d19efb247895',
            'merchant_identifier': 'abcdi',
            'access_code': 'm6ScifP9737ykbx31Z7i',
            'order_description': 'some order description',
            'payment_option': 'VISA',
            'expiry_date': '2511',
            'customer_ip': '101.53.219.17',
            'language': 'en',
            'eci': 'ECOMMERCE',
            'fort_id': '169996200024611493',
            'command': 'PURCHASE',
            'response_message': 'Success',
            'merchant_reference': f'{self.site.id}-{self.cart.id}',
            'authorization_code': '742138',
            'customer_email': 'tehreemsadat19@gmail.com',
            'currency': 'SAR',
            'acquirer_response_code': '00',
            'status': '14',
        }
        self.request_factory = RequestFactory()

    def test_post_for_invalid_cart_in_merchant_ref(self) -> None:
        """
        Test that posting with an invalid cart ID in merchant_reference raises PayFortException.

        :return: None
        """
        data = self.valid_response.copy()
        data.update({'merchant_reference': '1-10000'})
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        with pytest.raises(PayFortException) as excinfo:
            PayfortFeedbackView.as_view()(request)
        assert str(excinfo.value) == 'Cart with id: 10000 does not exist.', \
            'Expected exception for invalid cart ID'

    def test_post_for_invalid_site_in_merchant_ref(self) -> None:
        """
        Test that posting with an invalid site ID in merchant_reference raises PayFortException.

        :return: None
        """
        data = self.valid_response.copy()
        data.update({'merchant_reference': f'10000-{self.cart.id}'})
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        with pytest.raises(PayFortException) as excinfo:
            PayfortFeedbackView.as_view()(request)
        assert str(excinfo.value) == 'Site with id: 10000 does not exist.', \
            'Expected exception for invalid site ID'

    def test_post_for_cart_not_in_processing_state(self) -> None:
        """
        Test that posting with a cart not in PROCESSING state raises PayFortException.

        :return: None
        """
        self.cart.status = Cart.Status.PENDING
        self.cart.save()
        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        with pytest.raises(PayFortException) as excinfo:
            PayfortFeedbackView.as_view()(request)
        expected_msg = (f'Cart with id: {self.cart.id} is not in {Cart.Status.PROCESSING} state. '
                        f'State found: {self.cart.status}')
        assert str(excinfo.value) == expected_msg, \
            'Expected exception for cart not in processing state'

    @patch('zeitlabs_payments.providers.payfort.views.render')
    def test_post_for_unsuccessful_payment(self, mock_render) -> None:
        """
        Test handling of unsuccessful payment status.

        :param mock_render: mocked render function
        :return: None
        """
        data = self.valid_response.copy()
        data.update({'status': '20'})
        request = self.request_factory.post(self.url, data)
        request.user = self.user
        PayfortFeedbackView.as_view()(request)
        mock_render.assert_called_with(request, 'zeitlabs_payments/payment_unsuccessful.html')

    @patch('zeitlabs_payments.providers.payfort.views.render')
    @patch('zeitlabs_payments.providers.payfort.views.logger.error')
    def test_post_for_success_payment_enroll_error_no_course_mode(
        self, mock_logger, mock_render
    ) -> None:
        """
        Test successful payment but course mode missing, triggers error logging and error page.

        :param mock_logger: mocked logger.error function
        :param mock_render: mocked render function
        :return: None
        """
        assert not Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should not exist before test'
        assert self.cart.status == Cart.Status.PROCESSING, \
            'Cart should be in PROCESSING state'

        self.course_mode.delete()  # delete course mode for cart item
        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        PayfortFeedbackView.as_view()(request)

        assert Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should exist after payment'
        self.cart.refresh_from_db()
        assert self.cart.status == Cart.Status.PAID, \
            'Cart status should be PAID after successful payment'

        mock_logger.assert_called_with(
            f'CourseMode not found for SKU: {self.course_item.sku} - Item ID: {self.course_item.id}'
        )
        mock_render.assert_called_with(request, 'zeitlabs_payments/payment_error.html')

    @patch('zeitlabs_payments.providers.payfort.views.render')
    @patch('zeitlabs_payments.providers.payfort.views.logger.exception')
    @patch('zeitlabs_payments.providers.payfort.views.CourseEnrollment.enroll')
    def test_post_for_success_payment_paid_course_with_unsuccessful_enrollment(
        self, mock_enroll, mock_logger, mock_render
    ) -> None:
        """
        Test payment success but enrollment fails, logs exception and shows error page.

        :param mock_enroll: mocked CourseEnrollment.enroll method
        :param mock_logger: mocked logger.exception function
        :param mock_render: mocked render function
        :return: None
        """
        mock_enroll.side_effect = Exception('Unexpected error during enrollment')
        assert not Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should not exist before test'
        assert self.cart.status == Cart.Status.PROCESSING, \
            'Cart should be in PROCESSING state'

        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        PayfortFeedbackView.as_view()(request)

        assert Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should exist after payment'
        self.cart.refresh_from_db()
        assert self.cart.status == Cart.Status.PAID, \
            'Cart status should be PAID after successful payment'

        mock_logger.assert_called_with(
            f'Unexpected error while enrolling user {self.cart.user.id} in course: '
            f'{self.course_mode.course.id}. Item ID: {self.cart.items.all()[0].id}'
        )
        mock_render.assert_called_with(request, 'zeitlabs_payments/payment_error.html')

    @patch('zeitlabs_payments.providers.payfort.views.render')
    def test_post_for_successful_payment(self, mock_render) -> None:
        """
        Test the full successful payment flow and enrollment.

        :param mock_render: mocked render function
        :return: None
        """
        assert not Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should not exist before test'
        assert self.cart.status == Cart.Status.PROCESSING, \
            'Cart should be in PROCESSING state'
        assert not CourseEnrollment.objects.filter(
            user=self.cart.user, course=self.course_mode.course
        ).exists(), 'User should not be enrolled before test'

        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        PayfortFeedbackView.as_view()(request)

        assert Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should exist after payment'
        self.cart.refresh_from_db()
        assert self.cart.status == Cart.Status.PAID, \
            'Cart status should be PAID after payment'
        assert CourseEnrollment.objects.filter(
            user=self.cart.user, course=self.course_mode.course
        ).exists(), 'User should be enrolled after payment'

        mock_render.assert_called_with(
            request, 'zeitlabs_payments/payment_successful.html', {'cart': self.cart, 'site': self.site}
        )

    @patch('zeitlabs_payments.providers.payfort.views.render')
    @patch('zeitlabs_payments.providers.payfort.views.logger.exception')
    def test_post_for_success_payment_cart_with_unsupported_item(
        self, mock_logger, mock_render
    ) -> None:
        """
        Test successful payment but cart contains unsupported item, triggers error logging.

        :param mock_logger: mocked logger.exception function
        :param mock_render: mocked render function
        :return: None
        """
        assert not Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should not exist before test'
        assert self.cart.status == Cart.Status.PROCESSING, \
            'Cart should be in PROCESSING state'
        unsupported_item = CatalogueItem.objects.create(sku='abcd', type='unsupported', price=50)
        self.cart.items.all().delete()
        self.cart.items.create(
            catalogue_item=unsupported_item,
            original_price=unsupported_item.price,
            final_price=unsupported_item.price,
        )

        request = self.request_factory.post(self.url, self.valid_response)
        request.user = self.user
        PayfortFeedbackView.as_view()(request)

        assert Transaction.objects.filter(gateway='payfort', cart=self.cart).exists(), \
            'Transaction should exist after payment'
        self.cart.refresh_from_db()
        assert self.cart.status == Cart.Status.PAID, \
            'Cart status should be PAID after payment'

        mock_logger.assert_called_with(
            f'Cart with id: {self.cart.id} contains unsupported catalogue item: '
            f'{unsupported_item.id} of type: {unsupported_item.type}'
        )
        mock_render.assert_called_with(request, 'zeitlabs_payments/payment_error.html')
