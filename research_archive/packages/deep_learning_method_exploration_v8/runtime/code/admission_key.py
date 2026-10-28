"""A1: complete raw value key; original current admission/math unchanged."""
import hashlib,pickle,io
INSTALLED=False
def key(screen,belief,candidate,schedule):
 from loaded_context_reuse import raw
 # No memoization: two equal immutable value trees must have equal bytes even
 # when pickle round-tripping changes string/object aliasing. The tree is
 # acyclic and contains no borrowed live plant objects.
 stream=io.BytesIO();encoder=pickle.Pickler(stream,protocol=5);encoder.fast=True
 encoder.dump(raw((screen,belief,candidate,schedule)))
 return hashlib.sha256(stream.getvalue()).hexdigest()
def install():
 global INSTALLED
 if INSTALLED:return
 import admission_certificates
 admission_certificates.key=key;INSTALLED=True
