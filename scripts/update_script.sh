#!/bin/bash

DATE=$(date "+%Y%m%d%H%M")
# Log file path
log_file="/var/log/update_script.log"
echo "Started sync at ${DATE}"  >> "$log_file"

base_directory="/opt/DRaaS"
config_file="${base_directory}/config/draas_config.ini"
# Check if the configuration file exists
if [ -f "$config_file" ]; then
    echo "found config file: draas_config.ini" >> "$log_file"
    source "$config_file"
else
    echo "New installation detected. Creating necessary directories..." >> "$log_file"
    # Create the config directory
    config_dir="${base_directory}/config"
    if [ -d "$config_dir" ]; then
        echo "Found $config_dir directory"
    else
        sudo mkdir -p "$config_dir"
        echo "Created $config_dir directory"
    fi
fi

# Back up folder
backup_dir="${base_directory}/backup"
if [ -d ${backup_dir} ]; then
	echo "Found ${backup_dir} directory"
else
	sudo mkdir -p ${backup_dir}
    sudo chmod a+rw ${backup_dir} -R
fi

sudo apt-get install python3-venv -y
set_project_info() 
{
    if [ -z "$project_dir" ]; then
    	project_dir=$(dirname "$(dirname "$(realpath "$0")")")
    	echo "project_dir=${project_dir}" >> "$config_file"
    fi
    if python3 -V 2>&1| grep -q "Python 3"; then
		echo "Python 3 is installed" >> "$log_file"
    else
	    echo "Please install python 3" >> "$log_file"
	    exit 1 
    fi

    # Activate virtual environment if it exists
    if [ -f "$config_file" ]; then
        if [ -n "$venv_dir" ]; then
            echo "Config file is existing along with venv dir: $venv_dir" >> "$log_file"
            source "$venv_dir/bin/activate"
        else
            create_venv
        fi
    else
        # Create and activate virtual environment if it doesn't exist
        echo "No config file. Need to create the venv" >> "$log_file"
        create_venv
    fi
}

# Function to ask the user about the "whoami" command for the user parameter
ask_user_about_username() {
    read -p "Do you want to use the current user ($(whoami)) as the service username? (yes/no): " use_whoami
    if [ "$use_whoami" == "no"  ]; then
        read -p "Enter the desired username: " custom_user
        echo "user=$custom_user" >> "$config_file"
    else
        echo "user=$(whoami)" >> "$config_file"
    fi
}

# Function to check and create the virtual environment
create_venv() {
    if [ -f "$config_file" ]; then
        # source "$config_file"
        if [ -z "$venv_dir" ]; then
            echo "venv_dir not specified in $config_file. Using $base_directory directory $venv_dir." >> "$log_file"
            venv_dir="$base_directory/venv"
            mkdir -p "$venv_dir"
            python3 -m venv "$venv_dir"
            source "$venv_dir/bin/activate"
            echo "venv_dir=${venv_dir}" >> "$config_file"
        else
            echo "Using existing virtual environment in $venv_dir." >> "$log_file"
            source "$venv_dir/bin/activate"
        fi
    else
        echo "Config file not found. Creating and using $base_directory directory $venv_dir." >> "$log_file"
        venv_dir="$base_directory/venv"
        mkdir -p "$venv_dir"
        python3 -m venv "$venv_dir"
        source "$venv_dir/bin/activate"
        echo "venv_dir=${venv_dir}" >> "$config_file"
    fi
}

# Check if the project information is saved, otherwise ask the user
if [ -f "$config_file" ]; then
    if [ -z "$project_dir" ] || [ -z "$user" ] || [ -z "$venv_dir" ]; then
        echo "One or more parameters (project directory, user, MID Server, or venv directory) are missing in the config file. Please provide the missing information."
        set_project_info
        ask_user_about_username
        
    fi
else
    set_project_info
fi

echo "Project directory: $project_dir" >> "$log_file"

# Function to copy files
copy_file() {
    local source_file="$1"
    local destination="$2"
    if [ -f "$source_file" ]; then
        cp "$source_file" "$destination"
    else
        echo "Warning: Source file '$source_file' does not exist."
    fi
}

# Check if the tmp directory exists, if not, create it
tmp_dir="/tmp/scripts"
if [ ! -d "$tmp_dir" ]; then
    mkdir -p "$tmp_dir"
    chmod a+rw "$tmp_dir" -R 
fi

copy_file "$project_dir/producer.py" "/tmp/scripts/producer.py.old"
copy_file "$project_dir/consumer.py" "/tmp/scripts/consumer.py.old"

sudo cp -p "$project_dir/config/parameters.ini" "${base_directory}/config/"
# Extract MID_SERVER value from parameters.ini file
mid_server=$(awk -F "=" '/^[[:space:]]*MID_SERVER[[:space:]]*=/ {gsub(/[[:space:]]/, "", $2); print $2}' "${base_directory}/config/parameters.ini")
# Print the extracted MID_SERVER value
echo "MID_SERVER: $mid_server"


# Read username and password from parameters.ini file
username=$(awk -F "=" '/^[[:space:]]*username[[:space:]]*=/ {gsub(/[[:space:]]/, "", $2); print $2}' "${base_directory}/config/parameters.ini")
password=$(awk -F "=" '/^[[:space:]]*password[[:space:]]*=/ {gsub(/[[:space:]]/, "", $2); print $2}' "${base_directory}/config/parameters.ini")

# Ensure you are on the main branch
git checkout main
git fetch origin main

# Initialize message_counter
message_counter=0
# Check if the local branch is already up-to-date with the remote branch
if [ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]; then
    echo "Local branch is already up-to-date. No need to pull changes." >> $log_file
    message_counter=$(( (message_counter % 100) + 1 ))
    message_id=$(date '+%d%m%Y%H%M%S')-$message_counter
    curl -X POST -H "Content-Type: application/json" -d "{\"message\": \"Local branch is already up-to-date. No need to pull changes.\", \"severity\": \"info\", \"source\": \"$mid_server\", \"timestamp\": \"$(date '+%d/%m/%Y %I:%M:%S %p')\",  \"message_id\": \"$message_id\"}" -u "$username:$password" https://bynetprod.service-now.com/api/bdml/switch/postSwitchManagmentLogs
    exit 0
else
    # Fetch and reset to the remote main branch
    git stash
    git pull origin main
    message_counter=$(( (message_counter % 100) + 1 ))
    message_id=$(date '+%d%m%Y%H%M%S')-$message_counter
    curl -X POST -H "Content-Type: application/json" -d "{\"message\": \"The git pull request is done!\", \"severity\": \"info\", \"source\": \"$mid_server\", \"timestamp\": \"$(date '+%d/%m/%Y %I:%M:%S %p')\",  \"message_id\": \"$message_id\"}" -u "$username:$password" https://bynetprod.service-now.com/api/bdml/switch/postSwitchManagmentLogs
fi

# Activate virtual environment if it exists
if [ -f "$config_file" ]; then
    source $config_file
    if [ -n "$venv_dir" ]; then
        source "$venv_dir/bin/activate"
    fi
else
    create_venv
fi
# Install Python dependencies
pip install -r "$project_dir/requirements.txt"
# Copy the 'config' directory to /opt/
sudo cp -p "$project_dir/config/parameters.ini" "${base_directory}/config/"

# Function to update service file with correct parameters
update_service_file() 
{
    local service_file="$1"
    local user_param="User=$user"
    local wd_param="WorkingDirectory=$project_dir"
    local exec_param="ExecStart=$base_directory/venv/bin/python $project_dir/$2.py"

    local local_service_file="$project_dir/$2.service"
    if [ ! -f "$service_file" ]; then
        echo "$2 service file not found in the system. Creating..." >> "$log_file"
        sed -i "s#User=.*#$user_param#" "$local_service_file"
        sed -i "s#WorkingDirectory=.*#$wd_param#" "$local_service_file"
        sed -i "s#ExecStart=.*#$exec_param#" "$local_service_file"
        sudo cp "$local_service_file" "$service_file"
    else
        # Check if parameters match, update if needed
        if ! grep -q "^$user_param" "$service_file" || ! grep -q "^$wd_param" "$service_file" || ! grep -q "^$exec_param" "$service_file"; then
            echo "$2 service file parameters do not match. Updating..." >> "$log_file"
            sudo sed -i "s#User=.*#$user_param#" "$service_file"
            sudo sed -i "s#WorkingDirectory=.*#$wd_param#" "$service_file"
            sudo sed -i "s#ExecStart=.*#$exec_param#" "$service_file"
            # Copy the updated service file to the project directory
            cp "$service_file" "$local_service_file"
        fi
    fi
}

# Function to check if there are changes in systemd service files, producer.py, or consumer.py
check_systemd_changes() {
    local producer_diff=$(diff "$project_dir/producer.service" "$producer_service")
    local consumer_diff=$(diff "$project_dir/consumer.service" "$consumer_service")
    local producer_py_diff=$(diff "$project_dir/producer.py" "/tmp/scripts/producer.py.old")
    local consumer_py_diff=$(diff "$project_dir/consumer.py" "/tmp/scripts/consumer.py.old")

    if [ -z "$producer_diff" ] && [ -z "$consumer_diff" ] && [ -z "$producer_py_diff" ] && [ -z "$consumer_py_diff" ]; then
        echo -e "No changes in systemd service files, producer.py, or consumer.py. Skipping systemd reload." >> $log_file
        return 1  # Indicate no changes
    else
        echo -e "Changes detected in the following files:\n$( [ -n "$producer_diff" ] && echo "- producer.service" )\n$( [ -n "$consumer_diff" ] && echo "- consumer.service" )\n$( [ -n "$producer_py_diff" ] && echo "- producer.py" )\n$( [ -n "$consumer_py_diff" ] && echo "- consumer.py" )" >> $log_file
        return 0  # Indicate changes
    fi
}

# Check if service files exist, otherwise copy them
producer_service="/etc/systemd/system/producer.service"
consumer_service="/etc/systemd/system/consumer.service"
# Check if the config_file contains the user parameter
if grep -q "^user=" "$config_file"; then
    source $config_file
else
    ask_user_about_username
fi

update_service_file "$producer_service" "producer"
update_service_file "$consumer_service" "consumer"

# Check if there are changes in systemd service files
if check_systemd_changes; then
    # Reload systemd to pick up changes
    sudo systemctl daemon-reload

    # Restart your services and log the output
    sudo systemctl restart producer.service > "$log_file" 2>&1
    sudo systemctl restart consumer.service >> "$log_file" 2>&1
else
    echo "No need to reload systemd. Skipping systemd reload." >> "$log_file"
fi

# Restart your services and log the output
sudo systemctl restart producer.service > "$log_file" 2>&1
sudo systemctl restart consumer.service >> "$log_file" 2>&1

# Check the status of the services
producer_status=$(sudo systemctl is-active producer.service)
consumer_status=$(sudo systemctl is-active consumer.service)
# Print the status message
if [ "$producer_status" = "active" ] && [ "$consumer_status" = "active" ]; then
    echo "All services are up." >> "$log_file"
    echo "MID Server: $mid_server" >> "$log_file"
else
    echo "MID Server: $mid_server" >> "$log_file"
    echo "One or both services are not active. Fetching detailed service status..." >> "$log_file"

    producer_status_detail=$(sudo systemctl status producer.service)
    echo -e "Producer service status:\n$producer_status_detail" >> "$log_file"
    consumer_status_detail=$(sudo systemctl status consumer.service)
    echo -e "Consumer service status:\n$consumer_status_detail" >> "$log_file"
fi
