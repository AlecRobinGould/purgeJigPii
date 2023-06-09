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

class emailNotification(log.log):

    def __init__(self):
        super().__init__()
        self.fileAtachment = "/home/antlabpi/purgeJig/loggingdebug/logfiles/" + '{}.log'.format(strftime('%d-%m-%y'))
        emailUserPath = '/home/antlabpi/purgeJig/notificationHandle/users.txt'
        base_path = os.path.dirname(os.path.abspath(__file__))
        print(base_path)
        config_path = os.path.join(base_path, "email.ini")
        self.header = 'Content-Disposition', 'attachment; filename="%s"' % self.fileAtachment

        # get the config
        if os.path.exists(config_path):
            cfg = ConfigParser()
            cfg.read(config_path)
        else:
            print("Config not found! Exiting!")
            sys.exit(1)

        # extract server and from_addr from config
        self.host = cfg.get("smtp", "server")
        fromAddr = cfg.get("smtp", "from_addr")

        # create the message
        self.msg = MIMEMultipart()
        self.msg["From"] = fromAddr
        self.logger('debug', 'Email is being sent from: {}'.format(self.msg["From"]))

        with open(emailUserPath, 'r') as usersFile: #read the login details
            toSendTo = ''
            for line in usersFile:
                if toSendTo != '':
                    toSendTo = toSendTo+ '; ' + line.strip()
                else:
                    toSendTo = toSendTo + line.strip()
        
        self.msg['To'] = toSendTo
        self.logger('debug', 'Email is being sent to: {}'.format(self.msg["To"]))
        # self.msg["To"] = ', '.join(to_emails)
        # self.msg["cc"] = ', '.join(cc_emails)

    def sendMailAttachment(self, subject, bodyText):
        """
        Send an email with an attachment
        """
        # create the message
        self.logger('debug', 'An email has been requested')
        self.msg["Subject"] = subject
        self.msg["Date"] = formatdate(localtime=True)
        if bodyText:
            self.msg.attach( MIMEText(bodyText) )
        
        attachment = MIMEBase('application', "octet-stream")
        try:
            with open(self.fileAtachment, "rb") as fh:
                data = fh.read()
            attachment.set_payload( data )
            encoders.encode_base64(attachment)
            attachment.add_header(*self.header)
            self.msg.attach(attachment)
        except IOError:
            self.msg = "Error opening attachment file %s" % self.fileAtachment
            print(self.msg)
            sys.exit(1)

        # emails = to_emails# + cc_emails

        server = smtplib.SMTP(self.host)
        server.starttls()
        server.send_message(self.msg)
        server.quit()

def main():
    # cc_emails = ["someone@gmail.com"]
    # bcc_emails = ["anonymous@circe.org"]

    subject = "Test email with attachment from Python"
    bodyText = "This email contains an attachment!"
    # send_email_with_attachment(subject, bodyText, emails,
    #                            cc_emails, bcc_emails, path)
    test = emailNotification()
    test.sendMailAttachment(subject, bodyText)

if __name__ == "__main__":
    main()
