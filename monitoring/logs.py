# import subprocess
# import re

# def get_parsed_logs(service_name, lines=100):
#     try:
#         # Retrieve logs from journalctl
#         result = subprocess.run(['journalctl', '-u', service_name, '--lines', str(lines)], capture_output=True, text=True, check=True)
#         logs = result.stdout
        
#         # Parse logs
#         log_entries = {
#             'error': [],
#             'warning': [],
#             'info': []
#         }
        
#         for line in logs.splitlines():
#             if 'error' in line.lower():
#                 log_entries['error'].append(line)
#             elif 'warning' in line.lower():
#                 log_entries['warning'].append(line)
#             elif 'info' in line.lower():
#                 log_entries['info'].append(line)
        
#         return log_entries
    
#     except subprocess.CalledProcessError as e:
#         return {"error": [f"Error: {e}"]}

# from flask import Flask, jsonify, Response
# import subprocess
# import logging
# import time

# app = Flask(__name__)

# @app.route('/logs', methods=['GET'])
# def stream_logs():
#     def generate():
#         # Use journalctl to read logs for the specific service
#         command = ['journalctl', '-u', 'producer.service', '-f', '-o', 'cat']
#         process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
#         for line in iter(process.stdout.readline, b''):
#             yield f"data: {line.decode('utf-8')}\n\n"
    
#     return Response(generate(), mimetype='text/event-stream')

# if __name__ == '__main__':
#     app.run(debug=True, threaded=True)
