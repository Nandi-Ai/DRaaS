import requests, json
from urllib3.exceptions import InsecureRequestWarning
import re

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

def gaia_api_call(ip_addr, port, command, json_payload, sid):
    url = f'https://{ip_addr}:{port}/gaia_api/{command}'
    if sid == '':
        request_headers = {'Content-Type': 'application/json'}
    else:
        request_headers = {'Content-Type': 'application/json', 'X-chkp-sid': sid}
    r = requests.post(url, data=json.dumps(json_payload), headers=request_headers, verify=False)
    return r.json()

def gaia_login(ip_addr, user, password):
    payload = {'user': user, 'password': password}
    response = gaia_api_call(ip_addr, '443', 'login', payload, '')
    return response["sid"]

def gaia_logout(ip_addr, sid):
    return gaia_api_call(ip_addr, '443', 'logout', {}, sid)

def gaia_show_interfaces(ip_addr, sid):
    return gaia_api_call(ip_addr, '443', 'v1.5/show-interfaces', '', sid)


if __name__ == "__main__":
    gaia_ip = "10.169.32.178"
    try:
        sid = gaia_login(gaia_ip,'admin','iolredi8')
    except Exception as error:
        print(error)

    #show_interface_data = {'name':'eth0'}

    show_interfaces_result = gaia_show_interfaces(gaia_ip ,sid)

    print(json.dumps(show_interfaces_result, indent=4))
    vlans_to_create = []

    logout_result = gaia_logout(gaia_ip, sid)