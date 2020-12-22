#! /usr/bin/env python3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import csv
import ssl
import os

### USAGE
"""
this script parses a csv file with newly creaeted users (which also is accepted by gosa) in this form:
>>>givenname,   surname,    email,                      password,   user_id     <<<
>>>Max,         Mustermann, max.mustermann@email.de,    12345678,   mmustermann <<<
do not use the first row in your file to identify the columns, just order it correctly.
do not use quotation marks, even on double names.
edit the user settings accordingly, USER_LIST ist the path to your csv file.
if a attachment file should be appended, add its path and filename to the corresponding variable.
if SMTP throws errors you can debug it by setting SMTP_DEBUG to True.
to run just execute 'python sendmail.py'
"""

### User Settings
NAME = '' # sendername which is used in the mail template
USERNAME = ''  # username to authenticate against the smtp server
SENDER = '' # mail address to be used in the FROM field
PASSWORD = '' # password to authenticate against the smtp server
USER_LIST = '/path/to/user_list.csv' # path to csv file to use

### Server Settings
SMTPserver = 'smtp.stuvus.uni-stuttgart.de'
SMTPport = 587
SMTP_DEBUG = False

### Edit Message Template here:
subject = 'Stuvus Account eingerichtet'
body='''Hallo %s %s,

wir haben dir einen Stuvus Account eingerichtet:

Nutzerkennung: %s
Initialpasswort: %s

Bitte ändere dein Initialpasswort unter https://stuvus.uni-stuttgart.de/gosa/main.php

Im Anhang findest du eine Anleitung für unsere IT Dienste. Ggf. sind noch nicht alle Dienste für deine Hochschulgruppe/Fachgruppe konfiguriert und müssen erst beantragt werden.
Bitte melde dich bei Problemen oder Fragen zur IT unter support@stuvus.uni-stutgart.de
Gruß,

%s'''

### Set Attachment Path here. leave blank if not needed
attachment_path = '/path/to'
attachment_name = 'attachment.pdf'

context = ssl.create_default_context()
d={}
d['givenname']=[]
d['sn']=[]
d['pmail']=[]
d['password']=[]
d['uid']=[]

def add_attachment(message):
    file = os.path.join(attachment_path,attachment_name)
    if(file):
        with open(file,'rb') as raw_file:
            obj = MIMEBase('application','octet-stream')
            obj.set_payload((raw_file.read()))
            encoders.encode_base64(obj)
            obj.add_header('Content-Disposition','attachment; filename='+attachment_name)
            message.attach(obj)


with open(USER_LIST) as file:
    input = csv.DictReader(file, fieldnames = ['givenname', 'sn', 'pmail', 'password', 'uid'], delimiter = ',')
    for i,row in enumerate(input):
        for key in row:
            d[key].append(row[key])
    print('read %i lines from %s'%(i+1,USER_LIST))


for i in range(0,len(d['sn'])):
        message = MIMEMultipart()
        message['From'] = SENDER
        message['To'] = d['pmail'][i]
        message['Subject'] = subject
        message.attach(MIMEText(body % (d['givenname'][i],d['sn'][i],d['uid'][i],d['password'][i],NAME),'plain', 'utf-8'))
        add_attachment(message)
        msg = message.as_string()
        
        with smtplib.SMTP(SMTPserver, SMTPport) as server:
            server.set_debuglevel(SMTP_DEBUG)
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(USERNAME, PASSWORD)
            server.sendmail(SENDER, d['pmail'][i], msg)
        print('email sent to: %s %s Mail: %s'%(d['givenname'][i],d['sn'][i],d['pmail'][i]))