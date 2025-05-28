"""Test zeitlabs payment sertializers."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from zeitlabs_payments.models import Cart, CartItem, CatalogueItem
from zeitlabs_payments.serializers import CartItemSerializer, CartSerializer, CourseSerializer


@pytest.mark.django_db
@patch('zeitlabs_payments.serializers.relative_url_to_absolute_url')
def test_course_serializer_course_image_exception(mock_relative_url):
    course = CourseOverview.objects.get(id='course-v1:org1+1+1')
    mock_request = MagicMock(scheme='https', site=MagicMock(domain='example.com'))
    mock_relative_url.side_effect = ValueError('something went wrong')

    serializer = CourseSerializer(instance=course, context={'request': mock_request})
    data = serializer.data
    assert data['course_id'] == 'course-v1:org1+1+1'
    assert data['course_name'] == 'Custom Course 1 of org1'
    assert data['course_image'] is None


@pytest.mark.django_db
def test_cart_item_serializer_for_paid_course_type_and_invalid_ref_id(base_data):  # pylint: disable=unused-argument
    user = get_user_model().objects.get(id=3)
    course_item = CatalogueItem.objects.get(sku='custom-sku-with_invlaid_ref_id')
    cart = Cart.objects.create(user=user, status=Cart.Status.PENDING)
    cart.items.create(
        catalogue_item=course_item,
        original_price=course_item.price,
        final_price=course_item.price
    )
    with pytest.raises(Exception) as exc:
        _ = CartSerializer(instance=cart).data
    assert str(exc.value) == 'Catalogue item of type: paid_course must be linked with course_id.'


@pytest.mark.django_db
def test_get_courses_raises_if_catalogue_item_type_unsupported():
    catalogue_item = MagicMock()
    catalogue_item.type = 'UNSUPPORTED_TYPE'
    catalogue_item.item_ref_id = 'abc123'
    cart_item = MagicMock(spec=CartItem)
    cart_item.catalogue_item = catalogue_item
    serializer = CartItemSerializer(instance=cart_item, context={})
    with pytest.raises(Exception) as exc_info:
        serializer.get_courses(cart_item)
    assert 'Unsupported catalogue item type' in str(exc_info.value)


@pytest.mark.django_db
def test_cart_serializer_returns_serialized_items(base_data):  # pylint: disable=unused-argument
    user = get_user_model().objects.get(id=3)
    course_item = CatalogueItem.objects.get(sku='custom-sku-1')
    cart = Cart.objects.create(user=user, status=Cart.Status.PENDING)
    cart.items.create(
        catalogue_item=course_item,
        original_price=course_item.price,
        final_price=course_item.price
    )
    serializer = CartSerializer(instance=cart)
    data = serializer.data
    assert data['id'] == cart.id
    assert data['user'] == user.id
    assert data['status'] == Cart.Status.PENDING
    assert data['total'] == course_item.price
    assert isinstance(data['items'], list)
    assert len(data['items']) == 1
    assert data['items'][0]['sku'] == 'custom-sku-1'
    assert data['items'][0]['type'] == course_item.type
    assert data['items'][0]['currency'] == course_item.currency
    assert data['items'][0]['original_price'] == str(course_item.price)
    assert data['items'][0]['final_price'] == str(course_item.price)
    assert data['items'][0]['courses'][0]['course_id'] == 'course-v1:org1+1+1'
    assert data['items'][0]['courses'][0]['course_name'] == 'Custom Course 1 of org1'
