import subprocess


def sum_digits(n: int) -> int:
    s = 0
    while n:
        s += n % 10
        n //= 10
    return s


def run_command(ps: list[str]):
    result = subprocess.run(ps)
    if result.returncode != 0:
        cmd = " ".join(ps)
        raise Exception(
            f"result.returncode {result.returncode} for command\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n{cmd}"
        )


# Generates TLS certificate, calculates fingerprints, LFDI, SFDI
if __name__ == "__main__":
    # generate new cert
    run_command(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-keyout",
            "key.pem",
            "-out",
            "cert.pem",
            "-nodes",
            "-days",
            "5110",
            "-subj",
            "/C=GB/ST=London/L=London/O=Example/OU=Example/CN=example.com",
        ]
    )

    # generate fingerprint
    run_command(["openssl", "x509", "-in", "cert.pem", "-out", "cert.pem.fingerprint", "-fingerprint", "-sha256"])

    raw_fingerprint: str
    with open("cert.pem.fingerprint") as f:
        raw_fingerprint = f.readline()

    raw_pem: str
    with open("cert.pem") as f:
        raw_pem = f.read()

    fingerprint = raw_fingerprint.split("=")[1].lower().rstrip()

    lfdi = "".join(fingerprint.split(":")[:20])

    raw_sfdi = int(("0x" + lfdi[:9]), 16)
    sfdi_checksum = (10 - (sum_digits(raw_sfdi) % 10)) % 10
    sfdi = raw_sfdi * 10 + sfdi_checksum

    print(f'TEST_CERTIFICATE_PEM = b"""{raw_pem}"""\n')
    print(f'TEST_CERTIFICATE_FINGERPRINT = (\n"    {fingerprint.replace(":", "")}"\n)\n')
    print(f'TEST_CERTIFICATE_LFDI = "{lfdi}"\n')
    print(f'TEST_CERTIFICATE_SFDI = "{sfdi}"\n')
