import subprocess
import logging


log_file = '/var/log/restart_services.log'
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def restart_services(service_names):
    for name in service_names:
        try:
            subprocess.run(['sudo', 'systemctl', 'restart', name], check=True)
            logging.info(f"Service {name} restarted successfully.")
        except subprocess.CalledProcessError as err:
            logging.error(f"Failed to restart service {name}. Error: {err}")
        except Exception as err:
            logging.error(f"An unexpected error occurred while restarting service {name}. Error: {err}")


def main():
    services = ['consumer.service']    
    restart_services(services)

if __name__ == "__main__":
    main()


# 0 * * * * /usr/bin/python3 /path/script.py

# sudo visudo
# username ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart consumer1.service, /bin/systemctl restart consumer2.service, /bin/systemctl restart consumer3.service
