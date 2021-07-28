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

This is the test version installed on the Pi 7-25-2021 Curt

"""
import socket
import select
import os
import sys
from typing import Optional

import serial
import serial.tools.list_ports
import time
import random
import dotenv
import json


class FileToSend:
    def __init__(self, file_name):
        self.file_name = file_name
        self.line_buf = []      # Lines of file with \n stripped off.
        self.lines_sent = 0     # Index of next line to send
        self._read_file()

    @property
    def lines(self) -> int:
        """ Total number of lines from file to be sent. """
        return len(self.line_buf)

    @property
    def percent_sent(self) -> int:
        """ Percent line_buf sent (0 to 100) """
        return int(self.lines_sent * 100 / self.lines)

    @property
    def eof(self) -> bool:
        return self.lines_sent >= len(self.line_buf)

    @property
    def status(self):
        """ e.g. "Line 89/234 34%" """
        status = f"Line {file_to_send.lines_sent}/{file_to_send.lines} " \
                 f"{file_to_send.percent_sent}%"
        return status

    def _read_file(self) -> None:
        """ Read file into memory.

            Builds the list of line_buf to transmit (without \r or \n) and makes
            sure it starts with a blank line and ends with the needed % marker.

            Only reads up to the % End-of-code marker and skips a beginning
            % if there is one.

            open() will throw OSError exception
        """

        self.line_buf = []

        saw_start_percent = False
        with open(self.file_name) as fd:
            while True:
                line = fd.readline()
                if line == "":  # EOF
                    break
                line = line.rstrip().upper()    # Strip \n, spaces, make upper
                if len(self.line_buf) == 0:
                    if line == "":
                        # skip all initial blank line_buf.
                        continue
                    if not saw_start_percent and line[0] == "%":
                        # We treat an initial '%' as a G code start of code
                        # marker but we can not send it because the Matsuura
                        # will treat it as an end of code marker and stop
                        # reading. So we strip it, but we only strip one. The
                        # next one we see is the end of code marker.
                        saw_start_percent = True
                        continue
                if line == "":
                    # Strip all blank line_buf. They are both unneeded, waste
                    # precious space on the Matsuura limited memory, and
                    # might risk an RS-232 Overrun issue.
                    continue
                # We have a non blank line
                if line[0] == "%":  # end of code marker
                    break
                self.line_buf.append(line)

        # End of file.

        # Add a % to the end of the line buffer.
        #
        # Because there is a really odd bug here we add it to the end of the
        # last line so it gets sent at the same time the last line is sent. The
        # bug is if we are drip feeding slowly, and the M30 stop command at the
        # end of the file gets executed before we send the %, then the Matsuura
        # stops reading.  So CTS will never go low and we will be hung waiting
        # for the Matsuura to ask for another line.  In drip feed (TAPE) mode,
        # we could imply never bother to send the %. But when sending to load a
        # program into memory, the % is required.  Since we don't know if we
        # are drip feeding or loading into memory, we must send the %.  So the
        # simple hack I choose to use here, is to send it as part of the last
        # line of the file.

        if len(self.line_buf) == 0:
            # There is no last line to add it to!
            self.line_buf.append("%")
        else:
            self.line_buf[-1] += "\n%"

        # Add initial blank line for the Matsuura LSK (Leader Skip) to eat.
        self.line_buf.insert(0, "")

        self.lines_sent = 0

    def next_line(self) -> Optional[str]:
        """ Return next line to send (with \n), or None for EOF. """
        if self.eof:
            return None
        line = self.line_buf[self.lines_sent] + '\n'
        self.lines_sent += 1
        return line


dotenv.load_dotenv()  # get envars from .env
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

read_list = []
serial_port_name = os.environ.get('SERIAL_PORT_NAME', "/dev/ttyUSB0")
serial_tcp_port = int(os.environ.get('SERIAL_TCP_PORT', 1111))
upload_path = os.environ.get('UPLOAD_PATH', "/home/pi/matsuura_uploader/uploads")
serial_connection: Optional[serial.Serial] = None
file_to_send: Optional[FileToSend] = None
file_first_line = False
file_size: Optional[int] = None
# bytes_sent = None
# sent_percent = 0

last_cts = None


main_loop_iterations = 0


def log(s: str):
    # write string s to stderr with timestamp
    now = time.time()
    m_sec = int(now*1000 % 1000)
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
    # list_ports()
    while True:
        if file_to_send is None:
            # time.sleep(.8)
            pass
            # e('sersender loop #%i\r' % (main_loop_iterations))

        # time.sleep(.02)     # TODO: Maybe needs to sleep based on how many chars sent?
        time.sleep(.01)
        main_loop_iterations += 1
        # if not( main_loop_iterations%100):
        # e('sersender loop #%i\r' % (main_loop_iterations))

        serial_chores()
        if serial_connection is None:
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
                    m += "Idle "
                else:
                    m += file_to_send.status

                if serial_connection.cts:
                    m += ' Matsuura Waiting For Data'

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
    log(f"port is {serial_tcp_port}")
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
            time.sleep(1.0)

        if serial_connection is not None:
            log('Serial Port open [%s] success\n' % serial_port_name)

    return serial_connection


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

    if file_to_send is not None:
        return {'error': 1, 'message': 'Already Busy Sending.'}

    file_with_path = os.path.join(upload_path, filename)
    try:
        file_to_send = FileToSend(file_with_path)
    except OSError:
        file_to_send = None
        return {'error': 1, 'message': 'open [%s] FAIL' % filename}

    return {'error': 0, 'message': 'Started sending [%s] ' % filename}


def serial_chores():
    # call periodically
    # if file is open, send another line
    global file_to_send
    global file_first_line
    global main_loop_iterations
    # global bytes_sent
    # global sent_percent
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

    msg = f"serial_chores() start cts: {cts!s:<5}"

    if file_to_send is not None:
        msg += f" out_waiting: {serial_connection.out_waiting:<3} " \
               f" {file_to_send.status}"

    if cts != last_cts:
        last_cts = cts
        log(msg)
        msg = None

    if file_to_send is None:
        return

    # if serial_connection.out_waiting == 0 and serial_connection.cts:
    if serial_connection.out_waiting == 0:
        if msg is not None:
            log(msg)
        line_from_file = file_to_send.next_line()
        # log(f'    read line_from_file[{line_from_file!r}]\n')
        if line_from_file is None:
            log('    eof on file return.\n')
            file_to_send = None
            return

        line_from_file_as_bytes = line_from_file.encode('utf-8')
        log(f"SEND: {line_from_file!r} {len(line_from_file_as_bytes)} bytes")
        _wret = serial_connection.write(line_from_file_as_bytes)
        # log(f"       ... DONE wrote {wret} bytes\n")
        # bytes_sent += len(line_from_file_as_bytes)

        log(f"    chore done cts: {cts!s:<5}"
            f" out_waiting: {serial_connection.out_waiting:<3} "
            f" {file_to_send.status}: "
            )


if __name__ == '__main__':
    main()
    exit(0)
