#!/usr/bin/env python3

"""
Greg Conan: gregmconan@gmail.com
Created: 2025-02-12
Updated: 2025-03-13
"""
# Import standard libraries
import pdb
import sys
from typing import Any, Callable, Dict, Iterable, List, Mapping

# Import Selenium library
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.proxy import Proxy
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as Expect
from selenium.webdriver.support.ui import WebDriverWait

# Import other third-party PyPI libraries
from webdriver_manager.firefox import GeckoDriverManager

# Import remote custom libraries
from gconanpy.debug import Debuggable
from gconanpy.dissectors import Xray
from gconanpy.io.local import save_to_json
from gconanpy.io.web import extract_params_from_url
from gconanpy.seq import to_file_path

# Import local constants
try:
    from constants import FF_BIN, LINKEDIN_SEARCH
except ModuleNotFoundError:
    from emailbot.constants import FF_BIN, LINKEDIN_SEARCH


class FFOptions(FirefoxOptions):  # TODO Use FirefoxCapabilities instead?
    def __init__(self, *arguments: Any,
                 binary_location: str | None = FF_BIN,
                 headless: bool = True, log_level: Any = None,
                 profile_dir: str | None = None,
                 proxy: Proxy | None = None,
                 **preferences: Any) -> None:
        super().__init__()

        for arg in arguments:
            self.add_argument(arg)

        if binary_location:
            self.binary_location = binary_location

        self.headless = headless
        if headless:
            self.add_argument("-headless")  # Belt & suspenders

        if log_level:
            self.log.level = log_level

        if profile_dir:
            self.profile = webdriver.FirefoxProfile(profile_dir)
            # self.add_argument("-profile")  # Belt & suspenders
            # self.add_argument(profile_dir)

        if proxy:
            self.proxy = proxy

        for name, value in preferences.items():
            self.set_preference(name, value)


class LinkedInBot(webdriver.Firefox, Debuggable):
    def __init__(self, debugging: bool = False,
                 from_file_at: str | None = None, keep_alive: bool = True,
                 options: FirefoxOptions = FFOptions(),
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
            # ff_service = FirefoxService(FF_BIN, log_output=out_log)  # new_gecko,

            pdb.set_trace()
            super().__init__(options=options,  # service=ff_service,
                             keep_alive=keep_alive)

            self.wait = WebDriverWait(self, 30)

    @classmethod
    def from_file_at(cls, fpath: str, debugging: bool = False,
                     out_dir_path: str | None = None) -> "LinkedInBot":
        super(Debuggable).__init__()  # TODO ?
        pdb.set_trace()
        pass  # TODO

    def get_job_details_of(self, job_details: WebElement) -> Dict[str, Any]:
        pdb.set_trace()
        pass  # TODO

    def iterate_jobs_at(self, linkedin_search_URL: str = LINKEDIN_SEARCH):
        self.get(linkedin_search_URL)
        self.wait.until(Expect.visibility_of_element_located("job-details"))

        # Save entire HTML source document into local text file for testing
        if self.debugging:
            src_fpath = self.save_source_code()
            pdb.set_trace()

        job_cards = self.find_elements(By.CSS_SELECTOR, "div[data-job-id]")
        for job_card in job_cards:
            # TODO If the card isn't for the displayed job, click the card
            card_job_ID = job_card.get_dom_attribute('data-job-id')
            # url_params = extract_params_from_url(linkedin_search_URL)
            # url_job_ID = linkedin_search_URL[""]

            job_details = self.find_element(
                by=By.CLASS_NAME, value="jobs-details__main-content")

            # Once the card is clicked, get key details from job description
            self.get_job_details_of(job_details)  # TODO

    def login(self, username: str, password: str):

        self.get("http://www.linkedin.com/login")
        self.when_ready_click(By.ID, "username").send_keys(username)
        self.when_ready_click(By.ID, "password").send_keys(password)

        self.wait.until(Expect.element_to_be_clickable((
            By.CSS_SELECTOR, "button[type=submit]"))).click()
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
            path = to_file_path(dir_path if dir_path else self.out_dir,
                                file_name if file_name else self.current_url,
                                ".html", put_dt_after="_")
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
        fpath = to_file_path(dirpath, fname, ".png", put_dt_after=" ")
        return fpath if self.save_full_page_screenshot(fpath) else None

    def when_ready_click(self, select_by: str, select_value: Any
                         ) -> WebElement:  # , wait: WebDriverWait
        return self.wait.until(Expect.element_to_be_clickable(
            (select_by, select_value)))
