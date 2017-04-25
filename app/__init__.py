# Gevent needed for sockets
from gevent import monkey
monkey.patch_all()

# Imports
import os
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import boto3

# Configure app
socketio = SocketIO()
app = Flask(__name__)
app.config.from_object(os.environ["APP_SETTINGS"])
app.config.update(STEAM_API_KEY=os.environ['STEAM_API_KEY'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

import nltk
# noop if dataset already downloaded!
nltk.download("punkt")

# DB
db = SQLAlchemy(app)
dynamodb = boto3.resource("dynamodb",
                          region_name=app.config["DYNAMO_REGION"],
                          endpoint_url=app.config["DYNAMO_DATABASE_URI"])
s3 = boto3.resource("s3", region_name=app.config["DYNAMO_REGION"])

from app.steam.models import Review
Review._create_table()

from app.steam.models import Tag
Tag._create_table()

from app.steam.models import Game
Game._load_caches()
Game._create_table()

# Import + Register Blueprints
from app.accounts import accounts as accounts
app.register_blueprint(accounts)
from app.irsystem import irsystem as irsystem
app.register_blueprint(irsystem)

# Initialize app w/SocketIO
socketio.init_app(app)

# HTTP error handling
@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404
