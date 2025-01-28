# SPDX-FileCopyrightText: 2022 Jonathan Neuhauser <jonathan.neuhauser@outlook.com>
# SPDX-FileCopyrightText: 2023 Software Freedom Conservancy <info@sfconservancy.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later
import os
import sys

# definitions
HERE = os.path.abspath(os.path.dirname(__file__))
PARENT = os.path.abspath(os.path.dirname(HERE))

#
# We might get executed in HERE.
# This might lead to problems.
# In this case, we move one down.
#
import warnings

if not hasattr(warnings, "warn"):
    del sys.modules["warnings"]
    for i, path in reversed(list(enumerate(sys.path[:]))):
        if os.path.abspath(path) == HERE:
            del sys.path[i]

try:
    import inkex  # check inkex
    from . import svg  # check that we are a package
except ImportError:
    # This is suggested by https://docs.python-guide.org/writing/structure/.
    sys.path.insert(0, PARENT)
    try:
        from inkaf.afinput import main
    except ImportError:
        # from inkaf.run_in_virtual_env import main
        raise
else:
    # All modules are installed and we are in a package
    # seems like we should be executed.
    from .afinput import main

main()
