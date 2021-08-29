from enum import Enum
import hashlib
from pathlib import Path
import logging
from typing import List
from bs4 import BeautifulSoup
import requests
import configparser
import time
import schedule
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging.handlers import TimedRotatingFileHandler

logger = logging.getLogger()
logger_fmt = '%(asctime)s | %(levelname)s | %(message)s'
handler = TimedRotatingFileHandler("tracker.log", when="midnight", interval=1)
handler.suffix = "%Y.%m.%d"
logger.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(logger_fmt))
logger.addHandler(handler)


class Config:
    def __init__(self) -> None:
        config = configparser.ConfigParser()
        config.read('config.ini')
        self.service_health_notifications = config.getboolean(
            config.default_section, 'ServiceHealthNotification')
        self.service_health_notification_freq = config.getint(
            config.default_section, 'ServiceHealthNotificationFrequency')
        self.service_health_notification_recipients = list(map(str.strip, config.get(
            config.default_section, 'ServiceHealthNotificationRecipients').split(',')))
        self.notification_frequency = config.getint(
            config.default_section, 'NotificationFrequency')
        self.notification_recipients = list(map(str.strip, config.get(
            config.default_section, 'NotificationRecipients').split(',')))
        self.mail_api_token = config.get(
            config.default_section, 'MailApiToken')
        self.sender_email = config.get(
            config.default_section, 'SenderEmail')

    def __repr__(self) -> str:
        return f"""
Send Health Notifications = {self.service_health_notifications}
Health Notification Freq = Every {self.service_health_notification_freq} hours
Health Notification Recipients = {self.service_health_notification_recipients}
NotificationFrequency = Every {self.notification_frequency} minutes
Notification Recipients = {self.notification_recipients}
        """


class ServiceStatus(Enum):
    HEALTHY = 1
    UNHEALTHY = 2
    EXCEPTION = 3


class Hash:
    def __init__(self) -> None:
        self.htmlhashFile = "./html.hash"
        self.apiHashFile = "./api.hash"

    def __readHashFromFile(self, type):
        fname = self.htmlhashFile
        if type == "api":
            fname = self.apiHashFile

        if Path(fname).is_file():
            with open(fname, 'r') as f:
                hash = f.read()
                if len(hash) > 0:
                    return hash
                return None
        else:
            return None

    def __writeHashtoFile(self, type, hash):
        fname = self.htmlhashFile
        if type == "api":
            fname = self.apiHashFile
        with open(fname, 'w') as f:
            f.write(hash)

    def get(self, toHash):
        return hashlib.sha384(str(toHash).encode()).hexdigest()

    def isChanged(self, new_hash, type="html"):
        existingHash = self.__readHashFromFile(type)
        if existingHash is None:
            logger.info(
                f"No hash found for {type}! Writing given hash to file")
            self.__writeHashtoFile(type, new_hash)
            return False
        if existingHash != new_hash:
            logger.info(f"Hash mismatch for type: {type}")
            self.__writeHashtoFile(type, new_hash)
            return True
        return False


class Notify:
    def __init__(self, conf: Config) -> None:
        self._base_url = "https://api.sendgrid.com/v3/mail/send"
        self.content = {
            ServiceStatus.HEALTHY: "The service is healthy and running as configured !",
            ServiceStatus.UNHEALTHY: "There are some issues in the service, you might want to check them out !",
            ServiceStatus.EXCEPTION: "An exception was encountered during the process ! Go check logs !"
        }

    def __getEmail(self, recipients: List, subject: str, content: str):
        message = MIMEMultipart()
        message['From'] = conf.sender_email
        message['To'] = ",".join(recipients)
        message['Subject'] = subject
        message.attach(MIMEText(content, 'plain'))
        return message.as_string()

    def __sendEmail(self, recipients, subject, content):
        email_data = self.__getEmail(
            recipients, subject, content)
        logger.debug(email_data)
        session = smtplib.SMTP('smtp.gmail.com', 587)  # use gmail with port
        session.starttls()  # enable security
        # login with mail_id and password
        session.login(conf.sender_email, conf.mail_api_token)
        session.sendmail(conf.sender_email, recipients, email_data)
        session.quit()

    def send_health_notification(self, type: ServiceStatus, additional_info=None):
        subject = f"Service Health Notification: {type.name}"
        try:
            logger.debug(
                f"Attempting to send service health notification, {type.name}")
            self.__sendEmail(
                conf.service_health_notification_recipients, subject, self.content[type]+f"\nAdditional Info:\n{additional_info}")
            logger.debug(
                f"Sucessfully sent service health notification, {type.name}")
        except Exception as e:
            logger.exception(
                f"Error encountered when sending service health notification, {type.name}")

    def send_change_notification(self, additional_info):
        subject = "Toll Brothers House Tracker | DATA CHANGE !"
        try:
            logger.debug(
                f"Attempting to send data change notification")
            self.__sendEmail(
                conf.notification_recipients, subject, additional_info)
            logger.debug(
                f"Sucessfully sent data change notification")
        except Exception as e:
            logger.exception(
                f"Error encountered when sending data change notification")


class HousingWebsite:
    def __init__(self, hash: Hash, notify: Notify) -> None:
        self.base_url = "https://www.tollbrothers.com/"
        self.base_api_url = "https://go.tollbrothers.com/"
        self._hash = hash

    def __isPageHtmlUpdated(self):
        _page_url = "luxury-homes-for-sale/Virginia/Arden"
        html_change_message = "Page HTML has updated ! Unable to parse !!"
        data_change_message = """
Page data has changed, either available number of homes or quick move in houses has changed !
(there's a chance that, page html has changed and this is a false alarm)
"""

        error_message = "Something went wrong. See logs for details !"

        try:
            response = requests.get(self.base_url+_page_url)
            soup = BeautifulSoup(response.text, "html.parser")
            availabilityDivs = soup.find_all(
                "div", {"class": "site-plan-list__right"})

            if len(availabilityDivs) != 1:
                logger.info(html_change_message)
                return (True, html_change_message)

            new_hash = self._hash.get(availabilityDivs[0])
            if self._hash.isChanged(new_hash):
                logger.info(data_change_message)
                return (True, data_change_message)

            return (False, "")

        except Exception as e:
            logger.exception(error_message)
            notify.send_health_notification(ServiceStatus.EXCEPTION, e)
            return True, error_message

    def __isAPIResultUpdated(self):
        _api_url = "ws/topo.json?action=get_lots&comm_num=13154&id=topomap1"
        data_change_message = "House availability has changed !"
        error_message = "Something went wrong (Maybe the API has changed!). See logs for details !"

        lotsAvailable = []
        try:
            response = requests.get(self.base_api_url + _api_url)
            for lot in response.json():
                if lot['lot_status'] == 'Available':
                    if 'lot_type' in lot:
                        if lot['lot_type'] != 'Model':
                            lotsAvailable.append(lot['lot_num'])
                    else:
                        lotsAvailable.append(lot['lot_num'])
            logger.info(
                f"Available Number of Lots (Including quick move ins): {len(lotsAvailable)}")

            new_hash = self._hash.get(lotsAvailable)
            if self._hash.isChanged(new_hash, "api"):
                logger.info(data_change_message)
                return True, data_change_message

            return False, ""

        except Exception as e:
            logger.exception(error_message)
            notify.send_health_notification(ServiceStatus.EXCEPTION, e)
            return False, ""

    def isPageChanged(self):
        htmlChange, htmlChangeMessage = self.__isPageHtmlUpdated()
        apiChange, apiChangeMessage = self.__isAPIResultUpdated()

        if apiChange:
            return True, apiChangeMessage
        if htmlChange:
            return True, htmlChangeMessage

        return False, ""


def check(hWeb: HousingWebsite, notify: Notify):
    changed, message = hWeb.isPageChanged()
    if changed:
        logger.info("Changes detected in this run !")
        notify.send_change_notification(message)
        return

    logger.info("NO changes detected in this run !")


if __name__ == "__main__":
    conf = Config()
    notify = Notify(conf)
    hWeb = HousingWebsite(Hash(), notify)

    logger.info("Application Started !")

    schedule.every(conf.notification_frequency).minutes.do(
        check, hWeb=hWeb, notify=notify)
    schedule.every(conf.service_health_notification_freq).hours.do(
        notify.send_health_notification, type=ServiceStatus.HEALTHY)

    while True:
        schedule.run_pending()
        time.sleep(1)
