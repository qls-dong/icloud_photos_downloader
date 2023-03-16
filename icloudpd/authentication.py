"""Handles username/password authentication and two-step authentication"""

import sys
import click
import pyicloud
from icloudpd.logger import setup_logger


class TwoStepAuthRequiredError(Exception):
    """
    Raised when 2SA is required. base.py catches this exception
    and sends an email notification.
    """

def authenticator(domain):
    """Wraping authentication with domain context"""
    def authenticate_(
            username,
            password,
            cookie_directory=None,
            raise_error_on_2sa=False,
            client_id=None,
            china_mainland=True,
    ):
        """Authenticate with iCloud username and password"""
        logger = setup_logger()
        logger.debug("Authenticating...")
        while True:
            try:
                # If password not provided on command line variable will be set to None
                # and PyiCloud will attempt to retrieve from its keyring
                icloud = pyicloud.PyiCloudService(
                    domain,
                    username, password,
                    cookie_directory=cookie_directory,
                    client_id=client_id,
                    china_mainland=china_mainland,
                    )
                break
            except pyicloud.exceptions.PyiCloudNoStoredPasswordAvailableException:
                # Prompt for password if not stored in PyiCloud's keyring
                password = click.prompt("iCloud Password", hide_input=True)
                icloud = pyicloud.PyiCloudService(
                    username, password,
                    cookie_directory=cookie_directory,
                    client_id=client_id,
                    china_mainland=china_mainland)

        if icloud.requires_2fa:
            if raise_error_on_2sa:
                raise TwoStepAuthRequiredError(
                    "Two-factor authentication is required!"
                )
            logger.info("Two-factor authentication is required!")
            request_2fa(icloud, logger)
        elif icloud.requires_2sa:
            if raise_error_on_2sa:
                raise TwoStepAuthRequiredError(
                    "Two-step/two-factor authentication is required!"
                )
            logger.info("Two-step authentication is required!")
            request_2sa(icloud, logger)
        return icloud
    return authenticate_

def request_2fa(icloud, logger):
    """Request two-factor authentication."""
    code = click.prompt("Please enter two-factor authentication code")
    if not icloud.validate_2fa_code(code):
        logger.error("Failed to verify two-factor authentication code")
        sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2FA expires.\n"
        "You can set up email notifications for when "
        "the two-factor authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )

def request_2sa(icloud, logger):
    """Request two-step authentication. Prompts for SMS or device"""
    devices = icloud.trusted_devices
    devices_count = len(devices)
    device_index = 0
    if devices_count > 0:
        for i, device in enumerate(devices):
            # pylint: disable-msg=consider-using-f-string
            print(
                "  %s: %s" %
                (i, device.get(
                    "deviceName", "SMS to %s" %
                    device.get("phoneNumber"))))
            # pylint: enable-msg=consider-using-f-string

        # pylint: disable-msg=superfluous-parens
        print(f"  {devices_count}: Enter two-factor authentication code")
        # pylint: enable-msg=superfluous-parens
        device_index = click.prompt(
            "Please choose an option:",
            default=0,
            type=click.IntRange(
                0,
                devices_count))

    if device_index == devices_count:
        # We're using the 2FA code that was automatically sent to the user's device,
        # so can just use an empty dict()
        device = {}
    else:
        device = devices[device_index]
        if not icloud.send_verification_code(device):
            logger.error("Failed to send two-factor authentication code")
            sys.exit(1)

    code = click.prompt("Please enter two-factor authentication code")
    if not icloud.validate_verification_code(device, code):
        logger.error("Failed to verify two-factor authentication code")
        sys.exit(1)
    logger.info(
        "Great, you're all set up. The script can now be run without "
        "user interaction until 2SA expires.\n"
        "You can set up email notifications for when "
        "the two-step authentication expires.\n"
        "(Use --help to view information about SMTP options.)"
    )
