
#!/usr/bin/env python3

"""
Lower-level utilities & convenience functions for multiple emailbot files' use
Overlaps significantly with:
    Knower/utilities.py, audit-ABCC/src/utilities.py, \
    abcd-bids-tfmri-pipeline/src/pipeline_utilities.py, etc.
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2025-01-24
"""
# Import standard libraries
import datetime as dt
import logging
import pdb
from typing import (Any, Callable, Dict, Hashable, Iterable, List, Mapping)

# Constants
try:
    from constants import LOGGER_NAME
    from emailbot.seq import stringify_list, uniqs_in, Xray
except ModuleNotFoundError:
    from emailbot.constants import LOGGER_NAME
    from emailbot.seq import stringify_list, uniqs_in, Xray


# NOTE All classes and functions below are in alphabetical order.


def debug(an_err: Exception, local_vars: Mapping[str, Any]) -> None:
    """
    :param an_err: Exception (any)
    :param local_vars: Dict[str, Any] mapping variables' names to their \
                       values; locals() called from where an_err originated
    """
    locals().update(local_vars)
    logger = logging.getLogger(LOGGER_NAME)
    logger.exception(an_err)
    try:
        print(Xray(locals(), list_its="Local variables"))
    except:
        pass
    # show_keys_in(locals(), level=logger.level)
    pdb.set_trace()
    pass


class Debuggable:
    """I put the debugger function in a class so it can use its \
    implementer classes' self.debugging variable."""

    def debug_or_raise(self, an_err: Exception, local_vars: Mapping[str, Any]
                       ) -> None:
        """
        :param an_err: Exception (any)
        :param local_vars: Dict[str, Any] mapping variables' names to their \
                           values; locals() called from where an_err originated
        :raises an_err: if self.debugging is False; otherwise pause to debug
        """
        if self.debugging:
            debug(an_err, local_vars)
        else:
            raise an_err


# TODO Replace "print()" calls with "log()" calls after making log calls
#      display in the Debug Console window when running pytest tests
def log(content: str, level: int = logging.INFO,
        logger_name: str = LOGGER_NAME) -> None:
    """
    :param content: String, the message to log/display
    :param level: int, the message's importance/urgency/severity level as \
                  defined by logging module's 0 (ignore) to 50 (urgent) scale
    """
    logging.getLogger(logger_name).log(msg=content, level=level)


def noop(*_args: Any, **_kwargs: Any) -> None:
    """Do nothing. Convenient to use as a default callable function parameter.

    :return: None
    """
    pass  # or `...`


def show_keys_in(a_dict: Mapping[str, Any],  # show: Callable = print,
                 what_keys_are: str = "Local variables",
                 level: int = logging.INFO,
                 logger_name: str = LOGGER_NAME) -> None:
    """
    :param a_dict: Dictionary mapping strings to anything
    :param log: Function to log/print text, e.g. logger.info or print
    :param what_keys_are: String naming what the keys are
    """
    log(f"{what_keys_are}: {stringify_list(uniqs_in(a_dict))}", level=level,
        logger_name=logger_name)


class ShowTimeTaken:
    """Context manager to time and log the duration of any block of code."""

    # Explicitly defining __call__ as a no-op to prevent instantiation.
    __call__ = noop

    def __init__(self, doing_what: str, show: Callable = print) -> None:
        """
        :param doing_what: String describing what is being timed
        :param show: Function to print/log/show messages to the user
        """  # TODO Use "log" instead of "print" by default?
        self.doing_what = doing_what
        self.show = show

    def __enter__(self):
        """Log the moment that script execution enters the context manager \
        and what it is about to do.
        """
        self.start = dt.datetime.now()
        self.show(f"Started {self.doing_what} at {self.start}")
        return self

    def __exit__(self, exc_type: type | None = None,
                 exc_val: BaseException | None = None, exc_tb=None):
        """Log the moment that script execution exits the context manager \
        and what it just finished doing.

        :param exc_type: Exception type
        :param exc_val: Exception value
        :param exc_tb: Exception traceback
        """
        self.elapsed = dt.datetime.now() - self.start
        self.show(f"\nTime elapsed {self.doing_what}: {self.elapsed}")
