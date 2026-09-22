"""Confirmed blank legacy image fingerprints, not a heuristic about real photos.

These twelve exact source byte hashes decode to uniform opaque RGB(170,170,170).
The September 2026 source-image-quality report documents sizes and reference counts.
Other hashes are unclassified, not certified usable photographs.
"""
BLANK_LEGACY_IMAGE_SHA256 = frozenset({
    "66a20efff8e8bf6739e2e2580c287f7947a53662519cb0132216d59b657d6223",
    "c0dc5e9d88a4c1e6747a3cb96faf6da439a271f5358dcb78242b8c882a31238c",
    "bbb65960ae58fc57729ca1d94158572a1355edccf33c56deb1fd4dd364223109",
    "6d03734fce5116e72294a986f663a667fa3b8e1ba5c38494631bc6261f104e15",
    "d578ba323c0b5b1645d1af2323c09ae06ea015bd0e48bdde67bbddfc4e305edd",
    "f2bcce012f4fd4edc539ef4c915df237888f05efe5ae97beb35d1ec91befba1a",
    "5de0baf79754b071347b9a44a15f18d82cc5f5d2c0fc477bd236167acad1c3f1",
    "6001b1662efc9fe843b99b7906a248e624df175e4a9c3731f99b06112a134418",
    "b3d050623783ff5bb7e695e0cf0cda1fec16fbd4761c3d3ce2dc177b1424b296",
    "17b9a4ce7c3a52812d04278325d05f7fc859df3f53a243e5f974250b8871672a",
    "7bf19fb9bcd200d1776797c1e0c23922a8ad2a1f86238d9982a3c46d339261b9",
    "5d3c7a439ed5b86be8d7147abf9a791881cd4d398e6561a02893450d5f44e416",
})
