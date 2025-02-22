
#!/usr/bin/env python3

"""
Lower-level tools & convenience functions to manipulate sequences & mappings.
Overlaps significantly with:
    Knower/utilities.py, audit-ABCC/src/utilities.py, \
    abcd-bids-tfmri-pipeline/src/pipeline_utilities.py, etc.
Greg Conan: gregmconan@gmail.com
Created: 2025-01-24
Updated: 2025-01-26
"""
# Import standard libraries
from abc import ABC
from itertools import chain
import re
import sys
from typing import (Any, Callable, Container, Dict, Hashable, Iterable, List,
                    Mapping, Sequence, Set, SupportsBytes, Tuple)


# NOTE All classes and functions below are in alphabetical order.


class Bytesifier:
    """Class with a method to convert objects into bytes without knowing \
    what type those things are."""

    def can_bytesify(self, an_object: Any) -> bool:
        """
        :return: bool, True if self.bytesify(an_object) will work, else \
                       False if it will raise an exception
        """
        return hasattr(an_object, "encode") or hasattr(an_object, "to_bytes")

    def bytesify(self, an_obj: SupportsBytes, **kwargs) -> bytes:
        """
        :param an_obj: SupportsBytes, something to convert to bytes
        :raises AttributeError: if an_obj has no 'to_bytes' or 'encode' method
        :return: bytes, an_obj converted to bytes
        """
        try:
            return an_obj.encode(**setdefaults_of(kwargs, encoding="utf-8"))
        except AttributeError:
            return an_obj.to_bytes(**setdefaults_of(
                kwargs, length=1, byteorder="big", signed=False
            ))


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


def extract_letters_from(a_str: str) -> str:
    return re.sub(r'[^a-zA-Z]', '', a_str)


class Peeler(ABC):

    @staticmethod
    def can_peel(an_obj: Any) -> bool:  # TODO REFACTOR (VERY INELEGANT!)
        """ 
        :param an_obj: Any
        :return: bool, True if you can run Peeler.peel(an_obj) or \
                 Peeler.core(an_obj) without error, else False
        """
        result = False
        if isinstance(an_obj, Iterable):
            primitivity = [
                hasattr(an_obj, "__mod__"),  # ONLY in primitives
                not hasattr(an_obj, "__class_getitem__"),  # NOT in them
                isinstance(an_obj, Hashable)]
            result = primitivity.count(True) < 2
        return result

    @classmethod
    def core(cls, to_peel: Iterable) -> Any:
        """Extract the biggest (longest) datum from a nested data structure.

        :param to_peel: Iterable, especially a nested container data structure
        :return: Any, the longest datum buried in to-peel's nested layers
        """
        fruits = cls.peel(to_peel)
        if len(fruits) > 1:
            sizes = [len(f) for f in fruits]
            biggest = fruits[sizes.index(max(sizes))]
        else:
            biggest = fruits[0]
        return biggest

    @classmethod
    def peel(cls, to_peel: Iterable) -> list:
        """Extract data from bothersome nested container data structures.

        :param to_peel: Iterable, especially a nested container data structure
        :return: list, all data buried in to_peel's nested container layers, \
                 regardless of its exact location inside to_peel
        """
        if cls.can_peel(to_peel):
            try:
                fruit_lists = [cls.peel(to_peel[k])
                               for k in to_peel.keys()]
            except AttributeError:
                fruit_lists = [cls.peel(item) for item in to_peel]
            fruits = list(chain(*fruit_lists))
        else:
            # fruits.append(to_peel)
            fruits = [to_peel, ]
        return fruits


def seq_startswith(seq: Sequence, prefix: Sequence) -> bool:
    """Check if prefix is the beginning of seq.

    :param seq: Sequence, _description_
    :param prefix: Sequence, _description_
    :return: bool, True if seq starts with the specified prefix, else False.
    """
    return len(seq) >= len(prefix) and seq[:len(prefix)] == prefix


def setdefaults_of(a_dict: dict, **kwargs: Any) -> dict:  # Dict[str, Any]:
    """dict.update prefers to overwrite old values with new ones.
    setdefaults_of is basically dict.update that prefers to keep old values.

    :param a_dict: dict, _description_
    :param kwargs: Dict[str, Any], _description_
    :return: Dict[str, Any], _description_
    """
    for key, value in kwargs.items():
        a_dict.setdefault(key, value)
    return kwargs


def startswith(an_obj: Any, prefix: Any) -> bool:
    """Check if the beginning of an_obj is prefix.
    Type-agnostic extension of str.startswith and bytes.startswith.

    :param an_obj: Any, _description_
    :param prefix: Any, _description_
    :return: bool, True if an_obj starts with the specified prefix, else False
    """
    try:
        try:
            result = an_obj.startswith(prefix)
        except AttributeError:  # then an_obj isn't a str or bytes
            result = seq_startswith(an_obj, prefix)
    except TypeError:  # then an_obj isn't a Sequence or obj2 isn't
        result = seq_startswith(stringify(an_obj), stringify(prefix))
    return result


def stringify(an_obj: Any, encoding: str = sys.getdefaultencoding(),
              errors: str = "ignore") -> str:
    """Improved str() function that automatically decodes bytes.

    :param an_obj: Any
    :param encoding: str, _description_, probably "utf-8" by default
    :param errors: str, _description_, defaults to "ignore"
    :return: str, _description_
    """
    try:
        stringified = str(an_obj, encoding=encoding, errors=errors)
    except TypeError:
        stringified = str(an_obj)
    return stringified


def stringify_list(a_list: list) -> str:
    """
    :param a_list: List[Any]
    :return: str containing all items in a_list, single-quoted and \
             comma-separated if there are multiple
    """  # TODO Combine w/ stringify() function?
    result = ""
    if a_list and isinstance(a_list, list):  # TODO REFACTOR (INELEGANT)
        list_with_str_els = [stringify(el) for el in a_list]
        if len(a_list) > 1:
            result = "'{}'".format("', '".join(list_with_str_els))
        else:
            result = list_with_str_els[0]
    return result


def uniqs_in(listlike: Iterable[Hashable]) -> List[Hashable]:
    """Alphabetize and list the unique elements of an iterable.
    To list non-private local variables' names, call uniqs_in(locals()).

    :param listlike: Iterable[Hashable] to get the unique elements of
    :return: List[Hashable] (sorted) of all unique strings in listlike \
             that don't start with an underscore
    """
    uniqs = [*set([v for v in listlike if not startswith(v, "_")])]
    uniqs.sort()
    return uniqs


class Xray(list):
    """Given any object, easily check what kinds of things it contains.
    Extremely convenient for interactive debugging."""

    def __init__(self, an_obj: Any, list_its: str | None = None):
        """_summary_ 

        :param an_obj: Any
        :param list_its: str naming which detail of an_obj to list; defaults to None
        :raises err: _description_
        """
        to_check = iter(("contents", "outputs", "attributes"))
        what_elements_are = list_its
        gotten = None
        while gotten is None:
            try:  # Figure out what details of an_obj to list
                match what_elements_are:
                    case "contents":
                        gotten = [x for x in an_obj]
                    case "outputs":
                        gotten = [x for x in an_obj()]
                    case "attributes":
                        gotten = [x for x in dir(an_obj)]
                    case _:
                        what_elements_are = next(to_check)
            except (NameError, TypeError) as err:
                if list_its:  # Crash if we cannot get what was asked for
                    raise err
                else:  # Keep looking for useful info to return
                    what_elements_are = next(to_check)

        if not list_its:
            list_its = what_elements_are
        what_obj_is = getattr(an_obj, "__name__", type(an_obj).__name__)
        self.what_elements_are = \
            f"{what_obj_is} {list_its if list_its else what_elements_are}"

        try:
            gotten = uniqs_in(gotten)
        except TypeError:
            pass
        super().__init__(gotten)

    def __repr__(self):
        return f"{self.what_elements_are}: {stringify_list(self)}"
