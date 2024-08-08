from flask import Flask, jsonify
import psutil


app = Flask(__name__)

def get_service_info(service_name):
    for proc in psutil.process_iter(['pid', 'cmdline']):
        cmdline = proc.info.get('cmdline', [])
        if cmdline and service_name in ' '.join(cmdline):
            pid = proc.info['pid']
            try:
                process = psutil.Process(pid)
                cpu_usage = process.cpu_percent(interval=1) 
                memory_info = process.memory_info()  
                return {
                    'running': True,
                    'pid': pid,
                    'cpu_usage': cpu_usage,
                    'memory_usage_mb': memory_info.rss / (1024 * 1024) 
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
    })

if __name__ == '__main__':
    app.run(debug=True)
