FROM balenalib/raspberry-pi-python:3.5-buster

WORKDIR /home/pi/matsuura_uploader

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN ln -s /home/pi/matsuura_uploader/matsuura_uploader.service /etc/systemd/system
RUN ln -s /home/pi/matsuura_uploader/serial_sender.service /etc/systemd/system
#RUN systemctl enable matsuura_uploader
#RUN sytemctl enable serial_sender

RUN cp .env-example .env

RUN mkdir /home/pi/matsuura_uploader/uploads

RUN ln -s /home/pi/matsuura_uploader /root

EXPOSE 80/tcp
EXPOSE 1111/tcp

CMD [ "/bin/bash" ]
