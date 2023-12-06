import redis, requests
import re, json, math
import time; from time import * 
import time as my_time
import requests; import re; import json; import logging
from datetime import datetime
import settings
settings.init()


redis_server = redis.Redis()
queue_name = "api_req_queue"
switch_info_url = settings.switch_info_url
get_cmds_url = settings.url + "/getCommands"
update_req_url = settings.url + "/SetCommandStatus"
update_status_url= settings.url + "/postHealthMonitoring"

# get an instance of the logger object this module will use
logger = logging.getLogger(__name__)

# Check if the systemd.journal module is available
try:
    from systemd.journal import JournaldLogHandler

    # instantiate the JournaldLogHandler to hook into systemd
    journald_handler = JournaldLogHandler()

    # set a formatter to include the level name
    journald_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))

    # add the journald handler to the current logger
    logger.addHandler(journald_handler)

except ImportError:
    # systemd.journal module is not available, use a different logging mechanism
    logging.basicConfig(level=logging.DEBUG)

# Optionally set the logging level
logger.setLevel(logging.DEBUG)


def get_requests():
    commands = requests.post(get_cmds_url, headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
    print (commands['result'])
    return commands['result']


def send_status_update(ID, STATUS, OUTPUT):
    try:
        payload = json.dumps(
            {
                "command_id": f"{ID}",
                "command_status": f"{STATUS}",
                "command_output": f"{OUTPUT}"
            })
        # print(payload)
        answer = requests.post(update_req_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()

    except Exception as e:
        logger.error('Error in send_status_update: %s', str(e))


def send_health_monitoring_update (mid_name, items_in_queue, items_in_process, items_failed,Timestamp):
    try:
        payload = json.dumps(
            {
                "mid_name": mid_name,
                "items_in_queue": items_in_queue,
                "items_in_process": items_in_process,
                "items_failed": items_failed,
                "timestamp": Timestamp
            })
        print(payload)
        answer = requests.post(update_status_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()

    except Exception as e:
        logger.error('Error in send_health_monitoring_update: %s', str(e))


def redis_queue_push(TASKS):
    try:
        for TASK in TASKS:
            if bool(re.search('(active|failed)', TASK["dr_status"])):
                kv_status = redis_server.get(TASK["record_id"])
                if kv_status is not None:
                    kv_status = json.loads(kv_status.decode())
                    if "completed" in kv_status["status"]:
                        output = re.sub("      ", "\n", kv_status["output"])
                        send_status_update(TASK["record_id"], kv_status["status"], output)

                    else:
                        # Check if mid_name matches the specified value
                        if TASK.get("mid_name", "") == settings.mid_server:
                            redis_server.rpush(queue_name, str(TASK))
                            logger.info('Added %s to queue', TASK["record_id"])
                            print(f'added {TASK["record_id"]} to queue')
                        else:
                            logger.info('Skipped %s because mid_name does not match', TASK["record_id"])
                else:
                    # Check if mid_name matches the specified value
                    if TASK.get("mid_name", "") == settings.mid_server:
                        redis_server.rpush(queue_name, str(TASK))
                        logger.info('Added %s to queue', TASK["record_id"])
                        print(f'added {TASK["record_id"]} to queue')
                    else:
                        logger.info('Skipped %s because mid_name does not match', TASK["record_id"])

    except Exception as e:
        logger.error('Error in redis_queue_push: %s', str(e))

if __name__ == "__main__":
    while True:
        # Get the tasks from the API
        tasks = get_requests()

        items_in_progress = sum(1 for task in tasks if task['dr_status'] == 'active')
        items_failed = sum(1 for task in tasks if task['dr_status'] == 'failed')
        # Format timestamp as HH:MM:SS
        Timestamp = datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')

        send_health_monitoring_update(settings.mid_server, len(tasks) , items_in_progress, items_failed ,Timestamp)
        
        # Push tasks to the Redis queue
        redis_queue_push(tasks)
        # Sleep for 10 seconds before the next iteration
        sleep(10)