from flask import Flask, jsonify, request
import redis, requests, json, datetime, settings, time
from functions import send_logs_to_api


settings.init()

update_status_url= settings.url + "/postHealthMonitoring"
app = Flask(__name__)

# global variables...
consumer = {}
producer = {}
rservice = {}
Data = {}


def send_health_monitoring_update(producer: dict, consumer: dict, redis: dict) -> json:
    try:
        payload = json.dumps({
            "mid_name": settings.mid_server,
            "queues": redis,
            "services": {
                "producer": producer,
                "consumer": consumer
            }
        })
        # Check if payload is empty
        if not payload:
            print("Empty payload. Skipping health monitoring update.")
            send_logs_to_api(f'Empty payload. Skipping health monitoring update.', 'info', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
            return
        try:
            answer = requests.post(update_status_url, data=payload,
                                headers={'Content-Type': 'application/json'}, auth=(settings.username, settings.password),timeout=5).json()
        except (requests.ConnectionError, requests.Timeout) as err:
            print(f"Network error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(5)  # Sleep for 10 seconds before retrying in case of network errors
        except Exception as err:
            print("error sending post")
            print(f"An unexpected error occurred: {err}. Retrying in 10 seconds...")
            time.sleep(5)
            
        print("Payload Sent...")
        print(payload)
        return payload
    except Exception as e:
        send_logs_to_api(f'Error in send_health_monitoring_update: {str(e)}', 'error', settings.mid_server, datetime.now().strftime('%d/%m/%Y %I:%M:%S %p'))
        print(f'Error in send_health_monitoring_update: {str(e)}')
        return None


@app.route('/receive', methods=['GET', 'POST'])
def receive_data():
    global consumer
    global producer
    global rservice
    global Data

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            service_name = data.get('service_name')
            if service_name == "redis":
                rservice.update(data)
            if service_name == "consumer":
                consumer.update(data)
            elif service_name == "producer":
                producer.update(data)

            Data = send_health_monitoring_update(producer, consumer,rservice)
            return jsonify({"message": "Data received successfully"}), 200
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    
    # testing
    if request.method == 'GET':
        return jsonify({'Data': Data}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
    
    
