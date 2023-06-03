import datetime
from sqlite3 import Connection as SQLite3Connection

from flask_security import RoleMixin, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, orm
from sqlalchemy.engine import Engine
from sqlalchemy_continuum import make_versioned
from sqlalchemy_continuum.plugins import FlaskPlugin

from config import Config

db = SQLAlchemy()

# Enable foreign keys in SQLite
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

# Enable SQLAlchemy-Continuum
make_versioned(plugins=[FlaskPlugin()])

# We explicitly declare primary keys to prevent a unique constraint problem
# in SQLAlchemy-Continuum.
roles_users = db.Table('roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)


class Role(db.Model, RoleMixin):
    # Flask-Security roles
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, nullable=False)
    # Flask-Security requires us to call this field email, but as we don't
    # really need email functionality, we'll just store usernames in the field.
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    roles = db.relationship('Role', secondary=roles_users,
                            backref=db.backref('users', lazy='dynamic'))


class Participant(db.Model):
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    given_name = db.Column(db.String(30), nullable=False)
    surname = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    country = db.Column(db.String(2), nullable=False)
    stake = db.Column(db.String(25), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gluten_intolerant = db.Column(db.Boolean, nullable=False, server_default='False')
    lactose_intolerant = db.Column(db.Boolean, nullable=False, server_default='False')
    vegetarian = db.Column(db.Boolean, nullable=False, server_default='False')
    other_needs = db.Column(db.String(1000))
    payment_transaction_id = db.Column(db.String(25))
    payment_date = db.Column(db.DateTime)
    has_paid = db.Column(db.Boolean, default=False, nullable=False)


class Stake(db.Model):
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25), nullable=False)


class Configuration(db.Model):
    """ Site configuration. They need to be changed from the admin panel, so
    we'll store them here and just use the first row.
    """
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    # Time zone doesn't matter. It's hardcoded when needed.
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    logo_filename = db.Column(db.String(100), nullable=False)
    facebook_url = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    nordic_participant_limit = db.Column(db.Integer)
    international_participant_limit = db.Column(db.Integer)
    home_title = db.Column(db.String(100), nullable=False)
    home_text = db.Column(db.Text)
    registration_introduction = db.Column(db.Text)
    registration_paypal_instructions = db.Column(db.Text)
    code_of_conduct = db.Column(db.Text)
    confirm_payment_title = db.Column(db.String(100))
    confirm_payment_instructions = db.Column(db.Text)
    registration_success_title = db.Column(db.String(100))
    registration_success_instructions = db.Column(db.Text)
    location_text = db.Column(db.Text)
    google_maps_embed_link = db.Column(db.String(500))

    def nordic_spots_left(self):
        if not self.nordic_participant_limit:
            return True

        return self.nordic_participant_limit - len(
            Participant.query.filter_by(has_paid=True).filter(Participant.country.in_(Config.NORDIC_COUNTRIES)).all())

    def international_spots_left(self):
        if not self.international_participant_limit:
            return True

        return self.international_participant_limit - len(
            Participant.query.filter_by(has_paid=True).filter(~Participant.country.in_(Config.NORDIC_COUNTRIES)).all())

    def participant_limit_reached(self):
        return not self.nordic_spots_left() and not self.international_spots_left()

    def event_finished(self):
        """ Returns True if it's past the end datetime. """
        return datetime.datetime.now() > self.end_datetime


class Teaser(db.Model):
    """ Little content teasers at the bottom of the home page. """
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    text = db.Column(db.Text, nullable=False)


class FAQ(db.Model):
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)


class ProgramItem(db.Model):
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.Integer, nullable=False) # 1, 2, or 3
    position = db.Column(db.Integer, nullable=False)
    time = db.Column(db.String(20))
    text = db.Column(db.String(500))
    information_item_id = db.Column(db.Integer, db.ForeignKey('information_item.id'))


class InformationItem(db.Model):
    __versioned__ = {}
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(500), nullable=False)
    text = db.Column(db.Text, nullable=False)
    program_items = db.relationship('ProgramItem',
        backref='information_item', lazy='dynamic')

    def __repr__(self):
        return self.title


# This is necessary for Flask-Migrate to recognise version tables.
# (See https://github.com/kvesteri/sqlalchemy-continuum/issues/128)
orm.configure_mappers()
