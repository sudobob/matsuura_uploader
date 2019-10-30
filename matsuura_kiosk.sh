#!/bin/bash
#
#
xset s noblank
xset s off
xset -dpms

unclutter -idle 0.5 -root &

source /home/pi/matsuura_uploader/.env

curl -X POST -H 'Content-type: application/json' --data '{"text":"Matsuura was turned *ON*"}' $SLACK_WEBHOOK_URL

sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' /home/pi/.config/chromium/Default/Preferences
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' /home/pi/.config/chromium/Default/Preferences

DISPLAY=:0.0

/usr/bin/chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost/login\?username=$KIOSK_USER_NAME\&password=$PASSWORD 

