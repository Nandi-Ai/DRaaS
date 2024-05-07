import redis, requests
import re, json, math
import time; from time import * 
import time as my_time
import requests; import re; import json; import logging
from datetime import datetime
import glv; from glv import Enabled
import settings
from functions import *
settings.init()

redis_server = redis.Redis(host='localhost', port=6379, db=0)

# Set the value of Enabled to Redis when the script starts
redis_server.set("Enabled", int(glv.Enabled))

active_tasks = glv.active_tasks
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

#Getting singel command and pushing it to redis (active,failed,completed)
def redis_queue_push(task):
    record_id=task["record_id"]
    record_status = task["dr_status"]
    try:
            if bool(re.search('(active|failed|completed)', record_status)):
                # Convert the dictionary to a JSON string
                # You need to convert the dictionary (task) into a format that Redis understands. 
                # Two common options are JSON and pickle
                task_json = json.dumps(task)

                #t parameter is task in queue
                if "completed"in record_status:
                    print("completed")
                    #completed_records = redis_server.lrange("completed_tasks", 0, -1)
                    #if record_id not in [json.loads(t)["record_id"] for t in redis_server.lrange("completed_tasks",0,-1)]:
                    redis_server.rpush(completed_tasks, task_json)
    
                #Active task
                elif "active" in record_status:
                    print(f"Job status is {record_status} waiting to be executed")
                    #if record_id not in [json.loads(t)["record_id"] for t in redis_server.lrange("active_tasks",0,-1)]:
                    redis_server.rpush(active_tasks, task_json)

                #failed task
                elif "failed" in record_status:
                    #if record_id not in [json.loads(t)["record_id"] for t in redis_server.lrange("failed_tasks",0,-1)]:
                    redis_server.rpush(failed_tasks, task_json)

            else:
                logger.warning("Job status is empty or None for record_id: %s", record_id)
                print(f"else: {record_status}")
                logger.info('Not added to queue because status is not active/completed/failed', record_id)

    except Exception as e:
        #send_logs_to_api(f'Error in redis_queue_push: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        logger.error('Error in redis_queue_push: %s', str(e))


last_cleanup_time = None
if __name__ == "__main__":
    while True:
        # enabled_value = redis_server.get("Enabled")
        # if enabled_value and not bool(int(enabled_value.decode())):
        #     logger.info("Processing is disabled. Waiting for 'Enabled' to be True.")
        #     send_logs_to_api(f'Processing is disabled. Waiting for Enabled to be True.', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        #     sleep(5)
        #     continue

        #Getting all commands from ServiceNow [tasks=array of commands]
        tasks = get_requests()

        for task in tasks:
            mid_name = task['mid_name']
            if mid_name == settings.mid_server:
                record_id=task["record_id"]
                # Push task to the Redis queue
                redis_queue_push(task)

        #tasks_for_mid_server number of all commands per mid_server -- Array of objects
        tasks_for_mid_server = [task for task in tasks if task['mid_name'] == settings.mid_server]
        items_in_queue = len(tasks_for_mid_server)
        items_in_progress = sum(1 for task in tasks_for_mid_server if task.get('dr_status') == 'active')
        items_failed = redis_server.llen(failed_tasks)
        items_incomplete = redis_server.llen(incompleted_tasks)
        Timestamp = datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')

        logger.info("%s, %s, %s, %s, %s, %s", settings.mid_server, items_in_queue, items_in_progress, items_failed, items_incomplete, Timestamp)        

        send_health_monitoring_update(settings.mid_server, items_in_queue, items_in_progress, items_failed, items_incomplete, Timestamp)
        sleep(10)