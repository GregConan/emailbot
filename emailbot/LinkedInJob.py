#!/usr/bin/env python3

"""
Class to insert a row with LinkedIn job application details into a \
    Google Sheets spreadsheet
Greg Conan: gregmconan@gmail.com
Created: 2025-03-16
Updated: 2025-03-18
"""
# Import standard libraries
import datetime as dt
from email.message import EmailMessage
import pdb
import re
from typing import Any, Callable, Iterable, Mapping

# Import third-party PyPI libraries
import bs4

# Import remote custom libraries
from gconanpy.dissectors import Peeler, Whittler, Xray
from gconanpy.maps import DotDict


class LinkedInJobNameRegex(list[re.Pattern]):
    # Non-word symbols at the beginning or end of the string, to remove
    START = re.compile(r"^[^\w\(]+")
    END = re.compile(r"[^\w\)]+$")

    # Slash symbols: remove any spaces before and after
    SLASH = re.compile(r"\s*\/\s*")

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

    def __init__(self):
        # Get the job title noun (that all other words in the title modify)
        JOBS = self._OR("Dev", "Eng", "Analy", "Scientist",
                        "Consultant", "Architect", "Programmer")
        self.TITLE = re.compile(r"((?:" + JOBS + r")(?:[a-z])*)")

        super().__init__(self.build_pattern(term) for term in self.TERMS)

    @staticmethod
    def _OR(*args: str) -> str:
        return r"|".join(args)

    @classmethod
    def build_pattern(cls, term: str) -> re.Pattern:
        return re.compile(f"{cls.SPECIAL}{cls.SEP}(?:{term})+", re.IGNORECASE)

    @classmethod
    def normalize(cls, a_str: str) -> str:
        return cls.END.sub("", cls.START.sub("", cls.SLASH.sub("/", a_str)))


class LinkedInJob:
    ABBR = DotDict(COMPANY=(("Technology", "Tech"),
                            ("Solution", "Soln")),
                   JOB=(("Senior", "Sr"),))
    APP_DATE_PREFIX = "Applied on "
    FORMULAS = {"status": ('=if(isdate(A2),if(today()-A2>30,'
                           '"Stale","Active"),"Not Yet")')}  # "date": "=TODAY()"}
    MAIL_SUBJECT = "your application was sent to "
    REGX = LinkedInJobNameRegex()
    UNNEEDED = (", Inc.", "Inc", "L.L.C", "LLC", "The")
    URL_PREFIX = "https://www.linkedin.com/jobs/view/"

    def __init__(self, company: str, name: str, url: str,
                 src: str = "LinkedIn", contact: str = "N/A",
                 applied_on: dt.date | None = None):
        self.company: str = company
        self.contact: str = contact
        self.date: str = applied_on.isoformat() if applied_on \
            else self.FORMULAS["date"]
        self.name: str = name
        self.src: str = src
        self.url: str = url

    @staticmethod
    def make_name_len_checker(max_len: int) -> Callable[[str], bool]:
        def is_too_long(name: str) -> bool:
            return len(name) > max_len
        return is_too_long

    @classmethod
    def shorten_company(cls, entire_name: str, max_len: int = 24) -> str:
        is_too_long = cls.make_name_len_checker(max_len)
        name = Whittler.whittle(entire_name.strip(), cls.UNNEEDED,
                                str.replace, is_too_long, [" "])
        name = Whittler.whittle(name, cls.ABBR.COMPANY, lambda x, pair:
                                str.replace(x, *pair).strip(), is_too_long)
        name, _ = Whittler.pop(name.split(), is_too_long)
        return name[:max_len] if is_too_long(name) else name

    @classmethod
    def shorten_name(cls, entire_name: str, max_len: int = 30) -> str:
        is_too_long = cls.make_name_len_checker(max_len)
        name = entire_name
        parts = [x for x in cls.REGX.BOUND.split(name.strip())]
        name, title_found = Whittler.pop(parts, is_too_long, 0,
                                         cls.REGX.TITLE.search)
        title_noun = title_found.groups()[0] if title_found else None

        name = Whittler.whittle(
            name, cls.REGX, lambda x, regx: regx.sub("", x), is_too_long,
            is_viable=lambda y: y and (not title_noun or title_noun in y))

        for shortenings in cls.ABBR.values():
            name = Whittler.whittle(name, shortenings, lambda x, pair:
                                    str.replace(x, *pair).strip(),
                                    is_too_long)

        words = name.split()
        title_noun_pos = words.index(title_noun) + 1 if title_noun else 1
        name, _ = Whittler.pop(words, is_too_long, min_len=title_noun_pos)
        name, _ = Whittler.pop(name.split(), is_too_long, pop_ix=0)
        name = cls.REGX.normalize(name).strip().removesuffix("s")

        return name[:name.rfind(" ", len(name) - max_len) + 1] \
            if is_too_long(name) else name

    def toGoogleSheetsRow(self) -> list[str]:
        """
        :return: list[str] of values to insert into a Google Sheet row.
        """
        return [self.date, self.shorten_company(self.company),
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
        body = bs4.BeautifulSoup(bodystr, features="html.parser")

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
            raise ValueError("Couldn't find job URL in the message")

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
        if job_app_date:
            if (job_app_date - dt.date.today()).days > 0:
                job_app_date = dt.date.today()  # cls.FORMULAS["date"]
        else:
            raise ValueError("Couldn't find job application date in message")

        # Instantiate LinkedInJob using the details from the message
        job_name = str.split(job_el.text, company, 1)[0].strip()
        return LinkedInJob(company=company, name=job_name,
                           url=job_URL.split('?', 1)[0],
                           applied_on=job_app_date)
