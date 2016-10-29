Factorio MMO Production scenario
--------------------------------


This repository contains a Python-written daemon that acts as a 
bridge between the factorio server and mission control server.


Usage
-----

```
 # apt-get install python3 python3-dev python-virtualenv
 # sudo -u factorio -i
 $ cd /opt
 $ git clone https://github.com/factoriommo/factoriommo-agent
 $ cd factoriommo-agent
 $ virtualenv -p /usr/bin/python3 env
 $ source env/bin/activate
 $ pip install -r requirements.txt
 $ cp config.example /etc/factoriomcd.ini
 > Edit /etc/factoriomcd.ini to suit your needs.
 # cp factoriomcd.service /etc/systemd/system/
 # systemctl start factoriomcd
 
```
