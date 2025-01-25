#!/usr/bin/env python3

"""
Gmail Bot
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2025-01-24
"""
# Import standard libraries
import argparse
from getpass import getpass
import pdb
import sys
from typing import Any, Dict

# Import local custom libraries
from emailbot.constants import TEMPLATE_ACCEPT, TEMPLATE_REJECT
from emailbot.CustomDicts import Cryptionary
from emailbot.GmailIMAPFetcher import GmailIMAPFetcher


def main():
    cli_args = get_cli_args()
    creds = get_credentials(cli_args)
    gmail = GmailIMAPFetcher(debugging=cli_args["debugging"])
    gmail.login_with(creds)
    if gmail.is_logged_out():
        sys.exit(1)
    gmail.load_templates_from(TEMPLATE_ACCEPT, TEMPLATE_REJECT)

    inbox_emails = gmail.get_emails_from()
    # creds.debug_or_raise(err, locals())

    pdb.set_trace()
    print("done")


def get_cli_args(parser: argparse.ArgumentParser | None = None
                 ) -> Dict[str, Any]:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: Dict[str, Any], all arguments collected from the command line
    """
    MSG_CRED = ("Your Gmail account {0}. If you don't include this argument, "
                "then you will be prompted to enter your {0} manually.")

    # Collect command-line input arguments
    if not parser:
        parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d", "-debug", "--debug", "--debugging",
        action="store_true",
        dest="debugging",
        help=("Include this flag to interactively debug on error instead of "
              "exiting the program.")
    )
    parser.add_argument(
        "-e", "-email", "--email", "--address", "--email-address",
        dest="address",
        metavar="EMAIL_ADDRESS",
        help=MSG_CRED.format("address")
    )
    parser.add_argument(
        "-p", "-pass", "--password",
        dest="password",
        help=MSG_CRED.format("password")
    )
    return vars(parser.parse_args())


def get_credentials(cli_args: Dict[str, Any]) -> Cryptionary:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: Cryptionary containing a Gmail account's login credentials
    """
    # Save credentials and settings into a custom encrypted dictionary
    creds = Cryptionary(**cli_args)

    # Prompt user for Gmail credentials if they didn't provide them as
    # command-line arguments
    PROMPT = "Please enter your Gmail %s: "
    creds.setdefault_or_prompt_for("address", input, PROMPT % "address")
    creds.setdefault_or_prompt_for("password", getpass, PROMPT % "password")
    return creds


if __name__ == "__main__":
    main()
