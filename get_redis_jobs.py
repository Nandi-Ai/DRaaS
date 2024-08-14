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
    print("Error while connecting to Redis:", err)
    exit(1)

# Function to safely parse JSON data that may contain single quotes
def safe_json_loads(item: str):
    try:
        # Replace single quotes with double quotes
        fixed_item = item.replace("'", '"')
        return json.loads(fixed_item)
    except json.JSONDecodeError as err:
        print(f"JSON decoding failed: {err}")
        return {"error": "JSONDecodeError", "raw_data": item}

# Getting data from each queue...
def get_raw_queue_data(queue_name: str) -> dict:
    try:
        raw_data = redis_conn.lrange(queue_name, 0, -1)
        jobs = []
    except Exception as err:
        print("Error while retrieving data from Redis:", err)
        return {"error": str(err)}
        
    for item in raw_data:
        item_str = item.decode('utf-8')  # Decode the byte string to a regular string
        job_data = safe_json_loads(item_str)  # Parse with error handling
        jobs.append(job_data)

    return {
        "queue_name": queue_name,
        "queue_length": len(raw_data),
        "jobs": jobs
    }

def generate_raw_queue_status() -> dict:
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
