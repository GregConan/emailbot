#!/usr/bin/env python3

"""
Greg Conan: gregmconan@gmail.com
Created: 2025-02-12
Updated: 2025-02-12
"""
# Import standard libraries
from typing import Any, Callable, Dict, Hashable, Iterable, List, Mapping

# Import third-party PyPI libraries
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as Expect


class LinkedInBot(webdriver.Firefox):  # , Debuggable):

    def when_ready_click(self, select_by: str, select_value: Any,
                         wait: WebDriverWait) -> WebElement:
        return wait.until(Expect.element_to_be_clickable((select_by,
                                                          select_value)))

    def login(self, username: str, password: str):
        wait = WebDriverWait(self, 30)

        self.get("http://www.linkedin.com/login")
        self.when_ready_click(By.ID, "username", wait).send_keys(username)
        self.when_ready_click(By.ID, "password", wait).send_keys(password)

        wait.until(Expect.element_to_be_clickable((
            By.CSS_SELECTOR, "button[type=submit]"))).click()
        # self.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
        # wait.until(Expect.element_to_be_clickable((By.XPATH, "//button[text()='Sign in']"))).click()
        print("Logged in")
