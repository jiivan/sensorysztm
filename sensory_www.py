import configparser
from flask import flash
from flask import Flask
from flask import render_template
from flask import request
from flask import session

app = Flask(__name__)
app.debug = True

def load_config():
    config = configparser.ConfigParser()
    config.read('settings.ini')
    return config

def save_config(config):
    with open('settings.ini', 'w') as f:
        config.write(f)

@app.route('/mail', methods=['GET', 'POST'])
def mail():
    config = load_config()
    if not session.get('logged_in'):
        session['logged_in'] = True
        flash('You were logged in')
    if request.method == "POST":
        email = request.form['email']
        if request.form['action'] == 'del':
            del config['emails'][email]
        else:
            config['emails'][email] = None
        save_config(config)
        flash('New entry was successfully posted')
    entries = config['emails']
    return render_template('mail.j2', entries=entries)

@app.route('/test')
def test():
    return 'OK'


if __name__ == '__main__':
    app.run()
