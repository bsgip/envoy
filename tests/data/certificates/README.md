# Generating Test Certificates

Just run `python generate.py` to build a new set but the process is also described below

## Generate a certificate

`openssl req -x509 -newkey rsa:4096 -keyout key1.pem -out cert1.pem -sha256 -days 5110 -nodes`

## Calculate sha256 fingerprint

`openssl x509 -in cert1.pem -fingerprint -sha256`

Example fingerprint: `4B:10:73:CE:35:07:17:2E:5F:50:5E:37:F5:79:BC:E9:7F:79:93:0F:38:20:23:EA:0C:F4:6F:96:92:C6:B8:20`

## Converting fingerprint to LFDI

Take the first 20 octects, turn lower case and remove any ":" chars

Example LFDI: `4b1073ce3507172e5f505e37f579bce97f79930f`

## Converting fingerprint to SFDI

Take the first 9 octets, convert to a decimal number and add a digit to ensure that the sum of all digits is 0
