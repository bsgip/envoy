import json
import os
import argparse
import httpx
import asyncio
from typing import Tuple
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from cryptography import x509

from envoy.server.api.depends.lfdi_auth import LFDIAuthDepends

from envoy_schema.admin.schema import uri
from envoy_schema.admin.schema.certificate import CertificateAssignmentRequest
from envoy_schema.admin.schema.aggregator import AggregatorRequest, AggregatorDomain
from envoy_schema.admin.schema.aggregator import AggregatorPageResponse, AggregatorResponse


env_path = Path(__file__).parent.parent.parent.parent / '.env'
assert env_path.exists()
load_dotenv(env_path)
DEFAULT_USERNAME = os.getenv('ADMIN_USERNAME')
DEFAULT_PASSWORD = os.getenv('ADMIN_PASSWORD')


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


def check_certificate(pem_file_path: str) -> Tuple[str, datetime]:
    """
    Checks that the PEM file contains three certificates (client, intermediate,
    root), extracts expiry date from client certificate, and calculates the LFDI
    (first 40 hex chars of client cert in base64).
    
    Returns:
        lfdi (str): First 40 hex characters of client cert in base64.
        cert_expiry (str): Not valid after date of client cert (ISO format).
    """

    with open(pem_file_path, 'rb') as f:
        pem_data = f.read()

    lfdi = LFDIAuthDepends.generate_lfdi_from_pem(pem_data.decode('utf-8'))
    certs = x509.load_pem_x509_certificates(pem_data)

    if len(certs) != 3:
        raise ValueError("PEM file must contain exactly three certificates (client, intermediate, root)")
    if not is_intermediate_certificate(certs[1]):
        raise ValueError("The second entry in the PEM file must be a valid intermediate certificate")
    if not is_root_certificate(certs[2]):
        raise ValueError("The last entry in the PEM file must be a valid root certificate")

    return lfdi, certs[0].not_valid_before_utc


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

    created_time = datetime.now()
    changed_time = created_time
    domains = [AggregatorDomain(domain=aggregator_domain,
                                 created_time=created_time, changed_time=changed_time)]
    agg_payload = AggregatorRequest(name=aggregator_name, created_time=created_time,
                                     changed_time=changed_time, domains=domains).model_dump_json()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            admin_url + uri.AggregatorCreateUri,
            data=agg_payload,
            auth=auth
        )
        response.raise_for_status()

    return response.json()['aggregator_id']


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


async def create_or_update_client_certificate(aggregator_name: str, aggregator_domain: str, pem_file_path: str,
                                               admin_url: str, auth: Tuple[str, str], create_agg: bool=False) -> None:
    """
    Creates or updates a client certificate for an aggregator

    Args:
        aggregator_name (str): Name of the aggregator.
        aggregator_domain (str): Domain of the aggregator.
        pem_file_path (str): Path to .pem file containing the certificate.
        auth (Tuple[str, str]): Tuple containing username and password for basic HTTP authentication.
        create_aggregator (bool, optional): If True, creates a new aggregator before updating the certificate.
    """
    aggregators = await get_aggregators(admin_url, auth)

    if create_agg:
        aggregator_names = [agg.name for agg in aggregators]
        assert aggregator_name not in aggregator_names, "Aggregator already exists"

        agg_id = await create_aggregator(aggregator_name, aggregator_domain, admin_url, auth)

    lfdi, cert_expiry = check_certificate(pem_file_path)

    async with httpx.AsyncClient() as client:
        cert = CertificateAssignmentRequest(lfdi=lfdi, expiry=cert_expiry)
        response = await client.post(
            admin_url + uri.AggregatorCertificateListUri.format(aggregator_id=agg_id),
            content=f"[{cert.model_dump_json()}]",
            auth=auth
        )
        response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description="Update client certificate via admin aggregator endpoint.")
    parser.add_argument("--aggregator-name", required=True, help="Name of the aggregator whose certificate is being added.")
    parser.add_argument("--aggregator-domain", required=True, help="Whitelisted domain for the aggregator.")
    parser.add_argument("--pem", required=True, help="Path to the .pem file containing the new certificate.")
    parser.add_argument("--admin-url", default='http://127.0.0.1:9999', help="Base URL of the admin endpoint.")
    parser.add_argument("--username", default=DEFAULT_USERNAME, help="Username for basic HTTP authentication (default from .env).")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password for basic HTTP authentication (default from .env).")
    parser.add_argument("--create", action='store_true', default=False, help="Create a new aggregator with certificate.")

    args = parser.parse_args()

    asyncio.run(create_or_update_client_certificate(
        aggregator_name=args.aggregator_name,
        aggregator_domain=args.aggregator_domain,
        pem_file_path=args.pem,
        admin_url=args.admin_url,
        auth=(args.username,args.password),
        create_agg=args.create,
    ))


if __name__ == "__main__":
    main()