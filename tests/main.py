import unittest
from unittest.mock import patch, MagicMock
from cngn_manager import CNGnManager
import json
from cngn_manager.AESCrypto import AESCrypto 
from cngn_manager.Ed25519Crypto import Ed25519Crypto

from nacl.public import PrivateKey, PublicKey, Box
from requests.exceptions import RequestException, HTTPError

class TestCNGnManager(unittest.TestCase):

    def setUp(self):
        # Initialize CNGnManager with test data
        self.api_key = "test_api_key"
        self.private_key = "test_private_key"
        self.encryption_key = "test_encryption_key"
        self.manager = CNGnManager(self.api_key, self.private_key, self.encryption_key)

    @patch('requests.Session')
    def test_init(self, mock_session):
        # Test the initialization of CNGnManager
        manager = CNGnManager(self.api_key, self.private_key, self.encryption_key)
        self.assertEqual(manager.api_key, self.api_key)
        self.assertEqual(manager.api_url, CNGnManager.API_URL)
        mock_session.assert_called_once()

    @patch.object(AESCrypto, 'encrypt', return_value="encrypted_data")
    @patch.object(Ed25519Crypto, 'decrypt_with_private_key', return_value='{"decrypted":"data"}')
    @patch('requests.Session.request')
    def test_make_calls_success(self, mock_request, mock_decrypt, mock_encrypt):
        # Mock the response from the API
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "encrypted_response_data"}
        mock_request.return_value = mock_response

        # Test a successful GET call
        result = self.manager.get_balance()
        
        # Verify that encryption, request, and decryption were called
        mock_encrypt.assert_called_once_with(json.dumps(None), self.encryption_key)
        mock_request.assert_called_once_with('GET', f'{self.manager.api_url}/v1/api/balance', json="encrypted_data")
        mock_decrypt.assert_called_once_with(self.private_key, "encrypted_response_data")

        # Verify the response is properly decrypted
        self.assertEqual(result, {"data": {"decrypted": "data"}})

    @patch.object(AESCrypto, 'encrypt', return_value="encrypted_data")
    @patch.object(Ed25519Crypto, 'decrypt_with_private_key')
    @patch('requests.Session.request', side_effect=RequestException("API request failed"))
    def test_make_calls_request_error(self, mock_request, mock_decrypt, mock_encrypt):
        # Test handling of request exceptions
        result = self.manager.get_balance()
        
        # Verify that the request error is handled properly
        self.assertEqual(result['success'], False)
        self.assertEqual(result['error'], 'API request failed')
        self.assertEqual(result['message'], 'API request failed')

    @patch.object(AESCrypto, 'encrypt', return_value="encrypted_data")
    @patch('requests.Session.request', side_effect=HTTPError(response=MagicMock(status_code=500)))
    def test_make_calls_http_error(self, mock_request, mock_encrypt):
        # Test handling of HTTP errors
        result = self.manager.get_balance()
        
        # Verify that HTTPError is handled properly
        self.assertEqual(result['success'], False)
        self.assertEqual(result['error'], 'API request failed')
        self.assertEqual(result['status_code'], 500)

    @patch.object(AESCrypto, 'encrypt', side_effect=Exception("Unexpected error"))
    def test_make_calls_unexpected_error(self, mock_encrypt):
        # Test handling of unexpected errors
        result = self.manager.get_balance()
        
        # Verify that unexpected errors are handled properly
        self.assertEqual(result['success'], False)
        self.assertEqual(result['error'], 'An unexpected error occurred')
        self.assertEqual(result['message'], 'Unexpected error')
        self.assertEqual(result['status_code'], 500)

    @patch.object(AESCrypto, 'encrypt', return_value="encrypted_data")
    @patch.object(Ed25519Crypto, 'decrypt_with_private_key', return_value='{"decrypted":"data"}')
    @patch('requests.Session.request')
    def test_post_calls(self, mock_request, mock_decrypt, mock_encrypt):
        # Mock the response from the API
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "encrypted_response_data"}
        mock_request.return_value = mock_response

        # Test a POST call
        data = {"test": "data"}
        result = self.manager.swap_between_chains(data)

        # Verify that encryption, request, and decryption were called
        mock_encrypt.assert_called_once_with(json.dumps(data), self.encryption_key)
        mock_request.assert_called_once_with('POST', f'{self.manager.api_url}/v1/api/swap', json="encrypted_data")
        mock_decrypt.assert_called_once_with(self.private_key, "encrypted_response_data")

        # Verify the response is properly decrypted
        self.assertEqual(result, {"data": {"decrypted": "data"}})

    def test_prepare_request_data(self):
        aes_crypto = AESCrypto()

        # Test with data
        data = {"test": "data"}
        encrypted_data = self.manager._prepare_request_data(data, aes_crypto)
        self.assertIsNotNone(encrypted_data)

        # Test with no data
        encrypted_data = self.manager._prepare_request_data(None, aes_crypto)
        self.assertIsNone(encrypted_data)

    def test_handle_request_error(self):
        error = RequestException("Request failed")
        result = self.manager._handle_request_error(error)
        self.assertEqual(result['success'], False)
        self.assertEqual(result['error'], 'API request failed')
        self.assertEqual(result['message'], 'Request failed')

    def test_handle_unexpected_error(self):
        error = Exception("Something went wrong")
        result = self.manager._handle_unexpected_error(error)
        self.assertEqual(result['success'], False)
        self.assertEqual(result['error'], 'An unexpected error occurred')
        self.assertEqual(result['message'], 'Something went wrong')
        self.assertEqual(result['status_code'], 500)

if __name__ == '__main__':
    unittest.main()
