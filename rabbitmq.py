import pika
import settings; from settings import *; settings.init()

rabbitmq_ip = settings.rabbitmq_ip 
rabbitmq_port = settings.rabbitmq_port
rabbitmq_username = settings.rabbitmq_username
rabbitmq_password = settings.rabbitmq_password

#rabbit connection
def rabbit_connection():
    server = rabbitmq_ip
    port = rabbitmq_port
    user = rabbitmq_username
    password = rabbitmq_password
    
    credentials = pika.PlainCredentials(user, password)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(server, port, "/", credentials)
    )
    
    rabbit_channel = connection.channel()
    return rabbit_channel,connection