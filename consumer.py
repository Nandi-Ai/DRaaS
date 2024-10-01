import redis, requests; import re, json, sys, dotenv; from time import sleep, time; from functions import *
import glv; from glv import added_vlan
import gaia_ssh_connect
import logging, time
import settings
from settings import *
import send_logs
from datetime import datetime; 

from rabbitmq import *
rabbit_server = rabbit_connection()

logging.getLogger('pika').setLevel(logging.CRITICAL)

settings.init()

# Create a Redis server connections.
redis_server = redis.Redis()
from_api_queue = glv.api_queue_name
in_progress_tasks = glv.in_progress_tasks
completed_tasks = glv.completed_tasks
credential_dict = glv.credential_dict
failed_tasks = glv.failed_tasks
switch_info_url = settings.switch_info_url
get_cmds_url = settings.url + "/getCommands"
update_req_url = settings.url + "/SetCommandStatus"
get_id_url = settings.url + "/getCommandByID"
Managment_Logs = settings.url + "/postSwitchManagmentLogs"


service_name = 'consumer'


# this module will be used to get an instance of the logger object 
logger = logging.getLogger(__name__)
# Define the time format
time_format = glv.time_format
# Optionally set the logging level
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

    

# Function to get credentials from the dictionary
def get_credentials(ip):
    credential = credential_dict.get(ip, {})
    return (credential["user"], credential["pass"]) if credential.get("status") == "success" else (None, None)

# Function to send a status or update to ServiceNow API
def get_id_status(ID):
    payload = json.dumps({"command_id": f"{ID}"})
    print(f"get_id_status {payload}")
    commands = requests.post(get_id_url, data=payload, headers={'Content-Type': 'application/json'},
                           auth=(settings.username, settings.password))
    valid_response_code(commands.status_code, ID)
    commands = commands.json()
    return commands['result']


    

# funtion that checks if there is some stucked jobs or failed jobs 
# def check_jobs(taskCommandID):
#     task_status = redis_server.get(taskCommandID)
    
#     if task_status == "in_progress_tasks":
#         print("task command is in progress")
#     elif task_status == "failed_tasks":
#         print("task command is failed")
        
#     else:
#         print(f"command maybe stuck: {task_status}")
#         redis_remove_list(taskCommandID, in_progress_tasks)
#         return False
    
#     status = False
    
#     if status:
#         return True
#     else: 
#         return False


# Main function
def main():
    rabbit_server.queue_declare(queue=wait_queue, durable=True)

    while True:

        while True:
            q_len = rabbit_server.queue_declare(queue=from_api_queue, durable=True)
            q_len = q_len.method.message_count
            if q_len > 0:
                taskFromQueue = rabbitmq_queue_get(from_api_queue)
                taskStatus = get_task_status(taskFromQueue)
                logger.info(f"task from queue {taskFromQueue} task status {taskStatus}")

                if "in_progress" == taskStatus or "completed" == taskStatus:
                    print("Task already running")
                    continue
                else:
                    break
            else:

                taskFromWaitQueue = check_wait_queue()
                if taskFromWaitQueue:
                    print("break")

                # if job is stuck more than 2 minute it will try to process one more time.
                # if stuck_jobs:
                #     print("there is stuck jobs...")
                #     taskFromQueue = rabbitmq_queue_get(from_api_queue)
                #     break
                # else:
                #     # if job failed 10 minutes ago this will try to process one more time
                #     failed_jobs = check_jobs(failed_tasks)
                #     if failed_jobs:
                #         taskFromQueue = rabbitmq_queue_get(from_api_queue)
                        
                #         print("there is failed jobs trying to proccess one more time")
                #         break
            clean_redis_list()
            print("Queue is empty. Waiting...")
            logger.info("Queue is empty. Waiting...." )
            # sending data to flask api
            send_logs.send_data_to_flask(0, 'Waiting to queue...',  service_name)
            
            sleep(10)  # Wait for 10 seconds and check the queue again

        print(f'Queue length: {q_len}')
        if taskFromQueue is not None:
                send_logs.send_data_to_flask(0,'Getting data from queue...',   service_name)
                taskFromQueuefixQuotes = re.sub("'", "\"", taskFromQueue)
                taskFromQueueNoNone = re.sub("None", "\"\"", taskFromQueuefixQuotes)
                json_req = json.loads(taskFromQueueNoNone)
                taskCommandID = json_req["command_number"]
                taskFromQueueRecordID = json_req["record_id"]
                req_vlans = json_req["vlans"]
                req_switch =   json_req["switch"]
                req_switch_ip = json_req["switch_ip"]
                req_interface_name = json_req["interface_name"]
                req_port_mode = json_req["port_mode"]
                discovery=json_req["discovery"]
                destination=json_req["destination"]
                gateway=json_req["gateway"]

                vlan_ip = json_req["ip"]
                vlan_subnet = json_req["subnet"]
                comments = json_req["description"]
                comments = f'"{comments}"'
                priority = json_req["priority"]
                api_status = get_id_status(taskFromQueueRecordID)
                api_dr_status = api_status[0]['dr_status']
                print(f"** * api_status: {api_dr_status}")
                logger.info(f"api_status: {api_dr_status}")
                if 'failed' in api_dr_status:
                    # update Redis with new status and push to failed queue if not exists
                    task_set_status_and_queue(json_req, "failed")
                    # redis_server.set(taskCommandID, "failed")
                    continue
                send_status_update(taskFromQueueRecordID,"in_progress","f'task from queue {taskFromQueue} task status {taskStatus}'")
                if json_req["command"] != "":
                    req_cmd = json_req["command"]
                else:
                    req_cmd = ""
        else:
            print("Queue is empty. Waiting...")
            logger.info("Queue is empty. Waiting...")
            send_logs.send_data_to_flask(0, 'Queue is empty. waiting to queue...',  service_name)
            continue


        #### PUSH TO RABBIT "in_progress_tasks"
        # pushing in_progress task in rabbitmq queue 
        task_set_status_and_queue(json_req, "in_progress")
        print(f"taskCommandID: {taskCommandID} is push and set in progress")
        send_logs.send_data_to_flask(0, f"Request {taskCommandID} in progress ",  service_name)
        # redis_server.set(name="current_task_queue", value=json.dumps({"id": taskCommandID, "switch_ip": req_switch_ip, "command": req_cmd}))
        switch_user = None
        switch_password = None
        switch_device_type = None
        switch_details = requests.post(switch_info_url, data=f"{{ 'switch_id': '{req_switch}' }}",headers={'Content-Type': 'application/json'},auth=(settings.username, settings.password)).json()
        
        for i in range(len(switch_details['result'])):
            if (switch_details['result'][i]['ip'] == req_switch_ip):
                switch_user = switch_details['result'][i]['username']
                switch_password = switch_details['result'][i]['password']
                switch_device_type = switch_details['result'][i]['device_type']
                break
                
        if switch_device_type is not None:
            # Get credentials from the dictionary
            send_status_update(taskFromQueueRecordID, "in_progress", "retrieving credentials")
            retrieved_user, retrieved_password = get_credentials(req_switch_ip)

            if retrieved_user is None:
                retrieved_user = switch_user
                retrieved_password = switch_password

            if (retrieved_user is not None and retrieved_password is not None):
                #### TODO move it to ssh connect function
                send_logs.send_data_to_flask(0,f'connecting to {req_switch_ip}. calling function (SSHClient)',  service_name)
                ssh_client = SSHClient(req_switch_ip, retrieved_user, retrieved_password)
                send_logs.send_data_to_flask(0,f'Attempt to establish the SSH connection...',  service_name)
                # Attempt to establish the SSH connection
                sshConnectStatus = ssh_client.try_connect(taskFromQueueRecordID)
                send_logs.send_data_to_flask(0,f'SSH status: {sshConnectStatus}',  service_name)
                send_status_update(taskFromQueueRecordID, "in_progress", "Attempt to establish the SSH connection")

                if not sshConnectStatus:
                    # If failed to connect after MAX attempts, send a status update to ServiceNow
                    error_message = f"Failed to establish SSH connection to {req_switch_ip} after {SSHClient.MAX_RETRIES} attempts."
                    task_set_status_and_queue(json_req, "failed", error_message)
                    send_status_update(taskFromQueueRecordID, "failed",error_message)
                    continue
                send_logs.send_data_to_flask(0, f'closing ssh connection to {req_switch_ip}',  service_name)
                ssh_client.close_connection()

            if switch_device_type == 'switch':
                if (retrieved_user is not None and retrieved_password is not None):
                    # Check if the credentials status is 'failed' and the last attempt was 5 minutes ago
                    if (
                        retrieved_user == switch_user and retrieved_password == switch_password and req_switch_ip in credential_dict and credential_dict[req_switch_ip]["status"] == "failed"):
                        time_since_last_attempt = time() - credential_dict[req_switch_ip]["timestamp"]
                        if time_since_last_attempt > 300:  # 300 seconds = 5 minutes ####NEED to remove
                            try:
                                if req_cmd != "" and req_port_mode == "":
                                    if req_interface_name != "":
                                        send_logs.send_data_to_flask(0, 'calling function (run_command_and_get_json)',  service_name)
                                        output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                    else:
                                        send_logs.send_data_to_flask(0, 'calling function (run_command_and_get_json)...',  service_name)
                                        output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                else:
                                    send_logs.send_data_to_flask(0, 'calling function (change_interface_mode)...',  service_name)
                                    output = change_interface_mode(req_switch_ip, retrieved_user, retrieved_password, req_interface_name, req_port_mode, req_vlans)
                                if glv.added_vlan is not None:  # Check if a VLAN was added
                                    output_message = "Added VLANs: " + ", ".join(map(str, added_vlan))
                                    glv.added_vlan = None  # Reset it after displaying the message
                                else:
                                    output_message = ""
                        
                                if output == None:
                                    output = "operation is done."
                                send_status_update(taskFromQueueRecordID, "in_progress", output)

                            except Exception as error:
                                output = f"{error}"
                                send_logs.send_data_to_flask(1, f'Exception, taskFromQueueRecordID: {taskFromQueueRecordID}, Error: {error}',  service_name)
                                task_set_status_and_queue(json_req, "failed",output) 
                                send_status_update(taskFromQueueRecordID, "failed", error)

                                # Update the credentials with a "failed" status if not already present
                                if req_switch_ip not in credential_dict or credential_dict[req_switch_ip]["status"] != "failed":
                                    update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "failed")

                            else:
                                if output_message is not None:
                                    output = f"{output_message}\n{output}"
                                else:
                                    output = f"{output}"
                                redis_server.set(taskCommandID, "completed")
                                # testing
                                #rabbit_server.basic_publish(exchange="DRAAS",
                                #                            routing_key=completed_tasks,
                                #                            body=json.dumps(json_req),
                                #                            properties=pika.BasicProperties(delivery_mode=2))
                                send_status_update(taskFromQueueRecordID, "completed")
                                update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "success")

                    else:
                        try:
                            if req_cmd != "" and req_port_mode == "":
                                if req_interface_name != "":
                                    send_logs.send_data_to_flask(0, f"running {req_cmd}",  service_name)
                                    output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                else:
                                    send_logs.send_data_to_flask(0, f"running {req_cmd}",  service_name)
                                    output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                            else:
                                send_logs.send_data_to_flask(0, f"calling function (change_interface_mode) on {req_switch_ip} ",  service_name)
                                output = change_interface_mode(req_switch_ip, retrieved_user, retrieved_password, req_interface_name, req_port_mode, req_vlans)

                            if glv.added_vlan is not None:  # Check if a VLAN was added
                                output_message = "Added VLANs: " + ", ".join(map(str, added_vlan))
                                glv.added_vlan = None  # Reset it after displaying the message
                            else:
                                output_message = ""

                            if output == None:
                                output = "operation is done."
                        except Exception as error:
                            output = f"{error}"
                            task_set_status_and_queue(json_req, "failed",output)
                            # send_logs.send_data_to_flask(1, f'id: {taskFromQueueRecordID} failed, {error}',  service_name)
                            
                            # Update the credentials with a "failed" status if not already present
                            if req_switch_ip not in credential_dict or credential_dict[req_switch_ip]["status"] != "failed":
                                update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "failed")
                                push_in_wait_queue(taskFromQueue)

                        else:
                            if output_message is not None:
                                output = f"{output_message}\n{output}"
                            else:
                                output = f"{output}"
                            redis_set(taskCommandID, "completed_tasks")
                            # testing                             
                            # task_sts = json.loads(redis_server.get(taskFromQueueRecordID).decode())["status"]
                            send_status_update(taskFromQueueRecordID, "completed")
                            update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "success")

                # When a task is completed, remove the "current_task" key
                # redis_server.delete("current_task_queue")
            elif switch_device_type == 'gaia':
                try:
                    ##VLAN add/remove
                    if discovery == "0" and req_interface_name and req_vlans:
                        if req_cmd.lower() == "add vlan":
                            send_logs.send_data_to_flask(0, 'Calling function (add_gaia_vlan)...',  service_name)
                            cmd_output= gaia_ssh_connect.add_gaia_vlan(req_switch_ip, switch_user, switch_password, req_interface_name, req_vlans, vlan_ip, vlan_subnet,comments)
                            action = "added"
                        elif req_cmd.lower() == "delete vlan":
                            send_logs.send_data_to_flask(0, 'Calling function (remove_gaia_vlan)...',  service_name)
                            cmd_output= gaia_ssh_connect.remove_gaia_vlan(req_switch_ip, switch_user, switch_password, req_interface_name, req_vlans)
                            action = "removed"
                        
                        if "error" in cmd_output or "Invalid" in cmd_output or "is down" in cmd_output:
                            if action == "added":
                                output = f'Cannot add the VLAN because: {cmd_output}'
                            elif action == "removed":
                                output = f'Cannot delete the VLAN because: {cmd_output}'
                            send_logs.send_data_to_flask(0, 'Calling function (send_gaia_status)...',  service_name)
                            send_gaia_status(json_req, status_message="status: failed", output=output, error=output,
                                            req_cmd=req_cmd, destination=destination, gateway=gateway, req_vlans=req_vlans,req_interface_name=req_interface_name)
                        else:
                            send_logs.send_data_to_flask(0, 'Calling function (get_gaia_interface_info)...',  service_name)
                            gaia_interface_info = gaia_ssh_connect.get_gaia_interface_info(req_switch_ip, switch_user, switch_password)
                            send_logs.send_data_to_flask(0, 'Calling function (get_gaia_hostname)...',  service_name)
                            hostname = gaia_ssh_connect.get_gaia_hostname(req_switch_ip, switch_user, switch_password)
                            interface_dict = json.loads(gaia_interface_info)
                            combined_data = {"hostname": hostname, "interfaces": interface_dict}
                            json_data = json.dumps(combined_data, indent=4)

                            output_message = f"VLANs {req_vlans} {action} to interface {req_interface_name} on Gaia switch {req_switch_ip}."
                            output = f"{output_message}\n{json_data}"
                            send_logs.send_data_to_flask(0, 'Calling function (send_gaia_status)...',  service_name)
                            send_gaia_status(json_req, status_message="status: success", output=output, error=None,
                                            req_cmd=None, destination=None, gateway=None, req_vlans=None,req_interface_name=None)

                    ##routing add/remove
                    elif discovery == "0" and destination:
                        if req_cmd.lower() == "add route":
                            if gateway is not None:
                                if priority is not None:
                                    send_logs.send_data_to_flask(0, 'Calling function (add_gaia_route)...',  service_name)
                                    cmd_output= gaia_ssh_connect.add_gaia_route(req_switch_ip, switch_user, switch_password, destination, gateway,priority)
                                else:
                                    send_logs.send_data_to_flask(0, 'Calling function (add_gaia_route)...',  service_name)
                                    cmd_output= gaia_ssh_connect.add_gaia_route(req_switch_ip, switch_user, switch_password, destination, gateway)
                                action = "added"
                            else:
                                cmd_output = "No Gateway is provided"
                                
                        elif req_cmd.lower() == "delete route":
                            send_logs.send_data_to_flask(0, 'Calling function (remove_gaia_route)...',  service_name)                                
                            cmd_output = gaia_ssh_connect.remove_gaia_route(req_switch_ip, switch_user, switch_password, destination)
                            action = "removed"

                        if "error" in cmd_output or "Invalid" in cmd_output or "is down" in cmd_output:
                            if action == "added":
                                output = f'Cannot add the route because: {cmd_output}'
                            elif action == "removed":
                                output = f'Cannot delete the route because: {cmd_output}'

                            send_gaia_status(taskFromQueueRecordID, status_message="status: failed", output=output, error=output,
                                            req_cmd=req_cmd, destination=destination, gateway=gateway, req_vlans=req_vlans,req_interface_name=req_interface_name)

                        else:
                            send_logs.send_data_to_flask(0, 'Calling function (get_gaia_route_info)...',  service_name)                                
                            gaia_route_info = gaia_ssh_connect.get_gaia_route_info(req_switch_ip, switch_user, switch_password)
                            send_logs.send_data_to_flask(0, 'Calling function (get_gaia_hostname)...',  service_name)                                
                            hostname = gaia_ssh_connect.get_gaia_hostname(req_switch_ip, switch_user, switch_password)
                            route_dict = json.loads(gaia_route_info)
                            combined_data = {"hostname": hostname,"routes": route_dict}
                            json_data = json.dumps(combined_data, indent=4)
                        
                            output_message = f"Route for {destination} {action} on Gaia switch {req_switch_ip}."
                            output = f"{output_message}\n{json_data}"

                            send_gaia_status(taskFromQueueRecordID, status_message="status: success", output=output, error=None,
                                            req_cmd=None, destination=None, gateway=None, req_vlans=None,req_interface_name=None)

                    if discovery == "1":
                        send_logs.send_data_to_flask(0, 'calling function (get_gaia_interface_info)...',  service_name)                                                                
                        gaia_interface_info = gaia_ssh_connect.get_gaia_interface_info(req_switch_ip, switch_user, switch_password)
                        send_logs.send_data_to_flask(0, 'calling function (get_gaia_interface_info)...',  service_name)                                                                
                        gaia_route_info = gaia_ssh_connect.get_gaia_route_info(req_switch_ip, switch_user, switch_password)
                        hostname = gaia_ssh_connect.get_gaia_hostname(req_switch_ip, switch_user, switch_password)

                        interface_dict = json.loads(gaia_interface_info)
                        route_dict = json.loads(gaia_route_info)
                        hostname = hostname[0].strip() if hostname else None

                        combined_data = {"hostname": hostname, "interfaces": interface_dict, "routes": route_dict}
                        json_data = json.dumps(combined_data, indent=4)
                        output = json_data

                        send_gaia_status(json_req, status_message="status: success", output=output, error=None,
                                            req_cmd=None, destination=None, gateway=None, req_vlans=None,req_interface_name=None)

                except Exception as error:
                    send_gaia_status(json_req, status_message="status: failed", output=None, error=error,
                                            req_cmd=req_cmd, destination=destination, gateway=gateway, req_vlans=req_vlans,req_interface_name=req_interface_name)
        else:
            print(f"No matching switch found for IP: {req_switch_ip}")
            redis_set(taskCommandID, "failed")
            send_status_update(json_req, "failed", "Could not find switch for IP")

        sleep(10)

if __name__ == "__main__":
    main()
