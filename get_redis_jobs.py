import redis, requests, json
from datetime import datetime
import time



queue_names = ["api_req_queue", "current_task_queue", "failed_tasks", "incomplete_tasks", "completed_tasks"]
url = "http://localhost:5050/receive"
headers = {'Content-Type': 'application/json'}

try:
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)
except Exception as err:
    print("Error while connecting to redis:", err)
    exit(1)

# geting data from each queue...
def get_raw_queue_data(queue_name: list) -> dict:
    try:
        raw_data = redis_conn.lrange(queue_name, 0, -1)
        jobs = []
    except Exception as err:
        print("error", err)
        return 1
        
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
    for queue_name in queue_names:
        overall_status[queue_name] = get_raw_queue_data(queue_name)
    return overall_status


def send_data_to_flask():  
    output = generate_raw_queue_status() 
    msg = {
       "service_name": "redis", 
       "time_sent": datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'),
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
            time.sleep(10)  # Sleep for 10 seconds if everything is okay
        except (requests.ConnectionError, requests.Timeout) as err:
            print(f"Network error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(10)  # Sleep for 10 seconds before retrying in case of network errors
        except Exception as err:
            print(f"An unexpected error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(10)
    # while True:
    #     try:
    #         send_data_to_flask()
    #         time.sleep(10)
    #     except Exception as err:
    #         print("error...", err)
            
    
    