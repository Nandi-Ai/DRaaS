# import psutil, time
# import subprocess

# services = {
#     "Producer Service": "producer.py",
#     "Consumer Service": "consumer.py"
# }

# def is_service_running(script_name):
#     for proc in psutil.process_iter(['pid', 'cmdline']):
#         try:
#             cmdline = proc.info['cmdline']
#             if cmdline and script_name in ' '.join(cmdline):
#                 return proc.info
#         except (psutil.NoSuchProcess, psutil.AccessDenied):
#             continue
#     return None

# def get_service_info(script_name):
#     for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
#         try:
#             result = subprocess.run(['systemctl', 'is-active', script_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#             status = result.stdout.decode('utf-8').strip()
#         except Exception as err:
#             print(f"Error checking status of ({script_name}): {err}")
#             return None
#         if status == 'active':
#             if script_name in ' '.join(proc.info['cmdline']):
#                 p = psutil.Process(proc.info['pid'])
#                 return {
#                     'status': status,
#                     'cpu_percent': p.cpu_percent(interval=1.0),
#                     'memory_info': p.memory_info(),
#                     'open_files': p.open_files(),
#                     'connections': p.connections()
#                 }
#         else:
#             print(f"service {script_name} is not running")
#             return None
#     return None

# def monitoring():
#     while True:
#         for service_name, script_name in services.items():
#             info = get_service_info(script_name)
#             if info:
#                 print(f"{service_name} - is {info['status']}")
#                 print(f"{service_name} - CPU Percent: {info['cpu_percent']}")
#                 print(f"{service_name} - Memory Info: {info['memory_info']}")
#                 # print(f"{service_name} - Open Files: {info['open_files']}")
#                 # print(f"{service_name} - Connections: {info['connections']}")
#             else:
#                 print(f"{service_name} not found.")
#         time.sleep(10) 

# if __name__ == "__main__":
#     monitoring()
