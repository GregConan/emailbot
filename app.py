#!/usr/bin/env python3

"""
Gmail Bot
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2025-07-29
"""
# Import standard libraries
from configparser import ConfigParser
from getpass import getpass
from glob import glob
import os
import pdb
import sys

# Import remote custom libraries
from gconanpy.wrappers import ArgParser, Valid
from gconanpy.debug import ShowTimeTaken
from gconanpy.dissectors import Xray
from gconanpy.mapping.dicts import LazyDotDict, SubCryptionary

# Import local custom libraries
from emailbot.Gmailer import Gmailer
from emailbot.GoogleSheetUpdater import JobsAppsSheetUpdater
from emailbot.LinkedInBot import FFOptions, LinkedInBot


def main():
    cli_args = get_cli_args()

    config = ConfigParser()
    config.read(cli_args.configs)
    config = LazyDotDict.fromConfigParser(config)

    creds = get_credentials(cli_args, config, address="Gmail.address")

    match cli_args.run_mode:
        case "gmail":
            # Connect to Gmail and set up Gmail interactor
            with ShowTimeTaken("connecting to your Gmail account"):
                gmail = Gmailer(debugging=cli_args.debugging)
                gmail.login_with(creds)
                if gmail.is_logged_out():
                    sys.exit(1)

                templates = glob(os.path.join(config.Gmail.templates,
                                 "*.txt"))
                gmail.load_templates_from(*templates)

            with ShowTimeTaken("updating LinkedIn job apps Google Sheet"):
                updater = JobsAppsSheetUpdater.from_config(
                    config=config, debugging=cli_args.debugging, sep=":",
                    sheet_ID="Google.Worksheet:id",
                    worksheet_name="Google.Worksheet:name",
                    jobs_email="Jobs:address", relabel="Jobs:relabel",
                    tokenJSON="Google.JSON:token",
                    serviceJSON="Google.JSON:service")
                updater.sort_job_apps_from_gmail(gmail, cli_args.how_many)

        case "linkedin":
            options = FFOptions(  # "--safe-mode", "--allow-downgrade",
                profile_dir=cli_args.ff_profile,
                headless=True)
            with LinkedInBot(debugging=cli_args.debugging,
                             options=options,
                             out_dir_path=cli_args.output) as bot:
                pdb.set_trace()
                bot.login(creds["address"], creds["password"])
                pdb.set_trace()
                print("done")


def get_cli_args(parser: ArgParser | None = None) -> LazyDotDict:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: LazyDotDict[str, Any], all arguments collected from the command line
    """
    DEFAULT_CONFIG = "config.ini"
    MSG_CRED = ("Your account {0}. If you don't include this argument, "
                "then you will be prompted to enter your {0} manually.")
    RUN_MODES = ("gmail", "linkedin")

    # Collect command-line input arguments
    if not parser:
        parser = ArgParser("Python script(s) to interact with "
                           "Gmail, Google Sheets and LinkedIn.")
    parser.add_argument(
        "run_mode",  # "-m", "-mode", "--run-mode",
        choices=RUN_MODES,
        help=("Modes to run this script in. Enter 'gmail' to access Gmail "
              "account, or 'linkedin' to access LinkedIn account.")
    )
    parser.add_argument(
        "-c", "-config", "--config", "--config-file", "--config-file-paths",
        default=DEFAULT_CONFIG,
        dest="configs",
        metavar="PATHS_TO_CONFIG_FILES",
        nargs="*",
        type=Valid.readable_file,
        help=("Paths to valid readable config files defining values of "
              "important variables for this script to use. See `README.md` "
              "for an example config file. By default, this script will try "
              "to read from " + os.path.join(os.getcwd(), DEFAULT_CONFIG))
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
    parser.add_new_out_dir_arg("out", dest="output",
                               metavar="OUTPUT_DIRECTORY")
    parser.add_argument(
        "-n", "--number", "--count", "--n-emails", "--how-many",
        dest="how_many",
        type=Valid.whole_number,
        help=("Number of emails/jobs to fetch/check")
    )
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
    return LazyDotDict(vars(parser.parse_args()))


def get_credentials(cli_args: LazyDotDict, config: LazyDotDict,
                    **config_paths: str) -> SubCryptionary:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: SubCryptionary containing a Gmail account's login credentials
    """
    # Save credentials and settings into a custom encrypted dictionary
    try:
        cli_args.setdefaults(**config.get_subset_from_lookups(config_paths),
                             exclude={None})
        creds = SubCryptionary.from_subset_of(  # TODO use Locktionary?
            cli_args, keys=("address", "debugging", "password"),
            include_keys=True, values={None}, include_values=False)

        # Prompt user for Gmail credentials if they didn't provide them as
        # command-line arguments
        PROMPT = "Please enter your %s: "
        creds.setdefault_or_prompt_for(
            "address", PROMPT % "email address", exclude={None})
        creds.setdefault_or_prompt_for(
            "password", PROMPT % "password", getpass, exclude={None})
    except KeyError as err:
        pdb.set_trace()
        if cli_args.debugging:
            pdb.set_trace()
            print()
        else:
            raise err
    return creds


if __name__ == "__main__":
    main()
