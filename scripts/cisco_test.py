import paramiko
import time, re
import json
from functions import run_command_and_get_json, change_interface_mode
class SSHConnection:
    shell = None
    client = None
    transport = None

    def __init__(self, address, username, password):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        self.client.connect(address, username=username, password=password, look_for_keys=False)

    def close_connection(self):
        if self.client is not None:
            self.client.close()

    def open_shell(self):
        self.shell = self.client.invoke_shell()

    def exec_command(self, command):
        _, ssh_stdout, ssh_stderr = self.client.exec_command(command)
        err = ssh_stderr.readlines()
        return err if err else ssh_stdout.readlines()

    def send_shell(self, command):
        if self.shell:
            return self.shell.send(command + "\n")
        else:
            print("Shell not opened.")

def get_cisco_interface_info(ip, user, password):
    #Login by ssh
    connection = SSHConnection(ip, user, password)
    time.sleep(1)
    #Send command and get output
    output = connection.exec_command('show interfaces all')
    #Join it to one str
    output_str = '\n'.join(output)

    #Sent to another function and parse it to Json format
    parsed_data = parse_cisco_output(output_str)
    json_data = json.dumps(parsed_data, indent=4)
    
    connection.close_connection()
    return json_data

def parse_cisco_output(output):
    interfaces = {}
    current_interface = None
    # Split the output by interface sections
    sections = output.split("\n\n\n\n\n\n")

    for section in sections:
        lines = section.strip().split("\n")
        if not lines:
            continue
        current_interface = lines[0].split()[-1]
        interfaces[current_interface] = {}

        for line in lines[1:]:
            key_value = line.strip().split(maxsplit=1)
            if len(key_value) == 2:
                key, value = key_value
                interfaces[current_interface][key] = value
    return interfaces

def get_cisco_route_info(ip, user, password):
    connection = SSHConnection(ip, user, password)
    time.sleep(1)
    # Send command to get route information
    output = connection.exec_command('show route')
    # Join the output to form a string
    output_str = '\n'.join(output)

    # Parse the output to JSON format
    parsed_data = parse_cisco_route_output(output_str)
    json_data = json.dumps(parsed_data, indent=4)
    
    connection.close_connection()
    return json_data

def parse_cisco_route_output(output):
    routes = []
    lines = output.split("\n")
    for line in lines:
        # Check if the line starts with "C" indicating a connected route
        if line.startswith("C"):
            fields = line.split()
            if len(fields) >= 6:
                route_entry = {
                    "protocol": fields[0],      # Protocol type (C for connected)
                    "destination": fields[1],   # Destination network
                    "via": fields[3],           # Next hop or directly connected
                    "interface": fields[5]      # Interface
                }
                routes.append(route_entry)
    return routes

if __name__ == "__main__":
    cisco_ip = "192.168.128.1"
    cisco_username = "servicenow"
    cisco_password = "serv1cen0w10"
    req_cmd="show run"

    # cisco_interface_info = get_cisco_interface_info(cisco_ip, cisco_username, cisco_password)
    output = run_command_and_get_json(cisco_ip, cisco_username, cisco_password, req_cmd)
    #print("interfaces" + cisco_interface_info)
    #print("routes" + cisco_route_info)
    print(output)
#    interface_dict = json.loads(output)
#    route_dict = json.loads(cisco_route_info)
#    combined_data = {"interfaces": interface_dict, "routes": route_dict}
#    json_data = json.dumps(combined_data, indent=4)
#    print(json_data)
