# handlers/reg.py
from utils.sepidar.Configuration import Configuration
from utils.sepidar.DevicesService import DevicesService
from utils.sepidar.UsersService import UsersService
import config

config_obj = Configuration(config.BASE_URL, config.API_VERSION)
device = DevicesService(config_obj, config.REGISTRATION_CODE)
device.register()
print("✅ Device Registered:", device.DeviceName)

user = UsersService(device)
user.login(config.USERNAME, config.PASSWORD)
print("✅ Logged in as:", user.UserTitle)
