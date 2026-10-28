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

    def __init__(self, message: str | None = None, *, detail: str | None = None):
        self.message = message or self.message
        self.detail = detail
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


class LLMInvalidOutput(ProjectReviveError):
    code = "llm_invalid_output"
    status = 502
    message = (
        "The analysis model returned output that did not match the expected "
        "structure, so it was rejected rather than shown as a result."
    )
