from bdb import effective
from typing import Dict, List, Any, Tuple, Optional
import json

import fileinput
import shutil

HEADER_COLUMNS = [["time", "timestamp"],["level", "severity"],["message", "msg"]]
HEADER_DELIMITER= " "

def print_string(string: str, indent: int, continued_add_indent: int = 4):
    remaining_string = string
    effective_indent = indent
    while len(remaining_string) > 0:
        data_width = term_width - effective_indent
        string_part = remaining_string[0:data_width]
        remaining_string = remaining_string[data_width:]
        print(" "*effective_indent + string_part)
        if effective_indent == indent:
            effective_indent += continued_add_indent


def get_header_value(entry: Dict[str,Any], col_idx: int) -> Tuple[Optional[str], str]:
    """Return consumed key and header value"""
    for col_name in HEADER_COLUMNS[col_idx]:
        if col_name in entry:
            return col_name, entry[col_name]
    return None, ""

def print_header(entry: Dict[str,Any]) -> List[str]:
    """Print the header for the entry and return the consumed keys."""
    consumed_keys = []
    header_values = []
    for col in range(0, len(HEADER_COLUMNS)):
        key, value = get_header_value(entry, col)
        header_values.append(value)
        if key is not None:
            consumed_keys.append(key)
    header_str = HEADER_DELIMITER.join(header_values)
    print_string(header_str, 0)
    return consumed_keys

def _print_attributes_list(attributes: List[Any], indent: int, prefix=""):
    first = True
    for attribute in attributes:
        if first:
            print_attributes(attribute, indent, prefix + "- ")
            first = False
        else:
            print_attributes(attribute, indent + len(prefix), "- ")

def _print_attributes_dict(attributes: Dict[str, Any], indent: int, prefix=""):
    key_length = 0
    for key in attributes:
        k_l = len(key)
        if k_l > key_length:
            key_length = k_l

    first = True
    for key, value in attributes.items():
        padded_key = key.ljust(key_length) + ": "
        if first:
            print_attributes(value, indent, prefix + padded_key)
            first = False
        else:
            print_attributes(value, indent + len(prefix), padded_key)

def print_attributes(attributes: Any, indent: int = 2, prefix=""):
    if isinstance(attributes, list):
        _print_attributes_list(attributes, indent, prefix)
    elif isinstance(attributes, dict):
        _print_attributes_dict(attributes, indent, prefix)
    else:
        print_string(prefix + str(attributes), indent, len(prefix))

def print_entry(entry: Dict[str,Any]):
    counsumed_keys = print_header(entry)
    remaining_entry = {k:v for k,v in entry.items() if k not in counsumed_keys}
    print_attributes(remaining_entry)


def main():
    global term_width
    term_width = shutil.get_terminal_size((80, 20)).columns

    for line in fileinput.input():
        try:
            data = json.loads(line)
        except:
            print(f"Failed to load line as json: {line}")
            continue
        print_entry(data)


if __name__ == "__main__":
    main()
