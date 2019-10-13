# Matsuura Uploader

The matsuura uploader provides a web-based file upload interface to send jobs to the Matsuura-Yasnac CNC mill

The Matsuura mill is controlled by a Yasnac controller. The Yasnac is equipped with an RS232 interface that accepts G-code files for upload

This application runs on a dedicated raspberry pi. 
# Basic Use

 - On your PC, Navigate to [`https://matsuura.local`](http://matsuura.local/)
 - Login with the appropriate username and password
 - Upload your file
 - Navigate to the SEND page
 - Click on START
 

# Development Info
This app is written using the **python flask** framework for web applications. Main code is in the file `app.py` It relies on a separate process `serial_sender.py` to send the data to the serial port

## Handy commands during 
### Source local environment variables
source .env
### connect directly to serial usb dongle  0
t0
### connect directly to serial usb dongle  1
t1
###
### list all available serial ports
lp
### stop system instance of web app
sysctl_stop_web_app

### start system instance of web app
 sysctl_start_web_app

### stop system instance of uploader
 sysctl_stop_sender

### start system instace of uploader
 sysctl_start_sender

###  start web app in foreground for debugging
 dbg_start_web_app

###  start uploader in foreground for debugging
 dbg_start_sender


