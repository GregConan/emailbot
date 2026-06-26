#!/usr/bin/env python3

"""
Gmail Bot
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2026-04-15
"""
# Import standard libraries
from configparser import ConfigParser
from getpass import getpass
from glob import glob
import os
import pdb
import sys
from typing import Annotated, cast, get_args, Literal, TypeVar

# Import third-party PyPI libraries
import pydantic

# Import remote custom libraries
from gconanpy.access.nested import Xray
from gconanpy.cli import ArgumentParser, Arg, OutputDirArg, Valid
from gconanpy.debug import ShowTimeTaken
from gconanpy.mapping.dicts import LazyDotDict, SubCryptionary

# Import local custom libraries
from emailbot.Gmailer import Gmailer
from emailbot.GoogleSheetUpdater import JobsAppsSheetUpdater
from emailbot.LinkedInBot import LinkedInBot

# Type variables for command-line input argument parsing
_RunMode = Literal["gmail", "linkedin"]

# CLIArgs variables
DEFAULT_CONFIG = "config.ini"
MSG_CRED = ("Your account {0}. If you don't include this argument, "
            "then you will be prompted to enter your {0} manually.")
RUN_MODES = get_args(_RunMode)


class CLIArgs(pydantic.BaseModel):
    """ Command-line input parameters saved into a custom dict class with extra
        functionality. All input parameters' types are explicitly defined here
        for static type checking/highlighting/etc. """
    # Required Arg
    run_mode: Annotated[_RunMode, pydantic.Field(), Arg(
        "run_mode", choices=RUN_MODES, help_msg=(
            "Modes to run this script in. Enter 'gmail' to access Gmail "
            "account, or 'linkedin' to access LinkedIn account."))]

    # Optional Args
    address: Annotated[str | None, pydantic.Field(), Arg(
        "address", "-e", "-email", "--email", "--address", "--email-address",
        metavar="EMAIL_ADDRESS",
        help=MSG_CRED.format("address"))]

    configs: Annotated[list[str], pydantic.Field(), Arg(
        "configs", "-c", "-config", "--config", "--config-file-paths",
        "--config-file", type=Valid.readable_file, default=[DEFAULT_CONFIG],
        metavar="PATHS_TO_CONFIG_FILES", nargs="*", help_msg=(
            "Paths to valid readable config files defining values of "
            "important variables for this script to use. See `README.md` "
            "for an example config file. By default, this script will try "
            "to read from " + os.path.join(os.getcwd(), DEFAULT_CONFIG)))]

    debugging: Annotated[bool, pydantic.Field(), Arg(
        "debugging", "-d", "-debug", "--debug", "--debugging",
        default=False, action="store_true", help_msg=(
            "Include this flag to interactively debug on error instead of "
            "exiting the program."))]

    how_many: Annotated[int | None, pydantic.Field(), Arg(
        "how_many", "-n", "--number", "--count", "--n-emails", "--how-many",
        type=Valid.whole_number,
        help_msg=("Number of emails/jobs to fetch/check")
    )]

    output: Annotated[str, pydantic.Field(), OutputDirArg()]

    password: Annotated[str | None, pydantic.Field(), Arg(
        "password", "-p", "-pass", "--password",
        help_msg=MSG_CRED.format("password")
    )]

    ff_profile: Annotated[str | None, pydantic.Field(), Arg(
        "ff_profile", "-fp", "-profile", "--profile", "--ff-profile",
        "--profile-path", metavar="FIREFOX_PROFILE_PATH"
        # type=Valid.readable_file
    )]


def main():
    parser = ArgumentParser("Python script(s) to interact with "
                            "Gmail, Google Sheets and LinkedIn.")
    cli_args = parser.parse_args_to_model(CLIArgs)
    # cli_args = get_cli_args()

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
            # Make a TMPDIR to avoid Firefox crashing
            # tmp_dir = os.path.join(os.getcwd(), "tmp")
            os.environ["TMPDIR"] = cli_args.output
            # os.makedirs(tmp_dir, exist_ok=True)

            with LinkedInBot(debugging=cli_args.debugging,
                             out_dir_path=cli_args.output) as bot:
                bot = cast(LinkedInBot, bot)  # else assumes it's a WebDriver
                # pdb.set_trace()
                bot.login(creds["address"], creds["password"])
                bot.iterate_jobs_at()
                pdb.set_trace()
                print("done")


def get_credentials(cli_args: CLIArgs, config: LazyDotDict,
                    **config_paths: str) -> SubCryptionary:
    """
    :param parser: argparse.ArgumentParser to get command-line input arguments
    :return: SubCryptionary containing a Gmail account's login credentials
    """
    # Save credentials and settings into a custom encrypted dictionary
    try:
        args_dict = LazyDotDict(cli_args.model_dump())
        args_dict.setdefaults(**config.get_subset_from_lookups(config_paths),
                              exclude={None})
        creds = SubCryptionary.from_subset_of(  # TODO use Locktionary?
            args_dict, keys_are=("address", "debugging", "password"),
            values_arent=None)

        # Prompt user for Gmail credentials if they didn't provide them as
        # command-line arguments
        PROMPT = "Please enter your %s: "
        creds.setdefault_or_prompt_for(
            "address", PROMPT % "email address", exclude={None})
        creds.setdefault_or_prompt_for(
            "password", PROMPT % "password", getpass, exclude={None})
    except KeyError as err:
        # pdb.set_trace()
        if cli_args.debugging:
            pdb.set_trace()
            print()
        else:
            raise err
    return creds


if __name__ == "__main__":
    main()
