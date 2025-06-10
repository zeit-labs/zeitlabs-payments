"""Payfort helpers."""

import hashlib
import re
from typing import Any, Dict

from zeitlabs_payments.helpers import VALID_CURRENCY, verify_param
from zeitlabs_payments.providers.payfort.exceptions import PayFortBadSignatureException, PayFortException

MANDATORY_RESPONSE_FIELDS = [
    'merchant_reference',
    'command',
    'merchant_identifier',
    'amount',
    'currency',
    'response_code',
    'signature',
    'status',
]
MAX_ORDER_DESCRIPTION_LENGTH = 150
SUCCESS_STATUS = '14'
VALID_PATTERNS = {
    'order_description': r"[^A-Za-z0-9 '/\._\-#:$]",
    'customer_name': r"[^A-Za-z _\\/\-\.']",
}
SUPPORTED_SHA_METHODS = {
    'SHA-256': hashlib.sha256,
    'SHA-512': hashlib.sha512,
}


def get_signature(sha_phrase: str, sha_method: str, transaction_parameters: Dict[str, Any]) -> str:
    """
    Return the signature for the given transaction parameters.

    :param sha_phrase: The SHA phrase.
    :param sha_method: The SHA method.
    :param transaction_parameters: The transaction parameters.
    :return: The calculated signature.
    :raises PayFortException: If the SHA method is unsupported.
    """
    verify_param(sha_phrase, 'sha_phrase', str)
    verify_param(sha_method, 'sha_method', str)
    verify_param(transaction_parameters, 'transaction_parameters', dict)

    sha_method_fnc = SUPPORTED_SHA_METHODS.get(sha_method)
    if sha_method_fnc is None:
        raise PayFortException(f'Unsupported SHA method: {sha_method}')

    sorted_keys = sorted(transaction_parameters, key=lambda arg: arg.lower())
    sorted_dict = {key: transaction_parameters[key] for key in sorted_keys}

    result_string = f"{sha_phrase}{''.join(f'{key}={value}' for key, value in sorted_dict.items())}{sha_phrase}"

    return sha_method_fnc(result_string.encode()).hexdigest()


def verify_response_format(response_data: Dict[str, Any]) -> None:
    """
    Verify the format of the response from PayFort.

    :param response_data: The response data dictionary.
    :raises PayFortException: If any validation fails.
    """
    for field in MANDATORY_RESPONSE_FIELDS:
        if field not in response_data:
            raise PayFortException(f'Missing field in response: {field}')
        if not isinstance(response_data[field], str):
            raise PayFortException(
                f'Invalid field type in response: {field}. '
                f'Should be <str>, but got <{type(response_data[field]).__name__}>'
            )

    try:
        amount = int(response_data['amount'])
        if amount < 0 or response_data['amount'] != str(amount):
            raise ValueError
    except ValueError as exc:
        raise PayFortException(
            f'Invalid amount in response (not a positive integer): {response_data["amount"]}'
        ) from exc

    if response_data['currency'] != VALID_CURRENCY:
        raise PayFortException(f'Invalid currency in response: {response_data["currency"]}')

    if response_data['command'] != 'PURCHASE':
        raise PayFortException(f'Invalid command in response: {response_data["command"]}')

    if re.fullmatch(r'^\d+-\d+$', response_data['merchant_reference']) is None:
        raise PayFortException(
            f'Invalid merchant_reference in response: {response_data["merchant_reference"]}'
        )

    if (
        (response_data.get('eci') is None or response_data.get('fort_id') is None) and
        response_data['status'] == SUCCESS_STATUS
    ):
        raise PayFortException(
            f'Unexpected successful payment that lacks eci or fort_id: {response_data["merchant_reference"]}'
        )


def verify_signature(sha_phrase: str, sha_method: str, data: Dict[str, Any]) -> None:
    """
    Verify the data signature.

    :param sha_phrase: The SHA phrase.
    :param sha_method: The SHA method.
    :param data: The response data.
    :raises PayFortBadSignatureException: If signature is missing or invalid.
    :raises PayFortException: If SHA method is unsupported.
    """
    verify_param(data, 'response_data', dict)

    sha_method_fnc = SUPPORTED_SHA_METHODS.get(sha_method)
    if sha_method_fnc is None:
        raise PayFortException(f'Unsupported SHA method: {sha_method}')

    data = data.copy()
    signature = data.pop('signature', None)
    if signature is None:
        raise PayFortBadSignatureException('Signature not found!')

    expected_signature = get_signature(
        sha_phrase,
        sha_method,
        data,
    )
    if signature != expected_signature:
        raise PayFortBadSignatureException(
            f'Response signature mismatch. merchant_reference: {data.get("merchant_reference", "none")}'
        )
