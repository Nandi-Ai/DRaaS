from flask import Flask, jsonify, request
import redis, requests, settings
from datetime import datetime
from functions import send_logs_to_api
import settings
import json


settings.init()

update_status_url= settings.url + "/postHealthMonitoring"


queue_names = ["api_req_queue", "current_task_queue", "failed_tasks", "incomplete_tasks", "completed_tasks"]


app = Flask(__name__)


# Connect to redis...
try:
    redis_conn = redis.Redis(host='localhost', port=6379, db=0)
except Exception as err:
    print("Error while connecting to redis:", err)
    exit(1)

def get_raw_queue_data(queue_name):
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

def generate_raw_queue_status():
    overall_status = {}
    for queue_name in queue_names:
        overall_status[queue_name] = get_raw_queue_data(queue_name)
    return overall_status

def send_health_monitoring_update(producer, consumer):
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
        print(payload)
        # Check if payload is empty
        if not payload:
            print("Empty payload. Skipping health monitoring update.")
            send_logs_to_api(f'Empty payload. Skipping health monitoring update.', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
            return
        answer = requests.post(update_status_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
        print("Sent")
        return payload
    except Exception as e:
        send_logs_to_api(f'Error in send_health_monitoring_update: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        print(f'Error in send_health_monitoring_update: {str(e)}')
        return None

consumer = {}
producer = {}
Data = {}

@app.route('/receive', methods=['GET', 'POST'])
def receive_data():
    global consumer
    global producer
    global Data

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
            
            Data = send_health_monitoring_update(producer, consumer)
            return jsonify({"message": "Data received successfully"}), 200
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    
    # testing
    if request.method == 'GET':
        return jsonify({'Data': Data}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)






# def get_queue_status():
#     queue = Queue(queue_name, connection=redis_conn)
#     queue_status = {
#         'queue_name': queue_name,
#         'queue_length': len(queue),
#         'jobs': [],
#         'number_of_failed_jobs': 0,
#         'number_of_in_progress_jobs': 0,
#         'number_of_finished_jobs': 0
#     }
#     try:
#         job_ids = queue.job_ids
#         for job_id in job_ids:
#             job = Job.fetch(job_id, connection=redis_conn)
#             job_info = {
#                 'job_id': job.id,
#                 'job_status': job.get_status(),
#                 'job_enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
#                 'job_started_at': job.started_at.isoformat() if job.started_at else None,
#                 'job_ended_at': job.ended_at.isoformat() if job.ended_at else None,
#                 'job_failed': {
#                     'failed_time': job.ended_at.isoformat() if job.is_failed else None,
#                     'error_message': job.exc_info if job.is_failed else None
#                 },
#                 'job_finished': job.is_finished
#             }
#             queue_status['jobs'].append(job_info)

#             # Count jobs based on their status
#             if job.is_failed:
#                 queue_status['number_of_failed_jobs'] += 1
#             elif job.is_finished:
#                 queue_status['number_of_finished_jobs'] += 1
#             elif job.get_status() == 'started':
#                 queue_status['number_of_in_progress_jobs'] += 1
#     except Exception as err:
#         print(f"Error while getting data from redis: {err}")
    
#     return queue_status
