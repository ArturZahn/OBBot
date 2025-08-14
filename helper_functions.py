import re, uuid
from datetime import datetime


BRL_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<prefix_sign>[+-]?)       # optional sign before “R$”
    \s*R\$\s*
    (?P<post_sign>[+-]?)         # optional sign right after “R$”
    (?P<int>\d{1,3}(?:\.\d{3})*) # integer part with optional thousands dots
    ,
    (?P<dec>\d{2})               # exactly two centavos
    \s*$
    """,
    re.VERBOSE,
)

ISO_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DMY_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")

CHECK_ID_PATTERN = re.compile(r"check#(?P<id>[A-Za-z0-9]+)")

def convert_brl_format(text: str) -> float:
    """
    Convert strings such as R$+10,00 R$-10,00 +R$10,00 -R$10,00
    to a float (positive or negative).  Raises ValueError on unknown format.
    """
    m = BRL_PATTERN.match(text)
    if not m:
        raise ValueError("Balance format not recognized.")

    # Decide which sign applies (cannot have both)
    prefix, post = m["prefix_sign"], m["post_sign"]
    if prefix and post:
        raise ValueError("Conflicting signs in balance string.")

    sign = -1 if (prefix == "-" or post == "-") else 1

    integer_part = m["int"].replace(".", "")
    cents_part = m["dec"]
    return sign * float(f"{integer_part}.{cents_part}")

def convert_dmy_to_iso(dmy: str):
    if not DMY_PATTERN.match(dmy):
        raise ValueError("Invalid date formating")
    
    return datetime.strptime(dmy, "%d/%m/%Y").strftime("%Y-%m-%d")

def extract_check_id(text):
    m = CHECK_ID_PATTERN.search(text)

    if not m:
        return None
    
    return m['id']

def generate_check_id(existing_ids):
    while True:
        new_id = uuid.uuid4().hex
        if new_id not in existing_ids:
            return new_id