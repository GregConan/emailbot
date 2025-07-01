#!/usr/bin/env python3

"""
Class to insert a row with LinkedIn job application details into a \
    Google Sheets spreadsheet
Greg Conan: gregmconan@gmail.com
Created: 2025-03-16
Updated: 2025-07-01
"""
# Import standard libraries
import datetime as dt
from email.message import EmailMessage
import re
from typing import NamedTuple

# Import third-party PyPI libraries
from bs4 import BeautifulSoup
from pandas import DataFrame

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.mapping.dicts import DotDict, FancyDict
from gconanpy.dissectors import Shredder
from gconanpy.extend import weak_dataclass
from gconanpy.find import Spliterator
from gconanpy.IO.web import URL
from gconanpy.meta.classes import DATA_ERRORS
from gconanpy.reg import Abbreviations, Regextract


class LinkedInJobNameRegex(list[re.Pattern]):
    # Non-word symbols at the beginning or end of the string, to remove
    START = re.compile(r"^[^\w\(]+")
    END = re.compile(r"[^\w\)]+$")

    # Slash symbols: remove any spaces before and after
    SLASH = re.compile(r"\s*\/\s*")

    # Symbols delimiting sections of string: -,:;/@()
    BOUND = re.compile(r"\s*[-,:;@\(\)]+\s*")

    # LinkedIn automated (noreply) job app email subject line
    EMAIL_SUBJECT = re.compile(
        r"""
        (?:[Yy]ou(?:r\sapplication\s)?)(?:(?:was)?\s+    # Preface
        (?P<verb>[\S]*)\s+)*(?:to|by|for)+    # Status: "submitted", "viewed"
        \s*(?:(?P<name>.*?)\s+    # Title/name of job applied to
        (?:at)\s+)*(?P<company>.*)    # Title/name of company that job is at
        """, re.X)

    # Phrase in email saying when the job application was submitted
    EMAIL_APP_DATE = re.compile(
        r"""
        (?:Applied)  # Preface
        (?:\:\s*(?P<delta>[\d\.]+)\s*  # Amount of time since app submitted
        (?P<unit>\S+)\s*ago)*(?:\s*on\s*  # Unit of time since app submitted
        (?P<date>.*))*  # Exact date that job app was submitted
        """, re.X)

    # Job title noun that all other words in the title modify
    TITLES = r"|".join(("Dev", "Eng", "Analy", "Scientist", "Consultant",
                        "Architect", "Programmer"))
    TITLE = re.compile(r"((?:" + TITLES + r")(?:[a-z])*)")

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

    def __init__(self) -> None:
        super().__init__(self.build_pattern(term) for term in self.TERMS)

    @classmethod
    def build_pattern(cls, term: str) -> re.Pattern:
        return re.compile(f"{cls.SPECIAL}{cls.SEP}(?:{term})+", re.IGNORECASE)

    @classmethod
    def normalize(cls, a_str: str) -> str:
        return cls.END.sub("", cls.START.sub("", cls.SLASH.sub("/", a_str)))

    def remove_from(self, string: str, max_len: int,
                    but_keep: str = "") -> str:
        for removable in self:
            if len(string) <= max_len:
                break
            else:
                shortened = removable.sub("", name)
                if shortened and but_keep in shortened:
                    name = shortened
        return name


class LinkedInJobDetailParser(LinkedInJobNameRegex):
    class ABBR(NamedTuple):
        COMPANY = Abbreviations(Technology="Tech", Solution="Soln")
        JOB = Abbreviations(Senior="Sr", Junior="Jr")
    APP_DATE_PREFIX = "Applied on "
    APP_DATE_FORMATS = ("%B %d, %Y", "%b %d", "%b %d, %Y", "%B %d")
    MSG_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z (%Z)"
    UNNEEDED = (", Inc.", "Inc", "L.L.C", "LLC", "The")

    def parse_date_from(self, string: str, msg_date: dt.datetime
                        ) -> dt.date | None:
        """ 
        :param string: str, text that might contain a date
        :param msg_date: dt.datetime, the date that an email message was sent
        :return: dt.date, the date parsed from the `string` if any; else \
            None if the string doesn't contain a recognizable date
        """
        try:
            parsed = Regextract.parse(self.EMAIL_APP_DATE, string)
            assert parsed

            if parsed["delta"] is not None and parsed["unit"] is not None:
                timedeltattrs = {parsed["delta"]: float(parsed["unit"])}
                time_since_app = dt.timedelta(**timedeltattrs)
                return (msg_date - time_since_app).date()

            elif parsed["date"] is not None:
                for dtformat in self.APP_DATE_FORMATS:
                    try:
                        return dt.datetime.strptime(parsed["date"],
                                                    dtformat).date()
                    except DATA_ERRORS:
                        pass
        except (AssertionError, TypeError, ValueError):
            pass

    def parse_subject_of_email(self, msg: EmailMessage
                               ) -> dict[str, str | None]:
        """
        :param msg: EmailMessage, an email sent from LinkedIn noreply address
        :return: dict[str, str | None], details retrieved from subject of \
            email `msg`: the job name, the company that posted it, and/or \
            the job application status
        """
        return Regextract.parse(self.EMAIL_SUBJECT,
                                msg["Subject"].replace("\r", ""))

    @classmethod
    def shorten_company(cls, name: str, max_len: int = 24) -> str:
        """ Trim, truncate, rearrange, and abbreviate the name of a company \
            that posted a job on LinkedIn to remove unneeded details until \
            the company name fits into a maximum length requirement.

        :param name: str, the title of a company that posted a LinkedIn job
        :param max_len: int, the greatest acceptable number of characters in \
            the shortened name to return; defaults to 24
        :return: str, the shortened company name
        """
        for removable in cls.UNNEEDED:
            name = name.replace(removable, " ").strip()
        name = cls.ABBR.COMPANY.abbreviate(name, max_len)
        name, _ = Spliterator(max_len).spliterate(name.split())

        # TODO return ToString(name).truncate(max_len)?
        return name if len(name) <= max_len else name[:max_len]

    def shorten_name(self, name: str, max_len: int = 30) -> str:
        """ Trim, truncate, rearrange, and abbreviate the name of a LinkedIn \
            job posting to remove unneeded details until the name fits into a \
            maximum length requirement.

        :param name: str, the title of a LinkedIn job posting
        :param max_len: int, the greatest acceptable number of characters in \
            the shortened name to return; defaults to 30
        :return: str, the shortened LinkedIn job posting title/name
        """
        if len(name) > max_len:
            splitter = Spliterator(max_len)
            parts = [x for x in self.BOUND.split(name.strip())]
            name, title_found = splitter.spliterate(
                parts, pop_ix=0, get_target=self.TITLE.search)
            title_noun = title_found.groups()[0] if title_found else ""
            name = self.remove_from(name, max_len, but_keep=title_noun)
            name = self.ABBR.JOB.abbreviate(name, max_len)
            words = name.split()
            title_noun_pos = words.index(title_noun) + 1 if title_noun else 1
            name, _ = splitter.spliterate(words, min_parts=title_noun_pos)
            name, _ = splitter.spliterate(name.split(), pop_ix=0)
            name = self.normalize(name).strip()
            name = name.removesuffix(".").removesuffix("s")
            if len(name) > max_len:
                name = name[:name.rfind(" ", len(name) - max_len) + 1]
        return name


@weak_dataclass
class LinkedInJob(DotDict, Debuggable):
    # Input parameters without default values
    date: dt.date
    company: str
    short_company: str
    name: str
    short_name: str
    url: str

    # Attributes and input parameters with default values
    src: str = "LinkedIn"
    contact: str = "N/A"
    cols = dict(date=1, company=2, name=3, url=3, status=4, src=5, contact=6)

    status = '=let(datecell, INDIRECT("A" & TEXT(row(), "#"), TRUE), ' \
        'if(isdate(datecell),if(today()-datecell>30,"Stale","Active"),' \
        '"Not Yet"))'

    def filter_df_by_detail(self, df: DataFrame, detail: str) -> DataFrame:
        shortname = f"short_{detail}"
        details = {self[detail]}
        if shortname in self:
            details.add(self[shortname])

        new_df = df.loc[df[detail].isin(details)]
        return new_df if len(new_df.index) > 0 else df

    def toGoogleSheetsRow(self) -> list[str]:
        """
        :return: list[str] of values to insert into a Google Sheet row: \
            [date, company, hyperlink(name->url), status, src, contact]
        """
        try:
            row = [self.date, self.short_company,
                   f'=HYPERLINK("{self.url}","{self.short_name}")',
                   self.status, self.src, self.contact] if self else list()
        except DATA_ERRORS as err:
            self.debug_or_raise(err, locals())
        return row


class LinkedInJobFromMsg(LinkedInJob, FancyDict, Debuggable):
    MSG_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z (%Z)"
    REGX = LinkedInJobDetailParser()
    URL_PREFIX = "https://www.linkedin.com/jobs/view/"

    def __init__(self, msg: EmailMessage, debugging: bool = False) -> None:
        """ Instantiate LinkedInJob using the details from the message.

        :param msg: EmailMessage to extract LinkedIn job posting details from.
        :param debugging: bool, True to pause and interact on error, else \
            False to raise errors/exceptions; defaults to False.
        """
        FancyDict.__init__(self)
        Debuggable.__init__(self, debugging=debugging)
        self.update(self.REGX.parse_subject_of_email(msg))
        try:
            self.msg_date = dt.datetime.strptime(msg["Date"],
                                                 self.MSG_DATE_FORMAT)
            self.short_company = self.REGX.shorten_company(self.company)
        except (AttributeError, TypeError, ValueError) as err:
            self.debug_or_raise(err, locals())

        # Find the job application submission date in the email body
        self.body = self.get_body_of(msg)
        self.shredded = Shredder(debugging=self.debugging).shred(self.body)
        for part in self.shredded:
            app_date = self.REGX.parse_date_from(part, self.msg_date)
            if app_date is not None:
                self.date = self.correct_date(app_date)
                break

        # Find the job name, posting URL, & job status/verb in the email body
        self.found_name = False
        for link_el in self.body.find_all("a"):
            attrs: dict | None = getattr(link_el, "attrs", None)
            if attrs:
                link = attrs.get("href", None)
                if link:
                    self.get_details_from_link(link, link_el.text.strip())
            if self.has_all(keys=("name", "verb", "url"), exclude={None}):
                break
        if not self.get("name", None):
            self.debug_or_raise(ValueError("Job name not found."), locals())

        else:  # Abbreviate the job name
            self.short_name = self.REGX.shorten_name(self.name)

    def correct_date(self, job_app_date: dt.date) -> str:
        """ Correct the parsed job application date if it has issues

        :param job_app_date: dt.date, the date a LinkedIn job application \
            was submitted; verify/correct this
        :return: str, corrected and ISO-formatted `job_app_date`
        """
        today = dt.date.today()
        if job_app_date.year == 1900:  # => no year in msg; correct that
            job_app_date = job_app_date.replace(
                year=self.get("msg_date", today).year)
        if (job_app_date - today).days > 0:  # No job apps dated in future
            job_app_date = today
        return job_app_date.isoformat()  # to string: YYYY-MM-DD

    def get_details_from_link(self, url: str, text: str) -> None:
        """ Given the text and URL of a hyperlink parsed from a web object, \
            try to get the name, URL, and status of a LinkedIn job application

        :param url: str to save parts of if it's a LinkedIn job posting URL
        :param text: str to save part of if it's a LinkedIn job posting name
        """
        # If this is a LinkedIn job posting URL, then get details from it
        if "/jobs/view/" in url:
            if not self.get("url", None):  # Save job posting base URL
                self.url = URL(url).without_params()

            if text:  # If the link has text, use it to get the job name
                if not self.get("name", None):
                    self.name = text

                # The first link has the job and company names. The second
                # has only the job name. Trim the first using the second.
                elif not self.found_name:
                    if self.name.startswith(text):
                        self.name = text
                        self.found_name = True

                # Ensure job name saved from link (TODO redundant?)
                for company_name in {self.company, self.short_company}:
                    if not self.found_name and company_name in text:
                        self.name = text.split(company_name, 1)[0].strip()
                        self.found_name = True

        # Get the verb: what happened to the application? It was...
        if "rejected" in url:
            self.verb = "rejected"
        elif "viewed" in url:
            self.verb = "viewed"

    @staticmethod
    def get_body_of(msg: EmailMessage) -> BeautifulSoup:
        """ 
        :param msg: EmailMessage
        :return: bs4.BeautifulSoup, the body of the email `msg`.
        """
        # Convert EmailMessage to valid HTML body string
        msgstr = msg.as_string().replace("\r", "")
        despaced = msgstr.replace("=\n", "").replace("=3D", "=")
        start_ix = despaced.find("<body")
        end_ix = despaced.rfind("</body>") + 7  # +len("</body>")
        bodystr = despaced[start_ix:end_ix]

        # Convert HTML body string to BeautifulSoup to parse msg contents
        body = BeautifulSoup(bodystr, features="html.parser")

        # Filter out more useless whitespace from the message
        for blank_str in body.find_all(string=" "):
            blank_str.extract()  # Remove from BeautifulSoup XML element tree

        return body
