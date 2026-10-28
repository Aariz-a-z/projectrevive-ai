"""Domain errors with messages intended for end users.

Every error carries a stable `code` so the frontend can branch on it, and a
`message` written to be shown verbatim. README section 4.1 requires useful
errors instead of silent failures.
"""

from __future__ import annotations


class ProjectReviveError(Exception):
    """Base class. `status` maps to HTTP, `code` is a stable machine string."""

    code = "internal_error"
    status = 500
    message = "Something went wrong while processing the document."

    #: Extra response headers, e.g. Retry-After on a 429.
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        *,
        detail: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message or self.message
        self.detail = detail
        if headers is not None:
            self.headers = headers
        super().__init__(self.message)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.detail:
            payload["detail"] = self.detail
        return payload


class UnsupportedFileType(ProjectReviveError):
    code = "unsupported_file_type"
    status = 415
    message = "That file type is not supported. Upload a PDF or DOCX report."


class FileTooLarge(ProjectReviveError):
    code = "file_too_large"
    status = 413
    message = "That file is too large."


class EmptyDocument(ProjectReviveError):
    code = "empty_document"
    status = 422
    message = "No readable text was found in that document."


class EncryptedDocument(ProjectReviveError):
    code = "encrypted_document"
    status = 422
    message = "That PDF is password protected, so its text cannot be read."


class MalformedDocument(ProjectReviveError):
    code = "malformed_document"
    status = 422
    message = "That file could not be read as a valid document."


class ScannedDocument(ProjectReviveError):
    code = "scanned_document"
    status = 422
    message = (
        "That PDF appears to be scanned images rather than text, and OCR is "
        "disabled. Upload a text-based PDF, or enable OCR on the server."
    )


class DocumentTooLong(ProjectReviveError):
    code = "document_too_long"
    status = 422
    message = "That document has more pages than this service will process."


class AnalysisNotFound(ProjectReviveError):
    code = "analysis_not_found"
    status = 404
    message = "No analysis was found with that id."


class LLMUnavailable(ProjectReviveError):
    code = "llm_unavailable"
    status = 503
    message = "The analysis model is not reachable right now. Try again shortly."


class LLMRefused(ProjectReviveError):
    """The model's safety classifiers declined the request.

    Surfaced distinctly from a crash so the user learns their document tripped
    a policy check rather than that the service is broken.
    """

    code = "llm_refused"
    status = 422
    message = (
        "The analysis model declined to process this document. That usually "
        "means something in its content triggered a safety classifier."
    )


class LLMOutputTruncated(ProjectReviveError):
    """The model hit the output cap mid-structure."""

    code = "llm_output_truncated"
    status = 502
    message = (
        "The analysis did not fit within the model's output limit, so it was "
        "rejected rather than shown half-finished. Try a shorter document."
    )


class LLMInvalidOutput(ProjectReviveError):
    code = "llm_invalid_output"
    status = 502
    message = (
        "The analysis model returned output that did not match the expected "
        "structure, so it was rejected rather than shown as a result."
    )


# --- Authentication ---------------------------------------------------------


class NotAuthenticated(ProjectReviveError):
    code = "not_authenticated"
    status = 401
    message = "Sign in to continue."


class InvalidSession(NotAuthenticated):
    code = "invalid_session"
    message = "Your session is no longer valid. Sign in again."


class InvalidCredentials(ProjectReviveError):
    """Deliberately identical for an unknown email and a wrong password.

    Distinguishing them would let anyone test which email addresses have
    accounts here.
    """

    code = "invalid_credentials"
    status = 401
    message = "That email and password combination is not correct."


class EmailAlreadyRegistered(ProjectReviveError):
    code = "email_already_registered"
    status = 409
    message = "An account already exists for that email address."


class WeakPassword(ProjectReviveError):
    code = "weak_password"
    status = 422
    message = "That password is too weak."


class Forbidden(ProjectReviveError):
    code = "forbidden"
    status = 403
    message = "That item does not belong to your account."


class RateLimited(ProjectReviveError):
    """Too many requests. Always carries Retry-After so clients can back off."""

    code = "rate_limited"
    status = 429
    message = "Too many requests. Wait a moment and try again."

    def __init__(self, retry_after: int, message: str | None = None):
        self.retry_after = retry_after
        super().__init__(message, headers={"Retry-After": str(retry_after)})

    def to_payload(self) -> dict[str, object]:
        payload = super().to_payload()
        payload["retry_after_seconds"] = self.retry_after
        return payload


class AccountTemporarilyLocked(RateLimited):
    """Repeated failed sign-ins for one account.

    Separate from the generic 429 so the UI can explain that this is about the
    account rather than about request volume.
    """

    code = "account_locked"
