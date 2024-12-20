import datetime
import json
import re
import uuid
import logging
from http import HTTPStatus

from flask import Blueprint
# from flask import Blueprint, current_app, jsonify, flash, redirect
from flask import request, abort
from flask_login import login_required
from flask_restful import Resource, url_for
from marshmallow import Schema, fields, ValidationError, validate

from project.server.database import db
from project.server.models import Order, Worker

logger = logging.getLogger()

v1_order_blueprint = Blueprint(
    'v1_gallery',
    __name__,
)


def get_order_by_id_or_uuid(order_id, search_by_id=False, search_by_uuid=False):
    sql_order = db.session.query(Order)

    sql_order_got_a_where_clause = False
    if search_by_id:
        m = re.search(r'^(\d+)$', order_id)
        if m:
            sql_order = sql_order.where(Order.id == int(m.group(1)))
            sql_order_got_a_where_clause = True

    if not sql_order_got_a_where_clause and search_by_uuid:
        sql_order = sql_order.where(Order.uuid == order_id)
        sql_order_got_a_where_clause = True

    if not sql_order_got_a_where_clause:
        abort(HTTPStatus.NOT_FOUND)

    order = sql_order.one_or_none()

    if order is None:
        abort(HTTPStatus.NOT_FOUND)

    return order


class REST_Order_GET(Resource):
    def get(self, order_id):
        order = get_order_by_id_or_uuid(order_id, search_by_id=True, search_by_uuid=True)

        worker = db.session.query(Worker).where(Worker.order_id == order.id). \
            order_by(Worker.start_time.desc()).limit(1).one_or_none()

        order_as_json = order.as_json()

        order_as_json['worker'] = None

        if worker:
            order_as_json['worker'] = worker.as_json()

        return {
            'order': order_as_json
        }


class SchemaOrdersPost(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1))
    channel = fields.Str(required=True, validate=validate.Length(min=1))
    payload = fields.Dict(required=True)


class REST_Order_POST(Resource):
    @login_required
    def post(self):

        content = request.get_json()

        try:
            order_data: SchemaOrdersPost = SchemaOrdersPost().load(content)
        except ValidationError as err:
            # return str(err), 403
            return {
                'status': 'ERROR',
                'messages': err.messages,
            }, HTTPStatus.BAD_REQUEST

        registered_on = datetime.datetime.now()
        order_uuid = uuid.uuid4()

        order = Order(
            registered_on=registered_on,
            title=order_data['title'],
            channel=order_data['channel'],
            payload=json.dumps(order_data['payload']),
            status='new',
            uuid=str(order_uuid),
        )
        db.session.add(order)

        db.session.commit()
        return {
            'status': 'OK',
            'order': {
                'id': order.id,
                'registered_on': registered_on.timestamp(),
                'title': order_data['title'],
                'channel': order_data['channel'],
                'payload': order_data['payload'],
                'status': order.status,
                'uuid': str(order_uuid),
            },
            'meta': {
                'link': url_for('rest_order_get', order_id=order.id),
            }
        }, HTTPStatus.CREATED


class SchemaOrdersGet(Schema):
    status = fields.Str(load_default='new', validate=validate.OneOf(['all', 'working', 'finished', 'error', 'new']))


class REST_Orders_GET(Resource):
    @login_required
    def get(self):
        try:
            result = SchemaOrdersGet().load(request.args)
        except ValidationError as err:
            return {
                'status': 'ERROR',
                'messages': err.messages,
            }, HTTPStatus.BAD_REQUEST

        orders = []

        sql_order = db.session.query(Order)

        if result['status'] != 'all':
            sql_order = sql_order.where(Order.status == result['status'])

        sql_order = sql_order.order_by(Order.registered_on.desc())

        for o in sql_order.all():
            orders.append(o.as_json())

        return {
            'orders': orders,
            'meta': {},
        }


class SchemaOrderWorkerServer(Schema):
    channel = fields.Str(required=True, validate=validate.Length(min=1))
    name = fields.Str(required=True, validate=validate.Length(min=1))


class REST_Order_Worker_Reserve(Resource):

    def post(self):
        #   {
        #       'channel': 'foo/bar',
        #       'name': 'foobar',
        #   }
        #

        content = request.get_json()

        try:
            reserve_data: SchemaOrderWorkerServer = SchemaOrderWorkerServer().load(content)
        except ValidationError as err:
            # return str(err), 403
            return {
                'status': 'ERROR',
                'messages': err.messages,
            }, HTTPStatus.BAD_REQUEST

        order = db.session.query(Order). \
            with_for_update(read=True, of=Order). \
            where(Order.channel == reserve_data['channel'], Order.status == 'new'). \
            order_by(Order.registered_on.asc()). \
            limit(1). \
            one_or_none()

        if not order:
            return {
                'status': 'ERROR',
                'message': 'No entry found'
            }, HTTPStatus.NOT_FOUND

        worker = db.session.query(Worker). \
            with_for_update(read=True, of=Worker). \
            where(Worker.order_id == order.id). \
            order_by(Worker.start_time.desc()). \
            limit(1). \
            one_or_none()

        if not (order.status == 'new' or (worker is None) or (worker is not None and worker.status == 'error')):
            return {
                'status': 'ERROR',
                'message': 'Order/Worker is not in the right combination'
            }, HTTPStatus.BAD_REQUEST

        registered_on = datetime.datetime.now()
        new_worker_uuid = uuid.uuid4()

        order.status = 'working'
        if order.start_time:
            order.start_time = registered_on

        new_worker = Worker(
            # id = db.Column(db.Integer, primary_key=True, autoincrement=True)
            order_id=order.id,
            start_time=registered_on,

            finish_time=None,
            uuid=str(new_worker_uuid),
            name=content['name'],

            ip=request.remote_addr,

            output=None,
            exit_code=None,
        )

        db.session.add(order)
        db.session.add(new_worker)

        db.session.add(order.log('info', 'test'))

        db.session.commit()

        reservation = {
            'payload': json.loads(order.payload),
            'uuid:': str(new_worker_uuid),
            'callback_url': url_for('rest_result', _external=True, result_uuid=str(new_worker_uuid))
        }
        return {
            'status': 'OK',
            'reservation': reservation,
        }, HTTPStatus.CREATED
