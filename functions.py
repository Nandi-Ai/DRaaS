import time, sys, threading; from unittest import result; import requests, json, re, os; import logging
from datetime import datetime; import paramiko, configparser, confparser; from ntc_templates.parse import parse_output
from netmiko import ConnectHandler; import json
from dotenv import load_dotenv; from socket import *
import glv; import redis
load_dotenv()
from time import sleep, time
import settings; from settings import *; settings.init()
config = configparser.ConfigParser()
config.sections()
config.read('./config/parameters.ini')

logger = logging.getLogger(__name__)
redis_server = redis.Redis()
queue_name = glv.queue_name
completed_tasks = glv.completed_tasks
failed_tasks = glv.failed_tasks
incompleted_tasks = glv.incompleted_tasks
update_req_url = settings.url + "/SetCommandStatus"
managment_logs_url = settings.url + "/postSwitchManagmentLogs"
added_vlan = glv.added_vlan
credential_dict = glv.credential_dict


# Custom log handler class to send log messages to the API
class APILogHandler(logging.Handler):
    def __init__(self, source):
        super().__init__()
        self.source = source

    def emit(self, record):
        try:
            message = self.format(record)
            timestamp = datetime.fromtimestamp(record.created).strftime('%d/%m/%Y %I:%M:%S %p')
            message_id = f"{record.created}-{hash(message)}"  # Generate a unique message ID

            # Map logging levels to severity strings
            severity = {
                logging.INFO: "info",
                logging.WARNING: "warning",
                logging.ERROR: "error"
            }.get(record.levelno, "unknown")

            payload = {
                "message": message,
                "severity": severity,
                "source": self.source,
                "timestamp": timestamp,
                "message_id": message_id
            }
            response = requests.post(managment_logs_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
            response.raise_for_status()
        except Exception as e:
            logger.error("Error occurred while sending log to API: %s", e)

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
        from consumer import send_status_update
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

        # Check the status and push the task to the appropriate queue
        task_info = redis_server.get(KEY)
        if task_info:
            task_status = json.loads(task_info.decode()).get("status")
            if task_status == "completed":
                redis_server.rpush(completed_tasks, KEY)
            elif task_status == "failed":
                redis_server.rpush(failed_tasks, KEY)
            elif task_status == "active":
                redis_server.rpush(queue_name, KEY)
        else:
            logger.warning('No information found for key: %s', KEY)

    except Exception as e:
        logger.error('Error in redis_set: %s', str(e))

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

def send_logs_to_api(message, severity, source, timestamp, message_id):
    try:
        payload = json.dumps({
            "message": message,
            "severity": severity,
            "source": source,
            "timestamp": timestamp,
            "message_id": "123"})
        print(payload)
        answer = requests.post(managment_logs_url, data=payload,
                               headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password)).json()
    except Exception as e:
        logger.error("Error occurred while sending log to API: %s", str(e))

def valid_response_code(statusCode,ID):
    if statusCode != 200:
        print("Api is not accesble. StatusCode is:", statusCode)
        logger.error('Error in updating API')
        redis_server.rpush(incompleted_tasks, ID)

def send_successORfailed_status(req_id, status_message=None, output_message=None, error=None, output=None, req_switch_ip=None, retrieved_user=None, retrieved_password=None):
    if status_message == "status: success" and error is None:
        if output_message is not None:
            output = f"{status_message}\n{output_message}\n{output}"
        else:
            output = f"{status_message}\n{output}"
        redis_set(req_id, "completed", output)
        task_status = json.loads(redis_server.get(req_id).decode())["status"]
        send_status_update(req_id, task_status, output)
        update_credential_dict(req_switch_ip, retrieved_user, retrieved_password, "success")
        
    elif status_message == "status: failed":
        output = f"{status_message} {error}"
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
            output = f"{status_message} Error adding VLANs {req_vlans} to interface {req_interface_name}: {error}"
        elif req_cmd.lower() == "delete vlan":
            output = f"{status_message} Error removing VLANs {req_vlans} from interface {req_interface_name}: {error}"
        else:
            output = f"{status_message} Error: {error}"
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

