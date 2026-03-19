"""Security / certificate management service."""

import asyncio
import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.models import ArgusConfiguration

logger = logging.getLogger(__name__)

CA_CERT_FILENAME = "ca.crt"
CA_KEY_FILENAME = "ca.key"
DEFAULT_CERT_DIR = "/opt/argus-insight-server/certs"
OPENSSL_PATH_ERROR = (
    "Please specify the absolute path to OpenSSL "
    "in the Command Tab's OpenSSL Absolute Path."
)


async def _get_config_value(session: AsyncSession, category: str, key: str) -> str:
    """Retrieve a single infra config value."""
    logger.info(
        "Querying config value: category=%s, key=%s", category, key,
    )
    result = await session.execute(
        select(ArgusConfiguration).where(
            ArgusConfiguration.category == category,
            ArgusConfiguration.config_key == key,
        )
    )
    row = result.scalar_one_or_none()
    value = row.config_value if row else ""
    logger.info(
        "Config value retrieved: category=%s, key=%s, value=%s",
        category, key, value or "(empty)",
    )
    return value


async def get_openssl_path(session: AsyncSession) -> str:
    """Get the configured OpenSSL binary path."""
    value = await _get_config_value(session, "command", "openssl_path")
    logger.info("OpenSSL path resolved: %s", value or "(not configured)")
    return value


async def get_ca_cert_dir(session: AsyncSession) -> str:
    """Get the configured CA certificate directory path."""
    value = await _get_config_value(session, "security", "ca_cert_dir")
    resolved = value if value else DEFAULT_CERT_DIR
    if not value:
        logger.info(
            "CA cert directory not configured, using default: %s",
            DEFAULT_CERT_DIR,
        )
    logger.info("CA cert directory resolved: %s", resolved)
    return resolved


async def get_ca_cert_status(session: AsyncSession) -> dict:
    """Check if the CA certificate file exists."""
    logger.info("Checking CA certificate status")
    cert_dir = await get_ca_cert_dir(session)
    cert_path = Path(cert_dir) / CA_CERT_FILENAME
    logger.info("Checking CA certificate file existence: %s", cert_path)
    exists = cert_path.is_file()
    logger.info(
        "CA cert status result: path=%s, exists=%s", cert_path, exists,
    )
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
    logger.info(
        "Starting CA certificate upload: content_size=%d bytes",
        len(file_content),
    )
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
        logger.info("CA cert directory ready: %s", cert_dir)
    except OSError as exc:
        logger.error(
            "Failed to create CA cert directory %s: %s", cert_dir, exc,
        )
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    cert_file = cert_dir_path / CA_CERT_FILENAME

    # Write the file
    logger.info("Writing CA certificate to %s", cert_file)
    try:
        cert_file.write_bytes(file_content)
        logger.info(
            "CA certificate file written: path=%s, size=%d bytes",
            cert_file, len(file_content),
        )
    except OSError as exc:
        logger.error(
            "Failed to write CA cert file %s: %s", cert_file, exc,
        )
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    # Validate with openssl
    logger.info(
        "Validating CA certificate with openssl x509: "
        "openssl=%s, cert=%s",
        openssl_path, cert_file,
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            openssl_path, "x509", "-in", str(cert_file), "-text", "-noout",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        logger.info(
            "openssl x509 validation completed: returncode=%d",
            proc.returncode,
        )
        if proc.returncode != 0:
            logger.error(
                "CA certificate validation failed: %s", stderr.decode(),
            )
            cert_file.unlink(missing_ok=True)
            logger.info(
                "Invalid CA certificate file removed: %s", cert_file,
            )
            raise ValueError("유효하지 않은 인증서입니다.")
    except FileNotFoundError:
        logger.error("OpenSSL binary not found at %s", openssl_path)
        cert_file.unlink(missing_ok=True)
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    logger.info(
        "CA certificate uploaded and validated successfully: %s",
        cert_file,
    )
    return {
        "success": True,
        "filename": CA_CERT_FILENAME,
        "path": str(cert_file),
    }


async def view_ca_cert(session: AsyncSession) -> dict:
    """Read and decode the CA certificate file.

    Returns both the raw PEM content and the decoded openssl x509 -text output.
    """
    logger.info("Starting CA certificate view process")
    cert_dir = await get_ca_cert_dir(session)
    openssl_path = await get_openssl_path(session)

    if not openssl_path:
        logger.error("OpenSSL path is not configured")
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    cert_file = Path(cert_dir) / CA_CERT_FILENAME
    logger.info("Checking CA certificate file: %s", cert_file)

    if not cert_file.is_file():
        logger.error("CA certificate file not found: %s", cert_file)
        raise FileNotFoundError("CA 인증서 파일이 존재하지 않습니다.")

    # Read raw content
    logger.info("Reading raw CA certificate content: %s", cert_file)
    raw = cert_file.read_text(encoding="utf-8", errors="replace")
    logger.info(
        "CA certificate raw content read: size=%d chars", len(raw),
    )

    # Decode with openssl
    logger.info(
        "Decoding CA certificate with openssl x509 -text -noout: "
        "openssl=%s, cert=%s",
        openssl_path, cert_file,
    )
    proc = await asyncio.create_subprocess_exec(
        openssl_path, "x509", "-in", str(cert_file), "-text", "-noout",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    logger.info(
        "openssl x509 decode completed: returncode=%d", proc.returncode,
    )

    if proc.returncode != 0:
        logger.error(
            "Failed to decode CA certificate: %s", stderr.decode(),
        )
        raise ValueError("인증서 디코딩에 실패했습니다.")

    decoded = stdout.decode(encoding="utf-8", errors="replace")
    logger.info(
        "CA certificate decoded: decoded_size=%d chars", len(decoded),
    )
    logger.info("CA certificate view completed successfully: %s", cert_file)
    return {"raw": raw, "decoded": decoded}


async def delete_ca_cert(session: AsyncSession) -> dict:
    """Delete the CA certificate file."""
    logger.info("Starting CA certificate deletion process")
    cert_dir = await get_ca_cert_dir(session)
    cert_file = Path(cert_dir) / CA_CERT_FILENAME
    logger.info("Checking CA certificate file for deletion: %s", cert_file)

    if not cert_file.is_file():
        logger.error(
            "CA certificate file not found for deletion: %s", cert_file,
        )
        raise FileNotFoundError("CA 인증서 파일이 존재하지 않습니다.")

    logger.info("Deleting CA certificate file: %s", cert_file)
    cert_file.unlink()
    logger.info("CA certificate deleted successfully: %s", cert_file)
    return {"success": True, "message": "CA 인증서가 삭제되었습니다."}


# --------------------------------------------------------------------------- #
# CA Key Management
# --------------------------------------------------------------------------- #


async def get_ca_key_status(session: AsyncSession) -> dict:
    """Check if the CA key file exists."""
    logger.info("Checking CA key status")
    cert_dir = await get_ca_cert_dir(session)
    key_path = Path(cert_dir) / CA_KEY_FILENAME
    logger.info("Checking CA key file existence: %s", key_path)
    exists = key_path.is_file()
    logger.info(
        "CA key status result: path=%s, exists=%s", key_path, exists,
    )
    return {
        "exists": exists,
        "filename": CA_KEY_FILENAME if exists else "",
        "cert_path": cert_dir,
    }


async def upload_ca_key(
    session: AsyncSession, file_content: bytes,
) -> dict:
    """Upload and validate a CA key file.

    Steps:
    1. Resolve the CA cert directory (from config or default).
    2. Create the directory if it does not exist.
    3. Write the uploaded content as ca.key.
    4. Validate with openssl rsa -in ca.key -check -noout.
    5. Delete the file if validation fails (RSA key ok not in output).
    """
    logger.info(
        "Starting CA key upload: content_size=%d bytes",
        len(file_content),
    )
    cert_dir = await get_ca_cert_dir(session)
    openssl_path = await get_openssl_path(session)

    if not openssl_path:
        logger.error("OpenSSL path is not configured")
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    cert_dir_path = Path(cert_dir)

    # Create directory if it doesn't exist
    logger.info("Ensuring CA key directory exists: %s", cert_dir)
    try:
        cert_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info("CA key directory ready: %s", cert_dir)
    except OSError as exc:
        logger.error(
            "Failed to create CA key directory %s: %s", cert_dir, exc,
        )
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    key_file = cert_dir_path / CA_KEY_FILENAME

    # Write the file
    logger.info("Writing CA key to %s", key_file)
    try:
        key_file.write_bytes(file_content)
        logger.info(
            "CA key file written: path=%s, size=%d bytes",
            key_file, len(file_content),
        )
    except OSError as exc:
        logger.error(
            "Failed to write CA key file %s: %s", key_file, exc,
        )
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    # Validate with openssl rsa -check
    logger.info(
        "Validating CA key with openssl rsa -check -noout: "
        "openssl=%s, key=%s",
        openssl_path, key_file,
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            openssl_path, "rsa", "-in", str(key_file), "-check", "-noout",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        output = stdout.decode() + stderr.decode()
        logger.info(
            "openssl rsa validation completed: returncode=%d, output=%s",
            proc.returncode, output.strip(),
        )
        if "RSA key ok" not in output:
            logger.error("CA key validation failed: %s", output)
            key_file.unlink(missing_ok=True)
            logger.info("Invalid CA key file removed: %s", key_file)
            raise ValueError("유효하지 않은 Key입니다.")
    except FileNotFoundError:
        logger.error("OpenSSL binary not found at %s", openssl_path)
        key_file.unlink(missing_ok=True)
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    logger.info(
        "CA key uploaded and validated successfully: %s", key_file,
    )
    return {
        "success": True,
        "filename": CA_KEY_FILENAME,
        "path": str(key_file),
    }


async def view_ca_key(session: AsyncSession) -> dict:
    """Read and decode the CA key file.

    Returns both the raw PEM content and the decoded openssl rsa -text output.
    """
    logger.info("Starting CA key view process")
    cert_dir = await get_ca_cert_dir(session)
    openssl_path = await get_openssl_path(session)

    if not openssl_path:
        logger.error("OpenSSL path is not configured")
        raise ValueError("OpenSSL Absolute Path를 먼저 지정해주세요.")

    key_file = Path(cert_dir) / CA_KEY_FILENAME
    logger.info("Checking CA key file: %s", key_file)

    if not key_file.is_file():
        logger.error("CA key file not found: %s", key_file)
        raise FileNotFoundError("CA Key 파일이 존재하지 않습니다.")

    # Read raw content
    logger.info("Reading raw CA key content: %s", key_file)
    raw = key_file.read_text(encoding="utf-8", errors="replace")
    logger.info("CA key raw content read: size=%d chars", len(raw))

    # Decode with openssl
    logger.info(
        "Decoding CA key with openssl rsa -text -noout: "
        "openssl=%s, key=%s",
        openssl_path, key_file,
    )
    proc = await asyncio.create_subprocess_exec(
        openssl_path, "rsa", "-in", str(key_file), "-text", "-noout",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    logger.info(
        "openssl rsa decode completed: returncode=%d", proc.returncode,
    )

    if proc.returncode != 0:
        logger.error("Failed to decode CA key: %s", stderr.decode())
        raise ValueError("Key 디코딩에 실패했습니다.")

    decoded = stdout.decode(encoding="utf-8", errors="replace")
    logger.info("CA key decoded: decoded_size=%d chars", len(decoded))
    logger.info("CA key view completed successfully: %s", key_file)
    return {"raw": raw, "decoded": decoded}


async def delete_ca_key(session: AsyncSession) -> dict:
    """Delete the CA key file."""
    logger.info("Starting CA key deletion process")
    cert_dir = await get_ca_cert_dir(session)
    key_file = Path(cert_dir) / CA_KEY_FILENAME
    logger.info("Checking CA key file for deletion: %s", key_file)

    if not key_file.is_file():
        logger.error(
            "CA key file not found for deletion: %s", key_file,
        )
        raise FileNotFoundError("CA Key 파일이 존재하지 않습니다.")

    logger.info("Deleting CA key file: %s", key_file)
    key_file.unlink()
    logger.info("CA key deleted successfully: %s", key_file)
    return {"success": True, "message": "CA Key가 삭제되었습니다."}


# --------------------------------------------------------------------------- #
# Self-Signed CA Generation
# --------------------------------------------------------------------------- #


async def generate_self_signed_ca(
    session: AsyncSession,
    *,
    country: str,
    state: str,
    locality: str,
    organization: str,
    org_unit: str,
    common_name: str,
    days: int,
    key_bits: int,
) -> dict:
    """Generate a self-signed CA certificate and key.

    Steps:
    1. Validate OpenSSL path exists and is a real file.
    2. Resolve the CA cert directory; create if needed.
    3. Generate RSA private key with openssl genrsa.
    4. Generate self-signed CA certificate with openssl req -x509.
    5. Return filenames on success.
    """
    logger.info(
        "Starting self-signed CA generation: "
        "C=%s, ST=%s, L=%s, O=%s, OU=%s, CN=%s, days=%d, bits=%d",
        country, state, locality, organization,
        org_unit, common_name, days, key_bits,
    )
    cert_dir = await get_ca_cert_dir(session)
    openssl_path = await get_openssl_path(session)

    # Validate openssl path
    logger.info("Validating OpenSSL binary path: %s", openssl_path)
    if not openssl_path:
        logger.error("OpenSSL path is not configured")
        raise ValueError(OPENSSL_PATH_ERROR)

    if not os.path.isfile(openssl_path):
        logger.error(
            "OpenSSL binary not found at configured path: %s",
            openssl_path,
        )
        raise ValueError(OPENSSL_PATH_ERROR)
    logger.info("OpenSSL binary validated: %s", openssl_path)

    cert_dir_path = Path(cert_dir)

    # Create directory if it doesn't exist
    logger.info(
        "Ensuring CA directory exists for generation: %s", cert_dir,
    )
    try:
        cert_dir_path.mkdir(parents=True, exist_ok=True)
        logger.info("CA directory ready: %s", cert_dir)
    except OSError as exc:
        logger.error(
            "Failed to create CA directory %s: %s", cert_dir, exc,
        )
        raise PermissionError("디렉토리를 생성할 수 없습니다.") from exc

    key_file = cert_dir_path / CA_KEY_FILENAME
    cert_file = cert_dir_path / CA_CERT_FILENAME

    # Step 1: Generate RSA private key
    logger.info(
        "Generating RSA private key: bits=%d, path=%s", key_bits, key_file,
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            openssl_path, "genrsa", "-out", str(key_file), str(key_bits),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        logger.info(
            "openssl genrsa completed: returncode=%d", proc.returncode,
        )
        if proc.returncode != 0:
            logger.error(
                "Failed to generate RSA key: %s", stderr.decode(),
            )
            key_file.unlink(missing_ok=True)
            raise ValueError(
                f"RSA Key 생성에 실패했습니다: {stderr.decode().strip()}"
            )
    except FileNotFoundError:
        logger.error("OpenSSL binary not found at %s", openssl_path)
        raise ValueError(OPENSSL_PATH_ERROR)
    logger.info("RSA private key generated successfully: %s", key_file)

    # Set key file permissions to 400
    logger.info("Setting key file permissions to 400: %s", key_file)
    try:
        os.chmod(str(key_file), 0o400)
        logger.info(
            "Key file permissions set to 400 successfully: %s", key_file,
        )
    except OSError as exc:
        logger.warning("Failed to set key file permissions: %s", exc)

    # Step 2: Generate self-signed CA certificate
    subj = (
        f"/C={country}/ST={state}/L={locality}"
        f"/O={organization}/OU={org_unit}/CN={common_name}"
    )
    logger.info(
        "Generating self-signed CA certificate: subj=%s, days=%d, path=%s",
        subj, days, cert_file,
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            openssl_path, "req", "-x509", "-new", "-nodes",
            "-key", str(key_file),
            "-sha256",
            "-days", str(days),
            "-out", str(cert_file),
            "-subj", subj,
            "-addext", "basicConstraints=critical,CA:TRUE",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        logger.info(
            "openssl req -x509 completed: returncode=%d",
            proc.returncode,
        )
        if proc.returncode != 0:
            logger.error(
                "Failed to generate CA certificate: %s", stderr.decode(),
            )
            key_file.unlink(missing_ok=True)
            cert_file.unlink(missing_ok=True)
            logger.info(
                "Cleaned up failed generation files: key=%s, cert=%s",
                key_file, cert_file,
            )
            raise ValueError(
                f"CA 인증서 생성에 실패했습니다: {stderr.decode().strip()}"
            )
    except FileNotFoundError:
        logger.error("OpenSSL binary not found at %s", openssl_path)
        key_file.unlink(missing_ok=True)
        raise ValueError(OPENSSL_PATH_ERROR)

    logger.info(
        "Self-signed CA certificate generated successfully: %s",
        cert_file,
    )
    logger.info(
        "Self-signed CA generation completed: cert=%s, key=%s",
        cert_file, key_file,
    )
    return {
        "success": True,
        "cert_filename": CA_CERT_FILENAME,
        "key_filename": CA_KEY_FILENAME,
        "cert_path": str(cert_file),
        "key_path": str(key_file),
    }
