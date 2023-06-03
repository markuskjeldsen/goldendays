import datetime

from flask import Blueprint, request
import pycountry
import werkzeug.datastructures

from config import Config


# Using this as a blueprint allows us to pass functions to templates through
# a context processor.
utilities = Blueprint('utilities', __name__)


datetime_now = datetime.datetime.now()


def country_name(alpha_2):
    country = pycountry.countries.get(alpha_2=alpha_2)
    return country.name


def country_sort_key(key):
    """ To pin select countries at the top of the dropdown, this sorting key
    replaces the input key (a country code) with a number if the code matches
    a country from the list.
    """
    code, name = key
    countries = Config.PINNED_COUNTRIES
    if code in countries:
        return str(countries.index(code))
    else:
        return name


def ordered_storage(f):
    """ From http://flask.pocoo.org/snippets/112/. Necessary because PayPal IPN
    parameters must be returned in the same order they were received.
    """
    def decorator(*args, **kwargs):
        request.parameter_storage_class = werkzeug.datastructures.ImmutableOrderedMultiDict
        return f(*args, **kwargs)
    return decorator


@utilities.app_context_processor
def utility_processor():
    """ Utilities made available to templates. """
    return dict(
        country_name=country_name,
        datetime_now=datetime_now
    )
