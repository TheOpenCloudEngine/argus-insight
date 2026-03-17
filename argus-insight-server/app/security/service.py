"""Security / certificate management service."""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infraconfig.models import ArgusConfigurationInfra

logger = logging.getLogger(__name__)

CA_CERT_FILENAME = "ca.crt"
DEFAULT_CERT_DIR = "/opt/argus-insight-server/certs"


async def _get_config_value(session: AsyncSession, category: str, key: str) -> str:
    """Retrieve a single infra config value."""
    result = await session.execute(
        select(ArgusConfigurationInfra).where(
            ArgusConfigurationInfra.category == category,
            ArgusConfigurationInfra.config_key == key,
        )
    )
    row = result.scalar_one_or_none()
    return row.config_value if row else ""


async def get_openssl_path(session: AsyncSession) -> str:
    """Get the configured OpenSSL binary path."""
    return await _get_config_value(session, "command", "openssl_path")


async def get_ca_cert_dir(session: AsyncSession) -> str:
    """Get the configured CA certificate directory path."""
    value = await _get_config_value(session, "security", "ca_cert_dir")
    return value if value else DEFAULT_CERT_DIR


async def get_ca_cert_status(session: AsyncSession) -> dict:
    """Check if the CA certificate file exists."""
    cert_dir = await get_ca_cert_dir(session)
    cert_path = Path(cert_dir) / CA_CERT_FILENAME
    exists = cert_path.is_file()
    logger.info("CA cert status check: path=%s, exists=%s", cert_path, exists)
    return {
        "exists": exists,
        "filename": CA_CERT_FILENAME if exists else "",
        "cert_path": cert_dir,
    }


async def upload_ca_cert(
    session: AsyncSession, file_content: bytes,
) -> dict:
    """Upload and validate a CA certificate file.

    Steps:
    1. Resolve the CA cert directory (from config or default).
    2. Create the directory if it does not exist.
    3. Write the uploaded content as ca.crt.
    4. Validate with openssl x509.
    5. Delete the file if validation fails.
    """
    cert_dir = await get_ca_cert_dir(session)
    openssl_path = await get_openssl_path(session)

    if not openssl_path:
        logger.error("OpenSSL path is not configured")
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    cert_dir_path = Path(cert_dir)

    # Create directory if it doesn't exist
    logger.info("Ensuring CA cert directory exists: %s", cert_dir)
    try:
        cert_dir_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create CA cert directory %s: %s", cert_dir, exc)
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    cert_file = cert_dir_path / CA_CERT_FILENAME

    # Write the file
    logger.info("Writing CA certificate to %s", cert_file)
    try:
        cert_file.write_bytes(file_content)
    except OSError as exc:
        logger.error("Failed to write CA cert file %s: %s", cert_file, exc)
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    # Validate with openssl
    logger.info("Validating CA certificate with openssl: %s", cert_file)
    try:
        proc = await asyncio.create_subprocess_exec(
            openssl_path, "x509", "-in", str(cert_file), "-text", "-noout",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.error("CA certificate validation failed: %s", stderr.decode())
            cert_file.unlink(missing_ok=True)
            raise ValueError("유효하지 않은 인증서입니다.")
    except FileNotFoundError:
        logger.error("OpenSSL binary not found at %s", openssl_path)
        cert_file.unlink(missing_ok=True)
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    logger.info("CA certificate uploaded and validated successfully: %s", cert_file)
    return {
        "success": True,
        "filename": CA_CERT_FILENAME,
        "path": str(cert_file),
    }


async def view_ca_cert(session: AsyncSession) -> dict:
    """Read and decode the CA certificate file.

    Returns both the raw PEM content and the decoded openssl x509 -text output.
    """
    cert_dir = await get_ca_cert_dir(session)
    openssl_path = await get_openssl_path(session)

    if not openssl_path:
        logger.error("OpenSSL path is not configured")
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    cert_file = Path(cert_dir) / CA_CERT_FILENAME

    if not cert_file.is_file():
        logger.error("CA certificate file not found: %s", cert_file)
        raise FileNotFoundError("CA 인증서 파일이 존재하지 않습니다.")

    # Read raw content
    logger.info("Reading CA certificate: %s", cert_file)
    raw = cert_file.read_text(encoding="utf-8", errors="replace")

    # Decode with openssl
    logger.info("Decoding CA certificate with openssl: %s", cert_file)
    proc = await asyncio.create_subprocess_exec(
        openssl_path, "x509", "-in", str(cert_file), "-text", "-noout",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("Failed to decode CA certificate: %s", stderr.decode())
        raise ValueError("인증서 디코딩에 실패했습니다.")

    decoded = stdout.decode(encoding="utf-8", errors="replace")
    logger.info("CA certificate viewed successfully: %s", cert_file)
    return {"raw": raw, "decoded": decoded}


async def delete_ca_cert(session: AsyncSession) -> dict:
    """Delete the CA certificate file."""
    cert_dir = await get_ca_cert_dir(session)
    cert_file = Path(cert_dir) / CA_CERT_FILENAME

    if not cert_file.is_file():
        logger.error("CA certificate file not found for deletion: %s", cert_file)
        raise FileNotFoundError("CA 인증서 파일이 존재하지 않습니다.")

    logger.info("Deleting CA certificate: %s", cert_file)
    cert_file.unlink()
    logger.info("CA certificate deleted successfully: %s", cert_file)
    return {"success": True, "message": "CA 인증서가 삭제되었습니다."}
