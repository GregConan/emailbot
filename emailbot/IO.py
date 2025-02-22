
#!/usr/bin/env python3

"""
Lower-level utilities & convenience functions for multiple emailbot files' use
Overlaps significantly with:
    Knower/utilities.py, audit-ABCC/src/utilities.py, \
    abcd-bids-tfmri-pipeline/src/pipeline_utilities.py, etc.
Greg Conan: gregmconan@gmail.com
Created: 2025-01-26
Updated: 2025-02-21
"""
# Import standard libraries
import json
import os
import pdb
from string import Formatter, Template
import sys
from typing import (Any, Dict, Hashable, Iterable, List, Mapping, Set)


# NOTE All classes and functions below are in alphabetical order.


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
