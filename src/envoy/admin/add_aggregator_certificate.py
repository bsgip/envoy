import os
import sys
import json
import argparse
import httpx
import asyncio
import datetime as dt
from typing import Tuple
from pathlib import Path
from dotenv import load_dotenv
from cryptography import x509

from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends

from envoy_schema.admin.schema import uri
from envoy_schema.admin.schema.certificate import CertificateAssignmentRequest, CertificatePageResponse
from envoy_schema.admin.schema.certificate import CertificateResponse
from envoy_schema.admin.schema.aggregator import AggregatorRequest, AggregatorDomain
from envoy_schema.admin.schema.aggregator import AggregatorPageResponse, AggregatorResponse


env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)
DEFAULT_USERNAME = os.getenv("ADMIN_USERNAME")
DEFAULT_PASSWORD = os.getenv("ADMIN_PASSWORD")


def is_root_certificate(cert: x509.Certificate) -> bool:

    # Must be self-signed
    if cert.subject != cert.issuer:
        return False

    # Check for CA basic constraint
    try:
        basic_constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        return basic_constraints.ca
    except x509.ExtensionNotFound:
        return False


def is_intermediate_certificate(cert: x509.Certificate) -> bool:

    # Must not be self-signed (issuer ≠ subject)
    if cert.subject == cert.issuer:
        return False

    # Check for CA basic constraint
    try:
        basic_constraints = cert.extensions.get_extension_for_class(x509.BasicConstraints).value
        return basic_constraints.ca
    except x509.ExtensionNotFound:
        return False


def check_certificate(pem_file_path: Path) -> Tuple[str, dt.datetime]:
    """
    Checks that the PEM file naming convention, that it contains three
    certificates (client, intermediate, root), extracts expiry date from client
    certificate, and calculates the LFDI (first 40 hex chars of client cert in
    base64).

    Returns:
        lfdi (str): First 40 hex characters of client cert in base64.
        cert_expiry (str): Not valid after date of client cert (ISO format).
    """

    with open(pem_file_path, "rb") as f:
        pem_data = f.read()

    certs = x509.load_pem_x509_certificates(pem_data)
    cert_expiry = certs[0].not_valid_after_utc

    # Check that file name follows convention
    parts = pem_file_path.stem.split("-")
    try:
        expiry_date = dt.datetime.strptime(parts[-1], "%Y%m%d")
        if not (
            cert_expiry.year == expiry_date.year
            and cert_expiry.month == expiry_date.month
            and cert_expiry.day == expiry_date.day
        ):
            raise ValueError("Certificate expiry does not match date in filename")
    except Exception:
        expiry_date = None

    if (
        pem_file_path.suffix != ".pem"
        or len(parts) != 4
        or parts[0] != "edith"
        or parts[1] not in ["dev", "test", "prod"]
        or not expiry_date
    ):
        raise ValueError("Invalid PEM file name format, should be edith-[prod|test|dev]-<customer>-<expiry_date>.pem")

    # Certificate checks, including expiry dates
    if len(certs) != 3:
        raise ValueError("PEM file must contain exactly three certificates (client, intermediate, root)")
    if not is_intermediate_certificate(certs[1]):
        raise ValueError("The second entry in the PEM file must be a valid intermediate certificate")
    if not is_root_certificate(certs[2]):
        raise ValueError("The last entry in the PEM file must be a valid root certificate")

    for c in certs:
        if not c.not_valid_after_utc > dt.datetime.now(dt.timezone.utc):
            raise ValueError("Certificates must be valid (not expired)")

    # Calculate LFDI
    lfdi = LFDIAuthDepends.generate_lfdi_from_pem(pem_data.decode("utf-8"))

    return lfdi, cert_expiry


async def create_aggregator(aggregator_name: str, aggregator_domain: str, admin_url: str, auth: Tuple[str, str]) -> int:
    """
    Creates a new aggregator

    Args:
        aggregator_name (str)
        admin_url (str): Base URL of the admin endpoint.
        auth (Tuple[str, str]): Tuple containing username and password for basic HTTP authentication.

    Returns:
        int: aggregator id
    """

    created_time = dt.datetime.now()
    changed_time = created_time
    domains = [AggregatorDomain(domain=aggregator_domain, created_time=created_time, changed_time=changed_time)]
    agg_payload = AggregatorRequest(
        name=aggregator_name, created_time=created_time, changed_time=changed_time, domains=domains
    ).model_dump_json()

    async with httpx.AsyncClient() as client:
        response = await client.post(admin_url + uri.AggregatorCreateUri, content=agg_payload, auth=auth)
        response.raise_for_status()

    return response.json()["aggregator_id"]


async def get_aggregators(admin_url: str, auth: Tuple[str, str]) -> list[AggregatorResponse]:
    """
    Fetches the current list of aggregator names from the server asynchronously.

    Args:
        admin_url (str): URL of the admin aggregator endpoint.
        username (str): Username for basic HTTP authentication.
        password (str): Password for basic HTTP authentication.

    Returns:
        list[str]: List of aggregator names.
    """

    async with httpx.AsyncClient() as client:
        aggregator_list_url = admin_url + uri.AggregatorListUri
        response = await client.get(aggregator_list_url, auth=auth)
        response.raise_for_status()

        agg_page = AggregatorPageResponse(**json.loads(response.text))
        return agg_page.aggregators


async def get_certificates(aggregator_id: int, admin_url: str, auth: Tuple[str, str]) -> list[CertificateResponse]:

    async with httpx.AsyncClient() as client:
        certificate_list_url = admin_url + uri.AggregatorCertificateListUri.format(aggregator_id=aggregator_id)
        response = await client.get(certificate_list_url, auth=auth)
        response.raise_for_status()

        cert_page = CertificatePageResponse(**json.loads(response.text))
        return cert_page.certificates


async def add_client_certificate(
    aggregator_name: str,
    aggregator_domain: str,
    pem_file_path: Path,
    admin_url: str,
    auth: Tuple[str, str],
    create_agg: bool = False,
) -> None:
    """
    Adds a client certificate to an aggregator, can create the aggregator if it does not exist.

    Args:
        aggregator_name (str): Name of the aggregator.
        aggregator_domain (str): Domain of the aggregator.
        pem_file_path (str): Path to .pem file containing the certificate.
        auth (Tuple[str, str]): Tuple containing username and password for basic HTTP authentication.
        create_aggregator (bool, optional): If True, creates a new aggregator before updating the certificate.
    """

    lfdi, cert_expiry = check_certificate(pem_file_path)

    aggregators = await get_aggregators(admin_url, auth)

    if create_agg:
        aggregator_names = [agg.name for agg in aggregators]
        if aggregator_name in aggregator_names:
            raise ValueError(f"Aggregator {aggregator_name} already exists")

        agg_id = await create_aggregator(aggregator_name, aggregator_domain, admin_url, auth)
    else:
        for agg in aggregators:
            if agg.name == aggregator_name:
                agg_id = agg.aggregator_id
                break
        else:
            raise ValueError(f"Aggregator with name {aggregator_name} not found")

        # Check whether this aggregator already the given certificate
        existing_certs = await get_certificates(agg_id, admin_url, auth)
        for c in existing_certs:
            if c.lfdi == lfdi:
                raise ValueError(f"Certificate with LFDI {lfdi} already exists for aggregator {aggregator_name}")

    # Add certificate to aggregator
    async with httpx.AsyncClient() as client:
        cert = CertificateAssignmentRequest(lfdi=lfdi, expiry=cert_expiry)
        response = await client.post(
            admin_url + uri.AggregatorCertificateListUri.format(aggregator_id=agg_id),
            content=f"[{cert.model_dump_json()}]",
            auth=auth,
        )
        response.raise_for_status()


def main() -> int:
    parser = argparse.ArgumentParser(description="Add client certificate, optionally create aggregator.")
    parser.add_argument(
        "--aggregator-name", required=True, help="Name of the aggregator whose certificate is being added."
    )
    parser.add_argument("--aggregator-domain", required=True, help="Whitelisted domain for the aggregator.")
    parser.add_argument("--pem", required=True, type=Path, help="Path to the .pem file containing the new certificate.")
    parser.add_argument("--admin-url", default="http://127.0.0.1:9999", help="Base URL of the admin endpoint.")
    parser.add_argument(
        "--username", default=DEFAULT_USERNAME, help="Username for basic HTTP authentication (default from .env)."
    )
    parser.add_argument(
        "--password", default=DEFAULT_PASSWORD, help="Password for basic HTTP authentication (default from .env)."
    )
    parser.add_argument(
        "--create", action="store_true", default=False, help="Create a new aggregator with certificate."
    )

    args = parser.parse_args()

    asyncio.run(
        add_client_certificate(
            aggregator_name=args.aggregator_name,
            aggregator_domain=args.aggregator_domain,
            pem_file_path=args.pem,
            admin_url=args.admin_url,
            auth=(args.username, args.password),
            create_agg=args.create,
        )
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
