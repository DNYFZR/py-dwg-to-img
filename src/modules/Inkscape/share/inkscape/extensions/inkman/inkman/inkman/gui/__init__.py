#
# Copyright 2018-2022 Martin Owens <doctormo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>
#
"""All graphical interfaces bound into a GtkApp"""

import os

from inkex.gui import GtkApp

from .main import ExtensionManagerWindow
from .info import MoreInformation


class ManagerApp(GtkApp):
    """Load the inkscape extensions glade file and attach to window"""

    ui_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    app_name = "inkscape-extensions-manager"
    windows = [ExtensionManagerWindow, MoreInformation]
