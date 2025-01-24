#!/usr/bin/env python3

"""
Class to connect to a Gmail account and fetch emails from it
Greg Conan: gregmconan@gmail.com
Created: 2025-01-24
Updated: 2025-01-24
"""
# Import standard libraries
from email.message import Message
from email.parser import BytesParser
import imaplib
import pdb
from typing import Any, List

# Import local custom libraries
try:
    from constants import EXAMPLE_ADDRESS
except ModuleNotFoundError:
    from emailbot.constants import EXAMPLE_ADDRESS


# NOTE: Very much a work in progress.


class GmailIMAPFetcher:
    """
    _summary_
    Originally based on this junk: https://www.geeksforgeeks.org\
/python-fetch-your-gmail-emails-from-a-particular-user/
    """
    IMAP_URL: str = 'imap.gmail.com'

    def __init__(self):  # , address: str, password: str):
        # Make SSL connection with GMAIL
        self.con = imaplib.IMAP4_SSL(self.IMAP_URL)
        self.bp = BytesParser()

        # pdb.set_trace()
        # self.login(address, password)

    def check_inbox(self):
        # calling function to check for email under this label
        self.con.select('Inbox')
        msgs = self.get_emails_from(EXAMPLE_ADDRESS)

        # Uncomment this to see what actually comes as data
        # print(msgs)

        # Finding the required content from our msgs
        # User can make custom changes in this part to
        # fetch the required content he / she needs
        self.show(msgs)
        return msgs

    def get_body_of(self, msg: Message) -> Any:
        """Function to get the email content part, i.e its body part

        :param msg: email.message.Message, _description_
        :return: _type_, _description_
        """  # TODO does i=0 only get part of the body?
        return self.get_body_of(msg.get_payload(i=0)) if msg.is_multipart() \
            else msg.get_payload(i=None, decode=True)

    def fetch(self, msg_set: str, msg_parts: str = "(RFC822)"
              ) -> Message[str, str]:
        """
        _summary_ 
        :param msg_set: str, _description_
        :param msg_parts: str, _description_, defaults to "(RFC822)"
        :return: Message[str, str], _description_
        """
        _, msg_bytes = self.con.fetch(msg_set, msg_parts)
        return self.bp.parsebytes(msg_bytes)

    def fetch_all_emails_in(self, response_bytes: bytes,
                            msg_parts: str = "(RFC822)") -> List[Message]:
        """
        :param response_bytes: bytes, _description_
        :return: List[Message], _description_
        """
        return [self.con.fetch(msg_num, msg_parts)
                for msg_num in response_bytes[0].split()]

    def get_emails_from(self, an_address: str) -> List[Message]:
        """
        _summary_ 
        :param an_address: str, _description_
        :return: _type_, _description_
        """
        # self.con.select('Inbox')
        return self.fetch_all_emails_in(self.search('FROM', an_address))

    def login(self, address: str, password: str):
        """Log the user in.

        :param address: str, _description_
        :param password: str, _description_
        """
        self.con.login(address, password)

    def search(self, key: str, value: Any):
        """Function to search for a key value pair.

        :param key: _type_, _description_
        :param value: _type_, _description_
        :return: _type_, _description_
        """
        _, data = self.con.search(None, key, f'"{value}"')
        return data

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
