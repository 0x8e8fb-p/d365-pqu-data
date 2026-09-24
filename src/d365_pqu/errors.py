from __future__ import annotations


class PquError(Exception):
    """Base error for the dataset pipeline."""


class SourceFetchError(PquError):
    """The Microsoft source could not be resolved or downloaded."""


class ParserError(PquError):
    """The Microsoft source structure could not be parsed safely."""


class ValidationError(PquError):
    """The candidate dataset failed fatal validation."""


class PublishError(PquError):
    """Validated artifacts could not be written or published."""
