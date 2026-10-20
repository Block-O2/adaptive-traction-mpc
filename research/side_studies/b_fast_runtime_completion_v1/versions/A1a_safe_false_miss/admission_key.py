"""A1: complete raw value key; original current admission/math unchanged."""
import hashlib,pickle
INSTALLED=False
def key(screen,belief,candidate,schedule):
 from loaded_context_reuse import raw
 return hashlib.sha256(pickle.dumps(raw((screen,belief,candidate,schedule)),protocol=5)).hexdigest()
def install():
 global INSTALLED
 if INSTALLED:return
 import admission_certificates
 admission_certificates.key=key;INSTALLED=True
