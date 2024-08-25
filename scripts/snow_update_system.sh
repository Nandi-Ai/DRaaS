#!/bin/bash
DATE=$(date "+%Y%m%d%H%M")

# Log file path
log_file="/var/log/script.log"

# File to store project directory and venv flag
config_file="config/draas_config.ini"

# the update zip sended by ServiceNow
#update_file="/opt/servicenow/mid/agent/export/update.zip"
update_file=$(find /opt/servicenow/mid/agent/export/ -maxdepth 1 -type f -name '*.zip' -print -quit)

# File to store the code version
stored_version_file="config/version.txt"

echo "Started sync at ${DATE}"  >> "$log_file"
if [ -z "$update_file" ]; then
    echo "Error: No update file (*.zip) found in the project directory. Please check your folder." >> "$log_file"
    exit 1
fi

# Function to prompt user for project directory
get_project_info() 
{
    project_dir=$(pwd)
    if python3 -V 2>&1| grep -q "Python 3"; then
		echo "Python 3 is installed" >> "$log_file"
    else
	    echo "Please install python 3" >> "$log_file"
	    exit 1 
    fi

    if [ ! -d $project_dir/venv ]; then
        echo "Setting up virtual environment..." >> "$log_file"
    	apt-get install -y python3.10-venv
	python3 -m venv "$project_dir/venv"
    	source "$project_dir/venv/bin/activate"

	# Ensure pip is available in the virtual environment
        python -m ensurepip --default-pip
    else
    	source "$project_dir/venv/bin/activate"
    fi 
    echo "project_dir=$project_dir" > "$config_file"
}

# Function to ask the user about the "whoami" command for the user parameter
ask_user_about_username() {
    read -p "Do you want to use the current user ($(whoami)) as the service username? (yes/no): " use_whoami
    if [ "$use_whoami" == "no" ]; then
        read -p "Enter the desired username: " custom_user
        echo "user=$custom_user" >> "$config_file"
    else
        echo "user=$(whoami)" >> "$config_file"
    fi
}

# Check if the project information is saved, otherwise ask the user
if [ -f "$config_file" ]; then
    source $config_file
else
    get_project_info
fi

# Extract the contents of the update file.
temp_extracted_dir=$(mktemp -d)
unzip -q "$update_file" -d "$temp_extracted_dir"
echo "extracted the folder to "$temp_extracted_dir". " >> "$log_file"

# Find the version.txt file
version_file="$temp_extracted_dir/config/version.txt"

# Check if the version file exists
if [ ! -e "$version_file" ]; then
    echo "Error: No version.txt file found in the update. Aborting update." >> "$log_file"
    rm -r "$temp_extracted_dir"
    exit 1
fi

# Read the version from the version.txt file
new_version=$(grep "^version=" "$version_file" | cut -d '=' -f2)

# Check if the stored version file exists
if [ -e "$stored_version_file" ]; then
    # Read the stored version from the file
    stored_version=$(grep "^version=" "$stored_version_file" | cut -d '=' -f2)

    # Remove any non-numeric characters from the stored version
    stored_version=$(echo "$stored_version" | tr -cd '[:digit:]')
    echo "new_version: "$new_version", stored_version: "$stored_version"" >> "$log_file"

    # Compare versions
    if [ "$new_version" -le "$stored_version" ]; then
        echo "No newer version found. Aborting update." >> "$log_file"
        rm -r "$temp_extracted_dir"
        exit 0
    fi
    echo "version=$new_version" > "$stored_version_file"
fi

# Find the configuration file under the 'config' directory
config_dir="$project_dir/config/"
ini_file="$(find "$config_dir" -maxdepth 1 -type f -iname "*.ini" -print -quit)"

# Check if the parameters.ini file was found
if [ -z "$ini_file" ]; then
    echo "Error: No configuration file (*.ini) found in the 'config' directory. Please check your repository." >> "$log_file"
    exit 1
fi

# Back up the parameters.ini file
backup_dir="/opt/backup"

# Check if the backup directory exists, if not, create it
if [ ! -d "$backup_dir" ]; then
    sudo mkdir -p "$backup_dir"
    sudo chmod a+rw "$backup_dir" -R 
fi
backup_file="$backup_dir/parameters_backup.ini"

# Copy the parameters.ini file to the backup directory
sudo cp "$ini_file" "$backup_file"

# Parse the parameters.ini file to get the values
mid_server=$(awk -F "=" '/^MID_SERVER/ {print $2}' "$ini_file")

# Activate virtual environment if it exists
if [ -d "$project_dir/venv" ]; then
    source "$project_dir/venv/bin/activate"
else
    # Create and activate virtual environment if it doesn't exist
    apt-get install -y python3.10-venv
    echo "Setting up virtual environment..." >> "$log_file"
    python3 -m venv "$project_dir/venv"
    source "$project_dir/venv/bin/activate"
    
    # Ensure pip is available in the virtual environment
    python -m ensurepip --default-pip
fi

# Install Python dependencies
pip install -r requirements.txt
# Copy the 'config' directory to /opt/
sudo cp -a "$config_dir" /opt/

# Update specific files in DRaaS folder
for file in "$temp_extracted_dir"*; do
    filename=$(basename "$file")
    
    # Exclude config and ini files
    if [[ "$filename" != "config" && "$filename" != *.ini ]]; then
        # Update the file in the destination folder
        cp -r "$file" "$project_dir/$filename"
        echo "copied the new file: "$file"." >> "$log_file"
    fi
done

# Function to update service file with correct parameters
update_service_file() 
{
    local service_file="$1"
    local user_param="User=$user"
    local wd_param="WorkingDirectory=$project_dir"
    local exec_param="ExecStart=$project_dir/venv/bin/python $project_dir/$2.py"

    local local_service_file="$project_dir/$2.service"

    # Check if the service file exists
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
    local producer_py_diff=$(diff "$project_dir/producer.py" "$project_dir/venv/bin/producer.py")
    local consumer_py_diff=$(diff "$project_dir/consumer.py" "$project_dir/venv/bin/consumer.py")

    if [ -z "$producer_diff" ] && [ -z "$consumer_diff" ] && [ -z "$producer_py_diff" ] && [ -z "$consumer_py_diff" ]; then
        echo "No changes in systemd service files, producer.py, or consumer.py. Skipping systemd reload." >> $log_file
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
    echo "No need to reload systemd. Skipping systemd reload." >> $log_file
fi

# Restart your services and log the output
sudo systemctl restart producer.service > "$log_file" 2>&1
sudo systemctl restart consumer.service >> "$log_file" 2>&1

# Check the status of the services
producer_status=$(sudo systemctl is-active producer.service)
consumer_status=$(sudo systemctl is-active consumer.service)

# Update the stored version
#echo "$new_version" > "$stored_version_file"
#echo "Updated the new version of the code to: "$new_version"" >> "$log_file"

# Clean up the extracted update file if it exists
if [ -d "$temp_extracted_dir" ]; then
    rm -r "$temp_extracted_dir"
    echo "Extracted update files deleted." >> "$log_file"
fi

# Delete the update ZIP file
if [ -e "$update_file" ]; then
    rm "$update_file"
    echo "Update ZIP file deleted." >> "$log_file"
fi

# Clean up temporary folders
rm -rf $project_dir/tmp.*

# Print the status message
if [ "$producer_status" = "active" ] && [ "$consumer_status" = "active" ]; then
    echo "All services are up." >> "$log_file"
    echo "MID Server: $mid_server" >> "$log_file"
    echo "Update applied successfully." >> "$log_file"
else
    echo "Something went wrong. Check the status of your services. See the log file for details: $log_file"
fi
