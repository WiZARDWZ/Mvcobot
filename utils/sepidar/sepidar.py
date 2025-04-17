## utils/sepidar/configuration.py
from urllib import parse

class Configuration:
    def __init__(self, base_url: str, api_version: str):
        self._base_url = base_url
        self._generation_version = api_version

    def get_absolute_url(self, endpoint: str) -> str:
        return parse.urljoin(self._base_url, endpoint)

    def create_headers(self) -> dict:
        return {
            'GenerationVersion': self._generation_version,
        }


## utils/sepidar/crypto_helper.py
from base64 import b64encode, b64decode
from xml.etree.ElementTree import fromstring
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.Hash import MD5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad, unpad


def aes_encrypt(key: str, plain_text: str) -> dict:
    key_bytes = key.encode('utf-8')
    data = plain_text.encode('utf-8')
    cipher = AES.new(key_bytes, AES.MODE_CBC)
    encrypted = cipher.encrypt(pad(data, AES.block_size))
    return {
        'iv': b64encode(cipher.iv).decode('utf-8'),
        'cipher': b64encode(encrypted).decode('utf-8')
    }


def rsa_encrypt(public_key_xml: str, plain_bytes: bytes) -> bytes:
    xml = fromstring(public_key_xml)
    modulus = int.from_bytes(b64decode(xml.find('Modulus').text.strip()), byteorder='big')
    exponent = int.from_bytes(b64decode(xml.find('Exponent').text.strip()), byteorder='big')
    key = RSA.construct((modulus, exponent))
    encryptor = PKCS1_v1_5.new(key)
    return encryptor.encrypt(plain_bytes)


def md5_hash(text: str) -> str:
    hasher = MD5.new()
    hasher.update(text.encode('utf-8'))
    return hasher.hexdigest()


## utils/sepidar/devices_service.py
import base64
from uuid import uuid4
import requests
from .crypto_helper import aes_encrypt, rsa_encrypt

class DevicesService:
    def __init__(self, config: Configuration, registration_code: str):
        self._config = config
        self._registration_code = registration_code
        self._integration_id = registration_code[:4]
        self._public_key_xml = ''
        self.device_title = ''

    def register(self):
        url = self._config.get_absolute_url('/api/Devices/Register/')
        aes_key = self._registration_code * 2
        encrypted = aes_encrypt(aes_key, self._integration_id)
        payload = {
            'IntegrationID': int(self._integration_id),
            'Cypher': encrypted['cipher'],
            'IV': encrypted['iv']
        }
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Decrypt the public RSA key from server
        raw = base64.b64decode(data['Cypher'])
        iv = data['IV']
        # AES decrypt to get RSAKeyValue XML
        from .crypto_helper import aes_encrypt, pad, unpad, AES
        # Simplest: server returns RSAKeyValue plaintext in data['Cypher'] using same aes_key & IV
        aes_cipher = AES.new(aes_key.encode(), AES.MODE_CBC, base64.b64decode(iv))
        plaintext = unpad(aes_cipher.decrypt(b64decode(data['Cypher'])), AES.block_size)
        self._public_key_xml = plaintext.decode('utf-8')
        self.device_title = data.get('DeviceTitle', '')

    def create_headers(self) -> dict:
        headers = self._config.create_headers()
        headers['IntegrationID'] = self._integration_id
        arb = str(uuid4())
        headers['ArbitraryCode'] = arb
        enc = rsa_encrypt(self._public_key_xml, arb.encode('utf-8'))
        headers['EncArbitraryCode'] = base64.b64encode(enc).decode('utf-8')
        return headers


## utils/sepidar/users_service.py
import requests
from .crypto_helper import md5_hash

class UsersService:
    def __init__(self, device_service: DevicesService):
        self._device = device_service
        self._token = ''
        self.user_title = ''

    def login(self, username: str, password: str):
        url = self._device._config.get_absolute_url('/api/users/login/')
        headers = self._device.create_headers()
        payload = {
            'UserName': username,
            'PasswordHash': md5_hash(password)
        }
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        self._token = data['Token']
        self.user_title = data.get('Title', '')

    def create_headers(self) -> dict:
        headers = self._device.create_headers()
        if self._token:
            headers['Authorization'] = f"Bearer {self._token}"
        return headers


## utils/sepidar/invoices_service.py
import requests

class InvoicesService:
    def __init__(self, user_service: UsersService):
        self._user = user_service

    def get_invoices(self):
        url = self._user._device._config.get_absolute_url('/api/Invoices/')
        headers = self._user.create_headers()
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


# In your config.py, add:
# BASE_URL = 'http://localhost:8585'
# API_VERSION = '1.0.0'
# REGISTRATION_CODE = '10054425'
# USERNAME = 'mvcobot'
# PASSWORD = '001212'

# Then in handlers/reg.py and handlers/invoice.py, import and use these services accordingly.
