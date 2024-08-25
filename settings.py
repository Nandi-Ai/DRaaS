import configparser 
import os

def init():
    global mid_server
    global username
    global password
    global config
    global url
    global switch_info_url
    config = configparser.ConfigParser()
    config.sections()
    config.read('./config/parameters.ini')
    config.sections()

    if 'DEFAULT' in config:
        mid_server = config['DEFAULT']['MID_SERVER']
    else:
        mid_server = os.environ.get('MID_SERVER')

    if "DEFAULT" in config:
        username = config['DEFAULT']['username']
    else:
        username = os.environ.get('USER')

    if "DEFAULT" in config:
        password = config['DEFAULT']['password']
    else:
        password = os.environ.get('password')

    if "DEFAULT" in config:
        url = config['DEFAULT']['url']
    else:
        url = os.environ.get('url')

    if 'DEFAULT' in config:
        switch_info_url = config['DEFAULT']['switch_info_url']
    else:
        switch_info_url = os.environ.get('switch_info_url')


