"""The base of talkgenerator's data models."""

from pydantic import BaseModel, ConfigDict


class Data(BaseModel):
    """Immutable and strict: unknown fields are an error instead of being dropped without a word."""

    model_config = ConfigDict(extra="forbid", frozen=True)
