import os
import smtplib
import sys
from time import strftime

from configparser import ConfigParser
from email import encoders
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

class emailNotification(log.log):

    def __init__(self):
        pass

    def send_email_with_attachment(subject, body_text):
        """
        Send an email with an attachment
        """
        file_to_attach = "/home/antlabpi/purgeJig/loggingdebug/logfiles/" + '{}.log'.format(strftime('%d-%m-%y'))
        base_path = os.path.dirname(os.path.abspath(__file__))
        print(base_path)
        config_path = os.path.join(base_path, "email.ini")
        header = 'Content-Disposition', 'attachment; filename="%s"' % file_to_attach

        # get the config
        if os.path.exists(config_path):
            cfg = ConfigParser()
            cfg.read(config_path)
        else:
            print("Config not found! Exiting!")
            sys.exit(1)

        # extract server and from_addr from config
        host = cfg.get("smtp", "server")
        from_addr = cfg.get("smtp", "from_addr")

        # create the message
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        if body_text:
            msg.attach( MIMEText(body_text) )
        
        with open('/home/antlabpi/purgeJig/notificationHandle/users.txt', 'r') as usersFile: #read the login details
            toSendTo = ''
            for line in usersFile:
                if toSendTo != '':
                    toSendTo = toSendTo+ '; ' + line.strip()
                else:
                    toSendTo = toSendTo + line.strip()
        
        msg['To'] = toSendTo
        # msg["To"] = ', '.join(to_emails)
        # msg["cc"] = ', '.join(cc_emails)

        attachment = MIMEBase('application', "octet-stream")
        try:
            with open(file_to_attach, "rb") as fh:
                data = fh.read()
            attachment.set_payload( data )
            encoders.encode_base64(attachment)
            attachment.add_header(*header)
            msg.attach(attachment)
        except IOError:
            msg = "Error opening attachment file %s" % file_to_attach
            print(msg)
            sys.exit(1)

        # emails = to_emails# + cc_emails

        server = smtplib.SMTP(host)
        server.starttls()
        server.send_message(msg)
        server.quit()

if __name__ == "__main__":
    # cc_emails = ["someone@gmail.com"]
    # bcc_emails = ["anonymous@circe.org"]

    subject = "Test email with attachment from Python"
    body_text = "This email contains an attachment!"
    # send_email_with_attachment(subject, body_text, emails,
    #                            cc_emails, bcc_emails, path)
    send_email_with_attachment(subject, body_text)