from flask import Flask, jsonify, request
import redis, requests, json, datetime, settings
from functions import send_logs_to_api


settings.init()

update_status_url= settings.url + "/postHealthMonitoring"
queue_names = ["api_req_queue", "current_task_queue", "failed_tasks", "incomplete_tasks", "completed_tasks"]
app = Flask(__name__)

# global variables...
consumer = {}
producer = {}
# Data = {}

# Connecting to redis...
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


def send_health_monitoring_update(producer: dict, consumer: dict) -> json:
    data = generate_raw_queue_status()
    try:
        payload = json.dumps({
            "mid_name": settings.mid_server,
            "queues": data,
            "services": {
                "producer": producer,
                "consumer": consumer
            }
        })
        # Check if payload is empty
        if not payload:
            print("Empty payload. Skipping health monitoring update.")
            send_logs_to_api(f'Empty payload. Skipping health monitoring update.', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
            return
        answer = requests.post(update_status_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
        print("Payload Sent...")
        print(payload)
        return payload
    except Exception as e:
        send_logs_to_api(f'Error in send_health_monitoring_update: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        print(f'Error in send_health_monitoring_update: {str(e)}')
        return None


@app.route('/receive', methods=['GET', 'POST'])
def receive_data():
    global consumer
    global producer
    # global Data

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            service_name = data.get('service_name')
            if service_name == "consumer":
                consumer.update(data)
            elif service_name == "producer":
                producer.update(data)
            else:
                return jsonify({"error": "Unknown service name"}), 400
            
            send_health_monitoring_update(producer, consumer)
            return jsonify({"message": "Data received successfully"}), 200
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    
    # testing
    # if request.method == 'GET':
    #     return jsonify({'Data': Data}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
    
    