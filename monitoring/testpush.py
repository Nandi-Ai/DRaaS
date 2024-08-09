import redis
import json

redis_server = redis.Redis()

queue_name = "api_req_queue" 

data = {
    "record_id": "123456",
    "vlans": "10,20",
    "switch": "switch_1",
    "switch_ip": "192.168.1.1",
    "interface_name": "eth0",
    "port_mode": "access",
    "discovery": "0",
    "destination": "192.168.1.0/24",
    "gateway": "192.168.1.254",
    "ip": "192.168.1.10",
    "subnet": "255.255.255.0",
    "description": "Test description",
    "priority": "high",
    "command": "add vlan"
}

json_data = json.dumps(data)

redis_server.rpush(queue_name, json_data)

print(f"Data pushed into the queue: {json_data}")
