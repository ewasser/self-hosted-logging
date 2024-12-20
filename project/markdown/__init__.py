
import urllib.parse
from flask import jsonify

from flask import Blueprint, render_template, abort, request, flash
from flask import current_app as app
from flask_login import login_required, current_user

from flask_wtf import FlaskForm
from wtforms import TextAreaField
from wtforms.validators import DataRequired

from pathlib import Path

import fs
import fs.errors

import markdown2

markdown_blueprint = Blueprint(
    'markdown',
    __name__,
    template_folder='templates',
    static_folder='static'
)


def get_storage(name):

    for s in app.config['STORAGES']:
        if s['name'] == name:
            return s

    abort(404)


class MyForm(FlaskForm):
    markdown = TextAreaField('Markdown', validators=[DataRequired()])


@markdown_blueprint.route('/edit/<name>/<path:path>', methods=['GET', 'POST'])
@login_required
def edit(name, path):

    name = urllib.parse.unquote(name)

    app.logger.info("name = '{}', path = '{}'".format(name, path))

    title = '{}:{}'.format(name, path)

    entries = []

    storage = get_storage(name)

    markdown_content = ''

    try:
        filesystem = fs.open_fs(storage['filesystem_url'])

        with filesystem.open(path) as markdown_file:
            markdown_content = markdown_file.read()

    except fs.errors.ResourceNotFound:
        abort(503)

    pre_filled_values = {
        'markdown': markdown_content,
    }

    form = MyForm(data=pre_filled_values)

    p = {
        'head': {
            'title': title,
        },
        'body': {
            'title': title,
            'name': Path(name).name,
            'full_filename': title,
        },
        'current_user': current_user,
        'form': form,
    }

    if form.validate_on_submit():
        app.logger.debug("!")
        flash("Klatscher!", "error")


        try:
            filesystem = fs.open_fs(storage['filesystem_url'])

            with filesystem.open(path, "w+", encoding='utf8') as markdown_file:
                markdown_file.write(request.form.get('markdown'))

        except fs.errors.ResourceNotFound:
            abort(503)


    return render_template('markdown_edit.jinja2', **p)


@markdown_blueprint.route('/render', methods=['POST'])
def summary():

    content = request.get_json()

    d = {
        'markdown': {
            'content': markdown2.markdown(content['markdown']['text']),
        }
    }
    return jsonify(d)
