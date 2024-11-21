import redis, requests, json
from datetime import datetime
import time
import glv
import pika
from rabbitmq import *


url = "http://localhost:5050/receive"
headers = {'Content-Type': 'application/json'}
rabbit_server = rabbit_connection()


try:
    # connecting to redis
    redis_conn = redis.Redis()
    
    # connecting to rabbitmq
    rabbit_conn = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
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

    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
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
    
def get_rabbit_queues_status():
    queueNames = [ glv.current_task_queue, glv.failed_tasks, glv.in_progress_tasks]
    rqueue_tasks = {} 
    for queue_name in queueNames:  
        try:
            queueuHandler = rabbit_server.queue_declare(queue=queue_name, durable=True)
            queueLength = queueuHandler.method.message_count  

            print(f"Queue '{queue_name}' has {queueLength} items.")
            print("Members:")
            if queue_name == "fixme":
                tasks = []
                for jobs in queueuHandler:
                    task_data = jobs.decode('utf-8')
                    task = json.loads(task_data)
                    tasks.append(task)
                rqueue_tasks[queue_name] = {
                    "queue_name": queue_name,
                    "queue_length": queueLength,
                    "jobs": tasks
                }
            else:
                rqueue_tasks[queue_name] = {
                        "queue_name": queue_name,
                        "queue_length": queueLength,
                        "jobs": []
                    }
        except redis.exceptions.RedisError as e:
            print(f"An error occurred with queue '{queue_name}': {e}")
    
    return rqueue_tasks

def get_redis_jobs():
    queue_names = [ glv.current_task_queue, glv.failed_tasks, glv.in_progress_tasks]
    redis_tasks = {} 
    for set_name in queue_names:
        try: 
            members = redis_conn.smembers(set_name)  
            set_length = redis_conn.scard(set_name)
            print(f"Set '{set_name}' has {set_length} members.")
            print("Members:")
            if set_name == glv.current_task_queue:
                tasks = []
                for jobs in members:
                    task_data = jobs.decode('utf-8')
                    task = json.loads(task_data)
                    tasks.append(task)
                redis_tasks[set_name] = {
                    "queue_name": set_name,
                    "queue_length": set_length,
                    "jobs": tasks
                }
            else:
                redis_tasks[set_name] = {
                        "queue_name": set_name,
                        "queue_length": set_length,
                        "jobs": []
                    }
        except redis.exceptions.RedisError as e:
            print(f"An error occurred with set '{set_name}': {e}")
    
    return redis_tasks
        
def generate_raw_queue_status() -> json:
    queueConst = [ glv.api_queue_name, glv.completed_tasks]
    overall_status = {}
    for queue_name in queueConst:
        overall_status[queue_name] = get_raw_queue_data(queue_name)
        
    # queue_status = get_rabbit_queues_status()
    # overall_status.update(queue_status)
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
            time.sleep(10)      # Sleep for 10 seconds if everything is okay
        except (requests.ConnectionError, requests.Timeout) as err:
            print(f"Network error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(5) 
        except Exception as err:
            print(f"An unexpected error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(5)


    # while True:
    #     try:
    #         send_data_to_flask()
    #         time.sleep(10)
    #     except Exception as err:
    #         print("error...", err)
