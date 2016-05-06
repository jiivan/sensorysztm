#!/usr/bin/env python3

import configparser
import datetime
from io import BytesIO
import mimetypes
from pathlib import Path
import smtplib

from email import encoders
from email.generator import BytesGenerator
#from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.headerregistry import Address
from email.utils import make_msgid

def get_mails():
    config = configparser.ConfigParser()
    config.read('www/settings.ini')
    if 'emails' not in config:
        config.add_section('emails')
    return [Address(key.split('@')[0].capitalize(), addr_spec=key) for key in config['emails']]

def get_files(month):
    pattern = month.strftime('temp-%Y-%m-*.pdf')
    output_dir = Path(__file__).parent / 'output'
    return list(output_dir.glob(pattern))

def main():
    last_month = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    mails = get_mails()
    if not mails:
        print("No mails")
        return
    files = get_files(last_month)
    if not files:
        print("No files")
        return

    multipart = MIMEMultipart()
    multipart['Subject'] = last_month.strftime("Temp: %Y-%m")
    multipart['From'] = str(Address("Temperatura", addr_spec="temperatura2016@o2.pl"))
    multipart['To'] = ', '.join(str(m) for m in mails)

    multipart.attach(MIMEText("""\
Witaj!

W załączeniu zapisy temperatury z ostatniego miesiąca.

--Temperatura"""))
    
    for filepath in files:
        if not filepath.is_file():
            continue
        ctype, encoding = mimetypes.guess_type(filepath.name)
        if ctype is None or encoding is not None:
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        with filepath.open('rb') as f:
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(f.read())
        encoders.encode_base64(attachment)
        attachment.add_header('Content-Disposition', 'attachment', filename=filepath.name)
        multipart.attach(attachment)

    with open(datetime.datetime.now().strftime('email-%Y-%m-%d-%H-%M-%s.msg'), 'wb') as f:
        fp = BytesIO()
        g = BytesGenerator(fp, mangle_from_=True, maxheaderlen=60)
        g.flatten(multipart)
        text = fp.getvalue()
        f.write(text)
    try:
        with smtplib.SMTP_SSL('poczta.o2.pl', port=465) as s:
            s.login('temperatura2016@o2.pl', 'shtiSlaidd')
            s.send_message(multipart)
    except smtplib.SMTPResponseException as e:
        if e.smtp_code == 250 and e.smtp_error == b'Ok':
            pass # o2.pl bug. Returns 250 Ok instead of 221
        else:
            raise
if __name__ == '__main__':
    main()
