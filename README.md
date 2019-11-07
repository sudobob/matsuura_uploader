# Matsuura Yasnac Uploader
![enter image description here](https://raw.githubusercontent.com/sudobob/matsuura_uploader/master/static/matsuura_clipped_128w.png)

The matsuura uploader provides a web-based file upload interface to send jobs to the Matsuura-Yasnac CNC mill

The Matsuura mill is controlled by a Yasnac controller. The Yasnac is equipped with an RS232 interface that accepts G-code files for upload

This application runs on a dedicated raspberry pi with a touch screen.
# Basic Use

 - On your PC, Navigate to [`https://matsuura.local`](http://matsuura.local/)
 - Login with the appropriate username and password
 - Upload your file
 - Navigate to the SEND page
 - Click on START
 
 # Installation
 
- We are using the __raspbian buster desktop__ distro
- `sudo raspi-config` to set things like wifi network name and password. I typically enable ssh access and complete all setup via ssh. You'll also want to set Boot Options -> Auto Login Desktop
- if this is a new pi do a `sudo apt-get upgrade`  and if this is not a brand new distro then  a `sudo apt-get dist-upgrade`
-  install this repo into `/home/pi/matsuura_uploader` and `cd matsuura_uploader`
- If this was a -lite distro like raspbian buster lite  you'll need to do a 
`sudo apt-get install lightdm xserver-xorg lxde chromium-browser`
You should use doa a `sudo raspi-config` and select __Boot Options -> Desktop/CLI -> Desktop Autologin__ Then reboot
- install python package installer pip3
 `sudo apt-get install python3-pip`
- install python packages with 
`sudo -H pip3 -r requirements.txt`
 *Note since this is a dedicated raspi I don't see the need to use virtualenv*
- install boot-time invocations of web server and serial uploader daemons 


```
sudo ln -s /home/pi/matsuura_uploader/matsuura_uploader.service /etc/systemd/system/
sudo ln -s /home/pi/matsuura_uploader/serial_sender.service /etc/systemd/system/
sudo systemctl enable matsuura_uploader
sudo systemctl enable serial_sender
```
     
- configure the a browser instance to come up on the local touch screen in kiosk mode at boot time. if `
```
mv /home/pi/.config/lxsession/LXDE/autostart /home/pi/.config/lxsession/LXDE/autostart-

ln -s /home/pi/matsuura_uploader/autostart /home/pi/.config/lxsession/LXDE/
```
- do a `mv .env-example .env` Edit .env and set the USERNAME and PASSWORD values
- do a `source .env` to pick up the handy development aliases
- You should start the flask application in the foreground initially to see if it is starting up ok with `dbg_start_web_app`
- Same for the serial sender with `dbg_start_sender`
- At this point you should be able to browse to http://YourRaspisIPaddr/ and upload and send files
- If all is well then reboot your pi and the processes should start at boot time via systemd, the browser should come up on the local touch screen





# Development Info
This app is written using the **python flask** framework for web applications. Main code is in the file `app.py` It relies on a separate process `serial_sender.py` to send the data to the serial ports. The Flask web app services html, css, and js to render the page. When the user commands an action to send a file or get status, their flask web server instance makes a tcp socket connection to the serial sender on port 1111 and issues a one line command. The seial sender returns a 1 line json-encoded response which is sent directly back to the client's web browser

## Handy development debugging commands
You will need to source the local environment variables from `.env`  with `source .env`

connect directly to serial usb dongle  0  `t0`

connect directly to serial usb dongle  1  `t1`

list all available serial ports  `lp`

stop system instance of web app  `sysctl_stop_web_app`

start system instance of web app   `sysctl_start_web_app`

stop system instance of uploader   `sysctl_stop_sender`

start system instace of uploader  `sysctl_start_sender`

start web app in foreground for debugging  `dbg_start_web_app`

start uploader in foreground for debugging  `dbg_start_sender`



