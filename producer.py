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
from rabbitmq import *


settings.init()

service_name = "producer"

# testing
rabbit_server = rabbit_connection()
# rabbit_server.queue_declare(queue=queue_name)



# redis_server = redis.Redis(host='localhost', port=6379, db=0)

# Set the value of Enabled to Redis when the script starts
# redis_server.set("Enabled", int(glv.Enabled))

queue_name = glv.api_queue_name
failed_tasks=glv.failed_tasks
completed_tasks=glv.completed_tasks
in_progress_tasks = glv.in_progress_tasks
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
    # print (f"Got from commands from API: {commands['result']}")
    return commands['result']

def send_health_monitoring_update (mid_name, items_in_queue, items_in_process, items_failed, in_progress_tasks, Timestamp):
    try:
        payload = json.dumps(
            {
                "mid_name": mid_name,
                "items_in_queue": items_in_queue,
                "items_in_process": items_in_process,
                "items_failed": items_failed,
                "in_progress_tasks": in_progress_tasks,
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

        #send_logs_to_api(f'Sended info to send_health_monitoring_update: {payload}', 'info', settings.mid_server,  '123')
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

def queue_push(task):
    api_task_record_id=task["record_id"]
    api_task_command_number=task["command_number"]
    print(f"api_task_record_id: {api_task_record_id} {api_task_command_number} ")
    redisJobStatus = redis_server.get(api_task_command_number)
    
    # rabbitJobStatus = rabbit_server.get(api_task_record_id)
    print("Assigned Job status ", api_task_command_number)
    print("Redis job status: ", redisJobStatus)
    drStatus=task['dr_status']

    try:
        print(f"DR Status: {drStatus}")
        if bool(re.search('(active|failed|in_progress|queued)', drStatus)):
            print("active/failed task condition status " ,drStatus)

            send_logs.send_data_to_flask(0, f'recived task {task}', service_name) 
            #Active task

            if "active" in drStatus:   
                redis_server.set(api_task_command_number, drStatus)
                if redisJobStatus is None:
                    redis_server.set(api_task_command_number, drStatus)
                    print("Aha! Found new active status")                    
                    send_logs.send_data_to_flask(0, f'job status is active...  {task["dr_status"]}',  service_name)                                                                
                    print(f"Job {api_task_record_id} pushed to queue and waiting to be executed")
                    # redis_server.rpush(queue_name, str(task))
                
                    # pushing tasks inside rabbitmq 
                    rabbitmq_push(task, queue_name)
                    send_status_update(api_task_record_id,drStatus,"Pushed to Queue")
                    print(f"Job {api_task_record_id} pushed to queue {queue_name} and waiting to be executed")
                    return
                else:
                    if redisJobStatus not in drStatus:
                        send_status_update(api_task_record_id, redisJobStatus, f"Job exists on cache as {redisJobStatus}")
                    
            # If found this job on Redis what to do
            if redisJobStatus is not None:
                print("redisJobStatus is not empty, job exists on Redis: ", redisJobStatus)
                
                print("Job discarded")
                ### TODO THIS JOB WAS DONE
                # send_logs.send_data_to_flask(1, f'Error decoding JSON for api_task_record_id: {api_task_record_id}, Error: {str(json_error)}...',  service_name)
                return  # Exit the function if JSON decoding fails
                # if completed
            elif "queued" in drStatus or "in_progress" in drStatus:
                print("requeued job counld not find in redis")
                redis_server.set(api_task_command_number, "active")
                rabbitmq_push(task, queue_name) 
                send_status_update(api_task_record_id,drStatus,"Pushed to Queue again")
            

                ##TODO updating this part
                #failed task wait with the task, low priority
                    ## TODO Fix this part
                    ## redis_set(failed_tasks, task)

            else:
                print("Job exists on redis, quitting")
                logger.warning("Job status is empty or None for record_id: %s", task["record_id"])
                send_logs.send_data_to_flask(2, 'watning job status is empty or none record_id',  service_name)

                #  print(f"else: {job_status}")
                #  redis_server.rpush(queue_name, str(task))
                #  redis_server.set(api_task_record_id, "active")
                #  logger.info('Added %s to queue', task["api_task_record_id"])
                #  print(f'added {task["api_task_record_id"]} to queue')
        else:
          # print normal output for debug
          print(re.search('(active|failed|completed)', task["dr_status"]))
          print("else quit")


    except Exception as e:
        #send_logs_to_api(f'Error in redis_queue_push: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        logger.error('Error in redis_queue_push: %s', str(e))
        send_logs.send_data_to_flask(1, 'Error in redis queue push',  service_name)



last_cleanup_time = None
if __name__ == "__main__":
    while True:
        enabled_value = redis_server.get("Enabled")
##        if enabled_value and not bool(int(enabled_value.decode())):
##            logger.info("Processing is disabled. Waiting for 'Enabled' to be True.")
##            send_logs_to_api(f'Processing is disabled. Waiting for Enabled to be True.', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))            
##            sleep(5)
##            continue
##
        #if last_cleanup_time is None or (datetime.now() - last_cleanup_time).seconds >= 3600:
        #    cleanup_redis()
        #    send_logs_to_api(f'Cleaning up the failed redis queue', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        #    last_cleanup_time = datetime.now()

        tasks = get_requests()
        send_logs.send_data_to_flask(0, 'Getting Tasks...',  service_name)
        print("Read task batch")
        print("***************")
        print("***************")
        print("")
        for task in tasks:
            if task['mid_name'] == settings.mid_server:
                queue_push(task)
    
        # tasks_for_mid_server = [task for task in tasks if task['mid_name'] == settings.mid_server]
        # items_in_queue = len(tasks_for_mid_server)
        # items_in_progress = sum(1 for task in tasks_for_mid_server if task.get('dr_status') == 'active')
        # items_failed = redis_server.llen(failed_tasks)
        # in_progress_tasks = redis_server.llen(in_progress_tasks)
        # Timestamp = datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')

        # logger.info("%s, %s, %s, %s, %s, %s", settings.mid_server, items_in_queue, items_in_progress, items_failed, in_progress_tasks, Timestamp)        

        # send_logs.send_data_to_flask(0, f'Service up...',  service_name)
                                                                                                       
        # send_health_monitoring_update(settings.mid_server, items_in_queue, items_in_progress, items_failed, items_incomplete, Timestamp)
        print("***************")
        sleep(10)
