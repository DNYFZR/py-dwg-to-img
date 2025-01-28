#!/usr/bin/env python3

import sys

root = {}
children = {}

for line in sys.stdin:
    line = (
        line.rstrip()
        .replace("|", " ")
        .replace("--", "  ")
        .replace("`", " ")
        .replace("└", " ")
        .replace("├", " ")
        .replace("│", " ")
        .replace("─", " ")
    )

    record = line.strip()
    pkg, version, *_ = record.split(" ", 2)
    tab = len(line) - len(record)

    if tab == 0:
        root[pkg] = version
    else:
        children[pkg] = version

print("# Packages Used Directly\n\nYou must always include these in your package:\n")
for pkg, version in root.items():
    print(f" * {pkg} {version}")

print("\n")
print(
    "# Packages Used Indirectly\n\nYou may or may not need to include these, depending on if your packaging system automatically pulls in sub-deps:\n"
)
for pkg, version in children.items():
    print(f" * {pkg} {version}")
