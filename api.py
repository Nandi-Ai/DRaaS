from flask import Flask, request, jsonify
import redis, json
import re
import subprocess
from flasgger import Swagger

redis_server = redis.Redis()
redis_server2 = redis.Redis()

app = Flask(__name__)
Swagger(app)  # Initialize Swagger

def main():
    @app.route('/remaining_tasks', methods=['GET'])
    def get_remaining_tasks():
        """
        Get the number of remaining tasks in the Redis queue.
        ---
        responses:
          200:
            description: A JSON object with the remaining tasks count.
        """
        q_len = redis_server.llen('api_req_queue')
        return jsonify({"remaining_tasks": q_len})

    @app.route('/current_task', methods=['GET'])
    def get_current_task():
        """
        Get information about the current task being processed.
        ---
        responses:
          200:
            description: A JSON object with information about the current task.
        """
        task_info = redis_server2.get("current_task")  # Set this key when you start processing a task
        if task_info:
            task_info = task_info.decode()  # Decode from bytes to string
            task_dict = json.loads(task_info)
        else:
            task_dict = {}
        return jsonify({"current_task": task_dict})

    @app.route('/clear_cache', methods=['POST'])
    def clear_cache():
        """
        Clear the Redis cache (delete all keys).
        ---
        responses:
          200:
            description: A JSON object with a message indicating that the Redis cache has been cleared.
        """
        redis_server.flushall()
        return jsonify({"message": "Redis cache cleared"})
    

    @app.route('/service_status/producer', methods=['GET'])
    def get_producer_status():
        """
        Get the status of the producer service.
        ---
        responses:
          200:
            description: A JSON object with the producer service status.
        """
        try:
            result = subprocess.run(['systemctl', 'is-active', 'producer'], stdout=subprocess.PIPE)
            return jsonify({"producer_status": result.stdout.decode().strip()})
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route('/service_status/consumer', methods=['GET'])
    def get_consumer_status():
        """
        Get the status of the consumer service.
        ---
        responses:
          200:
            description: A JSON object with the consumer service status.
        """
        try:
            result = subprocess.run(['systemctl', 'is-active', 'consumer'], stdout=subprocess.PIPE)
            return jsonify({"consumer_status": result.stdout.decode().strip()})
        except Exception as e:
            return jsonify({"error": str(e)})

if __name__ == '__main__':
    main()
    app.run(host='0.0.0.0', port=5000, debug=True)