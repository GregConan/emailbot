#!/usr/bin/env python3

"""
Nonfunctional WIP of a job app bot. 
Greg Conan: gregmconan@gmail.com
Created: 2025-02-12
Updated: 2026-05-03
"""
# Import standard libraries
import pdb
import re
import sys
from typing import Any, Callable, Iterable, Mapping, Self

# Import Selenium library
# from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.proxy import Proxy
from selenium.webdriver.firefox.webdriver import WebDriver  # as FirefoxDriver
# from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as Expect
from selenium.webdriver.support.ui import WebDriverWait

# Import other third-party PyPI libraries
import html_to_markdown as html2md
from webdriver_manager.firefox import GeckoDriverManager

# Import remote custom libraries
from gconanpy.access.nested import Xray
from gconanpy.debug import Debuggable
from gconanpy.IO.local import save_to_json
from gconanpy.IO.web import URL
# from gconanpy.IO.web import extract_params_from_url
from gconanpy.reg import compress
from gconanpy.strings import FancyString


# Import local constants
try:
    from emailbot.constants import LINKEDIN_SEARCH
except ModuleNotFoundError:
    from constants import LINKEDIN_SEARCH


class LinkedInBot(WebDriver, Debuggable):
    def __init__(self, debugging: bool = False,
                 from_file_at: str | None = None, keep_alive: bool = True,
                 options: FirefoxOptions | None = None,
                 ff_service: FirefoxService | None = None,
                 out_dir_path: str | None = None) -> None:
        self.debugging = debugging
        self.out_dir = out_dir_path
        out_log = sys.stdout if debugging else None  # TODO add to FFOptions?
        if from_file_at:
            pass  # TODO
        else:
            # NOTE interestingly, calling locals() before instantiation
            # raises AttributeError because self.__repr__ assumes that
            # .session_id is already defined

            # new_gecko = GeckoDriverManager().install()
            if not ff_service:
                new_gecko = GeckoDriverManager().install()
                ff_service = FirefoxService(new_gecko, log_output=out_log)
            # ff_service = FirefoxService(FF_BIN, log_output=out_log)  # new_gecko,

            # pdb.set_trace()
            super().__init__(options=options, service=ff_service,
                             keep_alive=keep_alive)

            self.wait = WebDriverWait(self, 30)

    @classmethod
    def from_file_at(cls, fpath: str, debugging: bool = False,
                     out_dir_path: str | None = None):  # Self:
        # super(Debuggable).__init__()  # TODO ?
        pdb.set_trace()
        pass  # TODO

    def get_job_details_of(self, job_details: WebElement
                           ):  # -> dict[str, Any]:
        pdb.set_trace()
        pass  # TODO

    def get_job_desc(self) -> str | None:
        outfpath = None

        # Get "About the job" h2 element, which has the job desc after it
        job_desc_header = None
        for header2 in self.find_elements(By.TAG_NAME, "h2"):
            if header2.text.strip() == "About the job":
                job_desc_header = header2

        # Find the element containing the whole job description by iteratively
        # getting parents of title until one of them has text besides the title
        if job_desc_header is not None:
            parent = job_desc_header
            while parent.text.strip() == "About the job":
                parent = parent.find_element(By.XPATH, "..")

            # Step down into job description text to get the description
            job_desc_el = parent.find_element(By.TAG_NAME, "p")
            job_desc_html = job_desc_el.get_attribute("outerHTML")

            # Convert job description HTML to Markdown, then save it to .md 
            if job_desc_html:
                converted = html2md.convert(job_desc_html)["content"]
                if converted:
                    job_desc_md = compress(converted)
                    print(job_desc_md)
                    jobID = URL(self.current_url).params["currentJobId"][0]
                    outfpath = FancyString.filepath(
                        self.out_dir if self.out_dir else ".",
                        f"job-desc-{jobID}", ".md", put_date_after="_")
                    written = 0
                    with open(outfpath, "w+") as outfile:
                        written = outfile.write(job_desc_md)
                    if written == 0:
                        outfpath = None

        return outfpath


    def iterate_jobs_at(self, linkedin_search_URL: str = LINKEDIN_SEARCH):
        
        WebDriverWait(self, 1)  # Wait to avoid seeming automated?
        self.get(linkedin_search_URL)
        WebDriverWait(self, 1)  # Wait to avoid seeming automated?

        # Save entire HTML source document into local text file for testing
        if self.debugging:
            src_fpath = self.save_source_code()

        job_descs = [self.get_job_desc()]
        # TODO ITERATE MORE JOBS


    def login(self, username: str, password: str):

        self.get("http://www.linkedin.com/login")
        self.wait.until(Expect.visibility_of_element_located(
            (By.ID, "username"))).send_keys(username)
        # self.when_ready_click(By.ID, "username").send_keys(username)
        self.when_ready_click(By.ID, "password").send_keys(password)

        self.when_ready_click(By.CSS_SELECTOR, "button[type=submit]").click()
        # self.wait.until(Expect.element_to_be_clickable((By.CSS_SELECTOR, "button[type=submit]"))).click()
        # self.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
        # wait.until(Expect.element_to_be_clickable((By.XPATH, "//button[text()='Sign in']"))).click()
        if self.debugging:
            print("Logged in")
        # save_to_json(self.get_cookies(), )  # TODO

    def save_cookies_to(self, fpath: str) -> None:
        """ Get and store cookies after login, then store them in a file

        :param fpath: str, _description_
        """
        save_to_json(self.get_cookies(), fpath)

    def save_source_code(self, dir_path: str | None = None,
                         file_name: str | None = None) -> str | None:
        """ Save entire HTML source document into local text file for testing

        :param dir_path: str | None, valid path to existing local directory\
                         to write a new text file into containing the page's\
                         HTML code; if not provided, this will be self.out_dir
        :param file_name: str | None, name of the text file to write the\
                          current page's entire HTML source code into. By\
                          default, this will be generated from the URL and\
                          the current date/time.
        :return: str | None, either the full path to the new file written and\
                 saved successfully, or None if the operation failed
        """
        try:  # Write the page's HTML source code contents into new HTML file
            path = FancyString.filepath(
                dir_path if dir_path else self.out_dir,  # type: ignore  # TODO
                file_name if file_name else self.current_url,
                ".html", put_date_after="_")
            with open(path, "w+") as outfile:
                outfile.write(self.page_source)
            return path  # Return path to new HTML file

        # If the process fails, then either pause to debug or return None
        except (AttributeError, OSError, TypeError, ValueError) as e:
            if self.debugging:
                self.debug_or_raise(e, locals())
            else:
                pass  # return None

    def save_timestamped_screenshot(self, dirpath: str | None = None) -> str | None:
        """ Save a full page screenshot .png file into an output directory.
        Include the screenshot date and time in the file name.

        :param dirpath: str | None, valid path to existing local directory to\
                        save screenshot file into; defaults to self.out_dir
        :return: str | None, full path to new screenshot file if it was\
                 successfully created; else None if it wasn't
        """
        if not dirpath:
            dirpath = self.out_dir
        fname = f"{__class__.__name__} screenshot "
        fpath = FancyString.filepath(
            dirpath,  # type: ignore  # TODO
            fname, ".png", put_date_after=" ")
        return fpath if self.save_full_page_screenshot(fpath) else None

    def when_ready_click(self, select_by: str, select_value: Any
                         ) -> WebElement:  # , wait: WebDriverWait
        return self.wait.until(Expect.element_to_be_clickable(
            (select_by, select_value)))
