#!/bin/bash
#
# https://pimylifeup.com/raspberry-pi-kiosk/
#
xset s noblank
xset s off
xset -dpms

unclutter -idle 0.5 -root &

source /home/pi/matsuura_uploader/.env

sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' /home/pi/.config/chromium/Default/Preferences
sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' /home/pi/.config/chromium/Default/Preferences

/usr/bin/chromium-browser --noerrdialogs --disable-infobars --kiosk http://localhost/login\?username=$USER_NAME\&password=$PASSWORD

#while true; do
#  xdotool keydown ctrl+r; xdotool keyup ctrl+r;
#  sleep 10
#done
