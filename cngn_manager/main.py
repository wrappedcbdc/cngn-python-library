#   ____ _   _  ____       __  __                                   
#  / ___| \ | |/ ___|_ __ |  \/  | __ _ _ __   __ _  __ _  ___ _ __ 
# | |   |  \| | |  _| '_ \| |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
# | |___| |\  | |_| | | | | |  | | (_| | | | | (_| | (_| |  __/ |   
#  \____|_| \_|\____|_| |_|_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|   
#                                                   |___/           
# 


import json
from typing import Optional, Dict, Any
import requests
from requests.exceptions import RequestException, HTTPError
from .AESCrypto import AESCrypto
from .Ed25519Crypto import Ed25519Crypto

"""
    CNGnManager class is a wrapper around the CNGn API.
    It provides methods to interact with the CNGn API endpoints.
    It uses the requests library to make HTTP requests to the API.
    It uses the AESCrypto and Ed25519Crypto classes to encrypt and decrypt data.
    It handles API errors and returns appropriate error messages.
    It returns JSON responses from the API.
"""

class CNGnManager:
    API_URL = "https://api.cngn.co"
    API_CURRENT_VERSION = "v1"

    def __init__(self, api_key: str, private_key: str, encryption_key: str):
        self.api_key = api_key
        self.api_url = self.API_URL
        self.private_key = private_key
        self.encryption_key = encryption_key
        self.client = requests.Session()
        self.client.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def __make_calls(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        aes_crypto = AESCrypto()
        ed_crypto = Ed25519Crypto()

        try:
            url = f'{self.api_url}/{self.API_CURRENT_VERSION}/api{endpoint}'
            request_data = self._prepare_request_data(data, aes_crypto)
            response = self._send_request(method, url, request_data)
            return self._process_response(response, ed_crypto)

        except (RequestException, HTTPError) as e:
            return self._handle_request_error(e)
        except Exception as e:
            return self._handle_unexpected_error(e)

    def _prepare_request_data(self, data: Optional[Dict[str, Any]], aes_crypto: AESCrypto) -> Optional[str]:
        if data is None:
            return None
        json_data = json.dumps(data)
        return aes_crypto.encrypt(json_data, self.encryption_key)

    def _send_request(self, method: str, url: str, data: Optional[str]) -> requests.Response:
        return self.client.request(method, url, json=data)

    def _process_response(self, response: requests.Response, ed_crypto: Ed25519Crypto) -> Dict[str, Any]:
        response_data = response.json()
        if "data" in response_data:
            decrypted_response = ed_crypto.decrypt_with_private_key(self.private_key, response_data["data"])
            response_data["data"] = json.loads(decrypted_response)
        return response_data

    def _handle_request_error(self, error: RequestException) -> Dict[str, Any]:
        if error.response:
            return error.response.json()
        return {
            'success': False,
            'error': 'API request failed',
            'message': str(error),
            'status_code': error.response.status_code if error.response else None,
        }

    def _handle_unexpected_error(self, error: Exception) -> Dict[str, Any]:
        return {
            'success': False,
            'error': 'An unexpected error occurred',
            'message': str(error),
            'status_code': 500,
        }
    
    def get_balance(self) -> str:
        return self.__make_calls("GET", "/balance")

    def get_transaction_history(self, page: int = 1, limit: int = 10 ) -> str:
        return self.__make_calls("GET", f"/transactions?page{page}&limit={limit}")

    def withdraw(self, data: dict) -> str:
        return self.__make_calls("POST", "/withdraw", data)

    def redeem_assets(self, data: dict) -> str:
        return self.__make_calls("POST", "/redeemAsset", data)

    def create_virtual_account(self, data: dict) -> str:
        return self.__make_calls("POST", "/createVirtualAccount", data)

    def update_external_accounts(self, data: dict) -> str:
        return self.__make_calls("POST", "/updateBusiness", data)

    def get_banks(self):
        return self.__make_calls("GET", "/banks")
    
    def swap_asset(self, data: dict) -> str:
        return self.__make_calls("POST", "/swap", data)
    
