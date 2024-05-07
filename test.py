# task={'command_number': 'DRA0004393', 'record_id': 'fccc38e487fdcad0220a98a83cbb354c', 
#        'command': 'show running-config', 'switch': '4f6edb571b533110fee96573604bcb5e', 'switch_status': None, 
#        'switch_ip': '192.168.128.1', 'interface_name': None, 'port_mode': None, 'dr_status': 'completed', 
#        'vlans': None, 'mid_name': 'Leumit-PRD', 'discovery': '0', 'protocol': None, 
#        'destination': None, 'via': None, 'ip': None, 'subnet': None, 'gateway': None, 
#        'description': None, 'priority': None, 'updated': '2024-05-01 13:14:32', 'created': '2024-04-22 22:00:00'}

# job_status= task.get('dr_status')

# print(job_status)

import re
import json
import redis

def redis_queue_push(task):
    record_id = task["record_id"]
    print(f"record_id: {record_id}")
    try:
        status = task.get('dr_status')
        
        if status:
            if bool(re.search('(active|failed|completed)', status)):
                #print("received task:", task)

                if "completed" in status:
                    print("completed")
                    # Do something for completed tasks
                    # Example: redis_server.rpush(completed_tasks, str(task))

                elif "active" in status:
                    print("Job status is active waiting to be executed")
                    # Do something for active tasks
                    # Example: redis_server.rpush(queue_name, str(task))

                elif "failed" in status:
                    print("Job status is failed")
                    # Do something for failed tasks
                    # Example: redis_server.rpush(failed_tasks, str(task))

                else:
                    # Log error and continue to next task
                    print(f"Unknown status: {status}. Skipping task.")

        else:
            # Log error and continue to next task
            raise ValueError(f"Error: Status is None for task_id: {record_id}. Skipping task.")

    except Exception as e:
        # Handle exceptions
        raise RuntimeError(f'Error in redis_queue_push: {str(e)}')


# def process_task(task):
#     task_id = task["record_id"]
#     status = task.get('dr_status')
    
#     if status:
#         if status == "active":
#             print("active")
#         elif status == "failed":
#             print("failed")
#         elif status == "completed":
#             print("completed")
#         else:
#             print("Unknown status:", status)
#     else:
#         # Log error and continue to next task
#         print(f"Error: Status is None for task_id: {task_id}. Skipping task.")
#         return

# def redis_queue_push(task):
#     record_id=task["record_id"]
#     print(f"record_id: {record_id}")
#     status = task.get('dr_status')
#     print(f'status: {status}')
#     try:
#         if status == "active":
#             print(f"Job status is {status} waiting to be executed")
#             #redis_server.rpush(queue_name, str(task))

#         elif status == 'failed':
#             print(f'Job status is {status}. Will push to failed queue if not there')
#             #if record_id not in [json.loads(t)["record_id"] for t in redis_server.lrange(failed_tasks,0,-1)]:
#                 #redis_server.rpush(failed_tasks, json.dumps(task))
        
#         elif status == 'completed':
#             print("completed")
#             #redis_server.rpush(completed_tasks, str(task))

#         else:
#             print("non valid status")

#     except Exception as e:
#         print("error")
#         #logger.error('Error in redis_queue_push: %s', str(e))


# Simulated list of tasks
tasks = [
    {
        "command_number": "DRA0001364",
        "record_id": "004422ce9713f910683bfc8fe153afa8",
        "command": "show running-config",
        "switch": None,
        "switch_status": None,
        "switch_ip": "192.168.128.1",
        "interface_name": None,
        "port_mode": None,
        "dr_status": "active",
        "vlans": None,
        "mid_name": "Leumit-PRD",
        "discovery": "0",
        "protocol": None,
        "destination": None,
        "via": None,
        "updated": "2023-12-27 08:41:14",
        "created": "2023-12-25 14:46:03"
    },
    {
        "command_number": "DRA0004393",
        "record_id": "fccc38e487fdcad0220a98a83cbb354c",
        "command": "show running-config",
        "switch": "4f6edb571b533110fee96573604bcb5e",
        "switch_status": None,
        "switch_ip": "192.168.128.1",
        "interface_name": None,
        "port_mode": None,
        "dr_status": "completed",
        "vlans": None,
        "mid_name": "Leumit-PRD",
        "discovery": "0",
        "protocol": None,
        "destination": None,
        "via": None,
        "ip": None,
        "subnet": None,
        "gateway": None,
        "description": None,
        "priority": None,
        "updated": "2024-05-01 13:14:32",
        "created": "2024-04-22 22:00:00"
    }
]

# Processing each task
for task in tasks:
    redis_queue_push(task)






