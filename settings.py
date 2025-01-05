import configparser 
import os

def init():
    
    global rabbitmq_ip
    global rabbitmq_port
    global rabbitmq_username
    global rabbitmq_password
    
    global redis_ip
    global redis_port
    
    global mid_server
    global username
    global password
    global config
    global url
    global switch_info_url
    config = configparser.ConfigParser()
    config.sections()
    config.read('./config/parameters.ini')
    # config.read('/opt/DRaaS/config/parameters.ini')
    
    config.sections()
    
    # rabbit config
    if 'DEFAULT' in config:
        rabbitmq_ip = config['DEFAULT']['Rabbitmq_ip']
    else:
        rabbitmq_ip = os.environ.get('Rabbitmq_ip')
        
    if 'DEFAULT' in config:
        rabbitmq_port = config['DEFAULT']['Rabbitmq_port']
    else:
        rabbitmq_port = os.environ.get('Rabbitmq_port')
        
    if 'DEFAULT' in config:
        rabbitmq_username = config['DEFAULT']['Rabbitmq_username']
    else:
        rabbitmq_username = os.environ.get('Rabbitmq_username')

    if 'DEFAULT' in config:
        rabbitmq_password = config['DEFAULT']['Rabbitmq_password']
    else:
        rabbitmq_password = os.environ.get('Rabbitmq_password')
    
    # redis config
    if 'DEFAULT' in config:
        redis_ip = config['DEFAULT']['Redis_ip']
    else:
        redis_ip = os.environ.get('Redis_ip') 
        
    if 'DEFAULT' in config:
        redis_port = config['DEFAULT']['Redis_port']
    else:
        redis_port = os.environ.get('Redis_port') 
        
        
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
