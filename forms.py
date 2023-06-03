from flask_wtf import FlaskForm

from wtforms import BooleanField, HiddenField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NoneOf


class RegistrationForm(FlaskForm):
    given_name = StringField('Given name', validators=[DataRequired(), Length(max=30)])
    surname = StringField('Surname', validators=[DataRequired(), Length(max=30)])
    email = StringField('Email address', validators=[Email()])
    country = SelectField('Country', validators=[NoneOf(['0', '1'], message='Please select your country.')]) # 0 and 1 are given to blank and ------- choices.
    stake = SelectField('Stake/District', coerce=int, validators=[NoneOf([0], message='Please select your stake/district.')])
    age = SelectField('Age', coerce=int, validators=[NoneOf([0], message='Please select your age.')])
    gluten_intolerant = BooleanField('Gluten intolerant')
    lactose_intolerant = BooleanField('Lactose intolerant')
    vegetarian = BooleanField('Vegetarian')
    other_needs = TextAreaField('Other needs', validators=[Length(max=1000)])
    accept_code_of_conduct = BooleanField('I have read and accept the Code of Conduct', validators=[DataRequired(message='You must accept the Code of Conduct to participate in Golden Days.')])


class ConfirmForm(FlaskForm):
    payment_id = HiddenField('Payment ID', validators=[DataRequired()])
    payer_id = HiddenField('Payer ID', validators=[DataRequired()])


class CustomEmailForm(FlaskForm):
    recipient_email = StringField('To', validators=[Email()])
    subject = StringField('Subject')
    body = TextAreaField('Message')
    send_to_self = BooleanField('Send a blind copy to ourselves', default=True)
