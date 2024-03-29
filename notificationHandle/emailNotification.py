#!/usr/bin/env python

import os
import smtplib
import sys
from time import strftime
try:
    from loggingdebug import log
except ImportError:
    try:
        import sys
        sys.path.append('.')
        from loggingdebug import log
    except ImportError:
        raise ImportError(
            "Failed to import library from parent folder")

from configparser import ConfigParser
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

class emailNotification(object):

    def __init__(self):
        self.mailDebug = log.log()
        basePath = os.path.dirname(os.path.abspath(__file__))

        emailUserPath = basePath + '/users.txt'
        configFile = basePath + "/email.ini"
        # os.chdir('./')
        # basePath = os.getcwd()

        self.fileAtachment = self.mailDebug.logpath + self.mailDebug.logfile

        self.header = 'Content-Disposition', 'attachment; filename="%s"' % self.fileAtachment
        
        # get the config
        cfg = ConfigParser()
        if os.path.exists(configFile):
            
            cfg.read(configFile)
        else:
            # print("Config not found! Exiting!")
            # sys.exit(1)
            self.mailDebug.logger('error', 'Email config file not found')

        # extract server and from_addr from config
        self.host = cfg.get("smtp", "server")
        fromAddr = cfg.get("smtp", "from_addr")

        # create the message
        self.msg = MIMEMultipart()
        self.msg["From"] = fromAddr
        self.mailDebug.logger('debug', 'Email is being sent from: {}'.format(self.msg["From"]))

        with open(emailUserPath, 'r') as usersFile: #read the login details
            toSendTo = ''
            for line in usersFile:
                if toSendTo != '':
                    toSendTo = toSendTo+ '; ' + line.strip()
                else:
                    toSendTo = toSendTo + line.strip()
        
        self.msg['To'] = toSendTo
        self.mailDebug.logger('debug', 'Email is being sent to: {}'.format(self.msg["To"]))
        # self.msg["To"] = ', '.join(to_emails)
        # self.msg["cc"] = ', '.join(cc_emails)

    def sendMailAttachment(self, subject, bodyText):
        """
        Send an email with an attachment
        """
        # create the message
        self.mailDebug.logger('debug', 'An email has been requested')
        self.msg["Subject"] = subject
        self.msg["Date"] = formatdate(localtime=True)
        if bodyText:
            self.msg.set_payload([MIMEText(bodyText)])
            # self.msg.attach( MIMEText(bodyText) )
        
        attachment = MIMEBase('application', "octet-stream")
        try:
            with open(self.fileAtachment, "rb") as fh:
                data = fh.read()
            attachment.set_payload( data )
            encoders.encode_base64(attachment)
# Comment this to remove attachment
            attachment.add_header(*self.header)
            self.msg.attach(attachment)
        except Exception as excep:
            self.msg = "Error opening attachment file %s" % self.fileAtachment
            self.mailDebug.logger('error', self.msg)
            ercode = "Exception in mail: {}".format(excep)
            self.mailDebug.logger('error', ercode)
            return False
            # print(self.msg)
            # sys.exit(1)

        # emails = to_emails# + cc_emails
        try:
            server = smtplib.SMTP(self.host)
            server.starttls()
            server.send_message(self.msg)
            server.quit()
            self.logmsg = "Email sent successfully"
            self.mailDebug.logger('debug', self.logmsg)
            return True
        except Exception as failmail:
            self.logmsg = "Email failed: {}".format(failmail)
            self.mailDebug.logger('debug', self.logmsg)
            return False