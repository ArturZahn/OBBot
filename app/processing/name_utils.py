import unicodedata


def encode_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name.strip())
    only_ascii = nfkd.encode("ASCII", "ignore").decode("ASCII")
    return only_ascii.lower()
