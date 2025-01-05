#!/bin/bash

log_file="/var/log/restart_services.log"
log_message() {
    local level=$1
    local message=$2
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $level - $message" >> "$log_file"
}

restart_services() {
    local services=("$@")
    for service in "${services[@]}"; do
        if sudo systemctl restart "$service"; then
            log_message "INFO" "Service $service restarted successfully."
            echo "Service $service restarted successfully."
        else
            log_message "ERROR" "Restart_consumer.sh. Failed to restart service $service."
        fi
    done
}

main() {
    local services=("consumer.service")
    restart_services "${services[@]}"
}

main

# make sure to open crontab with sudo user...
# sudo crontab -e 
# * * * * * path/restart_consumer.sh >> /var/log/restart_services.log 2>&1
