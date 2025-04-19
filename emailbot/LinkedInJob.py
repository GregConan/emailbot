#!/usr/bin/env python3

"""
Class to insert a row with LinkedIn job application details into a \
    Google Sheets spreadsheet
Greg Conan: gregmconan@gmail.com
Created: 2025-03-16
Updated: 2025-04-16
"""
# Import standard libraries
from collections import namedtuple
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import datetime as dt
from email.message import EmailMessage
import pdb
import re
from typing import Any

# Import third-party PyPI libraries
import bs4

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.dissectors import Shredder, Xray
from gconanpy.find import modifind, ReadyChecker, spliterate
from gconanpy.IO.web import URL
from gconanpy.maps import DotDict, LazyDotDict
from gconanpy.metafunc import DATA_ERRORS, nameof
from gconanpy.seq import stringify_map


class LinkedInJobNameRegex(list[re.Pattern]):
    # Non-word symbols at the beginning or end of the string, to remove
    START = re.compile(r"^[^\w\(]+")
    END = re.compile(r"[^\w\)]+$")

    # Slash symbols: remove any spaces before and after
    SLASH = re.compile(r"\s*\/\s*")

    _OR = r"|".join

    # Symbols delimiting sections of string: -,:;/@()
    BOUND = re.compile(r"\s*[-,:;@\(\)]+\s*")

    # LinkedIn automated (noreply) job app email strings:
    EMAIL = {k: re.compile(v) for k, v in dict.items(dict(

        # Rejection message in email body
        REJECT=(r"(?:Thank you for your interest in the )(?P<name>.*)"
                r"(?: position .*)(?:at|by)\s(?P<company>(?:(?!in).)*)"
                r"(?: [^\.]+)*(?: [^\.]+)*(?:\. Unfortunately, we "
                r"[\S]+ not.*your application)"),

        # Email subject line
        SUBJECT=(r"(?:[Yy]ou(?:r application )?)(?:(?:was)?\s+"
                 r"(?P<verb>[\S]*)\s+)*(?:to|by|for)+\s*(?:"
                 r"(?P<name>.*?)\s+(?:at)\s+)*(?P<company>.*)")
    ))}

    # Job title noun that all other words in the title modify
    TITLES = _OR(("Dev", "Eng", "Analy", "Scientist", "Consultant",
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

    @classmethod
    def email_parse(cls, to_search: str, to_find: str) -> dict[str, str | None]:
        parsed = cls.EMAIL[to_find.upper()].search(to_search)
        return parsed.groupdict(default=None) if parsed else dict()


# Job = namedtuple("Job", "date company name URL src contact")
@dataclass
class LinkedInJob(LazyDotDict, Debuggable):
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
    status = '=if(isdate(A2),if(today()-A2>30,"Stale","Active"),"Not Yet")'

    def toGoogleSheetsRow(self) -> list[str]:
        """
        :return: list[str] of values to insert into a Google Sheet row: \
            [date, company, name+url, status, src, contact]
        """
        try:
            return [self.date, self.short_company,
                    f'=HYPERLINK("{self.url}","{self.short_name}")',
                    self.status, self.src, self.contact] if self else list()
        except DATA_ERRORS as err:
            self.debug_or_raise(err, locals())


class LinkedInJobFromMsg(LinkedInJob):
    ABBR = DotDict(COMPANY=(("Technology", "Tech"),
                            ("Solution", "Soln")),
                   JOB=(("Senior", "Sr"), ("Junior", "Jr")))
    APP_DATE_PREFIX = "Applied on "
    APP_DATE_FORMATS = ("%B %d, %Y", "%b %d", "%b %d, %Y", "%B %d")
    MSG_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %z (%Z)"
    REGX = LinkedInJobNameRegex()
    UNNEEDED = (", Inc.", "Inc", "L.L.C", "LLC", "The")
    URL_PREFIX = "https://www.linkedin.com/jobs/view/"

    def __init__(self, msg: EmailMessage, debugging: bool = False) -> None:
        LazyDotDict.__init__(self)
        errs = (AttributeError, TypeError, ValueError)
        self.debugging = debugging
        self.update(self.REGX.email_parse(msg["Subject"], "SUBJECT"))
        try:
            self.msg_date = dt.datetime.strptime(msg["Date"],
                                                 self.MSG_DATE_FORMAT)
        except (TypeError, ValueError) as err:
            self.debug_or_raise(err, locals())
        if "company" in self:
            self.body = self.get_body_of(msg)
            self.shredded = Shredder(debugging=self.debugging
                                     ).shred(self.body)
            self.date = self.get_date_from_body()

            iterlinks = iter(self.body.find_all("a"))
            link_el = next(iterlinks, None)
            while None in {self.get("verb", None), self.get("url", None)
                           } and link_el is not None:
                try:
                    # link_txt = link_el.get_text(strip=True)
                    # if link_txt:
                    link = link_el.attrs.get("href", None)
                    if link:
                        if "/jobs/view/" in link:
                            self.url = URL(link).without_params()
                        if "rejected" in link:
                            self.verb = "rejected"
                        elif "viewed" in link:
                            self.verb = "viewed"
                except AttributeError:
                    pass

                link_el = next(iterlinks, None)

            if not self.get("name", None):
                self.name = self.get_name_from(link_el)

            try:
                for detail in ("name", "company"):
                    self.lazysetdefault(f"short_{detail}",
                                        getattr(self, f"shorten_{detail}"),
                                        [self[detail]]),
            except (AttributeError, TypeError, ValueError) as err:
                self.debug_or_raise(err, locals())

            # TODO Only iterate over the body/shredded once?

    @staticmethod
    def get_body_of(msg: EmailMessage) -> bs4.BeautifulSoup:

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

        return body

    def get_date_from_body(self) -> str | None:
        """ Parse message to get the job application submission date 

        :return: str | None, _description_
        """
        # body: bs4.BeautifulSoup): # flattened: list):
        # self.lazysetdefault("flattened", Peeler.peel, [body])
        # self.flattened = Peeler.peel(self.body)
        job_app_date = modifind(find_in=self.shredded,
                                modify=self.get_date_from_el)
        if job_app_date:

            # Correct job app date if it has issues
            today = dt.date.today()
            if job_app_date.year == 1900:  # => no year in msg; correct that
                job_app_date = job_app_date.replace(
                    year=self.get("msg_date", today).year)
            if (job_app_date - today).days > 0:  # No job apps dated in future
                job_app_date = today  # cls.FORMULAS["date"]
            job_app_date = job_app_date.isoformat()  # to string: YYYY-MM-DD
        return job_app_date

    @classmethod
    def get_date_from_el(cls, date_el: Any) -> dt.date | None:
        try:
            txt_part = bs4.Tag.get_text(date_el, strip=True)
        except AttributeError:  # , TypeError): # ?
            txt_part = str(date_el)
        try:
            datesplit = str.split(txt_part, cls.APP_DATE_PREFIX)
            return None if len(datesplit) < 2 else modifind(
                find_in=cls.APP_DATE_FORMATS,
                modify=lambda x: dt.datetime.strptime(datesplit[1], x).date()
            )
        except (TypeError, ValueError) as err:
            pdb.set_trace()
            print()

    def get_name_from(self, job_link_el: bs4.PageElement) -> str:
        # Instantiate LinkedInJob using the details from the message
        return str.split(job_link_el.text, self.company, 1)[0].strip()

    @staticmethod
    def has_job_URL(link_el: bs4.Tag):
        return link_el.get_text(strip=True) and \
            "/jobs/view/" in link_el.attrs["href"]

    @staticmethod
    def make_name_len_checker(max_len: int) -> Callable[[str], bool]:
        def is_short_enough(name: str) -> bool:
            return max_len > len(name)
        return is_short_enough

    @classmethod
    def shorten_company(cls, entire_name: str, max_len: int = 24) -> str:
        is_short_enough = cls.make_name_len_checker(max_len)
        name = entire_name
        if not is_short_enough(name):
            with ReadyChecker(to_check=name.strip(), iter_over=cls.UNNEEDED,
                              ready_if=is_short_enough) as check:
                while check.is_not_ready():
                    check(str.replace(check.to_check, next(check), " "
                                      ).strip())
            name = cls.check_name(to_check=check.to_check.strip(),
                                  iter_over=cls.ABBR.COMPANY,
                                  ready_if=is_short_enough)
            name, _ = spliterate(parts=name.split(), ready_if=is_short_enough)
        # TODO seq.truncate
        return name if is_short_enough(name) else name[:max_len]

    @classmethod
    def shorten_name(cls, entire_name: str, max_len: int = 30) -> str:
        is_short_enough = cls.make_name_len_checker(max_len)
        name = entire_name
        if not is_short_enough(name):
            parts = [x for x in cls.REGX.BOUND.split(name.strip())]
            name, title_found = spliterate(
                parts=parts, ready_if=is_short_enough, pop_ix=0,
                get_target=cls.REGX.TITLE.search)
            title_noun = title_found.groups()[0] if title_found else None
            item = None
            with ReadyChecker(to_check=name, iter_over=cls.REGX,
                              ready_if=is_short_enough) as check:
                while check.is_not_ready():
                    prev = item
                    item = next(check).sub("", check.to_check)
                    check(item if item and (not title_noun or title_noun in
                                            item) else prev)

            for shortenings in cls.ABBR.values():
                name = cls.check_name(to_check=name, iter_over=shortenings,
                                      ready_if=is_short_enough)

            words = name.split()
            title_noun_pos = words.index(title_noun) + 1 if title_noun else 1
            name, _ = spliterate(parts=words, ready_if=is_short_enough,
                                 min_len=title_noun_pos)
            name, _ = spliterate(parts=name.split(), ready_if=is_short_enough,
                                 pop_ix=0)
            name = cls.REGX.normalize(name).strip()
            name = name.removesuffix("s").removesuffix(".")
        return name if is_short_enough(name) else \
            name[:name.rfind(" ", len(name) - max_len) + 1]

    @staticmethod
    def check_name(to_check: str, iter_over: Iterable[tuple[str, str]],
                   ready_if: Callable[[str], bool]) -> str:
        with ReadyChecker(to_check, iter_over, ready_if) as check:
            while check.is_not_ready():
                pair = next(check)
                check(str.replace(check.to_check, *pair).strip())
        return check.to_check
