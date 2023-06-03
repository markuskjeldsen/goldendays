# Flask-Security module. We really only use this for secure logins and role
# management.

from flask_security import Security, SQLAlchemyUserDatastore
from db import db, Role, User

user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security()
