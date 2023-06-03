# Config file (surprise!)


class Config(object):
    # SERVER_NAME = 'cphgoldendays.org'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Suppresses a warning by SQLAlchemy about a feature we don't use
    SECRET_KEY = 'hemmelighed'
    SECURITY_PASSWORD_SALT = '7b20351572a263c9b9a7ada81b59d6ace3933d6d54e25a122170d1a6f77ab98ac36763da3365e4bee9b8146f1519508680d7'
    PINNED_COUNTRIES = ['DK', 'NO', 'SE', 'FI']  # Countries pinned to the top of the dropdown in the registration form
    NORDIC_COUNTRIES = ['DK', 'NO', 'SE', 'FI', 'GL', 'IS', 'FO', 'EE', 'LV', 'LT']  # The last three are Baltic countries, also included as per the Area
    PAYPAL_MODE = 'live'
    PAYPAL_CLIENT_ID = 'AYKS5Mj6J5ybUKKvsNqumFjQYyD5lOxh0YcMLM8-RFiYFpaeO0A_lW2-Zc7XNIBouSNA3eCaUTo3s2of'
    PAYPAL_SECRET = 'EF5CTLzG_WgWA5VQS7rbFfX_4yYQEMnMXMjhAdJX-rhlpADcY4ZUsRGnJpDvkk91Y0wgiJdr6JMLlREB'
    IPN_URL = 'https://ipnpb.paypal.com/cgi-bin/webscr'
    PAYPAL_EMAIL = 'kbh.stav.1974@gmail.com'

    # Mail
    ADMINS = ['4trif4@gmail.com'] # For error mails
    MAIL_SERVER = 'smtp.mailgun.org'
    MAIL_PORT = '587'
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'postmaster@cphgoldendays.org'
    MAIL_PASSWORD = '10453295604f6fefb396fecd09b53326'
    MAIL_DEFAULT_SENDER = ('Golden Days', 'contact@cphgoldendays.org')
    ERROR_MAIL_SENDER = 'server-error@cphgoldendays.org'


class SandboxConfig(Config):
    PAYPAL_MODE = 'sandbox'
    PAYPAL_CLIENT_ID = 'AdMeMEwvopSvAF5gXjInoUXuRQNW2G7GVb7g3G-i5KaO87TTHiB6gGFsyU2wjQG06I0aiWwmmIHnNHpH'
    PAYPAL_SECRET = 'ENAC_6Za0aTqPJ5SIX0yfXeXVD4Q68KNWP8FB44Rsi4FYn78ULvPFkpH6WnGBlJDb2UBzJCrnJFyDIBL'
    PAYPAL_EMAIL = 'sb-kpxyq15344319@business.example.com'
    IPN_URL = 'https://ipnpb.sandbox.paypal.com/cgi-bin/webscr'


class DebugConfig(SandboxConfig):
    pass
