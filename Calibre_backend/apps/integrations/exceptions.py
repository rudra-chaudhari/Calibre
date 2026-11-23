from rest_framework.exceptions import APIException


class MoodleError(Exception):
    """Base exception for Moodle-related errors."""
    pass


class MoodleTokenError(MoodleError):
    """Moodle API returned an invalid token error."""
    pass


class MoodleAPIError(MoodleError):
    """Moodle API returned an error response (other than invalid token)."""

    def __init__(self, errorcode, message):
        self.errorcode = errorcode
        self.message = message
        super().__init__(f"{errorcode}: {message}")


class MoodleUnavailable(MoodleError):
    """Network error, timeout, or invalid response from Moodle."""
    pass


class MoodleReauthRequired(APIException):
    """
    The Moodle connection token is expired.
    Client must prompt the user to reconnect.
    """
    status_code = 409
    default_detail = {
        "code": "moodle_reauth_required",
        "detail": "Your Moodle connection expired. Please reconnect.",
    }
