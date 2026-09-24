"""Generate self-signed TLS cert for InevioNet dashboard (https://localhost:8080)."""
import datetime
import os
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tls")
os.makedirs(out, exist_ok=True)
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "InevioNet Dashboard")])
now = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.DNSName("localhost.localdomain")]), critical=False)
        .sign(key, hashes.SHA256()))
with open(os.path.join(out, "key.pem"), "wb") as f:
    f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
with open(os.path.join(out, "cert.pem"), "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
print("TLS cert created:", out)
