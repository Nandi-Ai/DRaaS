import time, sys, threading; from unittest import result; import requests, json, re, os; import logging
from datetime import datetime, timedelta; 
import configparser,confparser; import paramiko; from ntc_templates.parse import parse_output
from netmiko import ConnectHandler; import json; from dotenv import load_dotenv; from socket import *
import glv; import redis
load_dotenv()
from time import sleep, time
import settings; from settings import *; settings.init()
import send_logs
from rabbitmq import *

rabbit_server = rabbit_connection()
logging.getLogger('pika').setLevel(logging.CRITICAL)

config = configparser.ConfigParser()
config.sections()
config.read('../config/parameters.ini')
# config.read('./config/parameters.ini')

logger = logging.getLogger(__name__)
redis_server = redis.Redis(host='localhost', port=6379, db=0)
redis_server = redis.StrictRedis(charset="utf=8", decode_responses=True)
queue_name = glv.api_queue_name
completed_tasks = glv.completed_tasks
failed_tasks = glv.failed_tasks
incomplete_tasks = glv.incomplete_tasks
in_progress_tasks = glv.in_progress_tasks
wait_queue = glv.wait_queue
update_req_url = settings.url + "/SetCommandStatus"
managment_logs_url = settings.url + "/postSwitchManagmentLogs"
added_vlan = glv.added_vlan
credential_dict = glv.credential_dict
max_attempts = 3

#SSH connection function
class SSHClient:
    MAX_RETRIES = 3
    def __init__(self, address, username, password):
        print("Connecting to server on IP", str(address) + ".")
        self.connection_params = {
            'device_type': 'cisco_ios',
            'ip': address,
            'username': username,
            'password': password,
        }
        self.connection = None

    def connect(self):
        self.connection = ConnectHandler(**self.connection_params)
        self.connection.enable()

    def try_connect(self,req_id=None):
        # from consumer import send_status_update
        attempts = 0
        while attempts < self.MAX_RETRIES:
            try:
                self.connection = ConnectHandler(**self.connection_params)
                return True
            except Exception as e:
                print(f"Failed to connect. Attempt {attempts+1}/{self.MAX_RETRIES}. Error: {e}")
                send_status_update(req_id, "Active", f"Attempt {attempts+1}/{self.MAX_RETRIES} failed.")
                sleep(10)  # Wait for 10 seconds before retrying
                attempts += 1
        return False

    def close_connection(self):
        if self.connection:
            self.connection.disconnect()

    def exec_command(self, command, use_textfsm=False, expect_string=None):
        if self.connection:
            if use_textfsm:
                output = self.connection.send_command(command, use_textfsm=True, expect_string=expect_string)
            else:
                output = self.connection.send_command(command, expect_string=expect_string)
            return output
        else:
            raise ValueError("SSH connection is not established.")

class ssh_new:
    shell = None
    client = None
    transport = None

    def __init__(self, address, username, password):
        print("Connecting to server on ip", str(address) + ".")
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        self.client.connect(address, username=username, password=password, look_for_keys=False)

    def close_connection(self):
        if(self.client != None):
            self.client.close()

    def open_shell(self):
        self.shell = self.client.invoke_shell()


    def exec_command(self, command):
        _, ssh_stdout, ssh_stderr = self.client.exec_command(command)
        err = ssh_stderr.readlines()
        return err if err else ssh_stdout.readlines()

    def send_shell(self, command):
        if(self.shell):
            return self.shell.send(command + "\n")
        else:
            print("Shell not opened.")

def get_device_type(ssh_client):
    """Determine the device type based on the 'show version' output."""
    output = ssh_client.exec_command("show version")
    if "Cisco Nexus" in output or "Nexus" in output or "NX-OS" in output:
        return "nexus"
    elif "Cisco IOS" in output:
        return "ios"
    else:
        raise ValueError("Unsupported device type detected.")

def run_command_and_get_json(ip_address, username, password, command):
    # Create an instance of the SSHClient class
    ssh_client = SSHClient(ip_address, username, password)
    try:
        # Establish the SSH connection
        ssh_client.connect()

        # Determine device type
        device_type = get_device_type(ssh_client)

        if device_type == "nexus":
            if 'show run' in command:
                output = ssh_client.exec_command(command)
                parsed_data = confparser.Dissector.from_file('nexus.yaml').parse_str(output)
                json_data = json.dumps(parsed_data, indent=4)
            else:
                output = ssh_client.exec_command(command, use_textfsm=True )
                json_data = json.dumps(output, indent=2)
        elif device_type == "ios":
            if 'show run' in command:
                output = ssh_client.exec_command(command)
                parsed_data = confparser.Dissector.from_file('ios.yaml').parse_str(output)
                json_data = json.dumps(parsed_data, indent=4)
            else:
                output = ssh_client.exec_command(command, use_textfsm=True)
                json_data = json.dumps(output, indent=2)
        else:
            raise ValueError("Unsupported device type detected.")

        return json_data

    except (paramiko.AuthenticationException, paramiko.SSHException, ValueError) as error:
        # Raise an exception if there is an error during the connection or if unsupported device type detected
        raise error

    finally:
        # Close the SSH connection when done
        ssh_client.close_connection()



def notify(task, status, msg =""):
    recordID=task["record_id"]
    taskCommandID=task["command_number"]
    if status == "failed":
        send_status_update(recordID, "failed", msg)
        send_logs.send_data_to_flask(0, f' {msg}  Task command id {taskCommandID}',  "consumer")


def get_task_status(task):
    task = json.loads(task)
    task_command_id=task["command_number"]
    redisJobStatus = redis_server.get(task_command_id)
    return redisJobStatus


def redis_set(taskCommandID, taskStatus):
    redis_server.set(taskCommandID,taskStatus)


def redis_remove_list(taskCommandID="", task_status="", output = ""):
        allTasksinList = redis_server.lrange("inprogress_list", 0, -1)
        
        for task in allTasksinList:
            taskCommandIDL = task["command_number"]
            if taskCommandIDL == taskCommandID:
                redis_server.lrem("inprogress_list", 10, task)
                print(f"removed {taskCommandID} from list...")
                if task_status == "in_progress":
                    rabbitmq_push(task, incomplete_tasks)
                    send_status_update(taskCommandID, "incomplete", "taking too long to process")
                    send_logs.send_data_to_flask(0, f'task {taskCommandID} is stuck. pushing to incomplete_tasks',  "consumer")
                if task_status == "failed":
                    notify(taskCommandIDL, "failed", "task is failed")
                    send_status_update(taskCommandIDL, "failed", output)
                    send_logs.send_data_to_flask(0, f'task {taskCommandID} failed',  "consumer")

                return True
            
        print(f"didnt find {taskCommandID} in list")
        return False

def redis_set_list(taskCommandID="", taskStatus="", full_task="",output=""):
    try:
        if taskStatus == "failed":
            redis_set(taskCommandID, taskStatus)
            redis_remove_list(taskCommandID, taskStatus,output)
        elif taskStatus == "in_progress":
            redis_server.lpush(in_progress_tasks, full_task)
            redis_server.set(taskCommandID, taskStatus, ex=600) # 10 minute
            print(f"***** taskCommandID: {taskCommandID} is set and push redis in_progress queue: *****")
        else:
            redis_server.set(taskCommandID, taskStatus)
            print(f"***** taskCommandID: {taskCommandID} is set in {taskStatus}  *****")
            
        logger.info('Redis set - Key: %s, Value: %s', taskCommandID, taskStatus)
        send_logs_to_api(f'Redis set - Key: {taskCommandID}, Value: {taskStatus}', 'info', settings.mid_server)
        
    except Exception as err:
        send_logs_to_api(f'Error in updating API', 'error', settings.mid_server)
        logger.error('Error in redis_set: %s', str(err))



def rabbitmq_push(TASK, QUEUE_NAME):
    try:
        rabbit_server.basic_publish(exchange="",
                                    routing_key=QUEUE_NAME,
                                    body=json.dumps(TASK),
                                    properties=pika.BasicProperties(delivery_mode=2))
        print(f"***** Successfully Pushed to {QUEUE_NAME} *****")
    except Exception as err:
        print("***** Error While pushing task in queue Error_msg: ", err, " *****")


def push_in_wait_queue(task):
    time = round(time.time())
    if task["attempt"]:
        attempts = task["attempt"]
        if attempts > max_attempts:
            notify(task, "failed")
            return False
        else:
          task["attempt"] = attempts + 1
    else: 
        jsonToAppend = {
            "time": time,
            "attempt": 1
        }
    task.update(jsonToAppend)
    rabbitmq_push(task, wait_queue)
    return task
  
  
def rabbitmq_queue_get(queue_name):
    try:    
        method_frame, header_frame, body = rabbit_server.basic_get(queue=queue_name, auto_ack=True)

        if method_frame:
                       # i try this. to get dictionary from queue.  json.loads(body.decode()) 
            message = body.decode()
            print("Request from RabbitMQ:", message)
            logger.info('RabbitMQ queue get - Request: %s', message)
            send_logs_to_api('RabbitMQ queue get Request', 'info', settings.mid_server)
            return message
        else:
            return None    
    except Exception as err:
        logger.error('Error while getting rabbitmq queue: %s', str(err))
        send_logs_to_api(f'Error while getting rabbitmq queue: {str(err)}', 'error', settings.mid_server)
        return None

def check_wait_queue():
    current_time = round(time())

    task = rabbitmq_queue_get(wait_queue)
    if task:
        TaskTime=task["time"]
        attempts=task["attempt"]
        if (current_time - TaskTime > 300) :
            task["attempt"] = attempts + 1
            return task
        else:
            result = push_in_wait_queue(task)
            if result:
                return result
            else:
                return False
    else:
        print("No queue found in wait queue")
        return False
                
    
    

# Function to update the credentials dictionary with the status
def update_credential_dict(ip, username, password, status):
    timestamp = time()
    credential_dict[ip] = {"timestamp": timestamp, "status": status, "user": username, "pass": password}

# Function to send a status or update to ServiceNow API
def send_status_update(ID, STATUS, OUTPUT):
    status = STATUS.lower()
    print(f"{ID}, STATUS: {status}, OUTPUT: {OUTPUT}")
    payload = json.dumps({"command_id": f"{ID}", "command_status": f"{status}", "command_output": f"{OUTPUT}"})
    response = requests.post(update_req_url, data=payload, headers={'Content-Type': 'application/json'},
                           auth=(settings.username, settings.password))
    valid_response_code(response.status_code, ID)

# Initialize the message counter
message_counter = 0
def send_logs_to_api(message, severity, source):
    timestamp = datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')
    try:
        global message_counter 
        message_counter = (message_counter + 1) % 101
        message_id = f"{timestamp} - {message_counter}"
        payload = json.dumps({
            "message": message,
            "severity": severity,
            "source": source,
            "timestamp": timestamp,
            "message_id": message_id})
        print(payload)
        answer = requests.post(managment_logs_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
    except Exception as e:
        logger.error("Error occurred while sending log to API: %s", str(e))

def valid_response_code(statusCode,ID):
    if statusCode != 200:
        print("Api is not accesble. StatusCode is:", statusCode)
        logger.error('Error in updating API')
        send_logs_to_api(f'Error in updating API', 'error', settings.mid_server)
        redis_server.rpush(incompleted_tasks, ID)

#Not Working Function - Fix
def send_successORfailed_status(req_id, status_message=None, output_message=None, error=None, output=None, req_switch_ip=None, retrieved_user=None, retrieved_password=None):
    
    if status_message == "status: success":
        if output_message is not None:
            output = f"{output_message}\n{output}"
        else:
            output = f"{output}"
        redis_set(req_id, "completed", output)
        task_status = json.loads(redis_server.get(req_id).decode())["status"]
        send_status_update(req_id, task_status, output)
        update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "success")

    elif status_message == "status: failed":
        output = f"{error}"
        send_status_update(req_id, "failed", error)
        #Update the credentials with a "failed" status if not already present
        if req_switch_ip not in credential_dict or credential_dict[req_switch_ip]["status"] != "failed":
            update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "failed")    

def send_gaia_status(req_id, status_message=None, output=None, error=None, req_cmd=None, destination=None, gateway=None, req_vlans=None,req_interface_name=None):
    if status_message == "status: success":
        redis_set(req_id, "completed", output)
        task_status = json.loads(redis_server.get(req_id).decode())["status"]
        send_status_update(req_id, task_status, output)

    elif status_message == "status: failed":
        if req_cmd.lower() == "add route":
            output = f"{status_message} Error adding route for {destination} and gateway {gateway if gateway else 'None'}: {error}"
        elif req_cmd.lower() == "delete route":
            output = f"{status_message} Error removing route for {destination} and gateway {gateway if gateway else 'None'}: {error}"
        elif req_cmd.lower() == "add vlan":
            output = f"{status_message} Error adding VLANs {str(req_vlans)} to interface {req_interface_name}: {error}"
        elif req_cmd.lower() == "delete vlan":
            output = f"{status_message} Error removing VLANs {str(req_vlans)} from interface {req_interface_name}: {error}"
        else:
            output = f"{status_message} Error: {error}"
        redis_set(req_id, "failed", output)
        send_status_update(req_id, "failed", output)

def check_privileged_connection(connection):
    """
    Check if the SSH connection is privileged.
    """
    buffer_size = 4096
    def flush(connection):
        while connection.shell.recv_ready():
            connection.shell.recv(buffer_size)
    def get_prompt(connection):
        flush(connection)  # flush everything from before
        connection.shell.sendall('\n')

        time.sleep(.3)
        data = str(connection.shell.recv(buffer_size), encoding='utf-8').strip()
        flush(connection)  # flush everything after (just in case)

        return data
    prompt = get_prompt(connection)
    return True if prompt[-1] == '#' else False

def check_vlan_exists(ip_address, username, password, vlan_id):
    response = run_command_and_get_json(ip_address, username, password, f'show vlan id {vlan_id}')
    if "not found in current VLAN database" in response:
        print(f"VLAN {vlan_id} not found. Creating the VLAN...")
        create_vlan_command = f'vlan {vlan_id}'
        run_command_and_get_json(ip_address, username, password, create_vlan_command)
        print(f"VLAN {vlan_id} created.")
        added_vlan.append(vlan_id)  # Append the VLAN ID to the list of added VLANs in glv
        return True
    else:
        print(f"VLAN {vlan_id} already exists.")
        return True  # The VLAN exists

def change_interface_mode(ip_address, username, password, interface, mode, vlan_range, enable_pass=None):
    """
    Change the mode of a network interface on a switch.
    """
    connection = ssh_new(ip_address, username, password)
    try:
        connection.open_shell()
        time.sleep(1)

        if not check_privileged_connection(connection):
            if enable_pass is not None:
                connection.send_shell('enable')
                time.sleep(1)
                connection.send_shell(enable_pass)
                time.sleep(1)
            else:
                raise ValueError('enable_pass is missing, and SSH connection is not privileged')

        connection.send_shell('conf terminal')
        time.sleep(1)
        connection.send_shell(f'interface {interface}')
        time.sleep(1)

        # Remove any existing configuration related to the opposite mode
        if mode == 'trunk':
            connection.send_shell('no switchport access vlan')
            connection.send_shell('no switchport mode access')
            connection.send_shell('switchport trunk encapsulation dot1q')
            connection.send_shell('switchport mode trunk')
            
            vlan_ids = []

            for vlan_group in vlan_range.split(','):
                if "-" in vlan_group:
                    start_vlan, end_vlan = map(int, vlan_group.split('-'))
                    vlan_ids.extend(range(start_vlan, end_vlan + 1))
                else:
                    vlan_ids.append(int(vlan_group))

            for vlan_id in vlan_ids:
                if check_vlan_exists(ip_address, username, password, vlan_id) == False:
                    raise ValueError(f'VLAN {vlan_id} is missing in device configuration')
                connection.send_shell(f'switchport trunk allowed vlan add {vlan_id}')
            
            print(f'Interface {interface} mode changed to trunk, allowed VLANs: {vlan_range}')
        elif mode == 'access':
            connection.send_shell('no switchport trunk encapsulation dot1q')
            connection.send_shell('no switchport mode trunk')
            
            if "-" in vlan_range:
                raise ValueError("VLAN range is not supported in access mode")
            elif vlan_range:
                vlan_id = int(vlan_range)
                if check_vlan_exists(ip_address, username, password, vlan_id) == False:
                    raise ValueError(f'VLAN {vlan_id} is missing in device configuration')
                connection.send_shell(f'switchport access vlan {vlan_id}')
            
            print(f'Interface {interface} mode changed to access, VLAN: {vlan_range}')
            connection.send_shell('no switchport trunk allowed vlan')  # Remove trunk allowed VLANs
        
        connection.send_shell('exit')
        connection.send_shell('exit')
        connection.send_shell('write memory')  # Save the configuration to memory
        time.sleep(10)  # Give it some time to save the configuration
        connection.close_connection()

    except (paramiko.AuthenticationException, paramiko.SSHException) as error:
        # Raise an exception if there is an error during the connection
        raise error


    
    
