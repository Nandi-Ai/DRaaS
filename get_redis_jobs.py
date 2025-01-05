import redis, requests, json
from datetime import datetime
import time
import glv
import pika
from rabbitmq import *
import settings; from settings import *; settings.init()


url = "http://flaskapi:5050/receive"
headers = {'Content-Type': 'application/json'}
rabbit_server = rabbit_connection()
rabbitmq_ip = settings.rabbitmq_ip 

redis_ip = settings.redis_ip
redis_port = settings.redis_port

try:
    # connecting to redis
    redis_server = redis.Redis(host=redis_ip, port=redis_port, db=0)
    
    # connecting to rabbitmq
    rabbit_conn = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_ip))
    rabbit_channel = rabbit_conn.channel()
except Exception as err:
    print("Error while connecting to redis:", err)
    exit(1)


def get_raw_queue_data(queue_name: str) -> dict:
    raw_data = []
    queue_length = 0

    def callback(ch, method, properties, body):
        nonlocal queue_length
        queue_length += 1
        job_data = json.loads(body.decode('utf-8'))
        raw_data.append(job_data)

    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_ip))
    rabbit_channel = connection.channel()
    rabbit_channel.queue_declare(queue=queue_name, durable=True)
    try:
        for method_frame, properties, body in rabbit_channel.consume(queue=queue_name, inactivity_timeout=1, auto_ack=False):
            if body:
                callback(None, method_frame, properties, body)
            else:
                break
    finally:
        connection.close()
    jobs = raw_data if queue_length > 0 and queue_name == "api_req_queue" else []
    return {
        "queue_name": queue_name,
        "queue_length": queue_length,
        "jobs": jobs
    }
            
def generate_raw_queue_status() -> json:
    queueConst = [ glv.api_queue_name, glv.completed_tasks]
    overall_status = {}
    for queue_name in queueConst:
        overall_status[queue_name] = get_raw_queue_data(queue_name)
        

    print(overall_status)
    return overall_status

def send_data_to_flask():  
    output = generate_raw_queue_status() 
    msg = {
       "service_name": "redis", 
       "time_sent": datetime.now().strftime("%H:%M:%S"),
       "redis": output
    }
    print(msg)
    try:
        response = requests.post(url, json=msg, headers=headers, timeout=5)
        print(response.status_code, "---", response.json())
    except requests.RequestException as err:
        print("Error while sending data to API:", err)


if __name__ == '__main__':
    while True:
        try:
            send_data_to_flask()
            time.sleep(15)      # Sleep for 15 seconds if everything is okay
        except (requests.ConnectionError, requests.Timeout) as err:
            print(f"Network error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(5) 
        except Exception as err:
            print(f"An unexpected error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(5)
