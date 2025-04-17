# utils/sepidar/DevicesService.py
import requests
from base64 import b64decode
from .CryptoHelper import aes_encrypt, aes_decrypt, rsa_encrypt
from .Configuration import Configuration

class DevicesService:
    def __init__(self, config: Configuration, code: str):
        self._config = config
        self._registration_code = code
        self._integration_id = code[:4]
        self._public_key = ''
        self.DeviceName = ''

    def register(self):
        url = self._config.get_absolute_url('/api/Devices/Register/')
        aes_key = self._registration_code * 2
        encrypted_data = aes_encrypt(aes_key, self._integration_id)
        data = {
            'Cypher': encrypted_data['cipher'],
            'IV': encrypted_data['iv'],
            'IntegrationID': int(self._integration_id)
        }

        response = requests.post(url, json=data)
        if response.status_code in (200, 201):
            json = response.json()
            self._public_key = aes_decrypt(aes_key, json['Cypher'], json['IV'])
            self.DeviceName = json['DeviceTitle']
        else:
            raise Exception(response.json()['Message'])

    def create_headers(self):
        from uuid import uuid4
        headers = self._config.create_headers()
        headers['IntegrationID'] = self._integration_id
        uuid = uuid4()
        headers['ArbitraryCode'] = str(uuid)
        headers['EncArbitraryCode'] = b64encode(rsa_encrypt(self._public_key, uuid.bytes)).decode('utf-8')
        return headers
