"""Encoding-independent XML declaration rejection shared by intake and gates."""
from xml.etree import ElementTree as ET


class _NoDeclarationsBuilder(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        # The parser invokes this for UTF-8, UTF-16 LE/BE and other supported encodings.
        raise ValueError('DOCTYPE and entity declarations are forbidden')


def parse_xml(data, part, expected_root=None):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('DOCTYPE and entity declarations are forbidden: %s' % part)
    try:
        root = ET.fromstring(data, parser=ET.XMLParser(target=_NoDeclarationsBuilder()))
    except ET.ParseError as error:
        raise ValueError('invalid XML in %s: %s' % (part, error)) from error
    if expected_root is not None and root.tag != expected_root:
        raise ValueError('invalid XML root in %s: expected %s' % (part, expected_root))
    return root
