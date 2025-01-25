#!/usr/bin/env python3

"""
Class to connect to a Gmail account and fetch emails from it
Greg Conan: gregmconan@gmail.com
Created: 2025-01-24
Updated: 2025-01-25
"""
# Import standard libraries
from getpass import getpass
from email.message import Message
from email.parser import BytesParser
import imaplib
import pdb
from typing import Any, List, Mapping

# Import local custom libraries
try:
    from utilities import Debuggable, load_template_from, peel
except ModuleNotFoundError:
    from emailbot.utilities import Debuggable, load_template_from, peel


# NOTE: Very much a work in progress.


class GmailIMAPFetcher(Debuggable):
    """
    _summary_
    Originally based on this junk: https://www.geeksforgeeks.org\
/python-fetch-your-gmail-emails-from-a-particular-user/
    """  # TODO Integrate https://iq.opengenus.org/read-gmail-python/
    MSG_FMT: str = "(RFC822)"

    def __init__(self, imap_URL: str = "imap.gmail.com",
                 # , address: str, password: str):
                 debugging: bool = False) -> None:
        """
        :param imap_URL: str, host URL to connect to using IMAP4 client. \
                         Defaults to "imap.gmail.com"
        """
        self.debugging = debugging

        # IMAP4 client SSL connection with GMAIL
        self.con = imaplib.IMAP4_SSL(imap_URL)

        # For convenience later, alias the connection's log in/out methods
        self.login = self.con.login
        self.logout = self.con.logout

        # Keep a parser to translate incoming messages from raw bytes
        self.bp = BytesParser()
        self.parse = self.bp.parsebytes

        # Email templates
        self.templates = list()

    # TODO Add functionality to restore connection on abort

    def get_body_of(self, msg: Message) -> Any:
        """Function to get the email content part, i.e its body part

        :param msg: email.message.Message, _description_
        :return: _type_, _description_
        """  # TODO does i=0 only get part of the body?
        return self.get_body_of(msg.get_payload(i=0)) if msg.is_multipart() \
            else msg.get_payload(i=None, decode=True)

    def fetch(self, msg_ID: str | bytes, msg_parts: str = MSG_FMT) -> Message:
        """
        _summary_ 
        :param msg_ID: str, _description_
        :param msg_parts: str defining which parts of an email to download.
        :return: Message, _description_
        """
        return self.parse(peel(self.con.fetch(msg_ID, msg_parts)))

    def fetch_all_emails_in(self, response_bytes: bytes,
                            msg_parts: str = MSG_FMT) -> List[Message]:
        """
        :param response_bytes: bytes, _description_
        :param msg_parts: str defining which parts of an email to download.
        :return: List[Message], _description_
        """
        return [self.con.fetch(msg_num, msg_parts)
                for msg_num in response_bytes.split()]

    def get_emails_from(self, folder: str = "Inbox", key: str = "ALL",
                        value: Any = None, how_many: int = 50) -> List[Message]:
        """
        _summary_ 
        :param folder: str, folder/box to get emails from, defaults to "Inbox"
        :param key: str, _description_, defaults to "ALL"
        :param value: Any, _description_, defaults to None
        :param how_many: int, number of email messages to get, defaults to 50
        :return: List[Message], _description_
        """
        self.con.select(folder)
        filters = (key, f'"{value}"') if value else (key, )
        try:
            email_IDs = peel(self.con.search(None, *filters)).split()
            if how_many < len(email_IDs):  # TODO use ::-1 to iterate in reverse?
                email_IDs = email_IDs[-how_many:]
            return [self.fetch(msg_ID) for msg_ID in email_IDs]
        except (AttributeError, imaplib.IMAP4.error) as err:
            self.debug_or_raise(err, locals())

    def get_emails_from_sender(self, an_address: str, folder: str = "Inbox"
                               ) -> List[Message]:
        """
        _summary_ 
        :param an_address: str, _description_
        :return: _type_, _description_
        """
        return self.get_emails_from(folder, "FROM", an_address)

    def is_logged_out(self) -> bool:
        """
        :return: bool, True if self.con has not authenticated its connection \
                 to a Gmail account; else False if logged in
        """
        return self.con.state in imaplib.Commands["AUTHENTICATE"]

    def load_templates_from(self, *template_fpaths: str) -> None:
        for template_fpath in template_fpaths:
            self.templates.append(load_template_from(template_fpath))

    def login_with(self, credentials: Mapping[str, Any]) -> None:
        """Login and connect to a Gmail account with user credentials.

        :param credentials: Mapping[str, str] of "address" and "password" \
                            keys to a Gmail account's login credentials.
        """
        try:
            # TODO Implement Oauth2? https://stackoverflow.com/a/5366380
            # https://support.google.com/accounts/answer/185833
            self.login(credentials["address"], credentials["password"])

        # If credentials are incorrect, then keep prompting user for new password
        # until either the password works or the user quits
        except imaplib.IMAP4.error as err:
            PROMPT = "Incorrect email address or password. Failed to login " \
                f"to {credentials['address']}: {err.args[0].decode('utf-8')}"\
                "\nPlease reenter your password or press Enter to quit: "

            while self.is_logged_out():  # self.con.state == "NONAUTH":
                credentials["password"] = getpass(PROMPT)
                if credentials.get("password"):
                    self.login(credentials["address"],
                               credentials["password"])
                else:
                    break  # sys.exit(1)

    def search(self, key: str, value: Any):
        """Function to search for a key value pair.

        :param key: _type_, _description_
        :param value: _type_, _description_
        :return: _type_, _description_
        """
        return peel(self.con.search(None, key, f'"{value}"'))

    def show(self, msgs):
        # printing them by the order they are displayed in your gmail
        for msg in msgs[::-1]:
            for sent in msg:
                if isinstance(sent, tuple):  # if type(sent) is tuple:

                    # encoding set as utf-8
                    content = str(sent[1], 'utf-8')
                    data = str(content)

                    # Handling errors related to unicodenecode
                    try:
                        indexstart = data.find("ltr")
                        data2 = data[indexstart + 5: len(data)]
                        indexend = data2.find("</div>")

                        # printing the required content which we need
                        # to extract from our email i.e our body
                        print(data2[0: indexend])

                    except UnicodeEncodeError as e:
                        pass
