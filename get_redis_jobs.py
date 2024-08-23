import redis, requests, json
from datetime import datetime
import time
import glv


queue_names = [glv.api_queue_name, glv.current_task_queue, glv.failed_tasks, glv.incompleted_tasks, glv.completed_tasks]
url = "http://localhost:5050/receive"
headers = {'Content-Type': 'application/json'}

try:
    redis_conn = redis.Redis()
except Exception as err:
    print("Error while connecting to redis:", err)
    exit(1)

# geting data from each queue...
def get_raw_queue_data(queue_name: str) -> dict:
    try:
        raw_data = redis_conn.lrange(queue_name, 0, -1)
        qLength = redis_conn.llen(queue_name)
        
        jobs = []
        print(qLength)
    except Exception as err:
        print("error", err)
        return 1
    if qLength != 0:
        if queue_name == "current_task_queue" or queue_name == "api_req_queue":
            for item in raw_data:
                job_data = json.loads(item.decode('utf-8'))
                jobs.append(job_data)
    return {
                "queue_name": queue_name,
                "queue_length": len(raw_data),
                "jobs": jobs
           }
    
def generate_raw_queue_status() -> json:
    overall_status = {}
    print("generate_raw_queue_status")
    for queue_name in queue_names:
        overall_status[queue_name] = get_raw_queue_data(queue_name)
        print(overall_status[queue_name])
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
