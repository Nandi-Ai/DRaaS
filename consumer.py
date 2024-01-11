import redis, requests
import re, json, sys, dotenv
from time import sleep, time
from functions import *
import glv; from glv import added_vlan
import gaia_ssh_connect
#import api
import logging, time
import settings
from settings import *
settings.init()

# Create a Redis server connections.
redis_server = redis.Redis()
queue_name = "api_req_queue"
redis_server2 = redis.Redis()
current_task_que = "current_task_que"
switch_info_url = settings.switch_info_url
get_cmds_url = settings.url + "/getCommands"
update_req_url = settings.url + "/SetCommandStatus"

# this module will be used to get an instance of the logger object 
logger = logging.getLogger(__name__)
# Define the time format
time_format = "%Y-%m-%d %H:%M:%S"
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

# Dictionary to store credentials of switches
credential_dict = {}

# Function to set a value in Redis
def redis_set(KEY="", VALUE="", OUTPUT=""):
    try:
        if OUTPUT:
            OUTPUT = re.sub("\"", "\\\"", "      ".join(OUTPUT.splitlines()))
        else:
            OUTPUT = ""  # Handle the case where OUTPUT is None or empty
        redis_server.set(name=KEY, value=f'{{ "status": "{VALUE}", "output": "{OUTPUT}" }}')
        #print(redis_server.get(KEY))
        logger.info('Redis set - Key: %s, Value: %s', KEY, VALUE)
    except Exception as e:
        logger.error('Error in redis_set: %s', str(e))

# Function to get the next request from the Redis queue
def redis_queue_get():
    try:
        req = redis_server.lpop(queue_name)
        print(req)
        if req is not None:
            logger.info('Redis queue get - Request: %s', req.decode())
            return req.decode()
        else:
            return None
    except Exception as e:
        logger.error('Error in redis_queue_get: %s', str(e))
        return None
    
# Function to send a status or update to ServiceNow API
def send_status_update(ID, STATUS, OUTPUT):
    payload = json.dumps({"command_id": f"{ID}", "command_status": f"{STATUS}", "command_output": f"{OUTPUT}"})
    answer = requests.post(update_req_url, data=payload, headers={'Content-Type': 'application/json'},
                           auth=(settings.username, settings.password))
    
# Function to update the credentials dictionary with the status
def update_credential_dict(ip, username, password, status):
    timestamp = time()
    credential_dict[ip] = {"timestamp": timestamp, "status": status, "user": username, "pass": password}

# Function to get credentials from the dictionary
def get_credentials(ip):
    credential = credential_dict.get(ip, {})
    return (credential["user"], credential["pass"]) if credential.get("status") == "success" else (None, None)

# Main function
def main():
    glv.added_vlan  # Declare that we are using the global variable
    #max_wait_time = 100 * 60  # Maximum wait time in seconds (30 minutes)
    #start_time = time()
    while True:
        #start_time = time()
        while True:
            q_len = redis_server.llen(queue_name)
            if q_len > 0:
                break
            #if time() - start_time > max_wait_time:
                #print("Maximum wait time reached. Exiting.")
                #return  # Exit the program after waiting for the maximum time
            print("Queue is empty. Waiting...")
            logger.info("Queue is empty. Waiting...." )
            sleep(10)  # Wait for 10 seconds and check the queue again

        print(f'Queue length: {q_len}')
        requests_list = redis_server.lrange(queue_name, 0, q_len)

        for req in requests_list:
            next_req = redis_queue_get()
            if next_req is not None:
                fix_quotes = re.sub("'", "\"", next_req)
                no_none = re.sub("None", "\"\"", fix_quotes)
                json_req = json.loads(no_none)
                req_id = json_req["record_id"]
                req_vlans = json_req["vlans"]
                req_switch =   json_req["switch"] #2aa1ebb587571d905db3db1cbbbb359d
                req_switch_ip = json_req["switch_ip"]
                req_interface_name = json_req["interface_name"]
                req_port_mode = json_req["port_mode"]
                discovery=json_req["discovery"]

                #switch_status=json_req["switch_status"]
                destination=json_req["destination"]
                gateway=json_req["gateway"]

                if json_req["command"] != "":
                    req_cmd = json_req["command"]
                else:
                    req_cmd = ""
            else:
                print("Queue is empty. Waiting...")
                logger.info("Queue is empty. Waiting...")

            task_sts = redis_server.get(req_id)
            if task_sts is None:
                redis_set(req_id, "active")
                task_sts = redis_server.get(req_id)

            if "active" in str(task_sts):
                redis_server2.set(name="current_task", value=json.dumps({"id": req_id, "switch_ip": req_switch_ip, "command": req_cmd}))

                switch_user = None
                switch_password = None
                switch_device_type = None
                switch_details = requests.post(switch_info_url, data=f"{{ 'switch_id': '{req_switch}' }}",headers={'Content-Type': 'application/json'},auth=(settings.username, settings.password)).json()
                print(switch_details)
                
                for i in range(len(switch_details['result'])):
                    if (switch_details['result'][i]['ip'] == req_switch_ip):
                        switch_user = switch_details['result'][i]['username']
                        switch_password = switch_details['result'][i]['password']
                        switch_device_type = switch_details['result'][i]['device_type']
                        break

                print(switch_device_type)

                if switch_device_type is not None:
  
                    # Get credentials from the dictionary
                    retrieved_user, retrieved_password = get_credentials(req_switch_ip)

                    if retrieved_user is None:
                        retrieved_user = switch_user
                        retrieved_password = switch_password

                    if (retrieved_user is not None and retrieved_password is not None):
                        ssh_client = SSHClient(req_switch_ip, retrieved_user, retrieved_password)
                        # Attempt to establish the SSH connection
                        connected = ssh_client.try_connect(req_id)

                        if not connected:
                            # If failed to connect after 5 attempts, send a status update to ServiceNow
                            error_message = f"Failed to establish SSH connection to {req_switch_ip} after {SSHClient.MAX_RETRIES} attempts."
                            redis_set(req_id, "failed", error_message)
                            send_status_update(req_id, "failed", error_message)
                            # Update the credentials with a "failed" status if not already present
                            continue
                        ssh_client.close_connection()

                    if switch_device_type == 'switch':
                        if (retrieved_user is not None and retrieved_password is not None):
                            # Check if the credentials status is 'failed' and the last attempt was 5 minutes ago
                            if (
                                    retrieved_user == switch_user and
                                    retrieved_password == switch_password and
                                    req_switch_ip in credential_dict and
                                    credential_dict[req_switch_ip]["status"] == "failed"):

                                time_since_last_attempt = time() - credential_dict[req_switch_ip]["timestamp"]
                                if time_since_last_attempt > 300:  # 300 seconds = 5 minutes
                                    try:
                                        if req_cmd != "" and req_port_mode == "":
                                            if req_interface_name != "":
                                                output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                            else:
                                                output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                        else:
                                            output = change_interface_mode(req_switch_ip, retrieved_user, retrieved_password, req_interface_name, req_port_mode, req_vlans)

                                        if glv.added_vlan is not None:  # Check if a VLAN was added
                                            output_message = "Added VLANs: " + ", ".join(map(str, added_vlan))
                                            glv.added_vlan = None  # Reset it after displaying the message
                                        else:
                                            output_message = ""
                                
                                        if output == None:
                                            output = "operation is done."

                                    except Exception as error:
                                        status_message = "status: failed"
                                        output = f"{status_message} {error}"
                                        send_status_update(req_id, "failed", error)
                                        # Update the credentials with a "failed" status if not already present
                                        if req_switch_ip not in credential_dict or credential_dict[req_switch_ip]["status"] != "failed":
                                            update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "failed")

                                    else:
                                        status_message = "status: success"
                                        if output_message is not None:
                                            output = f"{status_message}\n{output_message}\n{output}"
                                        else:
                                            output = f"{status_message}\n{output}"
                                        redis_set(req_id, "completed", output)
                                        task_sts = json.loads(redis_server.get(req_id).decode())["status"]
                                        send_status_update(req_id, task_sts, output)
                                        update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "success")

                            else:
                                try:
                                    if req_cmd != "" and req_port_mode == "":
                                        if req_interface_name != "":
                                            output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                        else:
                                            output = run_command_and_get_json(req_switch_ip, retrieved_user, retrieved_password, req_cmd)
                                    else:
                                        output = change_interface_mode(req_switch_ip, retrieved_user, retrieved_password, req_interface_name, req_port_mode, req_vlans)

                                    if glv.added_vlan is not None:  # Check if a VLAN was added
                                        output_message = "Added VLANs: " + ", ".join(map(str, added_vlan))
                                        glv.added_vlan = None  # Reset it after displaying the message
                                    else:
                                        output_message = ""

                                    if output == None:
                                        output = "operation is done."

                                except Exception as error:
                                    status_message = "status: failed"
                                    output = f"{status_message} {error}"
                                    send_status_update(req_id, "failed", error)
                                    #Update the credentials with a "failed" status if not already present
                                    if req_switch_ip not in credential_dict or credential_dict[req_switch_ip]["status"] != "failed":
                                        update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "failed")

                                else:
                                    status_message = "status: success"
                                    if output_message is not None:
                                        output = f"{status_message}\n{output_message}\n{output}"
                                    else:
                                        output = f"{status_message}\n{output}"
                                    redis_set(req_id, "completed", output)
                                    task_sts = json.loads(redis_server.get(req_id).decode())["status"]
                                    send_status_update(req_id, task_sts, output)
                                    update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "success")

                        # When a task is completed, remove the "current_task" key
                        redis_server2.delete("current_task")

                        print(credential_dict)

                    elif switch_device_type == 'gaia':
                        try:
                            ##VLAN add/remove
                            if discovery == "0" and req_interface_name and req_vlans:
                                if req_cmd == "Add vlan":
                                    gaia_ssh_connect.add_gaia_vlan(req_switch_ip, switch_user, switch_password, req_interface_name, req_vlans)
                                    action = "added"
                                elif req_cmd == "Delete vlan":
                                    gaia_ssh_connect.remove_gaia_vlan(req_switch_ip, switch_user, switch_password, req_interface_name, req_vlans)
                                    action = "removed"

                                gaia_interface_info = gaia_ssh_connect.get_gaia_interface_info(req_switch_ip, switch_user, switch_password)
                                interface_dict = json.loads(gaia_interface_info)
                                combined_data = {"interfaces": interface_dict}
                                json_data = json.dumps(combined_data, indent=4)

                                status_message = "status: success"
                                output_message = f"VLANs {req_vlans} {action} to interface {req_interface_name} on Gaia switch {req_switch_ip}."
                                output = f"{status_message}\n{output_message}\n{json_data}"
                    
                                redis_set(req_id, "completed", output)
                                task_sts = json.loads(redis_server.get(req_id).decode())["status"]
                                send_status_update(req_id, task_sts, output)

                            ##routing add/remove
                            elif discovery == "0" and destination and gateway:
                                if req_cmd == "Add route":
                                    gaia_ssh_connect.add_gaia_route(req_switch_ip, switch_user, switch_password, destination, gateway)
                                    action = "added"
                                elif req_cmd == "Delete route":
                                    gaia_ssh_connect.remove_gaia_route(req_switch_ip, switch_user, switch_password, destination, gateway)
                                    action = "removed"

                                gaia_route_info = gaia_ssh_connect.get_gaia_route_info(req_switch_ip, switch_user, switch_password)
                                route_dict = json.loads(gaia_route_info)
                                combined_data = {"routes": route_dict}
                                json_data = json.dumps(combined_data, indent=4)

                                status_message = "status: success"
                                output_message = f"Route for {destination} {action} on Gaia switch {req_switch_ip}."
                                output = f"{status_message}\n{output_message}\n{json_data}"

                                redis_set(req_id, "completed", output)
                                task_sts = json.loads(redis_server.get(req_id).decode())["status"]
                                send_status_update(req_id, task_sts, output)

                            if discovery == "1":
                                gaia_interface_info = gaia_ssh_connect.get_gaia_interface_info(req_switch_ip, switch_user, switch_password)
                                gaia_route_info = gaia_ssh_connect.get_gaia_route_info(req_switch_ip, switch_user, switch_password)
                                interface_dict = json.loads(gaia_interface_info)
                                route_dict = json.loads(gaia_route_info)
                                combined_data = {"interfaces": interface_dict, "routes": route_dict}
                                json_data = json.dumps(combined_data, indent=4)
            
                                status_message = "status: success"
                                output = json_data

                                redis_set(req_id, "completed", output)
                                task_sts = json.loads(redis_server.get(req_id).decode())["status"]
                                send_status_update(req_id, task_sts, output)

                        except Exception as error:
                            status_message = "status: failed"
    
                            # Adjusting the error message based on the command and including the gateway if available
                            if req_cmd == "Add route":
                                output = f"{status_message} Error adding route for {destination} and gateway {gateway if gateway else 'None'}: {error}"
                            elif req_cmd == "Delete route":
                                output = f"{status_message} Error removing route for {destination} and gateway {gateway if gateway else 'None'}: {error}"
                            elif req_cmd == "Add vlan":
                                output = f"{status_message} Error adding VLANs {req_vlans} to interface {req_interface_name}: {error}"
                            elif req_cmd == "Delete vlan":
                                output = f"{status_message} Error removing VLANs {req_vlans} from interface {req_interface_name}: {error}"
                            else:
                                output = f"{status_message} Error: {error}"

                            send_status_update(req_id, "failed", output)
               
                else:
                    print(f"No matching switch found for IP: {req_switch_ip}")

            elif "completed" in str(task_sts):
                continue

        sleep(10)

if __name__ == "__main__":
    main()

