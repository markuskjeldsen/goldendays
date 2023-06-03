from collections import OrderedDict
import datetime
from functools import wraps
from itertools import chain
import json

import dateutil.parser
from flask import (flash, Flask, jsonify, redirect, render_template, request,
                   url_for, abort)
from flask_admin import Admin, BaseView, expose
from flask_admin.contrib.sqla import ModelView
from flask_mail import Mail, Message
from flask_migrate import Migrate
from flask_misaka import Misaka
from flask_security import current_user
from flask_security.utils import encrypt_password, url_for_security
import paypalrestsdk
import pycountry
import requests
import stripe

stripe.api_key = "sk_test_51N4OVqAZeR2tEfU5emP3XnJErDusheNj4fD06fVWkfxy2d0Q0WbKyB3xgySOOnnRpkgoXku7V633SJbcZM6GbndS00W5dPWAvP"

from assets import assets
# noinspection PyUnresolvedReferences
import config
from db import (Configuration, db, FAQ, InformationItem, Participant,
                ProgramItem, Stake, Teaser, User)
from forms import ConfirmForm, CustomEmailForm, RegistrationForm
from security import security, user_datastore
from utilities import country_name, country_sort_key, ordered_storage, utilities

app = Flask(__name__)
if app.debug:
    app.config.from_object('config.DebugConfig')
else:
    app.config.from_object('config.Config')

admin = Admin(app, name='Golden Admin', template_mode='bootstrap3')
assets.init_app(app)
db.init_app(app)
migrate = Migrate(app, db)
mail = Mail(app)
Misaka(app)
security.init_app(app, datastore=user_datastore)
paypalrestsdk.configure({
    'mode': app.config['PAYPAL_MODE'],
    'client_id': app.config['PAYPAL_CLIENT_ID'],
    'client_secret': app.config['PAYPAL_SECRET']
})

app.register_blueprint(utilities)

if not app.debug:
    import logging
    from logging.handlers import SMTPHandler

    mail_handler = SMTPHandler(
        mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
        fromaddr=app.config['ERROR_MAIL_SENDER'],
        toaddrs=app.config['ADMINS'],
        subject='[Golden Days] Error',
        credentials=(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD']),
        secure=()
    )
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(logging.Formatter('''
    Message type:       %(levelname)s
    Location:           %(pathname)s:%(lineno)d
    Module:             %(module)s
    Function:           %(funcName)s
    Time:               %(asctime)s

    Message:

    %(message)s
    '''))
    app.logger.addHandler(mail_handler)

    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    app.logger.addHandler(file_handler)


def check_date(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        configuration = Configuration.query.get_or_404(1)
        if configuration.event_finished():
            return redirect(url_for('home'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/checkout', methods=['POST'])
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': 'price_1NEBh0AZeR2tEfU5tbNqUJJ2',
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url='http://cphgoldendays.org/success.html',
            cancel_url='http://cphgoldendays.org/cancel.html',
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)


@app.route('/')
def home():
    configuration = Configuration.query.get_or_404(1)
    participant_count = len(Participant.query.filter_by(has_paid=True).all())
    if participant_count > 100 and not configuration.event_finished():
        home_text = '{} {} people have already signed up!'.format(configuration.home_text, participant_count)
    else:
        home_text = configuration.home_text
    teasers = Teaser.query.order_by('position').all()
    return render_template(
        'home.html',
        configuration=configuration,
        home_text=home_text,
        teasers=teasers
    )


@app.route('/register', methods=['GET', 'POST'])
@check_date
def register():
    configuration = Configuration.query.get_or_404(1)
    participants = Participant.query.filter_by(has_paid=True).all()
    for participant in participants:
        participant.country_name = country_name(participant.country)
    faqs = FAQ.query.all()
    form = RegistrationForm()
    form.stake.choices = [(stake.id, stake.name) for stake in
                          Stake.query.all()]
    form.country.choices = sorted([(country.alpha_2, country.name) for country in list(pycountry.countries)],
                                  key=country_sort_key)
    form.age.choices = [(x, x) for x in range(18, 31)]
    form.country.choices.insert(len(app.config['PINNED_COUNTRIES']), ('1', '-------------'))
    form.country.choices.insert(0, ('0', ''))  # Insert blank choice first in select
    form.stake.choices.insert(0, (0, ''))
    form.age.choices.insert(0, (0, ''))
    if form.validate_on_submit():
        app.logger.info('Registration form validated.')
        given_name = form.given_name.data.title()
        surname = form.surname.data.title()
        email = form.email.data
        country = form.country.data
        stake = form.stake.data
        age = form.age.data
        gluten_intolerant = form.gluten_intolerant.data
        lactose_intolerant = form.lactose_intolerant.data
        vegetarian = form.vegetarian.data
        other_needs = form.other_needs.data

        if (not configuration.nordic_spots_left() and country in app.config['NORDIC_COUNTRIES']) or (
                not configuration.international_spots_left() and country not in app.config['NORDIC_COUNTRIES']):
            app.logger.info('No spots left in region; registration aborted.')
            flash("We're sorry, but we have no more spots left in your region. Stay tuned on Facebook for updates.",
                  'danger')
        else:
            participant = Participant(given_name=given_name,
                                      surname=surname,
                                      email=email,
                                      country=country,
                                      stake=stake,
                                      age=age,
                                      gluten_intolerant=gluten_intolerant,
                                      lactose_intolerant=lactose_intolerant,
                                      vegetarian=vegetarian,
                                      other_needs=other_needs
                                      )
            db.session.add(participant)
            db.session.commit()
            app.logger.info('Added participant #{}.'.format(participant.id))
            print('participant added #{}'.format(participant.id))

            try:
                checkout_session = stripe.checkout.Session.create(
                    line_items=[
                        {
                            # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                            'price': 'price_1NEBh0AZeR2tEfU5tbNqUJJ2',
                            'quantity': 1,
                        },
                    ],
                    mode='payment',
                    success_url=url_for('home', _external=True),
                    cancel_url='http://cphgoldendays.org/cancel.html',
                    client_reference_id=participant.id,
                )
            except Exception as e:
                return str(e)

            print('redirecting to payment')
            return redirect(checkout_session.url, code=303)

    #            app.logger.info('Creating payment...')
    #            payment = paypalrestsdk.Payment({
    #                'intent': 'sale',
    #                'payer': {
    #                'payment_method': 'paypal'
    #                },
    #                'redirect_urls': {
    #                    'return_url': url_for('confirm_payment', _external=True),
    #                    'cancel_url': url_for('home', _external=True)
    #                },
    #                'transactions': [{
    #                    'amount': {
    #                        'total': configuration.price,
    #                        'currency': 'DKK'
    #                    },
    #                    'description': 'Golden Days {} admission'.format(configuration.start_datetime.year),
    #                    'custom': participant.id
    #                }]
    #            })
    #
    #            if payment.create():
    #                app.logger.info('Payment created.')
    #                for link in payment.links:
    #                    if link.method == 'REDIRECT':
    #                        redirect_url = str(link.href)
    #                        app.logger.info('Redirecting participant #{} to PayPal...'.format(
    #                            participant.id))
    #                        return redirect(redirect_url) # Redirect to PayPal.
    #            else:
    #                app.logger.error('Failed to create payment for participant #{}.'.format(participant.id))
    #                app.logger.error(payment.error)
    #                flash('Something went wrong—please try again. Contact us at contact@cphgoldendays.org if the problem persists.', 'danger')

    return render_template('register.html', configuration=configuration,
                           faqs=faqs, form=form, participants=participants)


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    print('WEBHOOK CALLED')

    if request.content_length > 1024 * 1024:
        print('REQUEST TOO BIG')
        abort(400)
    payload = request.get_data()
    sig_header = request.environ.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = 'whsec_a00f7d87a1e500543c7d4e7fe3f2fd92ed2a62dfc04f8d281e530ea9186ae959'
    event = None

    # participant = request.environ.get('customer')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        print('INVALID PAYLOAD')
        return {}, 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        print('INVALID SIGNATURE')
        return {}, 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        print(session)
        line_items = stripe.checkout.Session.list_line_items(session['id'], limit=1)
        print(line_items['data'][0]['description'])
        client_id = event["data"].object.client_reference_id
        cs_id = event["data"].object.id

        if event["data"].object.payment_status == 'paid':
            print("writing to database")
            participant = Participant.query.get(int(client_id))
            participant.payment_transaction_id = cs_id
            participant.has_paid = True
            db.session.commit()
        else:
            print("hasnt paid")
            participant = Participant.query.get(int(client_id))
            participant.payment_transaction_id = cs_id
            participant.has_paid = True
            db.session.commit()

        # participant = Participant.query.get(int(participant_id))
        # if participant:
        #    participant.payment_transaction_id = transaction_id
        #    participant.payment_date = payment_date
        #    participant.has_paid = True
        #    db.session.commit()

    return {},


@app.route('/confirm', methods=['GET', 'POST'])
@check_date
def confirm_payment():
    """ Put the query string variables in a form, ask for confirmation,
    execute payment using form variables, redirect.
    """
    configuration = Configuration.query.get_or_404(1)
    form = ConfirmForm()
    if not form.is_submitted():
        payment_id = request.args.get('paymentId')
        payer_id = request.args.get('PayerID')
        form.payment_id.data = payment_id
        form.payer_id.data = payer_id

    if form.validate_on_submit():
        app.logger.info('Confirmation form validated.')
        payment = paypalrestsdk.Payment.find(form.payment_id.data)
        if payment.execute({'payer_id': form.payer_id.data}):
            app.logger.info('Payment #{} executed.'.format(form.payment_id.data))
            return redirect(url_for('registration_success'))
        else:
            app.logger.warning('Payment #{} failed to execute.'.format(form.payment_id.data))
            flash(
                'Sorry, PayPal has rejected your payment. If you accidentally clicked twice, check the participants list in a minute or two—if you\'re on it, no worries! If not, please try again, perhaps with a different account or card. Contact us at contact@cphgoldendays.org if there are any issues.',
                'danger')
            return redirect(url_for('home'))
    elif form.is_submitted():
        app.logger.warning('Confirmation form did not validate.')
        flash(
            'An error occurred during payment. Check the participants list—if you\'re on it, no worries! If not, please try again. Contact us at contact@cphgoldendays.org if there are any issues.',
            'danger')
        return redirect(url_for('home'))
    return render_template('confirm_payment.html', configuration=configuration,
                           form=form)


@app.route('/success')
@check_date
def registration_success():
    configuration = Configuration.query.get_or_404(1)
    return render_template('registration_success.html',
                           configuration=configuration)


@app.route('/information')
@check_date
def information():
    configuration = Configuration.query.get_or_404(1)
    program_items = ProgramItem.query.all()
    for item in program_items:
        # Replace number with string
        item.day = ['Friday', 'Saturday', 'Sunday'][item.day - 1]
    information_items = InformationItem.query.all()
    return render_template('information.html', configuration=configuration,
                           program_items=program_items,
                           information_items=information_items)


@app.route('/location')
@check_date
def location():
    configuration = Configuration.query.get_or_404(1)
    return render_template('location.html', configuration=configuration)


"""
@app.route('/resetdb')
def resetdb():
    import os
    try:
        os.remove('/srv/golden-days/database.db')
    except:
        pass
    init_db()
    return redirect(url_for('home'))
"""


@app.route('/ipn', methods=['POST'])
@ordered_storage
def paypal_ipn_handler():
    app.logger.info('IPN received.')
    params = request.form
    verify_params = OrderedDict(chain(request.form.items(), (('cmd', '_notify-validate'),)))
    app.logger.info('Sending IPN back to PayPal to verify...')
    response = requests.post(app.config['IPN_URL'], data=verify_params)
    status = response.text
    if status == 'VERIFIED':
        app.logger.info('IPN verified.')
        configuration = Configuration.query.get(1)
        payment_status = params.get('payment_status')
        receiver_email = params.get('receiver_email')
        payer_email = request.form.get('payer_email')
        transaction_id = params.get('txn_id')
        payment_date = dateutil.parser.parse(params.get('payment_date'))
        mc_gross = params.get('mc_gross')
        mc_currency = params.get('mc_currency')
        participant_id = params.get('custom')
        if payment_status != 'Completed':
            app.logger.error('IPN: Payment not complete. {}'.format(json.dumps(verify_params)))
        elif receiver_email != app.config['PAYPAL_EMAIL']:
            app.logger.error('IPN: Receiver email did not match. {}'.format(json.dumps(verify_params)))
        elif int(mc_gross.split('.')[0]) != configuration.price or mc_currency != 'DKK':
            # The above trickery ignores the decimal places so we can compare
            # with our price value, which is an integer.
            app.logger.error('IPN: Price or currency did not match. {}'.format(json.dumps(verify_params)))
        elif Participant.query.filter_by(payment_transaction_id=transaction_id).first():
            app.logger.error('IPN: Transaction already handled. {}'.format(json.dumps(verify_params)))
        elif not participant_id:
            app.logger.error('IPN: Custom field (participant id) empty. {}'.format(json.dumps(verify_params)))
        else:
            participant = Participant.query.get(int(participant_id))
            if participant:
                participant.payment_transaction_id = transaction_id
                participant.payment_date = payment_date
                participant.has_paid = True
                db.session.commit()
                app.logger.info('Payment registered for participant #{}.'.format(participant.id))
                confirmation_mail = Message(
                    'Golden Days registration',
                    recipients=[participant.email],
                    body='''Congratulations {} {}, your registration for Golden Days {} has been processed and you\'re ready to go!

Feel free to contact us on Facebook or by replying to this mail. Your transaction ID is {}.
                    '''.format(participant.given_name, participant.surname, configuration.start_datetime.year,
                               transaction_id)
                )
                mail.send(confirmation_mail)
                app.logger.info('Confirmation mail sent to {}.'.format(participant.email))
            else:
                app.logger.error('IPN: Payment validated but participant not found!')
    else:
        app.logger.error('IPN: IPN string did not validate {}'.format(json.dumps(verify_params)))

    app.logger.info('Sending OK to PayPal.')
    return jsonify({'status': 'complete'})


# Admin views
class SecureModelView(ModelView):

    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for_security('login', next=request.url))


class ExportableModelView(SecureModelView):
    can_export = True


class CustomEmailView(BaseView):
    @expose('/', methods=['GET', 'POST'])
    def index(self):
        if not current_user.is_authenticated:
            return redirect(url_for_security('login', next=request.url))

        form = CustomEmailForm()

        if form.validate_on_submit():
            recipient_email = form.recipient_email.data
            subject = form.subject.data
            body = form.body.data
            bcc_list = [app.config['MAIL_DEFAULT_SENDER']] if form.send_to_self.data else None
            message = Message(
                subject,
                recipients=[recipient_email],
                body=body,
                bcc=bcc_list
            )
            mail.send(message)
            app.logger.info('Sent custom mail to {}. Subject: {}'.format(recipient_email, subject))
            flash('Mail sent.', 'success')

        return self.render('custom_email.html', form=form, sender_email=app.config['MAIL_DEFAULT_SENDER'][1])


admin.add_view(CustomEmailView(name='Send email', endpoint='email'))
admin.add_view(SecureModelView(Configuration, db.session))
admin.add_view(ExportableModelView(Participant, db.session))
admin.add_view(SecureModelView(Teaser, db.session))
admin.add_view(SecureModelView(FAQ, db.session))
admin.add_view(SecureModelView(ProgramItem, db.session))
admin.add_view(SecureModelView(InformationItem, db.session))
admin.add_view(SecureModelView(Stake, db.session))
admin.add_view(SecureModelView(User, db.session))


def init_db():
    """ Initialise database (run from a Python shell)
    """
    with app.app_context():
        db.create_all()
        user_datastore.create_role(
            name='admin',
            description='Doesn\'t actually change anything right now.')
        user_datastore.create_user(
            email='christian',
            password=encrypt_password('A5F1E5nGbEjDi1s*tOSxJs2@'),
            roles=['admin']
        )
        user_datastore.create_user(
            email='morten',
            password=encrypt_password('9%jc5I$F5@Lfa1nkMN4VK8q1'),
            roles=['admin']
        )

        stakes = [Stake(name=stake) for stake in
                  ['København', 'Århus', 'Oslo', 'Drammen', 'Göteborg', 'Malmö', 'Stockholm Sweden',
                   'Stockholm Sweden South', 'Umeås District', 'Helsinki', 'Tampere', 'Pietarsaaren', 'Oulun', 'Other']]

        configuration = Configuration(
            start_datetime=datetime.datetime(2017, 9, 15, 18, 0, 0),
            end_datetime=datetime.datetime(2017, 9, 17, 15, 0, 0),
            logo_filename='logo.svg',
            facebook_url='https://www.facebook.com/events/799249226906336',
            google_maps_embed_link='//www.google.com/maps/embed/v1/place?q=S%C3%B8parken+1,+3450+Liller%C3%B8d,%20DK&zoom=7&key=AIzaSyAU-0b7zY9vwc2HttbvlzKM6GbNl-Z8K3Y',
            price=1,
            home_title='Golden Days is back!',
            home_text='Guess what? This text was loaded from a database! Soon enough, you\'ll even be able to edit it!',
            registration_introduction='The admission fee for Golden Days 2017 is 250 DKK. Make sure to read the [Code of Conduct](#code-of-conduct) and the [frequently asked questions](#faq) below, then sign up for a fantastic weekend!',
            registration_paypal_instructions='Once you submit your registration, you\'ll be taken to PayPal to process your payment. You **do not** need to have a PayPal account—a regular credit card will do!',
            code_of_conduct='''I hereby agree to...

* Be good
* Not do stupid stuff
* Actually write a code of conduct

Should you fail to comply, you\'ll be degraded to Silven Days, a second-class convention with no snacks.

Better avoid that.''',
            confirm_payment_title='Confirm payment',
            confirm_payment_instructions='You\'re almost ready to go! A receipt will be sent to the e-mail address you provided to PayPal. You\'ll also receive a confirmation e-mail to let you know that your payment has been successfully processed.',
            registration_success_title='Success!',
            registration_success_instructions='''**Congratulations!** You\'re now registered for Golden Days and will appear on the participant list as soon as your payment has been processed (by the time you finish reading this, it\'s probably already there!).

Remember to keep an eye out for news on the official Facebook event page linked below! Don\'t hesitate to contact us there or at **contact@cphgoldendays.org**. See you at Golden Days!''',
            location_text='''Golden Days 2017 will take place at a cool school in Denmark. I\'m not sure what to say about it, but I\'m sure it\'s great! Here\'s the address:

> Kratbjergskolen, Ravnsholt
> Søparken 1
> 3450 Lillerød

The temple\'s not that far away! Are we supposed to put the temple address here or not? I don\'t know... Anyways, you\'ll get to go—woo!'''
        )

        teaser1 = Teaser(
            position=1,
            title='Denmark\'s coolest convention',
            text='Some introductory text briefly explaining and hyping Golden Days. It\'s cool! I want this text to be a little long so you get the idea of how it\'ll look with a description here. Sorry, I\'m a wanna-be developer, not a writer. Anyways, this should be good enough, I think. [Check the information pages!](/information)'
        )

        teaser2 = Teaser(
            position=2,
            title='At some random school',
            text='Slightly over-the-top description of the location. Did you know? You can get there! Lorem ipsum dolor sit amet blah blah I\'m too lazy to actually go get that text... This is easier! [Here\'s the map (and more information)](/location)!'
        )

        teaser3 = Teaser(
            position=3,
            title='What are you waiting for?',
            text='Registration is open! Repeat, registration is open! All aboard! All aboard! [Click this magical link to register!](/register)'
        )

        faq1 = FAQ(
            position=1,
            question='I don\'t have a PayPal! What do I do?',
            answer='Sorry, it appears that your reading comprehension skills are below the required threshold for participation in this year\'s conference.'
        )

        faq2 = FAQ(
            position=2,
            question='How come you\'re so rude? Isn\'t this a formal site?',
            answer='I\'m just pumping out savage example text. You\'re supposed to change this.'
        )

        faq3 = FAQ(
            position=3,
            question='Why don\'t you just use lorem ipsum?',
            answer='''Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas sed venenatis augue. Praesent eget mollis dolor. Nullam tempor ac turpis vel aliquet. Maecenas lobortis pellentesque metus, vel eleifend nisl pulvinar et. Vestibulum ut consequat libero. Nulla et diam metus. Sed ac arcu ut urna tempus consequat non vitae mi. Nulla pellentesque tempus nunc a consequat.

Sed libero lorem, tempor id felis vel, egestas porta sem. Integer in neque metus. Etiam ut magna iaculis, maximus tortor at, malesuada nunc. Sed eleifend commodo odio blandit condimentum. Morbi a viverra dui. Aliquam vitae varius mi, in feugiat felis. Nulla et volutpat metus. Nulla suscipit laoreet nisl, vitae efficitur libero efficitur in. Etiam risus velit, rutrum ac porta non, pharetra non urna. Phasellus dapibus cursus dictum.

Suspendisse imperdiet ex vel eros fringilla porttitor. Phasellus hendrerit sit amet tortor eget venenatis. Cras ultrices erat non leo maximus accumsan. Mauris in ex sodales sapien congue aliquet. Nullam ac tincidunt purus. Fusce consectetur purus metus, vel laoreet sem dignissim at. Duis condimentum pharetra lorem, laoreet faucibus purus fringilla vel. In sollicitudin quam a ligula fringilla, et viverra orci bibendum. Vivamus ac cursus dui, sed porta odio. In in consequat urna. Sed nisi ante, placerat in massa eu, porttitor viverra dolor. Aenean nec suscipit sem, et ullamcorper quam. Pellentesque elementum risus ac enim porttitor, vel rutrum est scelerisque.

Nulla rutrum, lacus sit amet pharetra varius, arcu enim sodales justo, sagittis vehicula orci sapien ac augue. Duis efficitur tellus a dolor lobortis tempus. Quisque dolor enim, porttitor a euismod vitae, convallis dapibus ipsum. Duis non nulla libero. Nunc dolor justo, consectetur ac est at, imperdiet tristique eros. Ut suscipit, mauris id vehicula rhoncus, ligula leo egestas lectus, at convallis metus nibh at turpis. Aliquam nec lorem nunc. Nullam quis sagittis odio.

Better?'''
        )

        faq4 = FAQ(
            position=4,
            question='I heard something about a Markdown thing...',
            answer='''It\'s time for...

A **magic show!**

Look up! Now look back. My text is in *italics*. Now what was that? Make it bold too? **You got it.**

Hey look, [a link!](https://vignette3.wikia.nocookie.net/zelda/images/3/3c/Link_%28Super_Smash_Bros._Brawl%29.png/revision/latest?cb=20121125020225&format=original)

---

Bullet list!

* Apples!
* Bananas!
* Circuses!

Numbered list!

1. One!
2. Two!
3. Tree-fiddy!

There shouldn't
be a line break here...

There should
be one here!

That's all for today, folks!'''
        )

        info1 = InformationItem(
            position=1,
            title='Flirtimony Dance',
            text='''Tired of testimony meetings turning into mass speed dating
competitions? We\'ve got a new take on the classic problem!

At Golden Days, we believe love and heartfelt declarations of gospel truths do
go hand in hand but simply need the right stage to take place. That\'s why
we\'re having the first ever flirtimony dance—a unique opportunity for you to
bond with people by dancing while crying!

**The rules are simple:** Find a dancing partner and find your groove. All
conversation is to be limited to testimonies. The flirtier, the better!

Tips for improving your flirtimony skills:

* Explain how you served in the toughest mission in the world
* Say that you\'ve been blessed with the gift of spouse-finding
* Quote your favourite Isaiah scriptures
* Include a heroic travel tale from the wilderness
* Sing your favourite Primary song

Come prepared—there\'s a special prize for the charming deliverer of the
longest flirtimony!

*Note: All music will be provided by the Mormon Tabernacle Choir.*''')

        info2 = InformationItem(
            position=2,
            title='Hide and Dance... Dance!',
            text='''There\'s always a boy or five that hide in some back room
chatting about video games, only to be seen as they sweep in for a single potato
chip before shortly vanishing again. If that\'s you, the tables have turned: At
Golden Days 2017, you\'ll have your golden chance to show everyone how asocial
you can be!

Hide and Dance is an award-winning concept developed by some indie startup
you\'ve never heard of. Participants are to hide from the opposite gender as
much as they can, but if they\'re discovered by a Dancer, they must... **dance!**

Incidentally, all girls that scream loudly enough will become Dancers, tasked
with hunting down the introverted victims. Who will be the grand star of the
night? ...We won\'t know, because he won\'t be there.''')

        info3 = InformationItem(
            position=3,
            title='Choose the Wright',
            text='''Are you flying in to Denmark? Don\'t get a return
flight—we\'ll be building our own air planes from local leftover scout scraps!

...Admit it, you feel *slightly* guilty about changing these.

*"Why did you even write them in the first place?!"*

It\'s an easy way to demonstrate
[Markdown](https://en.wikipedia.org/wiki/Markdown)! That\'s why!''')

        info4 = InformationItem(
            position=4,
            title='I want to test scrolling on this page',
            text='''**Palpatine**: Did you ever hear the tragedy of Darth
Plagueis The Wise?

**Anakin**: No?

**Palpatine**: I thought not. It’s not a story the Jedi would tell you. It’s a
Sith legend. Darth Plagueis was a Dark Lord of the Sith, so powerful and so wise
he could use the Force to influence the midichlorians to create life… He had
such a knowledge of the dark side, he could even keep the ones he cared about
from dying.

**Anakin**: He could actually save people from death?

**Palpatine**: The dark side of the Force is a pathway to many abilities some
consider to be unnatural.

**Anakin**: What happened to him?

**Palpatine**: He became so powerful… the only thing he was afraid of was losing
his power, which eventually, of course, he did. Unfortunately, he taught his
apprentice everything he knew, then his apprentice killed him in his sleep.
Ironic. He could save others from death, but not himself.

**Anakin**: Is it possible to learn this power?

**Palpatine**: Not from a Jedi.''')

        pi1 = ProgramItem(day=1, position=1, time='16:30', text='Check-in')
        pi2 = ProgramItem(day=1, position=2, time='18:00', text='Welcome dinner')
        pi3 = ProgramItem(day=1, position=3, time='19:30', text='Opening meeting')
        pi4 = ProgramItem(day=1, position=4, time='20:00', text='Flirtimony Dance', information_item=info1)
        pi5 = ProgramItem(day=1, position=5, time='0:00', text='Night snack')
        pi6 = ProgramItem(day=2, position=1, time='9:00', text='Breakfast')
        pi7 = ProgramItem(day=2, position=2, time='10:00', text='Morning devotional')
        pi8 = ProgramItem(day=2, position=3, time='11:00', text='Les Lanciers')
        pi9 = ProgramItem(day=2, position=4, time='13:00', text='Lunch')
        pi10 = ProgramItem(day=2, position=5, time='14:00', text='Temple, sports, workshops')
        pijoke = ProgramItem(day=2, position=6, time='14:00', text='Choose the Wright', information_item=info3)
        pi11 = ProgramItem(day=2, position=7, time='17:00', text='Dinner')
        pi12 = ProgramItem(day=2, position=8, time='19:00', text='Hide and Dance', information_item=info2)
        pi13 = ProgramItem(day=2, position=9, time='23:30', text='Look Up')
        pi14 = ProgramItem(day=3, position=1, time='9:00', text='Breakfast')
        pi15 = ProgramItem(day=3, position=2, time='10:30', text='Sacrament meeting')
        pi16 = ProgramItem(day=3, position=3, time='12:30', text='Classes')
        pi17 = ProgramItem(day=3, position=4, time='13:30', text='Lunch, leftovers, clean up')
        pi18 = ProgramItem(day=3, position=5, time='14:00', text='Goodbye')

        db.session.add_all(stakes)
        db.session.add_all([configuration, teaser1, teaser2, teaser3, faq1,
                            faq2, faq3, faq4, info1, info2, info3, info4, pi1, pi2, pi3, pi4,
                            pi5, pi6, pi7, pi8, pi9, pi10, pijoke, pi11, pi12, pi13, pi14, pi15,
                            pi16, pi17, pi18])
        db.session.commit()
