# utils/sepidar/ItemsService.py
import requests
from .UsersService import UsersService

class ItemsService:
    def __init__(self, user: UsersService):
        self._user = user

    def get_items(self):
        headers = self._user.create_headers()
        url = self._user._device._config.get_absolute_url('/api/items')
        response = requests.get(url, headers=headers)

        if response.status_code in (200, 201):
            return response.json()
        else:
            raise Exception(response.json()['Message'])
