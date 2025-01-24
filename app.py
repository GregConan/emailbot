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
import imaplib
import pdb

# Import local custom libraries
from emailbot.CustomDicts import Cryptionary
from emailbot.GmailIMAPFetcher import GmailIMAPFetcher


def main():
    creds = get_creds()

    try:
        gmail = GmailIMAPFetcher()
    except imaplib.IMAP4.error as err:
        creds.debug_or_raise(err, locals())
    gmail.login(creds["address"], creds["password"])

    pdb.set_trace()
    print("done")


def get_creds(parser: argparse.ArgumentParser | None = None
              ) -> Cryptionary:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: Cryptionary containing a Gmail account's login credentials
    """
    MSG_CRED = ("Your Gmail account {0}. If you don't include this argument, "
                "then you will be prompted to enter your {0} manually.")
    PROMPT = "Please enter your Gmail %s: "

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

    # Save credentials and settings into a custom encrypted dictionary
    creds = Cryptionary(**vars(parser.parse_args()))
    creds.setdefault_or_prompt_for("address", input, PROMPT % "address")
    creds.setdefault_or_prompt_for("password", getpass, PROMPT % "password")
    # TODO Implement Oauth2? https://stackoverflow.com/a/5366380
    # https://support.google.com/accounts/answer/185833
    return creds


if __name__ == "__main__":
    main()
