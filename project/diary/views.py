import io
import json
import logging
from pathlib import Path

from flask import render_template, url_for, request, redirect
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import TextAreaField
from wtforms.validators import DataRequired

from . import diary_blueprint
from ..server.models import Diary

logger = logging.getLogger()


@diary_blueprint.route('/show')
@login_required
def show():
    path_extender = request.args.get("path", default=None, type=str)

    diary = Diary(path_extender=path_extender)

    cards = []

    p = {
        'head': {
            'title': 'Tagebuch - Eintrag {!s}'.format(path_extender),
        },
        'page': {
            'title': 'Tagebuch - Eintrag {!s} 🐍'.format(path_extender),
        },
    }

    return render_template('diary-show.jinja2', **p)



@diary_blueprint.route('/dashboard')
@login_required
def dashboard():
    path_extender = request.args.get("path", default=".", type=str)

    highlight = request.args.get("highlight", default=None, type=str)

    if highlight is not None:
        highlight = Path(highlight)

    diary = Diary(path_extender=path_extender)

    cards = []

    for card in diary.collection():
        icon = 'folder'
        url = url_for('.dashboard', path=card.path_extender)
        css_class = ''

        logger.debug('{} ↔ {}: {}'.format(
            type(card.path_extender),
            type(highlight), card.path_extender == highlight))

        if card.node == 'file':
            icon = 'file'
            url = url_for('.show', path=card.path_extender)

        if highlight and card.path_extender == highlight:
            css_class = 'has-background-success'

        cards.append({
            'title': card.name,
            'url': url,
            'icon': icon,
            'class': css_class,
        })

    p = {
        'head': {
            'title': 'Tagebuch - ' + str(path_extender),
        },
        'page': {
            'title': 'Tagebuch - ' + str(path_extender) + ' 🐍',
        },
        'json_data': json.dumps({'foobar': 1, 'test': '<&;">'}),
        'cards': rows(4, cards),
    }

    return render_template('diary-dashboard.jinja2', **p)


class MyForm(FlaskForm):
    markdown = TextAreaField('Markdown', validators=[DataRequired()])


@diary_blueprint.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    path_extender = request.args.get("path", default=".", type=str)

    diary = Diary(path_extender=path_extender)

    title = 'Diary of {}'.format(path_extender)

    filename = diary.filename()
    logger.info(filename)

    markdown_content = ''

    if filename.exists() and filename.is_file():
        with io.open(filename) as f:
            markdown_content = f.read()

    logger.info(markdown_content)

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
            'name': Path(filename).name,
            'full_filename': title,
        },
        'page': {
            'title': 'Tagebuch - ' + str(path_extender) + ' 🐍',
        },
        'current_user': current_user,
        'form': form,
    }

    if form.validate_on_submit():

        with io.open(filename, 'w+') as f:
            markdown = request.form.get('markdown')
            markdown = markdown.replace('\r', '')
            f.write(markdown)

        return redirect(url_for('.dashboard', path='2001', highlight=path_extender))

    return render_template('diary-edit.jinja2', **p)
