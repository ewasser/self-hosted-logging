from flask import Blueprint

diary_blueprint = Blueprint(
    'diary',
    __name__,
    template_folder='templates',
    static_folder='static'
)

from . import views

