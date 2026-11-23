from rest_framework.exceptions import APIException


class SessionAlreadyRunning(APIException):
    """
    Raised when a user tries to start a new focus session while one is already running.
    Returns 409 Conflict with the running session's id so the client can resume or end it.
    """
    status_code = 409
    default_detail = "A focus session is already running."

    def __init__(self, session_id):
        self.detail = {
            "code": "session_already_running",
            "detail": "A focus session is already running.",
            "session_id": session_id,
        }
        super().__init__(self.detail)
