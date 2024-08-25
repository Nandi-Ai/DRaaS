
if facing certificate issues:

Locate your pip.conf file based on your operating system -

1. MacOS - $HOME/Library/Application Support/pip/pip.conf

2. Unix - $HOME/.config/pip/pip.conf

3. Windows - %APPDATA%\pip\pip.ini

Open the pip.conf file and add trusted-host under the global param -

[global]
trusted-host = pypi.python.org
               pypi.org
               files.pythonhosted.org


Restart your python and then the pip installer will trust these hosts permanently.

## Download and Install
1. Clone the repository:

```bash
Copy code
git clone https://github.com/Nandi-Ai/DRaaS.git
cd DRaaS 
```

2. Install dependencies by requirements.txt

## Prerequisites

- Python 3.8.10 installed
- Redis server installed and running
- Follow the requirements.txt file


**Windows**

install python from cmd shell type:
`python` and MS store shall popup, select python3 and click get/install.
After python is install install pip: by typing in cmd shell 
`python.exe -m pip install --upgrade pip`
after pip is installed from command shell type: 

`pip install -U python-dotenv requests configparser paramiko confparser`
removed sys windows-curses

you can navigate to control panel > System and Security > System > Advanced system Settings.
Now in Advance System Setting click on Environment Variables.
Here we can add new user variables and new system variables. We will add user variable by clicking New under user variables.

In the new window you can add Variable name and Variable value and click ok.
Now, click Ok on Environment Variables window to save changes.

**Linux**

Start by updating the package list using the following command: `sudo apt update`.
Use the following command to install pip for Python 3: `sudo apt install python3-pip`. ...
Once the installation is complete, verify the installation by checking the pip version: `pip3 --version`.
`pip3 install -U python-dotenv requests configparser paramiko  confparser`
removed sys curses

nano ~/.bash_profile
export USER="username"
export PASSWORD="password"


**systemd setup**
1. In the `producer.service` and `consumer.service`, update the `User` and `ExecStart` paths to reflect your system's    configuration.
2. Configure and start the services:

    ```bash
    sudo cp /path/to/DRaaS/producer.service /etc/systemd/system/
    sudo cp /path/to/DRaaS/consumer.service /etc/systemd/system/

    sudo systemctl daemon-reload

    sudo systemctl enable producer
    sudo systemctl enable consumer

    sudo systemctl start producer
    sudo systemctl start consumer 
    ```
3. Verify service status:

    ```bash
    sudo systemctl status producer
    sudo systemctl status consumer
    ```

--if not running try:
  sudo cp -a config /opt/

### Interacting with APIs
- The system provides the following APIs:

  **Endpoint 1: /api/remaining_tasks**
  
  - **Description:** Calculate the number of remaining tasks in the Redis queue
  - **Method:** GET
  - **Response:**
  
    ```json
    {
      "result": "Success",
      "data": {
        "remaining_tasks": 0
      }
    }
    ```
  
  **Endpoint 2: /api/current_task**
  
  - **Description:** Retrieve information about the current task being processed
  - **Method:** GET
  - **Response:**
  
    ```json
    {
      "result": "Success",
      "data": {
        "current_task": {
          // Task information fields
        }
      } 
    }
    ```

  **Endpoint 3: /api/clear_cache**
  
  - **Description:** Clear the Redis cache (delete all keys)
  - **Method:** POST
  - **Response:**
  
    ```json
    {
      "result": "Success",
      "data": {
        "message": "Redis cache cleared"
      }
    }
    ```

  **Endpoint 4: /api/service_status/producer**
  
  - **Description:** Get the status of the producer service
  - **Method:** GET
  - **Response:**
  
    ```json
    {
      "result": "Success",
      "data": {
        "producer_status": "active"
      }
    }
    ```

  **Endpoint 5: /api/service_status/consumer**
  
  - **Description:** Get the status of the consumer service
  - **Method:** GET
  - **Response:**
  
    ```json
    {
      "result": "Success",
      "data": {
        "consumer_status": "inactive"
      }
    }
    ```