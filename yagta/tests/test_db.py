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
from unittest import TestCase
from yagta import db
import sqlite3


class TestTaskDatabase(TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")
        self.db = db.TaskDatabase(self.con)

    def test_hooks(self):
        task = self.db.new_task()
        captures = []
        hook = captures.append
        self.db.add_hook(task, hook)
        self.db.set_title(task, title="Test")
        self.assertEqual(1, len(captures), "Wrong number of hook runs")
        self.assertEqual(captures[0]["title"], "Test")

    def test_init(self):
        """
        Test that init works on already created databases
        """
        db.TaskDatabase(self.con)

    def test_add_child(self):
        parent = self.db.new_task()
        self.assertEqual(
            (), self.db.get_task(parent)["children"], "Children not correct"
        )
        child = self.db.new_task(parent_id=parent)
        self.assertEqual(
            (child,), self.db.get_task(parent)["children"], "Children not correct"
        )

    def test_remove_child(self):
        parent = self.db.new_task()
        children = [self.db.new_task(parent_id=parent) for i in range(5)]
        self.assertEqual(
            tuple(children),
            self.db.get_task(parent)["children"],
            "Children not correct",
        )
        child_to_remove = children.pop(2)
        self.db.remove_child(parent, child_to_remove)
        self.assertEqual(
            tuple(children),
            self.db.get_task(parent)["children"],
            "Children not correct",
        )
