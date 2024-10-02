#!/bin/bash

restart_services() {
    local services=("consumer.service" "consumer1.service" "consumer2.service" "producer.service")

    for service in "${services[@]}"; do
        if sudo systemctl restart "$service"; then
            echo "Service $service restarted successfully."
        else
            echo "Failed to restart service $service."
        fi
    done
}
restart_services

