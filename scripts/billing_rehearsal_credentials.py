"""Read current-user Windows-encrypted secrets for the local billing rehearsal."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re


def read_private_json(name):
    if os.name != "nt":
        raise RuntimeError("Billing rehearsal credentials require Windows DPAPI.")
    path = Path(os.environ["LOCALAPPDATA"]) / "Rokkad" / "private" / name
    raw = path.read_bytes()

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    try:
        if not crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None,
                                       1, ctypes.byref(target)):
            raise RuntimeError("Cannot decrypt local rehearsal credentials.")
        return json.loads(ctypes.string_at(target.data, target.size))
    finally:
        if target.data:
            ctypes.memset(target.data, 0, target.size)
            kernel.LocalFree(target.data)


def validate_rehearsal(database, host, credentials):
    if not re.fullmatch(r"rokkad_baseline_rehearsal_billing_[a-z0-9_]+", database):
        raise RuntimeError("Billing rehearsal requires a dedicated billing rehearsal database.")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Billing rehearsal requires loopback PostgreSQL.")
    if (not isinstance(credentials, dict)
            or not re.fullmatch(r"rzp_test_[A-Za-z0-9]+", credentials.get("key_id", ""))
            or not credentials.get("key_secret")):
        raise RuntimeError("Billing rehearsal requires saved Test Mode credentials.")
