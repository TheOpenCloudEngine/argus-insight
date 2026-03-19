"""DNS zone management Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DnsRecord(BaseModel):
    """A single DNS record within an RRset."""

    content: str
    disabled: bool


class DnsComment(BaseModel):
    """A comment on an RRset."""

    content: str
    account: str
    modified_at: int


class DnsRecordRow(BaseModel):
    """Flattened row for the UI data table.

    Each record within an RRset becomes its own row.
    """

    name: str
    type: str
    ttl: int
    content: str
    disabled: bool
    comment: str = ""


class DnsZoneTableResponse(BaseModel):
    """Table-ready response with flattened records."""

    zone: str
    records: list[DnsRecordRow]


class DnsRRsetPatch(BaseModel):
    """A single RRset modification for PATCH requests."""

    name: str
    type: str
    ttl: int
    changetype: str  # "REPLACE" or "DELETE"
    records: list[DnsRecord] = []
    comments: list[DnsComment] = []


class DnsRecordUpdateRequest(BaseModel):
    """Request body for updating DNS records via PATCH."""

    rrsets: list[DnsRRsetPatch]
