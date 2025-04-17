# Python 3
from Configuration import Configuration
from DevicesService import DevicesService
from ItemsService import ItemsService
from UsersService import UsersService

BASE_URL = 'http://localhost:7373/'
GENERATION_VERSION = '101'
REGISTRATION__CODE = '100593a0'
USERNAME = 'shop'
PASSWORD = '1'


def main():
    config = Configuration(BASE_URL, GENERATION_VERSION)

    device = DevicesService(config, REGISTRATION__CODE)
    device.register()
    print(f'Device Name: {device.DeviceName}')

    user = UsersService(device)
    user.login(USERNAME, PASSWORD)
    print(f'User Title: {user.UserTitle}')

    item_service = ItemsService(user)
    items = item_service.get_items()
    print('Items:')
    print(items)


if __name__ == '__main__':
    main()
