import json
import os
import time
import getpass
from threading import Thread

from sshtunnel import SSHTunnelForwarder

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'ssh_config.json')


class SSHTunnelManager:
    def __init__(self, config):
        self.config = config
        self.tunnel = None

    def _connect(self):
        try:
            if self.tunnel:
                self.tunnel.stop()
            params = {
                'ssh_address_or_host': (self.config['host'], self.config.get('port', 22)),
                'ssh_username': self.config['username'],
                'remote_bind_address': ('127.0.0.1', self.config['remote_bind_port']),
                'local_bind_address': ('0.0.0.0', self.config.get('local_bind_port', self.config['remote_bind_port'])),
            }
            if self.config.get('password'):
                params['ssh_password'] = self.config['password']
            elif self.config.get('key_path'):
                params['ssh_pkey'] = self.config['key_path']
            self.tunnel = SSHTunnelForwarder(**params)
            self.tunnel.start()
            print('SSH tunnel established')
        except Exception as e:
            print(f'Failed to establish SSH tunnel: {e}')
            self.tunnel = None

    def _monitor(self):
        while True:
            if not self.tunnel or not self.tunnel.is_active:
                print('SSH tunnel disconnected, reconnecting...')
                self._connect()
            time.sleep(5)

    def start(self):
        self._connect()
        Thread(target=self._monitor, daemon=True).start()


def _load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def _save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


def _prompt_config():
    host = input('SSH Host (IP/domain): ').strip()
    port = input('SSH Port [22]: ').strip() or '22'
    username = input('SSH Username: ').strip()
    use_key = input('Use private key? (y/N): ').strip().lower() == 'y'
    key_path = None
    password = None
    if use_key:
        key_path = input('Path to private key: ').strip()
    else:
        password = getpass.getpass('SSH Password: ')
    remote_port = input('Remote port to forward: ').strip()
    local_port = input('Local bind port [{}]: '.format(remote_port)).strip() or remote_port
    return {
        'host': host,
        'port': int(port),
        'username': username,
        'password': password,
        'key_path': key_path,
        'remote_bind_port': int(remote_port),
        'local_bind_port': int(local_port)
    }


def ensure_tunnel():
    config = _load_config()
    if not config:
        print('SSH tunnel configuration not found. Setup...')
        config = _prompt_config()
        _save_config(config)
    manager = SSHTunnelManager(config)
    manager.start()
    return manager
