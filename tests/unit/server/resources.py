from server.main import settings

TEST_CERTIFICATE_PEM = b"""-----BEGIN CERTIFICATE-----
MIIEETCCAfkCAQEwDQYJKoZIhvcNAQELBQAwSzELMAkGA1UEBhMCQVUxDDAKBgNV
BAgMA05TVzEMMAoGA1UEBwwDQ0JSMQ4wDAYDVQQKDAVCU0dJUDEQMA4GA1UEAwwH
VEVTVF9DQTAeFw0yMDA5MTEwNDE2NTNaFw0yMTA5MTEwNDE2NTNaMFIxCzAJBgNV
BAYTAkFVMQwwCgYDVQQIDANOU1cxDDAKBgNVBAcMA0NCUjERMA8GA1UECgwIVEVT
VF9PUkcxFDASBgNVBAMMC1RFU1RfQ0xJRU5UMIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEAwDuIn6+NU2Hkm73+BVaPA8m+rgOI/VZKp0WaIFAKh2XSfJbq
/4s2kqqr2T1d2eGlGAxirb7hKxvEMK5KdlxsLdkz2EQJ3r+G7mt0oqhmKeEQMCOl
BNMryK7ZzU5IY1+uUV/Or0jx25j/kz6npXiMi664VuqSveiGQjd8tfe2bnnpoXpa
x/65dFDwhx5PJFiWd3ceHefOPxwfZP0R1iRyP+fW/A2mkKAj67RFKFOuuutGvMhl
8IlNE2cNlA0BQqkujoF/CQTfnqm6ux/ppeKyLYedVhuXb8k3yMjuQ1m6Q1CbA7E0
y0FkZ9sMoXk1YV/WowL4KdmW6lZh0g+y5T6eFwIDAQABMA0GCSqGSIb3DQEBCwUA
A4ICAQAav1OtAmg7wN2OxWOnJ7tUTlzh1/XsqhEn9Eea538FfjW+NxqHuqozFDTz
ozKSJChdJq+HXGW37hKw1CDSGL4i7dzzIm6SjznEzG2NRvPgpLPmgeTQ5NxGDM4l
cOZJy9TchdFd/aspnBPiyThgUtWONDnS+wwf4Pjc6JrLaDRJ6rLV9M6MM+AG+dBW
hq+0ruNehuTQ9C45uDsd8b3qFsYqNGrDe158e1SGGEyzyq98QGHaDGF7EL0+TbnL
YnpAC6NBCbss+hp6c79YFPH93gDNzBvSue961NrXyhVtj2w0wRKQDi1roo2KHZtB
+fNktxlCi6p50avISUhCs9L/dJ5aZXfo6EDAzJrbxxdHogbapMfofEGFFFwDCgeM
fNvVbulFHOSY8S6mxuRdEGUTXtXqbHU6wcZhD6dEvqohJnXErvz/4FlbyD/ELGhT
KZZFMwjfqNkyGWWOdQ+aDQTvjPL7DMdsH4WTJVupHfq4YftCk1APG8xtAf7qJMJW
N1UwoCrhqJdKlzUODdhe2HHiCf9frKTgCJ8jvvxGdV7usOwqFUly3UaA4PImNw9q
3HOYv/vANqh/pn3LKPxLipUQjfD0zf18l0yaDSfjFzOQdq7nQa9bhTlJ+AUoEQrC
qRyRKl+rY4NwOuMYqzYFeruO4Mr7i5Ik/R9ldY2MzSxQyiCfTw==
-----END CERTIFICATE-----
"""

bs_cert_pem_header = bytes(f"{settings.cert_pem_header}", "ascii")

TEST_LFDI = "2a22ef8a92ec1a5176c6baa75d6b408e25e5bc8f8d"
