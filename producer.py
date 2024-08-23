import redis, requests
import re, json, math
import time; from time import * 
import time as my_time
import requests; import re; import json; import logging
from datetime import datetime
import glv; from glv import Enabled
import settings
from functions import *
import send_logs

settings.init()

service_name = "producer"


redis_server = redis.Redis(host='localhost', port=6379, db=0)

# Set the value of Enabled to Redis when the script starts
redis_server.set("Enabled", int(glv.Enabled))

queue_name = glv.api_queue_name
failed_tasks=glv.failed_tasks
completed_tasks=glv.completed_tasks
incompleted_tasks = glv.incompleted_tasks
switch_info_url = settings.switch_info_url
get_cmds_url = settings.url + "/getCommands"
update_req_url = settings.url + "/SetCommandStatus"
update_status_url= settings.url + "/postHealthMonitoring"

# this module will be used to get an instance of the logger object 
logger = logging.getLogger(__name__)
# Define the time format
time_format = glv.time_format
logger.setLevel(logging.DEBUG)
try:
    from systemd.journal import JournaldLogHandler

    # Instantiate the JournaldLogHandler to hook into systemd
    journald_handler = JournaldLogHandler()

    journald_handler.setFormatter(logging.Formatter(fmt=f'%(asctime)s - %(levelname)-8s - %(message)s', datefmt=time_format))

    # Add the journald handler to the current logger
    logger.addHandler(journald_handler)

except ImportError:
    # systemd.journal module is not available, use basic console logging
    logging.basicConfig(level=logging.DEBUG, format=f'%(asctime)s - %(levelname)-8s - %(message)s', datefmt=time_format)

def get_requests():
    commands = requests.post(get_cmds_url, headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
    print (f"Got from commands from API: {commands['result']}")
    return commands['result']

def send_health_monitoring_update (mid_name, items_in_queue, items_in_process, items_failed, items_incomplete, Timestamp):
    try:
        payload = json.dumps(
            {
                "mid_name": mid_name,
                "items_in_queue": items_in_queue,
                "items_in_process": items_in_process,
                "items_failed": items_failed,
                "items_incomplete": items_incomplete,
                "timestamp": Timestamp
            })
        print(payload)
        # Check if payload is empty
        if not payload:
            logger.warning("Empty payload. Skipping health monitoring update.")
            send_logs_to_api(f'Empty payload. Skipping health monitoring update. {str(e)}', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
            return
        
        answer = requests.post(update_status_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()

        #send_logs_to_api(f'Sended info to send_health_monitoring_update: {payload}', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), '123')
    except Exception as e:
        send_logs_to_api(f'Error in send_health_monitoring_update: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        logger.error('Error in send_health_monitoring_update: %s', str(e))
        

def cleanup_redis():
    # Cleanup failed tasks
    failed_count = redis_server.llen(failed_tasks)
    if failed_count > 0:
        logger.info("Cleaning up failed tasks...")
        for _ in range(failed_count):
            task = redis_server.lpop(failed_tasks)
            if task:
                redis_server.delete(task)

def redis_queue_push(task):
    record_id=task["record_id"]
    print(f"record_id: {record_id}")
    try:
        if bool(re.search('(active|failed)', task["dr_status"])):
            print(task["record_id"])
            print(task)

            job_status = redis_server.get(task["record_id"])
            # job_status = task["record_id"]

            job_status1 = task["record_id"]
            print("job_status1", job_status1)
            print("job_status:", job_status)
            print("recieved task:",task)
            send_logs.send_data_to_flask(0, f'recived task {task}', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)                                                                

            if job_status is not None and job_status.strip():
                print("job status not equal none ", job_status)
                try:
                    print("movda aq")
                    job_status=json.loads(job_status.decode())
                except json.JSONDecodeError as json_error:
                    print("error")
                    logger.error("Error decoding JSON for record_id: %s. Error: %s", record_id, str(json_error))
                    send_logs.send_data_to_flask(1, f'Error decoding JSON for record_id: {record_id}, Error: {str(json_error)}...', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)
                    return  # Exit the function if JSON decoding fails
                
                if "completed" in job_status["status"]:

                    print("completed")
                    send_logs.send_data_to_flask(0, f'completed...', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)
                    
                    output = re.sub("      ", "\n", job_status["output"])
                    send_status_update(task["record_id"], job_status["status"], output)
                    redis_server.rpush(completed_tasks, str(task))

                #Active task
                elif "active" in job_status["status"]:
                    print("status activee")
                    send_logs.send_data_to_flask(0, f'job status is active...  {job_status["status"]}', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)                                                                

                    print(f"Job status is {job_status} waiting to be executed")
                    redis_server.rpush(queue_name, str(task))

                #failed task
                if task["record_id"] not in [json.loads(t)["record_id"] for t in redis_server.lrange(failed_tasks,0,-1)]:
                    send_logs.send_data_to_flask(0, f'failed job... ', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)                                                                
                    redis_server.rpush(failed_tasks, json.dumps(task))

            else:
                    logger.warning("Job status is empty or None for record_id: %s", task["record_id"])
                    send_logs.send_data_to_flask(2, 'watning job status is empty or none record_id', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)

                #  print(f"else: {job_status}")
                #  redis_server.rpush(queue_name, str(task))
                #  redis_server.set(record_id, "active")
                #  logger.info('Added %s to queue', task["record_id"])
                #  print(f'added {task["record_id"]} to queue')

    except Exception as e:
        #send_logs_to_api(f'Error in redis_queue_push: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        logger.error('Error in redis_queue_push: %s', str(e))
        send_logs.send_data_to_flask(1, 'Error in redis queue push', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)



last_cleanup_time = None
if __name__ == "__main__":
    while True:
        enabled_value = redis_server.get("Enabled")
        if enabled_value and not bool(int(enabled_value.decode())):
            logger.info("Processing is disabled. Waiting for 'Enabled' to be True.")
            send_logs_to_api(f'Processing is disabled. Waiting for Enabled to be True.', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))            
            sleep(5)
            continue

        #if last_cleanup_time is None or (datetime.now() - last_cleanup_time).seconds >= 3600:
        #    cleanup_redis()
        #    send_logs_to_api(f'Cleaning up the failed redis queue', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        #    last_cleanup_time = datetime.now()

        tasks = get_requests()
        send_logs.send_data_to_flask(0, 'Getting Tasks...', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)

        for task in tasks:
            if task['mid_name'] == settings.mid_server:
                record_id=task["record_id"]
                # Push task to the Redis queue
                redis_queue_push(task)
    
        tasks_for_mid_server = [task for task in tasks if task['mid_name'] == settings.mid_server]
        items_in_queue = len(tasks_for_mid_server)
        items_in_progress = sum(1 for task in tasks_for_mid_server if task.get('dr_status') == 'active')
        items_failed = redis_server.llen(failed_tasks)
        items_incomplete = redis_server.llen(incompleted_tasks)
        Timestamp = datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')

        logger.info("%s, %s, %s, %s, %s, %s", settings.mid_server, items_in_queue, items_in_progress, items_failed, items_incomplete, Timestamp)        

        # send_logs.send_data_to_flask(0, f'Service up...', datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'), service_name)
                                                                                                       
        # send_health_monitoring_update(settings.mid_server, items_in_queue, items_in_progress, items_failed, items_incomplete, Timestamp)
        sleep(10)