import paramiko
import time; from time import sleep
import time, re
import json
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
            self.shell.send(command + "\n")
            time.sleep(1)
            output=""
            while True:
                if self.shell.recv_ready():
                    output += self.shell.recv(1024).decode('utf-8')
                if self.shell.recv_stderr_ready():
                    output += self.shell.recv_stderr(1024).decode('utf-8')
                if not self.shell.recv_ready() and not self.shell.recv_stderr_ready():
                    break
            return output.strip()
        else:
            print("Shell not opened.")

    def create_vlan(self, physical_interface, vlan_id, vlan_ip, vlan_subnet, comments):
        try:
            output = ""
            print(vlan_id)
            command_create_vlan = f"add interface {physical_interface} vlan {vlan_id}"
            output += self.send_shell(command_create_vlan)
            time.sleep(1)

            command_comments_on_vlan = f"set interface {physical_interface}.{vlan_id} comments {comments}"
            output += self.send_shell(command_comments_on_vlan)
            time.sleep(1)

            command_configure_ip = f"set interface {physical_interface}.{vlan_id} ipv4-address {vlan_ip} subnet-mask {vlan_subnet}"
            output += self.send_shell(command_configure_ip)
            time.sleep(1)

            # print(f"VLAN {vlan_id} added successfully to interface {physical_interface}.")
            command_save_config = f"save config"
            output += self.send_shell(command_save_config)
            time.sleep(1)

            return output
        except Exception as e:
            print(f"Error occurred while creating VLAN: {e}")

    def create_route(self, destination_network, gateway, priority=None):
        try:
            if priority is not None:
                command = f"set static-route {destination_network} nexthop gateway address {gateway} priority {priority} on"
            else:
                command = f"set static-route {destination_network} nexthop gateway address {gateway} on"
        
            output= self.send_shell(command)
            time.sleep(1)

            if "Invalid command" in output:
                raise Exception("Invalid command while setting static route")

            command = f"save config"
            self.send_shell(command)
            time.sleep(1)
            print(f"Route to {destination_network} configured successfully.")
        except Exception as e:
            print(f"Error occurred while configuring route: {e}")

def get_gaia_interface_info(ip, user, password):
    #Login by ssh
    connection = SSHConnection(ip, user, password)
    time.sleep(1)
    #Send command and get output
    output = connection.exec_command('show interfaces all')
    #Join it to one str
    output_str = '\n'.join(output)

    #Sent to another function and parse it to Json format
    parsed_data = parse_gaia_output(output_str)
    json_data = json.dumps(parsed_data, indent=4)

    connection.close_connection()
    return json_data

def get_gaia_hostname(ip,user,password):
    connection = SSHConnection(ip, user, password)
    time.sleep(1)
    output = connection.exec_command('show hostname')
    return output

def parse_gaia_output(output):
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

def get_gaia_route_info(ip, user, password):
    connection = SSHConnection(ip, user, password)
    time.sleep(1)
    # Send command to get route information
    output = connection.exec_command('show route')
    # Join the output to form a string
    output_str = '\n'.join(output)
    
    configuration_output = connection.exec_command('show configuration')
    configuration_output = '\n'.join(configuration_output)
    # Parse the output to JSON format
    parsed_data = parse_gaia_route_output(output_str, configuration_output)
    json_data = json.dumps(parsed_data, indent=4)

    connection.close_connection()
    return json_data

def parse_gaia_route_output(output, configuration_output):
    routes = []
    lines = output.split("\n")
    for line in lines:
        if line.startswith("C") or line.startswith("S"):
            fields = line.split(",")  # Splitting by comma now
            if "cost" in line:  # Check if the line contains "cost"
                protocol = fields[0].split()[0]
                destination = fields[0].split()[1]
                via = fields[0].split()[3]
                interface = fields[1].strip()
                #cost = fields[0].split("cost")[1].split(",")[0].strip()
            else:
                fields = line.split()
                protocol = fields[0]
                destination = fields[1]
                via = fields[3]
                interface = fields[5]
                #cost = None
            priority = get_priority(destination,configuration_output)

            route_entry = {
                "protocol": protocol,
                "destination": destination,
                "via": via,
                #"cost": cost,
                "priority": priority,
                "interface": interface
            }
            routes.append(route_entry)
    return routes

def get_priority(destination,configuration_output):

    lines = configuration_output.split("\n")
    for line in lines:
        if destination in line:
            if "priority" in line:
                priority_index = line.index("priority") + len("priority")
                priority_value = line[priority_index:].split()[0]
                return priority_value
            else:
                return None
    return None

def add_gaia_vlan(ip, user, password, physical_interface, vlan, vlan_ip, vlan_subnet,comments):
    connection = SSHConnection(ip, user, password)
    connection.open_shell()
    time.sleep(1)
    int(vlan)
    output = connection.create_vlan(physical_interface, vlan, vlan_ip, vlan_subnet,comments)
    connection.close_connection()
    return output

def remove_gaia_vlan(ip, user, password , physical_interface, vlan_id):
    connection = SSHConnection(ip, user, password)
    connection.open_shell()
    time.sleep(1)

    output = connection.send_shell(f'delete interface {physical_interface} vlan {vlan_id}')
    time.sleep(1)
    
    connection.send_shell('save config')
    time.sleep(2)
    connection.close_connection()
    return output

def add_gaia_route(ip, user, password, destination_network, gateway,priority=None):
    connection = SSHConnection(ip, user, password)
    connection.open_shell()
    time.sleep(1)
    
    if gateway != None:
        if priority is not None:
            output = connection.create_route(destination_network, gateway, priority)
        else:
            output= connection.create_route(destination_network, gateway)
    else:
        print("Neither via nor gateway provided. Route configuration failed.")
    
    connection.close_connection()
    return output

def remove_gaia_route(ip,user,password,destination_network):
    connection = SSHConnection(ip,user, password)
    connection.open_shell()
    time.sleep(1)
    output= connection.send_shell(f'set static-route {destination_network} off')
    connection.send_shell('save config')
    connection.close_connection()
    return output

if __name__ == "__main__":
    gaia_ip = "10.169.32.178"
    gaia_username = "admin"
    gaia_password = "iolredi8"

    #remove vlan+route to test
    remove_gaia_route(gaia_ip,gaia_username,gaia_password,"192.168.2.0/24")
    remove_gaia_vlan(gaia_ip, gaia_username, gaia_password, "eth0", 18)

    gaia_interface_info = get_gaia_interface_info(gaia_ip, gaia_username, gaia_password)
    gaia_route_info = get_gaia_route_info(gaia_ip, gaia_username, gaia_password)

    interface_dict = json.loads(gaia_interface_info)
    route_dict = json.loads(gaia_route_info)
    combined_data = {"interfaces": interface_dict, "routes": route_dict}
    json_data = json.dumps(combined_data, indent=4)
    print(json_data)