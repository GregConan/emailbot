
#!/usr/bin/env python3

"""
Lower-level utilities & convenience functions for multiple emailbot files' use
Overlaps significantly with:
    Knower/utilities.py, audit-ABCC/src/utilities.py, \
    abcd-bids-tfmri-pipeline/src/pipeline_utilities.py, etc.
Greg Conan: gregmconan@gmail.com
Created: 2025-01-26
Updated: 2025-03-03
"""
# Import standard libraries
import argparse
import json
import os
import pdb
from string import Formatter, Template
import sys
from typing import (Any, Callable, Dict, Hashable,
                    Iterable, List, Mapping, Set)


# NOTE All classes and functions below are in alphabetical order.


def add_new_out_dir_arg_to(parser: argparse.ArgumentParser, name: str,
                           **kwargs: Any) -> argparse.ArgumentParser:
    """ Specifies argparse.ArgumentParser.add_argument for a valid path to\
    an output directory that must either exist or be created.

    :param name: str naming the directory to ensure exists
    :param kwargs: Mapping[str, Any], ArgumentParser.add_argument keyword args
    :return: argparse.ArgumentParser, now with the output directory argument
    """
    if not kwargs.get("default"):
        kwargs["default"] = os.path.join(os.getcwd(), name)
    if not kwargs.get("dest"):
        kwargs["dest"] = name
    if not kwargs.get("help"):
        kwargs["help"] = f"Valid path to local directory to save {name} " \
            "files into. If no directory exists at this path yet, then one " \
            "will be created. By default, this argument's value will be: " \
            + kwargs["default"]
    parser.add_argument(
        f"-{name[0]}", f"-{name}", f"--{name}", f"--{name}-dir",
        f"--{name}-dir-path", type=Valid.output_dir, **kwargs
    )
    return parser


def extract_from_json(json_path: str) -> dict:
    """
    :param json_path: str, a valid path to a real readable .json file
    :return: dict, the contents of the file at json_path
    """
    with open(json_path) as infile:
        return json.load(infile)


class LoadedTemplate(Template):
    """ string.Template that \
        (1) can be loaded from a text file, and \
        (2) stores its own field/variable names.
    """
    parse = Formatter().parse

    def __init__(self, template_str: str):
        super().__init__(template_str)
        self.fields = self.get_field_names_in(template_str)

    @classmethod
    def get_field_names_in(cls, template_str: str) -> Set[str]:
        """Get the name of every variables in template_str. Shamelessly \
            stolen from langchain_core.prompts.string.get_template_variables.

        :param template_str: str, the template string.
        :return: Set[str] of variable/field names in the template string.
        """
        return {field_name for _, field_name, _, _ in
                cls.parse(template_str) if field_name is not None}

    @classmethod
    def from_file_at(cls, txt_file_path: str) -> "LoadedTemplate":
        """
        :param txt_file_path: str, valid path to readable .txt file
        :return: LoadedTemplate loaded from the file at txt_file_path
        """
        with open(txt_file_path) as infile:
            return cls(infile.read())


def save_to_json(contents: Any, json_path: str) -> None:
    """
    :param json_path: str, a valid path to save a .json file at
    """
    with open(json_path, "w+") as outfile:
        json.dump(contents, outfile)


def wrap_with_params(call: Callable, *args: Any, **kwargs: Any) -> Callable:
    """
    Define values to pass into a previously-defined function ("call"), and
    return that function object wrapped with its new preset/default values
    :param call: Callable, function to add preset/default parameter values to
    :return: Callable, "call" with preset/default values for the 'args' and
             'kwargs' parameters, so it only accepts one positional parameter
    """
    def wrapped(*fn_args: Any, **fn_kwargs: Any) -> Any:
        fn_kwargs.update(kwargs)
        # print(f"Calling {call.__name__}(*{args}, *{fn_args}, **{fn_kwargs})")
        return call(*args, *fn_args, **fn_kwargs)
    return wrapped


class Valid:
    # TODO Do this in a more standard way
    dir_made: Callable = wrap_with_params(os.makedirs, exist_ok=True)
    readable: Callable = wrap_with_params(os.access, mode=os.R_OK)
    writable: Callable = wrap_with_params(os.access, mode=os.W_OK)

    @staticmethod
    def _validate(to_validate: Any, *conditions: Callable,
                  # conditions: Iterable[Callable] = list(),
                  err_msg: str = "`{}` is invalid.",
                  first_ensure: Callable | None = None,
                  final_format: Callable | None = None) -> Any:
        """ Parent/base function used by different type validation functions.
        Raises argparse.ArgumentTypeError if input object is somehow invalid.

        :param to_validate: Any, object to check if it represents valid input
        :param conditions: Callable, each returns true iff input obj is valid
        :param final_format: Callable, returns a fully validated object
        :param err_msg: str, msg to show to user to tell them what is invalid
        :param first_ensure: Callable, run before validation for preparation
        :return: Any, to_validate but fully validated
        """
        try:
            if first_ensure:
                first_ensure(to_validate)
            for is_valid in conditions:
                assert is_valid(to_validate)
            return final_format(to_validate) if final_format else to_validate
        except (argparse.ArgumentTypeError, AssertionError, OSError,
                TypeError, ValueError):
            raise argparse.ArgumentTypeError(err_msg.format(to_validate))

    @classmethod
    def output_dir(cls, path: Any) -> str:
        """
        Try to make a folder for new files at path; throw exception if that fails
        :param path: String which is a valid (not necessarily real) folder path
        :return: String which is a validated absolute path to real writeable folder
        """
        return cls._validate(path, os.path.isdir, cls.writable,
                             err_msg="Cannot create directory at `{}`",
                             first_ensure=cls.dir_made,  # [cls.dir_made],
                             final_format=os.path.abspath)

    @classmethod
    def readable_dir(cls, path: Any) -> str:
        """
        :param path: Parameter to check if it represents a valid directory path
        :return: String representing a valid directory path
        """
        return cls._validate(path, os.path.isdir, cls.readable,
                             err_msg="Cannot read directory at `{}`",
                             final_format=os.path.abspath)

    @classmethod
    def readable_file(cls, path: Any) -> str:
        """
        Throw exception unless parameter is a valid readable filepath string. Use
        this, not argparse.FileType('r') which leaves an open file handle.
        :param path: Parameter to check if it represents a valid filepath
        :return: String representing a valid filepath
        """
        return cls._validate(path, cls.readable,
                             err_msg="Cannot read file at `{}`",
                             final_format=os.path.abspath)

    @classmethod
    def whole_number(cls, to_validate: Any):
        """
        Throw argparse exception unless to_validate is a positive integer
        :param to_validate: Object to test whether it is a positive integer
        :return: to_validate if it is a positive integer
        """
        return cls._validate(to_validate, lambda x: int(x) >= 0,
                             err_msg="{} is not a positive integer",
                             final_format=int)
