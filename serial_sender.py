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

"""
import socket
import select
import os
import sys
import serial
import serial.tools.list_ports
from pprint import pprint as pp
import pdb
import time
import random 
import dotenv 
import json 

dotenv.load_dotenv() # get envars from .env

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
read_list = []

serial_port_name  = os.environ['SERIAL_PORT_NAME']
serial_tcp_port   = int(os.environ['SERIAL_TCP_PORT'])
upload_path       = os.environ['UPLOAD_PATH']
serial_connection = None
file_to_send = None
file_size = None
bytes_sent = None
sent_percent = 0

main_loop_iterations  = 0

def e(s):
  # write string s to stderr	
  sys.stderr.write(s)

def list_ports():
  # list available ports. For debugging
  iterator = serial.tools.list_ports.comports()
  port_names = []
  for n, (port, desc, hwid) in enumerate(iterator, 1):
      port_names.append(port)
      e("%d %s\n"% (n,port))
      e("    desc: {}\n".format(desc))
      e("    hwid: {}\n".format(hwid))
  return port_names

def prep_socket():
  # called once to prepare the primary tcp listener socket
  global server_socket, read_list
  server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  server_socket.bind(('', serial_tcp_port))
  server_socket.listen(1)
  e("Listening on port %d\n" %(serial_tcp_port) )

  read_list = [server_socket] # read list is the list of tcp ports

def serial_check_and_open():
  global serial_connection
  if  serial_connection == None:
		# if serial connection is not open attempt to open
    try:
      serial_connection = \
      serial.Serial(serial_port_name,
                    9600,
                    parity        = serial.PARITY_NONE,
                    write_timeout = None,
                    xonxoff       = False,
                    rtscts        = True)

    except serial.SerialException as er:
      e('could not open port [%s]:%s\n' %( serial_port_name, er))
      serial_connection = None

    if (serial_connection != None):
      e('Serial Port open success\n')


def process_inbound_socket_connections():
  #e('select()')

	# select() returns all the connections and their statuses
  readable, writable, errored = select.select(read_list, [], [],0)
  for s in readable:
			# for anything inbound...
      if s is server_socket:
					# new connections will appear on server_socket
          client_socket, address = server_socket.accept()
          read_list.append(client_socket) # put it on our read_list of sockets
          e("Connection from: %s:%s\n" % ( address[0], address[1] ))
      else:
					# handle messages from client connections	
          mesgb = b''
          try:
            mesgb = s.recv(1024)
          except:
            e('socket reset')

          if mesgb:
						# extract message. 
            try:
              mesg = mesgb.decode('utf-8')  # attempt to convert bytes to utf-8 string
            except UnicodeError:
              return [s,mesgb] # send raw if unable
            return[s,mesg.rstrip()] # otherwise send utf-8 version
          else:
            # otherwise connection must have shut down
            e("disconnecting from client\n")
            s.close()
            read_list.remove(s)
        

  return['',''] # if select() returns w/nothing readable return empty

def gen_send_random_string():
	# you never know when you are going to need to send a random string..
	return ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') for i in range(32)])

def serial_start_send(filename):
  # open file and start sending on serial port
  global file_to_send
  global file_size
  global bytes_sent
  file_with_path = os.path.join(upload_path,filename)
  try: 
    file_to_send = open(file_with_path,'r')
  except:
    file_to_send = None
    return {'error':1,'message': 'open [%s] FAIL' % (filename) }
    
  file_size = os.stat(file_with_path)[6]
  bytes_sent = 0
  return {'error':0,'message': 'Started sending [%s] ' % (filename) }

def serial_chores():
  # call periodically
  # if file is open, send another line
  global file_to_send
  global main_loop_iterations
  global bytes_sent
  global sent_percent

  if  serial_connection != None and  file_to_send != None:
  

    if serial_connection.out_waiting == 0 and serial_connection.cts == 1:
      line_from_file = file_to_send.readline().upper()
      if line_from_file == '':
        e('eof on file\n')
        file_to_send = None
        return

      line_from_file_as_bytes = line_from_file.encode('utf-8')
      wret = serial_connection.write(line_from_file_as_bytes)
      bytes_sent = bytes_sent + len(line_from_file_as_bytes)


      sent_percent = int((bytes_sent/file_size)*100.0)

      e('cts[%d] bs[%d] fs[%d] pct[%d] [%s]\n' % \
                    (serial_connection.cts, \
                    bytes_sent, \
                    file_size, \
                    sent_percent, \
                    line_from_file.rstrip())) 


if __name__ == '__main__':
  prep_socket()

  #e(gen_send_random_string() + '\n')


  while True:
    if file_to_send == None:
      time.sleep(.8)
      #e('sersender loop #%i\r' % (main_loop_iterations))

    time.sleep(.01)
    main_loop_iterations = main_loop_iterations + 1
    #if not( main_loop_iterations%100):	
      #e('sersender loop #%i\r' % (main_loop_iterations))

    serial_chores()
    serial_check_and_open()
    pisc = process_inbound_socket_connections()
    sock = pisc[0]
    mesg_from_socket = pisc[1] 

    if (mesg_from_socket != ''):
      # process inbound message
      e('message[%s]\n' %(mesg_from_socket))
      mesg = json.loads(mesg_from_socket.lower())

      if (mesg['cmd'] == 'start'): 
        e('got start message..\n')
        sssret = serial_start_send(mesg['file'])
        ssret_as_json_str = json.dumps(sssret).encode('utf-8')
        sock.send(ssret_as_json_str)

      elif (mesg['cmd'] == 'stop'): 
        e('i\'ve been asked to stop sending\n')
        if not file_to_send == None:
          e('closing file\n')
          file_to_send.close()
          file_to_send = None
          sock.send(json.dumps({'error':0,'message':'Stopped Sending'}).encode('utf-8'))
        else:
          sock.send(json.dumps({'error':1,'message':'Already Stopped'}).encode('utf-8'))

      elif (mesg['cmd'] == 'status'): 
        m = ''
        if file_to_send == None:
          m += 'Idle ' 
        else:
          m += 'Sent %d%% ' % (sent_percent)

        if serial_connection.cts == 1:
          m += 'Flow Controlled'

        sock.send(json.dumps({'error':0,'message':m }).encode('utf-8'))

      else:
          sock.send(json.dumps({'error':1,'message':'Unknown command'}).encode('utf-8'))

