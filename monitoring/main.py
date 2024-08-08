from flask import Flask, jsonify
import psutil
from flask import Flask, jsonify
from collections import deque


app = Flask(__name__)


log_path = {
    'consumer': '/var/log/consumer_error.log',
    'producer': '/var/log/producer_error.log'
}

def read_logs(log_path, max_entries=10):
    logs = {
        'info': deque(maxlen=max_entries),
        'error': deque(maxlen=max_entries),
        'warning': deque(maxlen=max_entries)
    }
    with open(log_path, 'r') as log_file:
        for line in log_file:
            if " - INFO " in line:
                logs['info'].append(line.strip())
            elif " - ERROR " in line:
                logs['error'].append(line.strip())
            elif " - WARNING " in line:
                logs['warning'].append(line.strip())    
    return {key: list(value) for key, value in logs.items()}

def get_service_info(service_name):
    for proc in psutil.process_iter(['pid', 'cmdline']):
        cmdline = proc.info.get('cmdline', [])
        if cmdline and service_name in ' '.join(cmdline):
            pid = proc.info['pid']
            try:
                process = psutil.Process(pid)
                cpu_usage = process.cpu_percent(interval=1) 
                memory_info = process.memory_info()  
                logs = read_logs(log_path[service_name])
                return {
                    'running': True,
                    'pid': pid,
                    'cpu_usage': cpu_usage,
                    'memory_usage_mb': memory_info.rss / (1024 * 1024),
                    'logs': logs
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return {'running': False}
    return {'running': False}

@app.route('/', methods=['GET'])
def service_status():
    producer_info = get_service_info('producer')
    consumer_info = get_service_info('consumer')

    return jsonify({
        'producer': producer_info,
        'consumer': consumer_info
    }), 200

if __name__ == '__main__':
    app.run(debug=True)
