
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
import json
import logging
import os
import pdb
from string import Template
import sys
from typing import (Any, Callable, Dict, Hashable, Iterable, List,
                    Mapping, Optional, SupportsBytes, Tuple)

# Constants
LOGGER_NAME = __name__


# NOTE All classes and functions below are in alphabetical order.


def as_HTTPS_URL(*parts: str, **url_params: Any) -> str:
    """Reusable convenience function to build HTTPS URL strings.

    :param parts: Iterable[str] of slash-separated URL path parts
    :param url_params: Mapping[str, Any] of variable names and their values \
                       to pass to the API endpoint as parameters
    :return: str, full HTTPS URL path
    """
    str_params = [f"{k}={v}" for k, v in url_params.items()]
    url = f"https://{'/'.join(parts)}"
    if str_params:
        url += "?" + "&".join(str_params)
    return url


class Bytesifier:
    """Class with a method to convert objects into bytes without knowing \
    what type those things are."""

    def __init__(self, **defaults):
        """
        :param defaults: Dict[str, Any], default values for required keyword \
                         arguments in methods to convert things to bytes
        """
        self.defaults = dict(encoding="utf-8", length=1,
                             byteorder="big", signed=False)
        self.defaults.update(defaults)

    def can_bytesify(self, an_object: Any) -> bool:
        """
        :return: bool, True if self.bytesify(an_object) will work, else \
                       False if it will raise an exception
        """
        return hasattr(an_object, "encode") or hasattr(an_object, "to_bytes")

    def bytesify(self, an_object: SupportsBytes, **kwargs) -> bytes:
        """
        :param an_object: SupportsBytes, something to convert to bytes
        :raises TypeError: if an_object has no 'to_bytes' or 'encode' method
        :return: bytes, an_object converted to bytes
        """
        if hasattr(an_object, "encode"):
            kwargs.setdefault("encoding", "utf-8")
            result = an_object.encode(**kwargs)
        elif hasattr(an_object, "to_bytes"):
            kwargs.setdefault("length", 1)
            kwargs.setdefault("byteorder", "big")
            kwargs.setdefault("signed", False)
            result = an_object.to_bytes(**kwargs)
        else:
            raise TypeError(f"Cannot convert {an_object} to bytes")
        return result


def debug(an_err: Exception, local_vars: Mapping[str, Any]) -> None:
    """
    :param an_err: Exception (any)
    :param local_vars: Dict[str, Any] mapping variables' names to their \
                       values; locals() called from where an_err originated
    """
    locals().update(local_vars)
    logger = logging.getLogger(LOGGER_NAME)
    logger.exception(an_err)
    show_keys_in(locals(), level=logger.level)
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


def default_pop(poppable: Any, key: Any = None,
                default: Any = None) -> Any:
    """
    :param poppable: Any object which implements the .pop() method
    :param key: Input parameter for .pop(), or None to call with no parameters
    :param default: Object to return if running .pop() raises an error
    :return: Object popped from poppable.pop(key), if any; otherwise default
    """
    try:
        to_return = poppable.pop() if key is None else poppable.pop(key)
    except (AttributeError, IndexError, KeyError):
        to_return = default
    return to_return


def extract_from_json(json_path: str) -> dict:
    """
    :param json_path: str, a valid path to a real readable .json file
    :return: dict, the contents of the file at json_path
    """
    with open(json_path) as infile:
        return json.load(infile)


def is_peelable(an_obj: Any) -> bool:
    result = False
    # return isinstance(an_obj, Iterable) and not isinstance(an_obj, Hashable)
    if isinstance(an_obj, Iterable):
        primitivity = [hasattr(an_obj, "__mod__"),  # ONLY in primitives
                       not hasattr(an_obj, "__class_getitem__"),  # NOT in them
                       isinstance(an_obj, Hashable)]
        result = primitivity.count(True) < 2
    return result


def load_template_from(txt_file_path: str) -> Template:
    """
    :param txt_file_path: str, valid path to readable .txt file
    :return: string.Template loaded from the file at txt_file_path
    """
    with open(txt_file_path) as infile:
        return Template(infile.read())


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


def peel(to_peel: Iterable) -> Any:  # , maxdepth: int | None = None
    max_len = 3
    while is_peelable(to_peel) and len(to_peel) < max_len:
        match len(to_peel):
            case 1:
                try:
                    _, to_peel = to_peel.popitem()
                except AttributeError:
                    to_peel = next(iter(to_peel))
            case 2:
                try:
                    # can_peel = [is_peelable(to_peel[ix]) for ix in range(len(to_peel))]
                    can_peel = [is_peelable(to_peel[0]),
                                is_peelable(to_peel[1])]
                    if can_peel[0] != can_peel[1]:
                        to_peel = to_peel[0 if can_peel[0] else 1]
                    else:
                        to_peel = to_peel[0 if len(to_peel[0])
                                          > len(to_peel[1]) else 1]
                except KeyError:
                    max_len = 2  # Only peel a len < 2 Mapping
            case _:
                pass  # If len > 3 then stop peeling
    return to_peel


def print_keys_in(a_dict: Mapping, what_keys_are: str = "Local variables"
                  ) -> None:
    """
    :param a_dict: Dictionary mapping strings to anything
    :param what_keys_are: String naming what the keys are
    """
    print(f"{what_keys_are}: {stringify_list(uniqs_in(a_dict))}")


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


def stringify_list(a_list: List[Any]) -> str:
    """
    :param a_list: List[Any]
    :return: String containing all items in a_list, single-quoted and \
             comma-separated if there are multiple
    """
    result = ""
    if a_list and isinstance(a_list, list):
        list_with_str_els = [str(el) for el in a_list]
        if len(a_list) > 1:
            result = "'{}'".format("', '".join(list_with_str_els))
        else:
            result = list_with_str_els[0]
    return result


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

    def __exit__(self, exc_type: Optional[type] = None,
                 exc_val: Optional[BaseException] = None, exc_tb=None):
        """Log the moment that script execution exits the context manager \
        and what it just finished doing.

        :param exc_type: Exception type
        :param exc_val: Exception value
        :param exc_tb: Exception traceback
        """
        self.elapsed = dt.datetime.now() - self.start
        self.show(f"\nTime elapsed {self.doing_what}: {self.elapsed}")


def uniqs_in(listlike: Iterable[str]) -> List[str]:
    """Get an alphabetized list of unique, non-private local variables' \
    names by calling locals() and then passing it into this function.

    :param listlike: List-like collection (or dict) of strings
    :return: List[str] (sorted) of all unique strings in listlike that \
             don't start with an underscore
    """
    uniqs = set([v if not v.startswith("_") else None
                 for v in listlike]) - {None}
    uniqs = [x for x in uniqs]
    uniqs.sort()
    return uniqs
