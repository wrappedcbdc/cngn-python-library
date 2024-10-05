import unittest
from unittest.mock import patch, MagicMock
from cngn_manager.main import CNGnManager
import json
import requests

class TestCNGnManager(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.private_key = "test_private_key"
        self.encryption_key = "test_encryption_key"
        self.manager = CNGnManager(self.api_key, self.private_key, self.encryption_key)

    def test_init(self):
        self.assertEqual(self.manager.api_key, self.api_key)
        self.assertEqual(self.manager.private_key, self.private_key)
        self.assertEqual(self.manager.encryption_key, self.encryption_key)
        self.assertIsInstance(self.manager.client, requests.Session)
        self.assertEqual(self.manager.client.headers['Authorization'], f'Bearer {self.api_key}')
        self.assertEqual(self.manager.client.headers['Content-Type'], 'application/json')
        self.assertEqual(self.manager.client.headers['Accept'], 'application/json')

    @patch('cngn_manager.AESCrypto')
    @patch('cngn_manager.Ed25519Crypto')
    @patch('requests.Session.request')
    def test_make_calls_success_with_data(self, mock_request, mock_ed_crypto, mock_aes_crypto):
        mock_aes_crypto.return_value.encrypt.return_value = "encrypted_data"
        mock_request.return_value.json.return_value = {"data": "encrypted_response"}
        mock_ed_crypto.return_value.decrypt_with_private_key.return_value = '{"key": "value"}'

        result = self.manager._CNGnManager__make_calls("POST", "/test", {"test": "data"})
        
        self.assertEqual(json.loads(result), {"data": {"key": "value"}})
        mock_request.assert_called_once()
        mock_aes_crypto.return_value.encrypt.assert_called_once()
        mock_ed_crypto.return_value.decrypt_with_private_key.assert_called_once()

    @patch('requests.Session.request')
    def test_make_calls_success_without_data(self, mock_request):
        mock_request.return_value.json.return_value = {"success": True}

        result = self.manager._CNGnManager__make_calls("GET", "/test")
        
        self.assertEqual(json.loads(result), {"success": True})
        mock_request.assert_called_once()

    @patch('requests.Session.request')
    def test_make_calls_http_error(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": '{"error": "Test error"}'}
        mock_response.status_code = 400
        mock_request.side_effect = requests.exceptions.HTTPError(response=mock_response)

        result = self.manager._CNGnManager__make_calls("GET", "/test")
        
        self.assertEqual(json.loads(result), {"message": {"error": "Test error"}})

    @patch('requests.Session.request')
    def test_make_calls_request_exception(self, mock_request):
        mock_request.side_effect = requests.exceptions.RequestException("Test exception")

        result = self.manager._CNGnManager__make_calls("GET", "/test")
        
        self.assertEqual(json.loads(result), {
            'success': False,
            'error': 'API request failed',
            'message': 'Test exception',
            'status_code': None,
        })

    @patch('requests.Session.request')
    def test_make_calls_unexpected_exception(self, mock_request):
        mock_request.side_effect = Exception("Unexpected error")

        result = self.manager._CNGnManager__make_calls("GET", "/test")
        
        self.assertEqual(json.loads(result), {
            'success': False,
            'error': 'An unexpected error occurred',
            'message': 'Unexpected error',
            'status_code': 500,
        })

    @patch.object(CNGnManager, '_CNGnManager__make_calls')
    def test_get_balance(self, mock_make_calls):
        self.manager.get_balance()
        mock_make_calls.assert_called_once_with("GET", "/api/balance")

    @patch.object(CNGnManager, '_CNGnManager__make_calls')
    def test_get_transaction_history(self, mock_make_calls):
        self.manager.get_transaction_history()
        mock_make_calls.assert_called_once_with("GET", "/api/transactions")

    @patch.object(CNGnManager, '_CNGnManager__make_calls')
    def test_swap_between_chains(self, mock_make_calls):
        data = {"amount": 100}
        self.manager.swap_between_chains(data)
        mock_make_calls.assert_called_once_with("POST", "/api/swap", data)

    @patch.object(CNGnManager, '_CNGnManager__make_calls')
    def test_deposit_for_redemption(self, mock_make_calls):
        data = {"amount": 100}
        self.manager.deposit_for_redemption(data)
        mock_make_calls.assert_called_once_with("POST", "/api/deposit", data)

    @patch.object(CNGnManager, '_CNGnManager__make_calls')
    def test_create_virtual_account(self, mock_make_calls):
        data = {"name": "Test Account"}
        self.manager.create_virtual_account(data)
        mock_make_calls.assert_called_once_with("POST", "/api/createVirtualAccount", data)

    @patch.object(CNGnManager, '_CNGnManager__make_calls')
    def test_whitelist_address(self, mock_make_calls):
        data = {"address": "0x1234567890"}
        self.manager.whitelist_address(data)
        mock_make_calls.assert_called_once_with("POST", "/api/whiteListAddress", data)

if __name__ == '__main__':
    unittest.main()
