"""
Definition of available Inkscape target directories and their machinery
"""

from .target import ExtensionsTarget, BasicTarget

TARGETS = [
    # Website slug, Visible name, local directory, search instead of list
    ExtensionsTarget(
        "extension", "Extensions", "extensions", True, filters=("*.inx",)
    ),
    BasicTarget(
        "template", "Templates", "templates", True, filters=("*.svg",)
    ),
    BasicTarget("palette", "Shared Paletts", "palettes", filters=("*.gpl",)),
    BasicTarget("symbol", "Symbol Collections", "symbols", filters=("*.svg",)),
    BasicTarget("keyboard", "Keyboard Shortcuts", "keys", filters=("*.xml",)),
    # ('marker', 'Marker Collections', '', False), # No marker config
    # ('pattern', 'Pattern Collections', '', False), # No pattern config
    # ('', 'User Interface Themes', 'themes', False), # No website category
    # ('', 'Paint Server', 'paint', False), # No website category
    # ('', 'User Interfaces', 'ui', False), # No website category
    # ('', 'Icon Sets', 'icons', False), # No website category
]
