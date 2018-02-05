from flask import Flask, request, render_template, redirect, url_for, session
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import InputRequired, Length
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from telethon import TelegramClient

APP = Flask(__name__)
APP.config['SECRET_KEY'] = 'somethingsectret'
APP.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////path-to-sqlite-db/telepost.db'
Bootstrap(APP)
DB = SQLAlchemy(APP)
LOGIN_MANAGER = LoginManager()
LOGIN_MANAGER.init_app(APP)
LOGIN_MANAGER.login_view = 'login'

class User(UserMixin, DB.Model):
    id = DB.Column(DB.Integer, primary_key=True)
    username = DB.Column(DB.String(15), unique=True)
    password = DB.Column(DB.String(80))

class TelegramUser(DB.Model):
    u_id = DB.Column(DB.Integer, primary_key=True)
    api_id = DB.Column(DB.String(15), unique=True)
    api_hash = DB.Column(DB.String(80))
    phone_number = DB.Column(DB.String(80))
    status = DB.Column(DB.Boolean())
    u_name = DB.Column(DB.String(15))

class TelegramGroups(DB.Model):
    g_id = DB.Column(DB.Integer, primary_key=True)
    g_link = DB.Column(DB.String(80))
    g_name = DB.Column(DB.String(15))


class LoginForm(FlaskForm):
    username = StringField('username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('remember me')


 

class TelegramUserForm(FlaskForm):
    api_id = StringField('API ID', validators = [InputRequired(), Length(min=1, max=15)])
    api_hash = StringField('API hash', validators=[InputRequired(), Length(min=8, max=80)])
    phone_number = StringField('Phone Number')
    u_name = StringField('Name of the User')
    
    
class SendMessageForm(FlaskForm):
    telegram_user = SelectField('Telegram users from Database', coerce=int)

class VerifyCodeForm(FlaskForm):
    telegram_code = StringField('Telegram Verification Code')

class ComposerMessageForm(FlaskForm):
    composed_message = TextAreaField('Message to send')
    group_link = SelectField('Select Group', coerce=int)


class GroupForm(FlaskForm):
    new_group = TextAreaField('Group invite URL')
    group_name = StringField('Group name')


@LOGIN_MANAGER.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@APP.route('/')
@login_required
def index():
    return render_template("index.html", name = current_user.username)


@APP.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if user.password == form.password.data:
                login_user(user, remember=form.remember.data)
                return redirect(url_for('index'))
        return '<h1> Invalid Username or Password </h1>'        

    return render_template('signin.html', form=form)

@APP.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@APP.route('/add-new-user', methods=['GET', 'POST'])
@login_required
def add_new_user():
    form = TelegramUserForm()
    if form.validate_on_submit():
        new_telegram_user = TelegramUser(api_id=form.api_id.data, api_hash=form.api_hash.data, phone_number=form.phone_number.data, u_name = form.u_name.data)
        DB.session.add(new_telegram_user)
        DB.session.commit()
        return redirect(url_for('index'))
    return render_template("add-new-user.html", name = current_user.username, form=form)

@APP.route('/send-messages', methods=['GET','POST'])
@login_required
def send_messages():
    form = SendMessageForm()
    users_collection = TelegramUser.query.all()
    form.telegram_user.choices = [(g.u_id, g.u_name) for g in users_collection]
    if form.validate_on_submit():
        global value 
        value = request.form.get("telegram_user")
        user_collection_by_id = TelegramUser.query.get(value)
        global api_id
        api_id = int(user_collection_by_id.api_id)
        session_name = str(api_id)
        global api_hash
        api_hash = user_collection_by_id.api_hash
        global phone_number 
        phone_number = user_collection_by_id.phone_number
        global client    
        client = TelegramClient(session_name, api_id, api_hash)
        status = sendToGroup()
        return status
        
         
    return render_template("send-messages.html", name = current_user.username, form=form)


@APP.route('/add-new-group', methods=['GET','POST'])
@login_required
def add_new_group():
    form = GroupForm()
    if form.validate_on_submit():
        new_group = TelegramGroups(g_link=form.new_group.data)
        DB.session.add(new_group)
        DB.session.commit()
        return redirect(url_for('index'))
    return render_template("add-new-group.html", form = form)


@APP.route('/send-to-group', methods = ['GET', 'POST']) 
@login_required
def sendToGroup(): 
    code = request.form.get("telegram_code")
    message = request.form.get("composed_message")
    g_id = request.form.get("group_link")
    if g_id:
        selected_group = TelegramGroups.query.get(g_id)
        selected_group_link = selected_group.g_link
        print(selected_group_link)
    if not code and not message:
        form = ComposerMessageForm()
        telegram_groups = TelegramGroups.query.all()
        form.group_link.choices = [(g.g_id, g.g_name) for g in telegram_groups]
        return render_template("compose-message.html", form = form)
    assert client.connect()
    if not client.is_user_authorized():
        if not code: 
            client.send_code_request(phone_number)
            form = VerifyCodeForm()
            return render_template("verify-code.html", form = form)
        me = client.sign_in(phone_number, int(code))
        return render_template("final-message.html")

        return redirect(url_for('verify_code', api_id = api_id, api_hash = api_hash, phone_number = phone_number))

    else:
        lonami = client.get_entity(selected_group_link)
        if client.send_message(lonami, message):
            return "<h2>Message sent. <a href=\"/\">Click here</a> to go back to dashboard </h2>"


@APP.route('/verify-code', methods = ['GET', 'POST'])
@login_required
def verify_code():
    code = request.form.get("telegram_code")
    if not code:
        form = VerifyCodeForm()
        return render_template("verify-code.html", form = form)
    send_it(api_id, api_hash, phone_number, code)
    return render_template("final-message.html")


def send_it(api_id, api_hash, phone_number, code):
    assert client.connect()

if __name__ == '__main__':
    APP.run(debug=True, port=3000, host="0.0.0.0")

