#   ____ _   _  ____       __  __                                   
#  / ___| \ | |/ ___|_ __ |  \/  | __ _ _ __   __ _  __ _  ___ _ __ 
# | |   |  \| | |  _| '_ \| |\/| |/ _` | '_ \ / _` |/ _` |/ _ \ '__|
# | |___| |\  | |_| | | | | |  | | (_| | | | | (_| | (_| |  __/ |   
#  \____|_| \_|\____|_| |_|_|  |_|\__,_|_| |_|\__,_|\__, |\___|_|   
#                                                   |___/           
# 


import requests # type: ignore
import json
from cngn_manager.AESCrypto import AESCrypto
from cngn_manager.Ed25519Crypto import Ed25519Crypto

"""
    CNGnManager class is a wrapper around the CNGn API.
    It provides methods to interact with the CNGn API endpoints.
    It uses the requests library to make HTTP requests to the API.
    It uses the AESCrypto and Ed25519Crypto classes to encrypt and decrypt data.
    It handles API errors and returns appropriate error messages.
    It returns JSON responses from the API.
"""

class CNGnManager:
    API_URL = "https://staging.api.wrapcbdc.com"
    API_CURRENT_VERSION = "v1"

    def __init__(self, api_key: str, private_key: str, encryption_key: str):
        self.api_key = api_key
        self.private_key = private_key
        self.encryption_key = encryption_key
        self.client = requests.Session()
        self.client.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def handle_api_error(self, error):
        # Handle the API error
        pass

    def __make_calls(self, method: str, endpoint: str, data: dict = None) -> str:


        aes_crypto = AESCrypto()
        ed_crypto = Ed25519Crypto()

        try:
            if data is not None:
                new_data = json.dumps(data)
                encrypted_data = aes_crypto.encrypt(new_data, self.encryption_key)
                data = encrypted_data
                response = self.client.request(method, f'{self.API_URL}/{self.API_CURRENT_VERSION}{endpoint}', json=data)
            else:
                response = self.client.request(method, f'{self.API_URL}/{self.API_CURRENT_VERSION}{endpoint}')

            response_data = response.json()

            if response_data.get("data") is not None:                
                decrypted_response = ed_crypto.decrypt_with_private_key(self.private_key, response_data["data"])
                response_data["data"] = json.loads(decrypted_response)

            return json.dumps(response_data)

        except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
            error_body = {
                'success': False,
                'error': 'API request failed',
                'message': str(e),
                'status_code': e.response.status_code if e.response else None,
            }

            if e.response:
                resp = e.response.json()
                message = json.loads(resp.get('message', '{}'))
                resp["message"] = message
                return json.dumps(resp)

            return json.dumps(error_body)

        except Exception as e:
            return json.dumps({
                'success': False,
                'error': 'An unexpected error occurred',
                'message': str(e.message if hasattr(e, 'message') else str(e)),
                'status_code': 500,
            })

    def get_balance(self) -> str:
        return self.__make_calls("GET", "/api/balance")

    def get_transaction_history(self) -> str:
        return self.__make_calls("GET", "/api/transactions")

    def swap_between_chains(self, data: dict) -> str:
        return self.__make_calls("POST", "/api/swap", data)

    def deposit_for_redemption(self, data: dict) -> str:
        return self.__make_calls("POST", "/api/deposit", data)

    def create_virtual_account(self, data: dict) -> str:
        return self.__make_calls("POST", "/api/createVirtualAccount", data)

    def whitelist_address(self, data: dict) -> str:
        return self.__make_calls("POST", "/api/whiteListAddress", data)
