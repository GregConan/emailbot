#!/usr/bin/env python3

"""
Class to update a Google Sheets spreadsheet
Greg Conan: gregmconan@gmail.com
Created: 2025-03-11
Updated: 2025-03-15
"""
# Import standard libraries
import datetime as dt
from email.message import EmailMessage
import os
import pdb
import re
from typing import Any, Callable, Generator, Iterable, Mapping, Sequence

# Import third-party PyPI libraries
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials as ServiceCredentials
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

import gspread
from gspread.utils import ValueInputOption
# from gspread.worksheet import Worksheet

import bs4
from bs4 import BeautifulSoup

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.dissectors import Peeler, Xray
from gconanpy.IO.local import save_to_json
from gconanpy.seq import as_HTTPS_URL

# Import local constants
try:
    from constants import (GOOGLE_CREDS_JSON, GOOGLE_SERVICE_JSON,
                           GOOGLE_SHEET_ID, GOOGLE_TOKEN_JSON,
                           WORKSHEET_NAME)
except ModuleNotFoundError:
    from emailbot.constants import (GOOGLE_CREDS_JSON, GOOGLE_SERVICE_JSON,
                                    GOOGLE_SHEET_ID, GOOGLE_TOKEN_JSON,
                                    WORKSHEET_NAME)


class GCPAuth(Debuggable):
    """ Google Cloud Platform Credentials Object Factory """

    # Base URL for all Google authorization scopes
    SCOPE_URL = "https://www.googleapis.com/auth/"

    # Credentials object attribute names to include when saving to JSON
    KEYS = {"token", "refresh_token", "token_uri", "rapt_token", "client_id",
            "account", "client_secret", "scopes", "expiry", "universe_domain"}

    def __init__(self, scopes: Iterable[str] = ("spreadsheets", "drive"),
                 debugging: bool = False):
        self.debugging = debugging
        self.scopes = self.get_scopes(*scopes)

    @classmethod
    def dictify(cls, creds: ServiceCredentials, strip: Sequence[str] = set()
                ) -> dict[str, Any]:
        """ Convert service account Credentials into a JSON-valid dict.
        Adapted from `google.oauth2.credentials.Credentials.to_json()`.

        :param creds: google.oauth2.service_account.Credentials
        :param strip: Sequence[str], optional list of members to exclude from
                      the output dict.
        :return: Dict[str, Any] representing this instance. Passing it into \
                 from_authorized_user_info() makes a new credential instance.
        """
        jsonified = dict()
        for key in cls.KEYS:

            if key not in strip:  # Don't add explicitly excluded entries
                value = getattr(creds, key, getattr(creds, f"_{key}", None))

                if value is not None:  # Don't add empty entries
                    jsonified[key] = value

        if "expiry" in jsonified:  # Flatten expiry timestamp
            jsonified["expiry"] = creds.expiry.isoformat() + "Z"

        return jsonified

    def get_creds_from(self, serviceJSON: str = GOOGLE_SERVICE_JSON,
                       tokenJSON: str = GOOGLE_TOKEN_JSON,
                       credsJSON: str = GOOGLE_CREDS_JSON, save: bool = False
                       ) -> Credentials | ServiceCredentials | None:
        """ Adapted from \
        https://developers.google.com/docs/api/quickstart/python

        :param tokenJSON: str, valid path to .JSON file storing the user's \
                          access & refresh tokens; created automatically when\
                          the authorization flow completes for the first \
                          time; default is GOOGLE_TOKEN_JSON from constants.py
        :param credsJSON: str, valid path to Google client secrets .JSON \
                          file; default is GOOGLE_CREDS_JSON from constants.py
        :return: Credentials | ServiceCredentials | None, _description_
        """
        creds = None
        if os.path.exists(serviceJSON):
            creds = ServiceCredentials.from_service_account_file(
                serviceJSON, scopes=self.scopes)

        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        elif os.path.exists(tokenJSON):
            creds = Credentials.from_authorized_user_file(
                tokenJSON, self.scopes)

        # If there are no (valid) credentials available, let the user log in.
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                credsJSON, self.scopes)
            creds = flow.run_local_server(port=0)

        elif not creds.valid:  # and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        else:
            save = False

        if save:  # Save the credentials for the next run
            save_to_json(self.dictify(creds), tokenJSON)

        return creds

    @classmethod
    def get_scopes(cls, *scope_names: str) -> list[str]:
        """
        :param scopes: Iterable[str],
        :return: List[str] of scope URLs to include in the credentials
        """
        return [cls.SCOPE_URL + scope for scope in scope_names]


class LinkedInJobNameRegex(list[re.Pattern]):
    NONWORD = re.compile(r"(\W)+")  # Only whitespaces and special chars

    # Symbols delimiting sections of string: -,:;/@()
    BOUND = re.compile(r"\s*[-,:;@\(\)]+\s*")

    FN_WORDS = r"(?:\s(?:of|or)\s)*"  # Words unneeded at string start/end
    SEP = r"(?:\W)*"  # Whitespace and special chars, if any
    SPECIAL = r"[^\s\w]*"  # Special characters only, if any, not whitespace
    SUFFIX = r"(?:[a-z]*)"  # Word ending/suffix: -ed, -s, etc.
    TERMS = (
        r"W2|Only|No|H1b",  # Visa status: "W2 Only No H1b", etc
        r"(?:Immediate|Urgen|Requir|Need)" + SUFFIX + FN_WORDS,  # Urgency
        r"100\%|Remote",  # Location: "100% Remote"
        r"Only|(?:[a-z]{4}\sTime)",  # Job type: full/part time
        r"Opening|Opportunity|Job|Position",  # The fact that it's a job
        r"(?:Contract)+[a-z\s]*"  # Job type: Contract[ to hire, etc]
    )

    # Get the job title noun (that all other words in the title modify)
    TITLE = re.compile(r"((?:Dev|Eng|Analy|Scien|Consultant)(?:[a-z])*)")

    def __init__(self):
        super().__init__(self.build_pattern(term) for term in self.TERMS)

    @classmethod
    def build_pattern(cls, term: str) -> re.Pattern:
        return re.compile(f"{cls.SPECIAL}{cls.SEP}(?:{term})+", re.IGNORECASE)

    @classmethod
    def normalize(cls, a_str: str) -> str:
        return cls.NONWORD.sub(repl=" ", string=a_str)


class LinkedInJob:
    APP_DATE_PREFIX = "Applied on "
    FORMULAS = {"status": ('=if(isdate(A2),if(today()-A2>30,'
                           '"Stale","Active"),"Not Yet")')  # ,
                # "link": '=HYPERLINK("{}","{}")'}
                }
    MAIL_SUBJECT = "your application was sent to "
    REGX = LinkedInJobNameRegex()
    URL_PREFIX = "https://www.linkedin.com/jobs/view/"

    def __init__(self, company: str, name: str, url: str,
                 src: str = "LinkedIn", contact: str = "N/A",
                 applied_on: dt.date | None = None):
        self.company: str = company
        self.contact: str = contact
        self.date: str = applied_on.isoformat() if applied_on else "=TODAY()"
        self.name: str = name
        self.src: str = src
        self.url: str = url

    @classmethod
    def shorten_name(cls, entire_name: str, max_len: int = 30) -> str:
        name = entire_name
        if len(name) > max_len:
            title_noun = None  # cls.REGX.TITLE.match(parts[-1])
            title_found = None
            parts = [x for x in cls.REGX.BOUND.split(name.strip())]
            while len(parts) > 0 and (title_found is None) \
                    and len(name) > max_len:
                title_found = cls.REGX.TITLE.search(parts[-1])
                if title_found is None:
                    parts.pop()
                else:
                    title_noun = title_found.groups()[0]
                shortened = " ".join(parts)
                if len(shortened) > 0:
                    name = shortened

            if len(name) > max_len:
                ix = 0
                while ix < len(cls.REGX) and len(name) > max_len:
                    shortened = cls.REGX[ix].sub(repl="", string=name)
                    if len(shortened) > 3 and (not title_noun or
                                               title_noun in shortened):
                        name = shortened
                    ix += 1

            if len(name) > max_len:
                # name = re.compile(cls.REGX.FN_WORDS)(" ", name)
                if title_noun:
                    words = name.split()
                    try:
                        title_noun_pos = words.index(title_noun)
                    except ValueError as err:
                        pdb.set_trace()
                        print(err)
                    while len(words) > title_noun_pos + 1 and len(name) > max_len:
                        words.pop()
                        name = " ".join(words)

                    while len(words) > 1 and len(name) > max_len:
                        words.pop(0)
                        name = " ".join(words)

                    name = cls.REGX.normalize(name).strip()

                    if len(name) > max_len:
                        name = name[:name.rfind(" ", max_len) + 1]

        return name

    def toGoogleSheetsRow(self) -> list[str]:
        """
        :return: list[str] of values to insert into a Google Sheet row.
        """
        return [self.date, self.company,
                f'=HYPERLINK("{self.url}","{self.shorten_name(self.name)}")',
                self.FORMULAS["status"], self.src, self.contact]

    @classmethod
    def fromGmailMsg(cls, msg: EmailMessage) -> "LinkedInJob":
        """
        :param msg: EmailMessage representing an automated email sent by \
            LinkedIn after applying to a job on the website.
        :return: LinkedInJob with the details of the job applied to.
        """
        # Get name of company that posted the job
        company = msg["Subject"].split(cls.MAIL_SUBJECT)[-1]

        # Convert EmailMessage to valid HTML body string
        msgstr = msg.as_string().replace("\r", "")
        despaced = msgstr.replace("=\n", "").replace("=3D", "=")
        start_ix = despaced.find("<body")
        end_ix = despaced.rfind("</body>") + 7  # +len("</body>")
        bodystr = despaced[start_ix:end_ix]

        # Convert HTML body string to BeautifulSoup to parse msg contents
        body = BeautifulSoup(bodystr, features="html.parser")

        # Filter out more useless whitespace from the message
        for blank_str in body.find_all(string=' '):
            blank_str.extract()  # Remove from BeautifulSoup XML element tree

        # Get first job hyperlink in the message
        job_el = None
        ix = 0
        all_links = body.find_all("a")
        while not job_el and ix < len(all_links):
            innerText = all_links[ix].get_text(strip=True)
            job_URL = all_links[ix].attrs["href"]
            if innerText and "/jobs/view/" in job_URL:
                job_el = all_links[ix]
            else:
                ix += 1
        if not job_el:
            raise ValueError("Couldn't find job URL in message")

        # Parse message to get the job application submission date
        ix = 0
        body_parts = Peeler.peel2(body)
        job_app_date = None
        while job_app_date is None and ix < len(body_parts):
            txt_part = bs4.Tag.get_text(body_parts[ix], strip=True)
            datesplit = str.split(txt_part, cls.APP_DATE_PREFIX)
            if len(datesplit) > 1:
                job_app_date = dt.datetime.strptime(
                    datesplit[1], '%B %d, %Y').date()
            else:
                ix += 1
        if not job_app_date:
            raise ValueError("Couldn't find job application date in message")

        # Instantiate LinkedInJob using the details from the message
        job_name = str.split(job_el.text, company, 1)[0].strip()
        return LinkedInJob(company=company, name=job_name,
                           url=job_URL.split('?', 1)[0],
                           applied_on=job_app_date)


class GoogleSheetUpdater(Debuggable):
    FORMULAS: dict[str:str] = {"status": ('=if(isdate(A2),if(today()-A2>30,'
                                          '"Stale","Active"),"Not Yet")')  # ,
                               # "link": '=HYPERLINK("{}","{}")'}
                               }

    def __init__(self, worksheet_name: str = WORKSHEET_NAME,
                 sheetID: str = GOOGLE_SHEET_ID,
                 creds: Credentials | ServiceCredentials | None = None,
                 debugging: bool = False) -> None:
        self.auth = GCPAuth(debugging=debugging)
        self.debugging = debugging
        try:
            if not creds:
                creds = self.auth.get_creds_from(save=True)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(sheetID)
            self.worksheet = self.spreadsheet.worksheet(worksheet_name)
        except (HttpError, ValueError) as err:
            self.debug_or_raise(err, locals())

    def add_job_row(self, job: LinkedInJob, row_num: int = 2) -> None:
        # self.worksheet.insert_rows()
        self.worksheet.insert_row(
            job.toGoogleSheetsRow(), index=row_num,
            value_input_option=ValueInputOption.user_entered)
