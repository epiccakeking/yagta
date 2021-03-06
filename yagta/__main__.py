"""
Copyright 2022 epiccakeking

This file is part of YAGTA.

YAGTA is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

YAGTA is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with YAGTA.
If not, see <https://www.gnu.org/licenses/>.
"""
from . import ui, db
import sqlite3

task_db = db.TaskDatabase(sqlite3.connect("tasks.db"))
ui.main(task_db)
