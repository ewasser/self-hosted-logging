import datetime
import json
import logging
from http import HTTPStatus

from flask import Blueprint
from flask import request
from flask_restful import Resource, url_for
from marshmallow import Schema, fields, ValidationError

from project.server.database import db
from project.server.models import Worker, Archive

logger = logging.getLogger()

v1_order_blueprint = Blueprint(
    'v1_gallery',
    __name__,
)


class SchemaResultResult(Schema):
    exit_code = fields.Integer(required=True, strict=True)
    output = fields.Str(required=True)


class SchemaResultBase(Schema):
    result = fields.Nested(SchemaResultResult)


class REST_Result(Resource):

    def post(self, result_uuid):
        #   {
        #       'exit_code':
        #       'output':
        #   }
        #

        content = request.get_json()

        try:
            result_data: SchemaResultBase = SchemaResultBase().load(content)
        except ValidationError as err:
            return {
                'status': 'ERROR',
                'messages': err.messages,
            }, HTTPStatus.BAD_REQUEST

        worker = db.session.query(Worker).where(Worker.uuid == str(result_uuid)).one_or_none()

        if worker is None:
            return {
                'status': 'ERROR',
                'messages': "I can't find a worker with the given result_uuid"
            }, HTTPStatus.NOT_FOUND

        if worker.finish_time is not None:
            return {
                'status': 'ERROR',
                'messages': "Your worker returned already an result"
            }, HTTPStatus.BAD_REQUEST

        order = worker.order

        order_payload = json.loads(order.payload)

        if worker is None:
            return {
                'status': 'ERROR',
                'messages': "I can't find a order for your order"
            }, HTTPStatus.NOT_FOUND

        registered_on = datetime.datetime.now()

        worker.finish_time = registered_on
        worker.output = result_data['result']['output']
        worker.finish_time = registered_on
        worker.exit_code = result_data['result']['exit_code']

        if worker.exit_code == 0:
            order.finish_time = registered_on

            order.status = 'finished'
        else:
            order.status = 'error'

        db.session.add(order)
        db.session.add(worker)

        archive = db.session.query(Archive).where(
            Archive.source == order_payload['archive']['source'],
            Archive.name == order_payload['archive']['name'],
        ).one_or_none()

        if not archive:
            archive = Archive(
                source=order_payload['archive']['source'],
                name=order_payload['archive']['name'],
            )

            db.session.add(archive)

        db.session.commit()

        return {
            'status': 'OK',
            'meta': {
                'link': url_for('rest_order_get', order_id=order.id),
            }
        }, HTTPStatus.OK

