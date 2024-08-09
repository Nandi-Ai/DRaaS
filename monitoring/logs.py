
import requests
import psutil

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
                        'running': True,
                        'pid': pid,
                        'cpu_usage': cpu_usage,
                        'memory_usage_mb': memory_usage_mb,
                    }
                except Exception as err:
                    return {"error1": str(err)}
        # Return an error if no process found
        return {"error": "No process found with the given service name"}
    except Exception as err:
        return {"error2": str(err)}

def send_data_to_api(message, severity, timestamp, servicename):
    url = "http://localhost:5000/receive"
    headers = {'Content-Type': 'application/json'}
    
    service_proc_data = get_proc_data(servicename)
    print(service_proc_data)  # Debug print
    
    msg = {
        "service_name": servicename,  # Changed to match the Flask endpoint
        "severity": severity,
        "time_sent": timestamp,
        "service_log": message,
        "service_process_data": service_proc_data,
    }
    
    try:
        response = requests.post(url, json=msg, headers=headers)
        print(response.status_code)
        print(response.json())  # Print response JSON for debugging
    except requests.RequestException as err:
        print("Error while sending data to API:", err)


