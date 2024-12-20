import datetime
import json

from flask import Blueprint, current_app, flash, redirect, jsonify, abort
from flask import url_for, render_template, request
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, TextAreaField, Field, SubmitField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextInput

from project.server.database import db
from project.server.models import Order, OrderLog, Worker

order_blueprint = Blueprint(
    'order',
    __name__,
    template_folder='templates',
    static_folder='static'
)


def order_title(verb, order):
    return "{} Order #{} 🐍: {}".format(verb, order.id, order.title)


class Length:
    def __init__(self, message=None):
        self.message = message

        if not self.message:
            self.message = 'Field must be valid JSON'

    def __call__(self, form, field):
        try:
            json.loads(field.data)
        except json.decoder.JSONDecodeError:
            raise ValidationError("Your JSON isn't valid.")


class TagListField(Field):
    widget = TextInput()

    def _value(self):
        if self.data:
            return self.data.strftime("%Y-%m-%d %H:%M:%S")

        return ''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = datetime.datetime.strptime(valuelist[0], "%Y-%m-%d %H:%M:%S")
        else:
            self.data = None


class MyForm(FlaskForm):
    id = IntegerField('ID', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    status = StringField('Status', validators=[DataRequired()])
    channel = StringField('Channel', validators=[DataRequired()])
    registered_on = TagListField('registered_on', validators=[DataRequired()])
    payload = TextAreaField('payload', validators=[Length()])

    submit = SubmitField('Submit')
    cancel = SubmitField('Cancel')


@order_blueprint.route('/edit/<int:order_id>', methods=['GET', 'POST'])
@login_required
def edit(order_id):
    order = db.session.query(Order).where(Order.id == order_id).first()
    form = MyForm(obj=order)

    if form.cancel.data:
        return redirect(url_for('order.dashboard'))

    if form.validate_on_submit():
        form.populate_obj(order)

        db.session.add(order)
        db.session.commit()

        flash('Your entry was saved', 'success')

        return redirect(url_for('order.dashboard'))

    p = {
        'head': {
            'title': order_title('Edit', order),
        },
        'page': {
            'title': order_title('Edit', order),
        },
        'form': form,
        'current_user': current_user,
        'order': order,
    }

    return render_template('order-edit.jinja2', **p)


@order_blueprint.route('/view/<int:order_id>/worker', methods=['GET'], defaults={'worker_id': -1})
@order_blueprint.route('/view/<int:order_id>/worker/<int:worker_id>', methods=['GET'])
@login_required
def view_worker(order_id, worker_id):
    order = db.session.query(Order).where(Order.id == order_id).first()
    if not order:
        abort(404)

    worker = order.worker

    all_order_ids = list(map(lambda x: x.id, db.session.query(Worker).where(Worker.order_id == order.id).
                             order_by(Worker.id.desc()).
                             all()))
    if len(all_order_ids) == 0:
        abort(404)

    current_app.logger.debug(all_order_ids)

    if worker_id == -1:
        worker_index = 0
    else:
        try:
            worker_index = all_order_ids.index(worker_id)
        except ValueError:
            abort(404)

    if worker_index == 0:
        prev_page = {
            'url': '',
        }
        next_page = {
            'url': url_for('.view_worker', order_id=order_id, worker_id=all_order_ids[worker_index + 1]),
        }
    elif worker_index == len(all_order_ids) - 1:
        prev_page = {
            'url': url_for('.view_worker', order_id=order_id, worker_id=all_order_ids[worker_index - 1]),
        }
        next_page = {
            'url': '',
        }
    else:
        prev_page = {
            'url': url_for('.view_worker', order_id=order_id, worker_id=all_order_ids[worker_index - 1]),
        }
        next_page = {
            'url': url_for('.view_worker', order_id=order_id, worker_id=all_order_ids[worker_index + 1]),
        }

    p = {
        'page': {
            'prev': prev_page,
            'next': next_page,
            'current': worker_index+1,
            'count': len(all_order_ids),
        },
        'worker': worker[worker_index],
    }

    current_app.logger.debug('worker[{}]: {!s}'.format(worker_index, worker[worker_index]))

    return jsonify(
        worker={
            'html': render_template('order-view-worker.jinja2', **p),
        }
    )


@order_blueprint.route('/view/<int:order_id>', methods=['GET', 'POST'])
@login_required
def view(order_id):
    order = db.session.query(Order).where(Order.id == order_id).first()

    #   See https://bulma.io/documentation/elements/icon/ for
    #   more details.

    #   Loglevel  BULMA
    #                             Text                          Icon
    #   ##################################################################################
    #   DEBUG     Success         fas fa-bug                    icon has-text-info
    #   INFO      Info            fas fa-check-square           icon has-text-success
    #   WARNING   Warning         fas fa-info-circle            icon has-text-warning
    #   ERROR     Danger          fas fa-exclamation-triangle   icon has-text-danger
    #   CRITICAL                  fas fa-bolt                   icon has-text-danger-dark

    #   2005-03-19 15:10:26,618 - simple_example - DEBUG - debug message
    #   2005-03-19 15:10:26,620 - simple_example - INFO - info message
    #   2005-03-19 15:10:26,695 - simple_example - WARNING - warn message
    #   2005-03-19 15:10:26,697 - simple_example - ERROR - error message
    #   2005-03-19 15:10:26,773 - simple_example - CRITICAL - critical message

    aaaa = {
        'debug': {
            'icon': 'icon has-text-info',
            'text': 'fas fa-bug',
        },
        'info': {
            'icon': 'icon has-text-success',
            'text': 'fas fa-check-square',
        },
        'warning': {
            'icon': 'icon has-text-warning',
            'text': 'fas fa-info-circle',
        },
        'error': {
            'icon': 'icon has-text-danger',
            'text': 'fas fa-exclamation-triangle',
        },
        'critical': {
            'icon': 'icon has-text-danger-dark',
            'text': 'fas fa-bolt',
        },
    }

    order_log_lines_objects = db.session.query(OrderLog).where(OrderLog.order_id == order_id). \
        order_by(OrderLog.registered_on.asc()).all()

    order_log_lines = []

    for order_log_line in order_log_lines_objects:
        order_log_lines.append({
            'id': order_log_line.id,
            'registered_on': order_log_line.registered_on,
            'order_id': order_log_line.order_id,
            'category': order_log_line.category,
            'line': order_log_line.line,
            'icon': aaaa[order_log_line.category]['icon'],
            'text': aaaa[order_log_line.category]['text']
        })

    current_app.logger.debug(order_log_lines)

    p = {
        'head': {
            'title': order_title('View', order),
        },
        'page': {
            'title': order_title('View', order),
        },
        'order': order,
        'order_log_lines': order_log_lines,
        'current_user': current_user,
        'GLOBALS': {
            'worker_url': url_for('.view', order_id=order_id) + '/worker',
        }
    }
    return render_template('order-view.jinja2', **p)


@order_blueprint.route('/delete/<int:order_id>', methods=['GET', 'POST'])
@login_required
def delete(order_id):
    order = db.session.query(Order).where(Order.id == order_id).first()

    if request.args.get('confirm') == 'yes':
        db.session.delete(order)
        db.session.commit()

        flash("Your order '{}' was deleted.".format(order_title(order)), 'success')

        return redirect(url_for('order.dashboard'))

    title = order_title('Delete', order)

    p = {
        'head': {
            'title': title,
        },
        'page': {
            'title': title,
        },
        'order': order,
        'current_user': current_user,
        'rows': [],
    }

    return render_template('order-delete.jinja2', **p)


@order_blueprint.route('/dashboard')
@login_required
def dashboard():
    with db.engine.connect() as con:
        objects_rows = db.session.query(Order). \
            order_by(Order.id.desc()).all()

    jinja2_rows = []

    for row in objects_rows:
        status = {
            'new': {
                'level': 'has-text-black',
                'icon': 'fas fa-info-circle',
            },
            'working': {
                'level': 'has-text-info',
                'icon': 'fas fa-paperclip',
            },
            'error': {
                'level': 'has-text-danger',
                'icon': 'fas fa-ban',
            },
            'finished': {
                'level': 'has-text-success',
                'icon': 'fas fa-check-square',
            },
        }

        jinja2_rows.append({
            'id': row.id,
            'mtime': row.registered_on.strftime("%Y-%m-%d %H:%M:%S"),
            'title': row.title,
            'channel': row.channel,
            'payload': json.dumps(json.loads(row.payload), indent=4, sort_keys=True),
            'status': {
                'text': row.status,
                'level': status[row.status]['level'],
                'icon': status[row.status]['icon'],
            },
        })

    title = 'Order Overview'

    p = {
        'head': {
            'title': title,
        },
        'page': {
            'title': title + ' 🐍',
        },
        'current_user': current_user,
        'rows': jinja2_rows,
    }

    return render_template('order-dashboard.jinja2', **p)
