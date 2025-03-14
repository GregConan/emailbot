#!/usr/bin/env python3

"""
Class to update a Google Sheets spreadsheet
Greg Conan: gregmconan@gmail.com
Created: 2025-03-11
Updated: 2025-03-13
"""
# Import standard libraries
from email.message import EmailMessage
import os
import pdb
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence
import xml.etree.ElementTree as ElementTree

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

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.dissectors import Xray
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


# NOTE: Very much a work in progress.


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
                ) -> Dict[str, Any]:
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
                       credsJSON: str = GOOGLE_CREDS_JSON, save: bool = True
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
    def get_scopes(cls, *scope_names: str) -> List[str]:
        """
        :param scopes: Iterable[str],
        :return: List[str] of scope URLs to include in the credentials
        """
        return [cls.SCOPE_URL + scope for scope in scope_names]


class LinkedInJob:
    URL_PREFIX = "https://www.linkedin.com/jobs/view/"
    FORMULAS = {"status": ('=if(isdate(A2),if(today()-A2>30,'
                           '"Stale","Active"),"Not Yet")')  # ,
                # "link": '=HYPERLINK("{}","{}")'}
                }

    def __init__(self, company: str, title: str, url: str,
                 src: str = "LinkedIn", contact: str = "N/A"):
        self.company = company
        self.contact = contact
        self.title = title
        self.src = src
        self.url = url

    def toGoogleSheetsRow(self) -> List[str]:
        return ["=TODAY()", self.company,
                f'=HYPERLINK("{self.url}","{self.title}")',
                self.FORMULAS["status"], self.src, self.contact]

    @classmethod  # -> Dict[str, Any]:
    def fromGmailMsg(cls, msg: EmailMessage) -> "LinkedInJob":
        pdb.set_trace()  # TODO

        cls()


class GoogleSheetUpdater(Debuggable):
    FORMULAS = {"status": ('=if(isdate(A2),if(today()-A2>30,'
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
