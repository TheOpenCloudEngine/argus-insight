"""DNS zone management module.

Provides REST API endpoints for managing DNS zones and records through
the PowerDNS Authoritative Server API. This module handles:

- Health checking of the PowerDNS server connection and zone existence
- Creating new DNS zones with default NS and glue records
- Fetching and updating DNS resource record sets (RRsets)
- Exporting zone data as BIND-compatible configuration files

The module reads PowerDNS connection settings (IP, port, API key, domain name)
from the application database (``argus_configuration`` table, category='domain')
and uses them to communicate with the PowerDNS REST API.

Module structure:
    - ``schemas.py``: Pydantic models for request/response validation
    - ``service.py``: Business logic and PowerDNS API communication
    - ``router.py``: FastAPI route definitions under ``/api/v1/dns``
"""
