import pika
#rabbit connection
def rabbit_connection():
    server = "localhost" # config["server"]
    port = "5672" # config["port"]
    user = "guest" # config["user"]
    password = "guest" # config["password"]
    
    credentials = pika.PlainCredentials(user, password)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(server, port, "/", credentials)
    )
    
    rabbit_channel = connection.channel()
    return rabbit_channel,connection