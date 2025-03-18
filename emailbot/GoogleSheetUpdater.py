#!/usr/bin/env python3

"""
Class to update a Google Sheets spreadsheet
Greg Conan: gregmconan@gmail.com
Created: 2025-03-11
Updated: 2025-03-17
"""
# Import standard libraries
import os
import pdb
from typing import Any, Callable, Iterable, Mapping, TypeVar

# Import third-party PyPI libraries
from google.auth.transport.requests import Request
# from google.auth.credentials import CredentialsWithQuotaProject
from google.oauth2.service_account import Credentials as OauthServiceCreds
from google.oauth2.credentials import Credentials as OauthCreds
from google_auth_oauthlib.flow import InstalledAppFlow
# from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from google.auth.external_account_authorized_user import Credentials
import gspread

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.dissectors import Peeler, Xray
from gconanpy.IO.local import save_to_json
from gconanpy.maps import Configtionary
from gconanpy.seq import stringify_list

# Import local custom libraries
try:
    from Gmailer import Gmailer
    from LinkedInJob import LinkedInJob
except ModuleNotFoundError:
    from emailbot.Gmailer import Gmailer
    from emailbot.LinkedInJob import LinkedInJob


class GCPAuth(Debuggable):
    """ Google Cloud Platform Credentials Object Factory """
    CREDS_TYPE = TypeVar("CredsType", Credentials,
                         OauthCreds, OauthServiceCreds)

    # Base URL for all Google authorization scopes
    SCOPE_URL = "https://www.googleapis.com/auth/"

    # Credentials object attribute names to include when saving to JSON
    KEYS = {"token", "refresh_token", "token_uri", "rapt_token", "client_id",
            "account", "client_secret", "scopes", "expiry", "universe_domain"}

    def __init__(self, scopes: Iterable[str] = ("spreadsheets", "drive"),
                 debugging: bool = False) -> None:
        """

        :param scopes: Iterable[str] of GCP authorization scope names; \
            defaults to ("spreadsheets", "drive")
        """
        self.debugging = debugging
        self.scopes = self.get_scopes(*scopes)

    @classmethod
    def dictify(cls, creds: CREDS_TYPE, strip: Iterable[str] = set()
                ) -> dict[str, Any]:
        """ Convert service account Credentials into a JSON-valid dict.
        Adapted from `google.oauth2.credentials.Credentials.to_json()`.

        :param creds: CREDS_TYPE, Credentials (imported from either \
            `google.oauth2.credentials`, `google.oauth2.service_account`, or \
            `google.auth.external_account_authorized_user`)
        :param strip: Iterable[str] of names of creds attributes to exclude \
            from the output dict; defaults to empty set to include them all.
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

    def get_creds_from(self, credsJSON: str | None = "credentials.json",
                       serviceJSON: str | None = None,  # GOOGLE_SERVICE_JSON,
                       tokenJSON: str | None = None,  # GOOGLE_TOKEN_JSON,
                       save_to: str | None = None) -> CREDS_TYPE | None:
        """ Adapted from \
        https://developers.google.com/docs/api/quickstart/python

        :param credsJSON: str | None, valid path to readable .JSON file \
            storing Google client secrets; defaults to "credentials.json"
        :param serviceJSON: str | None, valid path to readable .JSON file \
            storing user GCP service account credentials; \
            defaults to `GOOGLE_SERVICE_JSON` from `constants.py`
        :param tokenJSON: str | None, valid path to readable .JSON file \
            storing user access & refresh tokens; created automatically \
            when the authorization flow completes for the first time; \
            default is `GOOGLE_TOKEN_JSON` from `constants.py`
        :param save_to: str | None, valid .JSON file path to write the \
            resultant Credentials into, or None to skip writing/saving
        :return: CREDS_TYPE | None, Credentials (imported from either \
            `google.oauth2.credentials`, `google.oauth2.service_account`, or \
            `google.auth.external_account_authorized_user`) loaded from one of
            the provided .JSON file paths if possible; else None
        """
        creds = None
        if serviceJSON and os.path.exists(serviceJSON):
            creds = OauthServiceCreds.from_service_account_file(
                serviceJSON, scopes=self.scopes)

        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        elif tokenJSON and os.path.exists(tokenJSON):
            creds = OauthCreds.from_authorized_user_file(
                tokenJSON, self.scopes)

        # If there are no (valid) credentials available, let the user log in.
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(
                credsJSON, self.scopes)
            creds = flow.run_local_server(port=0)

        elif not creds.valid:  # and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        # Save Credentials to .JSON if they're valid and a path was given
        else:
            save_to = None
        if save_to:
            save_to_json(self.dictify(creds), save_to)

        return creds

    @classmethod
    def get_scopes(cls, *scope_names: str) -> list[str]:
        """
        :param scopes: Iterable[str],
        :return: List[str] of scope URLs to include in the credentials
        """
        return [cls.SCOPE_URL + scope for scope in scope_names]


class GoogleSheet(Debuggable):

    def __init__(self, sheet_ID: str, worksheet_name: str,
                 creds: GCPAuth.CREDS_TYPE,
                 debugging: bool = False) -> None:
        """

        :param worksheet_name: str naming the worksheet ; \
            defaults to `WORKSHEET_NAME` from `constants.py`
        :param sheet_ID: str, _description_; \
            defaults to `GOOGLE_SHEET_ID` from `constants.py`
        :param creds: GCPAuth.CREDS_TYPE | None, Credentials (imported from \
            `google.oauth2.credentials`, `google.oauth2.service_account`, or \
            `google.auth.external_account_authorized_user`) to connect to \
            Google Sheets with or None to automatically build Credentials from
            a local .JSON file (either `credentials.json` or a path from \
            `constants.py`: `GOOGLE_SERVICE_JSON` or `GOOGLE_TOKEN_JSON`).
        :param debugging: bool, True to pause and interact on error, else \
            False to raise errors/exceptions; defaults to False.
        """
        try:
            self.debugging = debugging
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(sheet_ID)
            self.worksheet = self.spreadsheet.worksheet(worksheet_name)
        except gspread.exceptions.GSpreadException as err:
            self.debug_or_raise(err, locals())


class JobsAppsSheetUpdater(GoogleSheet):

    def __init__(self, sheet_ID: str, worksheet_name: str,
                 jobs_email: str | None = None, relabel: str | None = None,
                 serviceJSON: str | None = None,
                 tokenJSON: str | None = None,
                 debugging: bool = False) -> None:
        """

        :param worksheet_name: str naming the worksheet ; \
            defaults to `WORKSHEET_NAME` from `constants.py`
        :param sheet_ID: str, _description_; \
            defaults to `GOOGLE_SHEET_ID` from `constants.py`
        :param creds: GCPAuth.CREDS_TYPE | None, Credentials (imported from \
            `google.oauth2.credentials`, `google.oauth2.service_account`, or \
            `google.auth.external_account_authorized_user`) to connect to \
            Google Sheets with or None to automatically build Credentials from
            a local .JSON file (either `credentials.json` or a path from \
            `constants.py`: `GOOGLE_SERVICE_JSON` or `GOOGLE_TOKEN_JSON`).
        :param debugging: bool, True to pause and interact on error, else \
            False to raise errors/exceptions; defaults to False.
        """

        # (GOOGLE_SERVICE_JSON, GOOGLE_SHEET_ID, GOOGLE_TOKEN_JSON, WORKSHEET_NAME)
        self.jobs_email = jobs_email
        self.relabel = relabel
        try:
            auth = GCPAuth(debugging=debugging)
            creds = auth.get_creds_from(
                credsJSON="credentials.json",
                serviceJSON=serviceJSON, tokenJSON=tokenJSON  # TODO
            )
            super().__init__(sheet_ID, worksheet_name, creds, debugging)
        except (HttpError, ValueError) as err:
            self.debug_or_raise(err, locals())

    @classmethod
    def from_config(cls, config: Configtionary, sep: str = ".",
                    default: Any | None = None, debugging: bool = False,
                    **config_vars: str):  # -> "GoogleSheetUpdater"
        """ _summary_ 

        :param config: Configtionary, _description_
        :param sep: str,_description_, defaults to "."
        :param debugging: bool, True to pause and interact on error, else \
            False to raise errors/exceptions; defaults to False
        :param config_vars: Mapping[str, str], _description_
        :return: _type_, _description_
        """
        return cls(**config.from_lookups(config_vars, sep, default),
                   debugging=debugging)

    def add_job_row(self, job: LinkedInJob, row_num: int = 2
                    ) -> gspread.worksheet.JSONResponse:
        """ _summary_ 

        :param job: LinkedInJob, _description_
        :param row_num: int,_description_, defaults to 2
        :return: gspread.worksheet.JSONResponse, _description_
        """
        return self.worksheet.insert_row(
            job.toGoogleSheetsRow(), index=row_num,
            value_input_option=gspread.utils.ValueInputOption.user_entered)

    def sort_job_apps_from_gmail(self, gmail: Gmailer, how_many: int = 10):
        """ _summary_ 

        :param gmail: Gmailer, _description_
        :param how_many: int,_description_, defaults to 10
        """
        added = dict()
        failed = dict()
        for unread_job_email, msg_ID in gmail.get_emails_from(
            address=self.jobs_email, how_many=how_many,
            subject_part=LinkedInJob.MAIL_SUBJECT, search_terms=["UNSEEN"]
        ):
            try:
                added[msg_ID] = LinkedInJob.fromGmailMsg(unread_job_email)
                self.add_job_row(added[msg_ID])
                if self.relabel:
                    gmail.move_msg(msg_ID, "Inbox", self.relabel)
            except ValueError:
                failed[msg_ID] = unread_job_email["Subject"]
        if failed:
            gmail.mark_unread([failed_msg_ID for failed_msg_ID in failed])
            if self.debugging:
                faileds = stringify_list(list(failed.values()))
                print(f"Failed to add jobs from these messages: {faileds}")
                pdb.set_trace()
                print("done")
