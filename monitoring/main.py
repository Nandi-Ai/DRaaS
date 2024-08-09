from flask import Flask, jsonify, request

app = Flask(__name__)

consumer = {}
producer = {}

@app.route('/receive', methods=['GET', 'POST'])
def receive_data():
    global consumer 
    global producer 
    
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json() 
            service_name = data.get('service_name')
            if service_name == "consumer":
                consumer.update(data) 
            elif service_name == "producer":
                producer.update(data)  
            else:
                return jsonify({"error": "Unknown service name"}), 400
            return jsonify({"message": "Data received successfully"}), 200 
        else:
            return jsonify({"error": "Unsupported Media Type"}), 415
    
    if request.method == 'GET':
        return jsonify({
            'consumer': consumer,
            'producer': producer
        }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
