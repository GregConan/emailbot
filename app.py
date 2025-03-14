#!/usr/bin/env python3

"""
Gmail Bot
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2025-03-14
"""
# Import standard libraries
import argparse
from getpass import getpass
import pdb
import sys
from typing import Any, Dict

# Import remote custom libraries
from gconanpy.cli import add_new_out_dir_arg_to
from gconanpy.debug import ShowTimeTaken
from gconanpy.dissectors import Xray
from gconanpy.maps import Cryptionary

# Import local custom libraries and constants
from emailbot.constants import TEMPLATES
from emailbot.Gmailer import Jobmailer  # Gmailer,
from emailbot.LinkedInBot import FFOptions, LinkedInBot


def main():
    cli_args = get_cli_args()
    creds = get_credentials(cli_args)

    match cli_args["run_mode"]:
        case "gmail":
            # Connect to Gmail and set up Gmail interactor
            gmail = Jobmailer(debugging=cli_args["debugging"])
            gmail.login_with(creds)
            if gmail.is_logged_out():
                sys.exit(1)

            gmail.load_templates_from(*TEMPLATES)

            with ShowTimeTaken("updating LinkedIn job apps Google Sheet"):
                gmail.check_linkedin_emails()

        case "linkedin":
            options = FFOptions(  # "--safe-mode", "--allow-downgrade",
                profile_dir=cli_args["ff_profile"],
                headless=True)
            with LinkedInBot(debugging=cli_args["debugging"],
                             options=options,
                             out_dir_path=cli_args["output"]) as bot:
                pdb.set_trace()
                bot.login(creds["address"], creds["password"])
                pdb.set_trace()
                print("done")


def get_cli_args(parser: argparse.ArgumentParser | None = None
                 ) -> Dict[str, Any]:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: Dict[str, Any], all arguments collected from the command line
    """
    MSG_CRED = ("Your account {0}. If you don't include this argument, "
                "then you will be prompted to enter your {0} manually.")
    RUN_MODES = ("gmail", "linkedin")

    # Collect command-line input arguments
    if not parser:
        parser = argparse.ArgumentParser()
    parser.add_argument(
        # "-m", "-mode", "--run-mode",
        "run_mode",
        choices=RUN_MODES,
        help=("Modes to run this script in. Enter 'gmail' to access Gmail "
              "account, or 'linkedin' to access LinkedIn account.")
    )
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
    parser = add_new_out_dir_arg_to(parser, "out", dest="output",
                                    metavar="OUTPUT_DIRECTORY")
    parser.add_argument(
        "-p", "-pass", "--password",
        dest="password",
        help=MSG_CRED.format("password")
    )
    parser.add_argument(
        "-fp", "-profile", "--profile", "--ff-profile", "--profile-path",
        dest="ff_profile",
        metavar="FIREFOX_PROFILE_PATH"
        # type=Valid.readable_file
    )
    return vars(parser.parse_args())


def get_credentials(cli_args: Dict[str, Any]) -> Cryptionary:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: Cryptionary containing a Gmail account's login credentials
    """
    # Save credentials and settings into a custom encrypted dictionary
    creds = Cryptionary.from_subset_of(cli_args, "address", "debugging",
                                       "password", keep_empties=False)

    # Prompt user for Gmail credentials if they didn't provide them as
    # command-line arguments
    PROMPT = "Please enter your %s: "
    creds.setdefault_or_prompt_for("address", input, PROMPT % "email address")
    creds.setdefault_or_prompt_for("password", getpass, PROMPT % "password")
    return creds


if __name__ == "__main__":
    main()
