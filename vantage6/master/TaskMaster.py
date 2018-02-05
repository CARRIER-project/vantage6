#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
import importlib

from flask import Flask, Response, request, render_template, make_response
from flask_restful import Resource, Api, fields
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_claims

from flask_marshmallow import Marshmallow

import datetime
import logging
log = logging.getLogger(__name__)

import json

import db
import util

__version__ = "0.01 - alpha"

# ------------------------------------------------------------------------------
# Initialize Flask
# ------------------------------------------------------------------------------
RESOURCES_INITIALIZED = False
API_BASE = '/api'
WEB_BASE = '/app'

# Create Flask app
app = Flask('taskmaster')

# Enable cross-origin resource sharing
CORS(app)


# ------------------------------------------------------------------------------
# Api - REST JSON-rpc
# ------------------------------------------------------------------------------
api = Api(app)

@api.representation('application/json')
def output_json(data, code, headers=None):

    if isinstance(data, db.Base):
        data = db.jsonable(data)
    elif isinstance(data, list) and len(data) and isinstance(data[0], db.Base):
        data = db.jsonable(data)

    resp = make_response(json.dumps(data), code)
    resp.headers.extend(headers or {})
    return resp


# ------------------------------------------------------------------------------
# Setup SQLAlchemy and Marshmallow for marshalling/serializing
# ------------------------------------------------------------------------------
ma = Marshmallow(app)


# ------------------------------------------------------------------------------
# Setup the Flask-JWT-Extended extension (JWT: JSON Web Token)
# ------------------------------------------------------------------------------
app.config['JWT_SECRET_KEY'] = 'f8a87430-fe18-11e7-a7b2-a45e60d00d91'
jwt = JWTManager(app)


@jwt.user_claims_loader
def user_claims_loader(user_or_client):
    if isinstance(user_or_client, db.User):
        type_ = 'user'
        roles = user_or_client.roles.split(',')
    else:
        type_ = 'client'
        roles = []
    
    claims = {
        'type': type_,
        'roles': roles,
    }

    return claims

@jwt.user_identity_loader
def user_identity_loader(user_or_client):
    if isinstance(user_or_client, db.Authenticatable):
        return user_or_client.id
    
    msg = "Could not create a JSON serializable identity from '{}'"
    msg = msg.format(user_or_client)
    log.error(msg)
    return None

@jwt.user_loader_callback_loader
def user_loader_callback(identity):
    user_or_client = None
    claims = get_jwt_claims()

    return db.Authenticatable.get(identity)


# ------------------------------------------------------------------------------
# Resources / API's
# ------------------------------------------------------------------------------
def load_resources(api, API_BASE, resources):
    for name in resources:
        module = importlib.import_module('resource.' + name)
        module.setup(api, API_BASE)

# ------------------------------------------------------------------------------
# Http routes
# ------------------------------------------------------------------------------
@app.route(WEB_BASE+'/', defaults={'path': ''})
@app.route(WEB_BASE+'/<path:path>')
def index():
    return "Hello, World"



# ------------------------------------------------------------------------------
# init & run
# ------------------------------------------------------------------------------
def init():
    global RESOURCES_INITIALIZED

    resources = [
            'client',
            'collaboration',
            'organization',
            'task',
            'result',
            'token',
            'user',
            'version',
    ]

    if not RESOURCES_INITIALIZED:
        load_resources(api, API_BASE, resources)
        RESOURCES_INITIALIZED = True

def run():
    app.run(debug=True, host='0.0.0.0', port=5000)


# ------------------------------------------------------------------------------
# __main__
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    cfg = util.init('taskmaster')
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    if cfg['env']['type'] == 'test':
        log.warning("Setting 'JWT_ACCESS_TOKEN_EXPIRES' to one day!")
        app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)

    init()    
    run()

