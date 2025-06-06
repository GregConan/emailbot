#!/usr/bin/env python3

"""
Class to connect to a Gmail account and fetch emails from it
Greg Conan: gregmconan@gmail.com
Created: 2025-01-24
Updated: 2025-06-05
"""
# Import standard libraries
from collections.abc import Callable, Iterable, Mapping
import datetime as dt
import email
from email.message import EmailMessage
from email.policy import Policy
from getpass import getpass
import imaplib
import os
import pdb
import re
from typing import Any

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.dissectors import Corer
from gconanpy.IO.local import LoadedTemplate
from gconanpy.ToString import stringify


# NOTE: Very much a work in progress.


class BytesOrStrMeta(type):  # TODO Move to gconanpy.metafunc?
    _Checker = Callable[[Any, type | tuple[type, ...]], bool]

    def _check(cls, thing: Any, check: _Checker) -> bool:
        return check(thing, (bytes, str))

    def __instancecheck__(cls, instance: Any) -> bool:
        return cls._check(instance, isinstance)

    def __subclasscheck__(cls, subclass: Any) -> bool:
        return cls._check(subclass, issubclass)


class BytesOrStr(metaclass=BytesOrStrMeta):  # TODO Move to gconanpy.metafunc?
    """ Any instance of bytes or str is a BytesOrStr instance. """


class ReplyTo(EmailMessage, Debuggable):
    def __init__(self, msg: EmailMessage, my_address: str,
                 template: LoadedTemplate,  # Mapping[str, Template],
                 debugging: bool = False, policy: Policy | None = None,
                 **template_fields: Any) -> None:
        try:
            super().__init__(policy=policy)
            self.debugging = debugging
            self.template = template

            self.msg = msg
            self["From"] = my_address
            self["To"] = msg["Return-Path"]
            old_subject = msg["Subject"].replace("\r", "").replace("\n", "")
            self["Subject"] = "Re: " + old_subject

            self.address = msg["Return-Path"].strip("<").rstrip(">")
            self.name = self.get_name()
            self.set_payload(self.write(**template_fields))

        except (AttributeError, KeyError, TypeError, ValueError) as err:
            self.debug_or_raise(err, locals())

    def write(self, **template_fields: Any) -> str:
        """ Insert this reply's specific fields/variables into its template.

        :param template_fields: Mapping[str, Any] of template variable names \
                                to their values.
        :return: str, self.template filled with the values in template_fields.
        """
        try:
            template_fields["sender_name"] = \
                template_fields.pop("name", self.name)
            assert self.template.fields.issuperset(template_fields.keys())
            to_write = self.template.substitute(template_fields)
        except AssertionError as err:
            self.debug_or_raise(err, locals())
        return to_write

    def get_name(self) -> list[str]:  # , msg: EmailMessage
        return [re.sub(r'[^a-zA-Z]', '', x)
                for x in self.msg['From'].split()
                if self.msg['Return-Path'] not in x
                and not re.search(r'\d', x)]


class Gmailer(Debuggable):
    """ _summary_

    Originally based on this junk: https://www.geeksforgeeks.org\
/python-fetch-your-gmail-emails-from-a-particular-user/
    """  # TODO Integrate https://iq.opengenus.org/read-gmail-python/
    MSG_FMT: str = "(RFC822)"

    def __init__(self, imap_URL: str = "imap.gmail.com",
                 debugging: bool = False) -> None:
        """
        :param imap_URL: str, host URL to connect to using IMAP4 client. \
                         Defaults to "imap.gmail.com"
        """
        self.debugging = debugging

        # IMAP4 client SSL connection with GMAIL
        self.con = imaplib.IMAP4_SSL(imap_URL)

        # For convenience later, alias the connection's log in/out methods
        # self.login = self.con.login
        self.logout = self.con.logout

        # Email templates
        self.templates = dict()

    # TODO Add functionality to restore connection on abort

    def draft_reply_to(self, msg: EmailMessage, template_name: str,
                       save_to: str = '[Gmail]/Drafts') -> ReplyTo:
        reply = ReplyTo(msg, debugging=self.debugging,
                        template=self.templates[template_name],
                        my_address=self.address)
        self.con.append(mailbox=save_to, flags="",
                        message=str(reply).encode("utf-8"),
                        date_time=imaplib.Time2Internaldate(
                            dt.datetime.now().astimezone()))
        return reply

    def fetch(self, msg_ID: str, msg_parts: str = MSG_FMT
              ) -> EmailMessage:
        """
        :param msg_ID: str | bytes containing only an int, the unique ID \
                       number representing a specific email message.
        :param msg_parts: str defining which parts of an email to download.
        :return: EmailMessage retrieved via IMAP
        """
        try:
            fetched = Corer().safe_core(self.con.fetch(msg_ID, msg_parts),
                                        as_type=bytes)
            msg = email.message_from_bytes(s=fetched, _class=EmailMessage)
        except (AttributeError, TypeError) as err:
            self.debug_or_raise(err, locals())
        return msg

    def get_emails_from(self, address: str | None = None,
                        folder: str = "Inbox", how_many: int = 1,
                        subject_part: str | None = None,
                        search_keywords: dict[str, Any] = dict(),
                        unread_only: bool = False
                        # search_terms: Iterable[str] = list()
                        ) -> list[tuple[EmailMessage, bytes | str]]:
        """ Get most recent {how_many} emails 

        :param folder: str, folder/box to get emails from, defaults to "Inbox"
        :param how_many: int, number of email messages to get, defaults to 1
        :return: List[EmailMessage], _description_
        """
        self.con.select(folder)
        result: list[tuple[EmailMessage, bytes | str]] = list()

        # Build search query
        if address:
            search_keywords["FROM"] = address
        if subject_part:
            search_keywords["HEADER SUBJECT"] = subject_part
        filters = [f'{k} "{v}"' for k, v in search_keywords.items()]
        if unread_only:
            filters.append("UNSEEN")

        try:  # Execute search query
            searched = stringify(self.search(*filters))

            # If search came up empty, return an empty list
            if searched == "OK":
                result = list()
            else:

                # Otherwise, fetch and return the searched-for messages
                email_IDs = searched.split()
                if how_many < len(email_IDs):
                    email_IDs = email_IDs[-how_many:]
                result = [(self.fetch(msg_ID), msg_ID)
                          for msg_ID in reversed(email_IDs)]
            if not result and self.debugging:
                print("No emails found.")
                pdb.set_trace()
        except (AttributeError, imaplib.IMAP4.error) as err:
            self.debug_or_raise(err, locals())
        return result

    def is_logged_out(self) -> bool:
        """
        :return: bool, True if self.con has not authenticated its connection \
                 to a Gmail account; else False if logged in
        """
        return self.con.state in imaplib.Commands["AUTHENTICATE"]

    def load_templates_from(self, *template_fpaths: str) -> None:
        """
        :param template_fpaths: list[str] of valid paths to existing \
                                text files to convert into `string.Templates`
        """
        for template_fpath in template_fpaths:
            name = os.path.splitext(os.path.basename(template_fpath))[0]
            self.templates[name] = LoadedTemplate.from_file_at(template_fpath)

    def login(self, address: str, password: str) -> Exception | None:
        """ Login and connect to a Gmail account with user credentials.

        :param address: str, user Gmail account email address
        :param password: str | None, user Gmail account password
        :return: Exception if login failed, else None if login succeeded
        """
        try:
            self.con.login(address, password)
            self.address = address
        except imaplib.IMAP4.error as err:
            return err

    def login_with(self, credentials: Mapping[str, str]) -> None:
        """ Login and connect to a Gmail account with user credentials.
        If credentials are incorrect, then keep prompting user for new \
            password until either the password works or the user quits.

        :param credentials: Mapping[str, str] of "address" to a valid Gmail
                            account email address and of "password" to that
                            Gmail account's password
        """
        # TODO Implement Oauth2? https://stackoverflow.com/a/5366380
        # https://support.google.com/accounts/answer/185833
        err = None
        address = credentials["address"]
        password = credentials.get("password")
        PROMPT_FMT = "\nPlease {}enter your password or press Enter to quit: "
        try:
            while self.is_logged_out():
                if err or not password:
                    PROMPT = "Incorrect email address or password. Failed " \
                        f"to login to {address}:\n{stringify(err.args[0])}" \
                        + PROMPT_FMT.format("re") if err \
                        else PROMPT_FMT.format("")
                    password = getpass(PROMPT)
                if not password:
                    break
                else:
                    err = self.login(address, password)
        except TypeError as err:
            self.debug_or_raise(err, locals())

    def mark_unread(self, msgIDs: Iterable[str]) -> None:
        for msgID in msgIDs:
            try:
                self.con.store(msgID, "-FLAGS", "\\Seen")
            except imaplib.IMAP4.error as err:
                self.debug_or_raise(err, locals())

    def move_msg(self, msgID: str, move_from: str, move_to: str) -> None:
        """ Transfer message from one Gmail box to a different one(/label).
        Instead of "removing" the original label, it deletes the email from \
        the label, since labels act like folders in Gmail. Adapted from \
        https://www.reddit.com/r/learnpython/comments/ckqrac/comment/evqjy5k

        :param move_from: str, _description_
        :param move_to: str, _description_
        """
        try:
            self.con.select(move_from)
            self.con.store(msgID, "+X-GM-LABELS", f"({move_to})")
            self.con.store(msgID, "+FLAGS", "\\Deleted")
        except imaplib.IMAP4.error as err:
            self.debug_or_raise(err, locals())

    def search(self, *filters: str) -> BytesOrStr:
        """ Search the contents of a Gmail account.

        :return: Any, _description_
        """
        return Corer(debugging=self.debugging).safe_core(
            self.con.search(None, *filters), as_type=BytesOrStr)
