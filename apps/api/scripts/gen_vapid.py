"""Print a fresh VAPID key pair as environment variables. Run once, store the output as secrets."""

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from py_vapid.utils import b64urlencode

vapid = Vapid()
vapid.generate_keys()
assert vapid.private_key is not None and vapid.public_key is not None
private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
public_raw = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
print(f"VAPID_PUBLIC_KEY={b64urlencode(public_raw)}")
print(f"VAPID_PRIVATE_KEY={b64urlencode(private_raw)}")
print("VAPID_SUBJECT=mailto:you@example.com")
