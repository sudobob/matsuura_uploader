#!/usr/bin/env python3
"""

matsuura file uploader web app


Handy links

    https://pimylifeup.com/raspberry-pi-kiosk/

"""

from flask import Flask, Response, redirect, url_for, render_template, flash, g, request, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from flask_bootstrap import Bootstrap
from flask_restful import Resource, Api

from flask_restful import Resource as FlaskRestResource
from flask_restful import reqparse as FlaskRestReqparse
from flask_restful import Api as FlaskRestAPI
from flask_restful import request as FlaskRestRequest

import urllib
import os,sys,requests
import dotenv 
import pdb # for debugging
import pprint
import json
import socket # to talk to serial port sender

import requests # for slack

flask_app = Flask(__name__)
Bootstrap(flask_app) # bootstrap-a-ma-tize flask
flask_rest_api = FlaskRestAPI(flask_app) # rest-a-ma-tize flask
flask_app.config['BOOTSTRAP_SERVE_LOCAL'] = True # tell bootstrap NOT to fetch from CDNs

dotenv.load_dotenv() # get envars from .env
flask_app.secret_key = os.environ['KEY']
single_user_name     = os.environ['USER_NAME']
single_user_password = os.environ['PASSWORD']
upload_path          = os.environ['UPLOAD_PATH']
serial_tcp_port      = int(os.environ['SERIAL_TCP_PORT'])
#slack_webhook_url    = os.environ['SLACK_WEBHOOK_URL']

login_manager            = LoginManager(flask_app) # login manager setup
login_manager.login_view = 'login'
pp = pprint.PrettyPrinter(stream=sys.stderr) # for debugging

def e(s):
    sys.stderr.write(s)

class User(UserMixin):
    def __init__(self,id):
        self.id = id

    def __repr__self():
        return "%d" % (self.id)
        
@login_manager.user_loader
def load_user(id):
    # required by flask_login
    return User.query.get(int(id))

# somewhere to login
@flask_app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == 'POST':
        args = request.form
    elif request.method == 'GET':
        # supply username login on url (for kiosk autologin)
        rp = FlaskRestReqparse.RequestParser()
        rp.add_argument('username',type=str)
        rp.add_argument('password',type=str)
        args = rp.parse_args()

    if ((args['username'] == single_user_name or
        args['username'] == os.environ['KIOSK_USER_NAME']) and  # login as kiosk modifies UI a bit
        args['password'] == single_user_password):        
        id = args['username']
        user = User(id)
        login_user(user)
        return redirect('/')
    else:
        return abort(401)

    flash('Please Log in')
    return render_template('login.html')

# somewhere to logout
@flask_app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect('/login')


# handle login failed
@flask_app.errorhandler(401)
def page_not_found(e):
    flash('login failed','error')
    flash('Please Log in','info')
    return render_template('login.html')
    
# callback to reload the user object        
@login_manager.user_loader
def load_user(userid):
    return User(userid)

@flask_app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if request.files:
            image = request.files["file"]
            if (image.filename == ''):
                flash('File NOT uploaded','error')
                return render_template("index.html")
            else:
                image.save(os.path.join(upload_path,image.filename))
                flash('file ' + image.filename + ' uploaded','success')

    global g
    g.files_uploaded = get_files_uploaded()
    g.kiosk_user_name = os.environ['KIOSK_USER_NAME']
    return render_template("index.html")

def get_first_line(fn):
    f = open(os.path.join(upload_path,fn),'r')
    # Skip blank lines and skip '%' line
    while True:
        line = f.readline()
        if line == '':    # EOF
            break
        line = line.rstrip()
        if line == '%' or line == '':
            continue
        break

    return line

def get_files_uploaded():
    file_names = os.listdir(upload_path)
    file_names.sort()
    o = []
    for fns in  file_names:
        fi = {'file_name':fns,'first_line':get_first_line(fns)}
        o.append(fi)
    return o


class rest_cmd(FlaskRestResource):
    # -----
    # REST communications with browser 
    def put(self):
        # curl localhost/api -X PUT -d 'cmd=start' -d 'go
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        e('connecting to serial sender...\n')
        try:
            sock.connect(('localhost',serial_tcp_port))
        except:
            return {'error': 1, 'message': 'could not connect to serial sender socket'}

        e('done\n')

        rp = FlaskRestReqparse.RequestParser()
        rp.add_argument('cmd')
        rp.add_argument('file')
        args = rp.parse_args()

        if (args['cmd'] == 'start' or 
            args['cmd'] == 'stop' or 
            args['cmd'] == 'status'):
            # send command to the serial listener
            arg_as_str = json.dumps(args)
            arg_as_bytes = arg_as_str.encode('utf-8')
            sock.sendall(arg_as_bytes)

						# get line line reply
            rx_mesg_bytes = sock.recv(1024)
            rx_mesg_str = rx_mesg_bytes.decode('utf-8')
            rx_mesg_obj = json.loads(rx_mesg_str)

            #pdb.set_trace()
            ret = rx_mesg_obj


        sock.close()
        return ret

flask_rest_api.add_resource(rest_cmd,'/api')
#--

# ------------
# http routes
@flask_app.route('/send')
@login_required
def send_file():
    global g
    g.files_uploaded = [] 
    fns = request.args.get('file_to_send')
    g.files_uploaded.append( {'file_name':fns,'first_line':get_first_line(fns)} )
    g.kiosk_user_name = os.environ['KIOSK_USER_NAME']
    return render_template('send.html')


@flask_app.route('/file_action', methods=["POST"])
@login_required
def file_action():
  if (request and request.form ):

    if 'file_to_delete' in request.form:
      try:
          os.unlink(os.path.join(upload_path,request.form['file_to_delete']))
      except:
          flash(request.form['file_to_delete']  + '  ' + 'probably already deleted')  
      else:
          flash(request.form['file_to_delete']  + '  ' + 'deleted')  

      global g
      g.files_uploaded = get_files_uploaded()
      g.kiosk_user_name = os.environ['KIOSK_USER_NAME']
      return render_template("index.html")

    if 'file_to_send' in request.form:
      return redirect("/send?file_to_send=" + request.form['file_to_send'])

@flask_app.route('/')
@login_required
def index():
  flash('You are logged in','success')
  global g
  g.files_uploaded = get_files_uploaded()
  g.kiosk_user_name = os.environ['KIOSK_USER_NAME']
  return render_template('index.html')

################################################################################
# Execution starts here
if __name__ == '__main__':
    # start up flask web server
    flask_app.run(host='0.0.0.0', port=80, debug=True)


