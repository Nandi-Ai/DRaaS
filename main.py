from flask import Flask, jsonify, request

import redis, requests, json
from rq import Queue, Connection, Worker
from rq.job import Job
from datetime import datetime
import glv
import settings

settings.init()

update_status_url= settings.url + "/postHealthMonitoring"


app = Flask(__name__)

# Connect to redis...
queue_name = 'api_req_queue'
redis_conn = redis.Redis(host='localhost', port=6379, db=0)
queue = Queue(queue_name, connection=redis_conn)


def get_queue_status():
    # Create a Queue object
    queue = Queue(queue_name, connection=redis_conn)
    
    # Initialize the status dictionary
    queue_status = {
        'queue_name': queue_name,
        'queue_length': len(queue),
        'jobs': [],
        'number_of_failed_jobs': 0,
        'number_of_in_progress_jobs': 0,
        'number_of_finished_jobs': 0
    }

    # Retrieve job IDs from the queue
    job_ids = queue.job_ids

    # Process each job in the queue
    for job_id in job_ids:
        job = Job.fetch(job_id, connection=redis_conn)
        job_info = {
            'job_id': job.id,
            'job_status': job.get_status(),
            'job_enqueued_at': job.enqueued_at.isoformat() if job.enqueued_at else None,
            'job_started_at': job.started_at.isoformat() if job.started_at else None,
            'job_ended_at': job.ended_at.isoformat() if job.ended_at else None,
            'job_failed': {
                'failed_time': job.ended_at.isoformat() if job.is_failed else None,
                'error_message': job.exc_info if job.is_failed else None
            },
            'job_finished': job.is_finished
        }
        queue_status['jobs'].append(job_info)

        # Count the jobs based on their status
        if job.is_failed:
            queue_status['number_of_failed_jobs'] += 1
        elif job.is_finished:
            queue_status['number_of_finished_jobs'] += 1
        elif job.get_status() == 'started':
            queue_status['number_of_in_progress_jobs'] += 1

    return queue_status


def send_health_monitoring_update (producer, consumer):
    data = get_queue_status()
    try:
        payload =(
            {
                # "mid_name": settings.mid_server,
                "queue": data,
                "services": {
                    "producer": producer,
                    "consumer": consumer
                }
            })
        print(payload)
        # Check if payload is empty
        if not payload:
            # logger.warning("Empty payload. Skipping health monitoring update.")
            # send_logs_to_api(f'Empty payload. Skipping health monitoring update. {str(e)}', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
            return
        answer = requests.post(update_status_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
        print("sent")
        return payload
        #send_logs_to_api(f'Sended info to send_health_monitoring_update: {payload}', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), '123')
    except Exception as e:
        # send_logs_to_api(f'Error in send_health_monitoring_update: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        # logger.error('Error in send_health_monitoring_update: %s', str(e))
        pass
        

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
            tasks = data.get('tasks')
            if service_name == "consumer":
                consumer.update(data) 
            elif service_name == "producer":
                producer.update(data)  
            else:
                return jsonify({"error": "Unknown service name"}), 400
            
            Data.update(send_health_monitoring_update(producer, consumer))
            return jsonify({"message": "Data received successfully"}), 200 
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    
    if request.method == 'GET':
        return jsonify({
            'Data': Data
        }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)






    # {
    # "command": "show running-config",
    # "command_number": "DRA0005542",
    # "created": "2024-07-01 22:00:03",
    # "description": null,
    # "destination": null,
    # "discovery": "0",
    # "dr_status": "completed",
    # "gateway": null,
    # "interface_name": null,
    # "ip": null,
    # "mid_name": "Leumit_mid_prod_1",
    # "port_mode": null,
    # "priority": null,
    # "protocol": null,
    # "record_id": "001cd50b83434650f53bbf65eeaad360",
    # "subnet": null,
    # "switch": "b5102f979717b150683bfc8fe153af8e",
    # "switch_ip": "192.168.128.17",
    # "switch_status": null,
    # "updated": "2024-07-22 16:02:59",
    # "via": null,
    # "vlans": null
    # },
