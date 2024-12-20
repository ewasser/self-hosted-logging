import datetime

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired

from project.server.models import User, MyUser
from project.server.crypt import bcrypt
from project.server.database import db

user_blueprint = Blueprint(
    'user',
    __name__,
    template_folder='templates',
    static_folder='static'
)


@user_blueprint.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect('/')


@user_blueprint.route('/dashboard')
@login_required
def dashboard():
    p = {
        'head': {
            'title': 'Dashboard',
        },
        'body': {
            'strftime': datetime.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S"),
        },
        'current_user': current_user,
    }
    return render_template('dashboard.jinja2', **p)


class MyForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])


@user_blueprint.route('/login', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:
        return redirect(url_for('user.dashboard'))

    form = MyForm()

    p = {
        'head': {
            'title': 'Login',
        },
        'body': {
            'title': 'Login',
        },
        'form': form,
    }

    if form.validate_on_submit():

        user_in_database = db.session.query(User).filter_by(email=request.form['username']).first()

        if user_in_database and \
                (bcrypt.check_password_hash(user_in_database.password, request.form['password'])):

            flash("You are logged in", "info")

            user = MyUser(user_in_database)

            login_user(user)

            return redirect(url_for('user.dashboard'))
        else:
            flash("Unknown email/password combination", "error")

    return render_template('login.jinja2', **p)


@user_blueprint.route('/status', methods=['GET'])
def status():
    user = {
        'authenticated': current_user.is_authenticated,
        'active': current_user.is_active,
        'anonymous': current_user.is_anonymous,
        'id': current_user.get_id(),
    }

    current_app.logger.debug(user)

    return jsonify({'user': user})
