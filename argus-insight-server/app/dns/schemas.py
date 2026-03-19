"""DNS zone management Pydantic schemas.

Defines the request and response models used by the DNS zone API endpoints.
These schemas mirror the PowerDNS API data structures but are tailored for
the Argus Insight UI, which expects a flat table of individual records
rather than the nested RRset format that PowerDNS uses natively.
"""

from __future__ import annotations

from pydantic import BaseModel


class DnsRecord(BaseModel):
    """A single DNS record within an RRset.

    Represents one record entry in the PowerDNS ``records`` array inside an RRset.
    Used both for reading existing records and for constructing PATCH payloads.
    """

    # The record data value (e.g. "10.0.1.50" for A, "ns1.example.com." for NS)
    content: str
    # Whether this record is disabled in PowerDNS (disabled records are not served)
    disabled: bool


class DnsComment(BaseModel):
    """A comment attached to an RRset in PowerDNS.

    PowerDNS allows associating free-text comments with each RRset.
    Comments are stored per-RRset, not per individual record.
    """

    # The comment text
    content: str
    # The account/user who created the comment
    account: str
    # Unix timestamp of when the comment was last modified
    modified_at: int


class DnsRecordRow(BaseModel):
    """Flattened row for the UI data table.

    PowerDNS groups records into RRsets (name + type), but the UI displays
    each individual record as its own row. This schema represents that
    flattened view where each record within an RRset becomes its own row,
    duplicating the name, type, and TTL fields.
    """

    # Fully qualified domain name (e.g. "www.example.com.")
    name: str
    # DNS record type (e.g. "A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA")
    type: str
    # Time-to-live in seconds for DNS caching
    ttl: int
    # The record data value, format depends on record type
    content: str
    # Whether this record is disabled (not served by PowerDNS)
    disabled: bool
    # Optional comment from the RRset (first comment only, shared across all records in the RRset)
    comment: str = ""


class DnsZoneTableResponse(BaseModel):
    """Table-ready response with flattened records.

    Returned by the GET /dns/zone/records endpoint.
    Contains the zone name and all records flattened into individual rows.
    """

    # The domain name of the zone (without trailing dot)
    zone: str
    # All DNS records in the zone, flattened from RRsets into individual rows
    records: list[DnsRecordRow]


class DnsRRsetPatch(BaseModel):
    """A single RRset modification for PATCH requests.

    Maps to a single entry in the PowerDNS PATCH ``/zones/{zone}`` payload.
    Used to add, update, or delete records within a zone.
    """

    # Fully qualified domain name for the RRset (must include trailing dot)
    name: str
    # DNS record type (e.g. "A", "CNAME", "MX")
    type: str
    # Time-to-live in seconds (ignored for DELETE operations)
    ttl: int
    # Operation type: "REPLACE" to add/update records, "DELETE" to remove the entire RRset
    changetype: str
    # Records to set (empty list for DELETE operations)
    records: list[DnsRecord] = []
    # Optional comments to attach to the RRset
    comments: list[DnsComment] = []


class DnsRecordUpdateRequest(BaseModel):
    """Request body for updating DNS records via PATCH.

    Wraps a list of RRset patches to be applied atomically to the zone.
    Sent by the UI when adding, editing, or deleting DNS records.
    """

    # List of RRset modifications to apply
    rrsets: list[DnsRRsetPatch]


class DnsHealthResponse(BaseModel):
    """Response from the PowerDNS health check.

    Used by the UI to determine the current state of the PowerDNS connection
    and decide which UI to display (settings prompt, zone creation, or records table).
    """

    # Whether the PowerDNS API server is reachable and responding
    reachable: bool
    # Whether the configured domain zone exists on the PowerDNS server
    zone_exists: bool
    # The configured domain name (may be empty if settings are not configured)
    zone: str
    # Human-readable error message if something went wrong, None if healthy
    error: str | None = None


class DnsZoneCreateResponse(BaseModel):
    """Response after creating a zone on the PowerDNS server."""

    # The domain name of the newly created zone
    zone: str
    # Whether the zone was successfully created
    created: bool


class BindConfigFile(BaseModel):
    """A single BIND configuration file for export.

    Represents one file in the BIND config export (e.g. named.conf.local or db.example.com).
    """

    # The filename (e.g. "named.conf.local", "db.example.com")
    filename: str
    # The full text content of the configuration file
    content: str


class BindConfigResponse(BaseModel):
    """Response containing BIND configuration files for a zone.

    Used by the UI to display a preview of the BIND config and offer
    a ZIP download of all configuration files.
    """

    # The domain name of the zone these config files belong to
    zone: str
    # List of generated configuration files (typically named.conf.local + db.{zone})
    files: list[BindConfigFile]
