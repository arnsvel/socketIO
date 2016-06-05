#!/usr/bin/env python

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on available packages.
async_mode = None

if async_mode is None:
    try:
        import eventlet
        async_mode = 'eventlet'
    except ImportError:
        pass

    if async_mode is None:
        try:
            from gevent import monkey
            async_mode = 'gevent'
        except ImportError:
            pass

    if async_mode is None:
        async_mode = 'threading'

    print('async_mode is ' + async_mode)

# monkey patching is necessary because this application uses a background
# thread
if async_mode == 'eventlet':
    import eventlet
    eventlet.monkey_patch()
elif async_mode == 'gevent':
    from gevent import monkey
    monkey.patch_all()

import time
from threading import Thread
from flask import Flask, render_template, session, request
from flask_socketio import SocketIO, emit, join_room, leave_room, \
    close_room, rooms, disconnect
import os
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)

APP_PORT = 3002
CLIENT_STATUS_CODE = {'JOINED': 1, 'LEAVED': -1, 'DISCONNECTED': -1, 'CLOSED': 0}
threads = [None]
connected_clients = []

# pgrc-prod variables
NAMESPACE_PGRC = "/pgrc"
ROOM_PGRC_PROD = "PGRC-PROD"

# Events
CONNECT_EVENT = "cpgrc event"
BROADCAST_EVENT = "bpgrc event"
ROOM_EVENT = "rpgrc event"

# Requests
JOIN_REQUEST = "join room"
LEAVE_REQUEST = "leave room"
CLOSE_ROOM_REQUEST = "close room"
DISCONNECT_REQUEST = "disconnect request"

DISCONNECT_SERVER = "disconnect"
CONNECT_SERVER = "connect"

# Production Module
# PROD_CONNECT = "prod connect"
PROD_EVENT = "prod event"
PROD_RESPONSE = "prod response"

# PGRC_SEND_PROD_RESPONSE = "pgrc response"

#message format: JobOrder Number-Material Number-Process Code-Process Status
#example: JO001-M001-ST-01
JOB_ORDER_MATERIAL_EVENT = "jobOrderMaterialEvent"

#message format: JobOrder Number-Process Code-Process Status
#example: JO001-ST-01
JOB_ORDER_EVENT = "jobOrderEvent"

#message format: {emp_id: 1, first_name: 'Arnold', last_name: 'Veliganio', process_code: 'DI'}
EMPLOYEE_ASSIGNMENT_EVENT = "employeeAssignmentEvent"

EVENT_TYPE = {'DISASSEMBLE_JO': 0, 'ASSEMBLE_JO': 1, 'EMPLOYEE_ASSIGNMENT': 2}

# Responses
SERVER_GEN_RESPONSE = "server response"

PROD_THREAD_INDEX = 0

def show_client_status(status_code, client_id=None):
    global connected_clients
    if status_code == CLIENT_STATUS_CODE['CLOSED']:
        connected_clients = []
    else:
        if status_code == CLIENT_STATUS_CODE['JOINED']:
            connected_clients.append(client_id)
            print("Client joined: ", client_id)
        elif status_code == CLIENT_STATUS_CODE['LEAVED']:
            if client_id in connected_clients:
                connected_clients.remove(client_id)
                print("Client leaved: ", client_id)
        elif status_code == CLIENT_STATUS_CODE['DISCONNECTED']:
            if client_id in connected_clients:
                connected_clients.remove(client_id)
                print('Client disconnected', client_id)

    print("Client count: ", len(connected_clients))
    print("Clients: ", connected_clients)


def add_thread(thread_index):
    global threads
    threads[thread_index] = Thread(target=background_thread)
    threads[thread_index].daemon = True
    threads[thread_index].start()


def background_thread():
    """Example of how to send server generated events to clients."""
    count = 0
    while True:
        time.sleep(10)
        count += 1
        socketio.emit(SERVER_GEN_RESPONSE, {'data': 'Server generated event', 'count': count},
              namespace=NAMESPACE_PGRC)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/prod')
def prod():
    return render_template('prod.html')


@socketio.on(CONNECT_EVENT, namespace=NAMESPACE_PGRC)
def test_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(SERVER_GEN_RESPONSE, {'data': message['data'], 'count': session['receive_count']})


@socketio.on(BROADCAST_EVENT, namespace=NAMESPACE_PGRC)
def test_broadcast_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(SERVER_GEN_RESPONSE, {'data': message['data'], 'count': session['receive_count']}, broadcast=True)


@socketio.on(ROOM_EVENT, namespace=NAMESPACE_PGRC)
def send_room_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    if message['room'] == ROOM_PGRC_PROD:
        if message['event_type'] == EVENT_TYPE['ASSEMBLE_JO']:
            emit(JOB_ORDER_EVENT, {'data': message['data'], 'count': session['receive_count']}, room=message['room'])
        elif message['event_type'] == EVENT_TYPE['DISASSEMBLE_JO']:
            emit(JOB_ORDER_MATERIAL_EVENT, {'data': message['data'], 'count': session['receive_count']}, room=message['room'])
        elif message['event_type'] == EVENT_TYPE['EMPLOYEE_ASSIGNMENT']:
            emit(EMPLOYEE_ASSIGNMENT_EVENT, {'data': message['data'], 'count': session['receive_count']}, room=message['room'])
    else:
        emit(SERVER_GEN_RESPONSE, {'data': message['data'], 'count': session['receive_count']}, room=message['room'])


@socketio.on(JOIN_REQUEST, namespace=NAMESPACE_PGRC)
def join(message):
    join_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(SERVER_GEN_RESPONSE, {'data': 'In rooms: ' + ', '.join(rooms()), 'count': session['receive_count']})
    if message['room'] == ROOM_PGRC_PROD:
        emit(PROD_RESPONSE, {'data': 'In rooms: ' + ', '.join(rooms()), 'count': session['receive_count']})
        show_client_status(CLIENT_STATUS_CODE['JOINED'], request.sid)


@socketio.on(LEAVE_REQUEST, namespace=NAMESPACE_PGRC)
def leave(message):
    leave_room(message['room'])
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(SERVER_GEN_RESPONSE, {'data': 'In rooms: ' + ', '.join(rooms()), 'count': session['receive_count']})
    if message['room'] == ROOM_PGRC_PROD:
        show_client_status(CLIENT_STATUS_CODE['LEAVED'], request.sid)


@socketio.on(CLOSE_ROOM_REQUEST, namespace=NAMESPACE_PGRC)
def close(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(SERVER_GEN_RESPONSE, {'data': 'Room ' + message['room'] + ' is closing.', 'count': session['receive_count']},
        room=message['room'])
    close_room(message['room'])
    if message['room'] == ROOM_PGRC_PROD:
        show_client_status(CLIENT_STATUS_CODE['CLOSED'])


@socketio.on(DISCONNECT_REQUEST, namespace=NAMESPACE_PGRC)
def disconnect_request():
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(SERVER_GEN_RESPONSE, {'data': 'Disconnected!', 'count': session['receive_count']})
    disconnect()


@socketio.on(DISCONNECT_SERVER, namespace=NAMESPACE_PGRC)
def test_disconnect():
    show_client_status(CLIENT_STATUS_CODE['DISCONNECTED'], request.sid)


@socketio.on(CONNECT_SERVER, namespace=NAMESPACE_PGRC)
def test_connect():
    emit(SERVER_GEN_RESPONSE, {'data': 'Connected', 'count': 0})


@socketio.on(PROD_EVENT, namespace=NAMESPACE_PGRC)
def prod_event_message(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit(PROD_RESPONSE, {'data': message['data'], 'count': session['receive_count']})


if __name__ == '__main__':
    app.logger.info('App is being running from command line.....')

    # add_thread(PROD_THREAD_INDEX)

    port = int(os.environ.get("PORT", APP_PORT))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)