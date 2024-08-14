import requests
import psutil

url = "http://localhost:5050/receive"
headers = {'Content-Type': 'application/json'}

# using psutil to get info for each service. 
def get_proc_data(servicename):
    try:
        for proc in psutil.process_iter(['pid', 'cmdline']):
            cmdline = proc.info.get('cmdline', [])
            if cmdline and servicename in ' '.join(cmdline):
                pid = proc.info['pid']
                try:
                    process = psutil.Process(pid)
                    cpu_usage = process.cpu_percent(interval=1)
                    memory_info = process.memory_info()
                    memory_usage_mb = memory_info.rss / (1024 * 1024)
                    return {
                        'pid': pid,
                        'cpu_usage': cpu_usage,
                        'memory_usage_mb': memory_usage_mb,
                    }
                except Exception as err:
                    return {"Error": str(err)}
        return {"Error": "No process found with the given service name"}
    except Exception as err:
        return {"Error": str(err)}
    
def send_data_to_flask(status, message,  timestamp, servicename):    
    service_proc_data = get_proc_data(servicename)
    print(service_proc_data)  
    msg = {
        "service_name": servicename, 
        "time_sent": timestamp,
        "service_status": status,
        "last_log_message": message,
        "service_process_data": service_proc_data,
    }
    try:
        response = requests.post(url, json=msg, headers=headers, timeout=5)
        print(response.status_code, "---", response.json())
    except requests.RequestException as err:
        print("Error while sending data to API:", err)