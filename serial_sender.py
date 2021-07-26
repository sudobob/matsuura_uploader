"""

serial port <> socket daemon for use with matsuura drip feed application

listens on a tcp port for connections, probably from web server

takes commands like 'send <file>', 'status', etc.

To test:

Hook 2 usb serial dongles  up to two ports
connect them with a null modem cable
run this code on one of them
run this on the other one

python3 /usr/lib/python3/dist-packages/serial/tools/miniterm.py --rtscts --rts 1 /dev/ttyUSB1 9600

# 9/29 haven't proven RTS/CTS handshake working in above config

A Change.

"""
import socket
import select
import os
import sys
import typing
from typing import Optional

import serial
import serial.tools.list_ports
import time
import random
import dotenv
import json

dotenv.load_dotenv()  # get envars from .env

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
read_list = []

serial_port_name = os.environ.get('SERIAL_PORT_NAME', "/dev/ttyUSB0")
serial_tcp_port = int(os.environ.get('SERIAL_TCP_PORT', 1111))
upload_path = os.environ.get('UPLOAD_PATH', "/home/pi/matsuura_uploader/uploads")
serial_connection: Optional[serial.Serial] = None
file_to_send: Optional[typing.TextIO] = None
file_first_line = False
file_size: Optional[int] = None
bytes_sent = None
sent_percent = 0
last_cts = None

main_loop_iterations = 0


def log(s: str):
    # write string s to stderr with timestamp
    now = time.time()
    m_sec = int(now*1000 % 1000)
    # message = s.removesuffix("\n")
    message = s
    if message[-1] == '\n':
        message = message[:-1]
    t = time.localtime(now)
    sys.stderr.write(f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{m_sec:03d}")
    sys.stderr.write(f" {message}\n")


def main():
    global main_loop_iterations, file_to_send
    prep_socket()
    # e(gen_send_random_string() + '\n')
    list_ports()
    while True:
        if file_to_send is None:
            time.sleep(.8)
            # e('sersender loop #%i\r' % (main_loop_iterations))

        time.sleep(.02)     # TODO: Maybe needs to sleep based on how many chars sent?
        main_loop_iterations += 1
        # if not( main_loop_iterations%100):
        # e('sersender loop #%i\r' % (main_loop_iterations))

        serial_chores()
        serial_check_and_open()
        pisc = process_inbound_socket_connections()
        sock = pisc[0]
        mesg_from_socket = pisc[1]

        if mesg_from_socket != '':
            # process inbound message
            log(f'{mesg_from_socket!r}\n')
            mesg = json.loads(mesg_from_socket.lower())

            if mesg['cmd'] == 'start':
                f = mesg["file"]
                log(f"got start message file:{f}")
                sssret = serial_start_send(mesg['file'])
                ssret_as_json_str = json.dumps(sssret).encode('utf-8')
                sock.send(ssret_as_json_str)

            elif mesg['cmd'] == 'stop':
                log('i\'ve been asked to stop sending\n')
                if file_to_send is not None:
                    log('closing file\n')
                    if file_to_send is not None:
                        file_to_send.close()
                    file_to_send = None
                    sock.send(json.dumps(
                        {'error': 0, 'message': 'Stopped Sending'}).encode(
                        'utf-8'))
                else:
                    sock.send(json.dumps(
                        {'error': 1, 'message': 'Already Stopped'}).encode(
                        'utf-8'))

            elif mesg['cmd'] == 'status':
                m = ''
                if file_to_send is None:
                    m += 'Idle '
                else:
                    m += 'Sent %d%% ' % sent_percent

                if serial_connection.cts == 0:
                    m += 'Flow Controlled'

                log(m + '\n')
                sock.send(
                    json.dumps({'error': 0, 'message': m}).encode('utf-8'))
            else:
                sock.send(json.dumps(
                    {'error': 1, 'message': 'Unknown command'}).encode(
                    'utf-8'))


def list_ports():
    # list available ports. For debugging
    iterator = serial.tools.list_ports.comports()
    port_names = []
    for n, (port, desc, hwid) in enumerate(iterator, 1):
        port_names.append(port)
        log("%d %s\n" % (n, port))
        log("    desc: {}\n".format(desc))
        log("    hwid: {}\n".format(hwid))
    return port_names


def prep_socket():
    # called once to prepare the primary tcp listener socket
    global server_socket, read_list
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', serial_tcp_port))
    server_socket.listen(1)
    log("Listening on port %d\n" % serial_tcp_port)

    read_list = [server_socket]  # read list is the list of tcp ports


def serial_check_and_open():
    global serial_connection
    if serial_connection is None:
        # if serial connection is not open attempt to open
        try:
            serial_connection = \
                serial.Serial(serial_port_name,
                              9600,
                              parity=serial.PARITY_NONE,
                              write_timeout=None,
                              # write_timeout=0, has no effect on small files where nothing is waiting
                              xonxoff=False,
                              rtscts=True)

        except serial.SerialException as er:
            log(er.strerror)
            serial_connection = None

        if serial_connection is not None:
            log('Serial Port open [%s] success\n' % serial_port_name)


def process_inbound_socket_connections():
    # e('select()')

    # select() returns all the connections and their statuses
    readable, writable, errored = select.select(read_list, [], [], 0)
    for s in readable:
        # for anything inbound...
        if s is server_socket:
            # new connections will appear on server_socket
            client_socket, address = server_socket.accept()
            read_list.append(
                client_socket)  # put it on our read_list of sockets
            log("Connection from: %s:%s\n" % (address[0], address[1]))
        else:
            # handle messages from client connections
            mesgb = b''
            try:
                mesgb = s.recv(1024)
            except:
                log('socket reset')

            if mesgb:
                # extract message.
                try:
                    mesg = mesgb.decode(
                        'utf-8')  # attempt to convert bytes to utf-8 string
                except UnicodeError:
                    return [s, mesgb]  # send raw if unable
                return [s, mesg.rstrip()]  # otherwise send utf-8 version
            else:
                # otherwise connection must have shut down
                log("disconnecting from client\n")
                s.close()
                read_list.remove(s)

    return ['', '']  # if select() returns w/nothing readable return empty


def gen_send_random_string():
    # you never know when you are going to need to send a random string..
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return ''.join([random.choice(chars) for _ in range(32)])


def serial_start_send(filename):
    # open file and start sending on serial port
    global file_to_send
    global file_first_line
    global file_size
    global bytes_sent

    if file_to_send is not None:
        return {'error': 1, 'message': 'Already Busy Sending.'}

    file_with_path = os.path.join(upload_path, filename)
    try:
        file_to_send = open(file_with_path, 'r')
    except OSError:
        file_to_send = None
        return {'error': 1, 'message': 'open [%s] FAIL' % filename}

    file_size = os.stat(file_with_path)[6]
    bytes_sent = 0
    file_first_line = True
    return {'error': 0, 'message': 'Started sending [%s] ' % filename}


def serial_chores():
    # call periodically
    # if file is open, send another line
    global file_to_send
    global file_first_line
    global main_loop_iterations
    global bytes_sent
    global sent_percent
    global last_cts
    global serial_connection

    if serial_connection is None:
        return

    try:
        cts = serial_connection.cts
    except OSError as err:
        log(f"USB Unplugged: {err.strerror}")
        # Someone unplugged the USB cable
        serial_connection.close()
        serial_connection = None
        return

    msg = f"serial_chores() start: cts[{cts:d}]"

    if file_to_send is not None:
        msg += (' out_waiting[%d] bs[%d] fs[%d] pct[%d]' %
                (serial_connection.out_waiting,
                 bytes_sent,
                 file_size,
                 sent_percent
                 ))

    if cts != last_cts:
        last_cts = cts
        log(msg)
        msg = None

    if file_to_send is None:
        return

    # if True:  # doesn't seem necessary: serial_connection.out_waiting == 0 and serial_connection.cts == 1:
    if serial_connection.out_waiting == 0 and serial_connection.cts:
        # if True:
        if msg is not None:
            log(msg)
        if file_first_line:
            line_from_file = "\n"
            file_first_line = False
        else:
            line_from_file = file_to_send.readline().upper()
        log(f'    read line_from_file[{line_from_file!r}]\n')
        if line_from_file == '':
            log('    eof on file return.\n')
            file_to_send.close()
            file_to_send = None
            return
        if line_from_file == "%\n":
            # The Matsuura stops at a %.
            # Only send the %, not the \n
            line_from_file = "%"
            file_to_send.close()
            file_to_send = None
            log("    Writing only % -- end of file")
        if line_from_file == "M30\n":
            log('    M30 treating like EOF on file return.\n')
            line_from_file = "M30\n%"
            file_to_send.close()
            file_to_send = None

        line_from_file_as_bytes = line_from_file.encode('utf-8')
        log(f"SEND: {line_from_file!r}")
        log(f"    writing {len(line_from_file_as_bytes)} bytes to file... ")
        wret = serial_connection.write(line_from_file_as_bytes)
        log(f"       ... DONE wrote {wret} bytes\n")
        bytes_sent = bytes_sent + len(line_from_file_as_bytes)

        sent_percent = int((bytes_sent / file_size) * 100.0)

        log('    chore done cts[%d] out_waiting[%d] bs[%d] fs[%d] pct[%d] [%s]\n' %
            (serial_connection.cts,
             serial_connection.out_waiting,
             bytes_sent,
             file_size,
             sent_percent,
             line_from_file.rstrip()))


if __name__ == '__main__':
    main()
    exit(0)
