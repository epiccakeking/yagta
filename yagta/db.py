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
import json
import sqlite3
import weakref


class TaskDatabase:
    def __init__(self, connection):
        self.con: sqlite3.Connection = connection
        self.init_table()
        """Connection to database"""
        self.hooks = {}
        ...

    def init_table(self):
        """
        Initialize tasks table
        uuid is used to detect rowid reuse, it is not intended as a real id
        Note: rowid/id 0 is reserved for the root node.
        """
        with self.con as con:
            con.execute(
                """\
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY,
    title TEXT,
    body TEXT,
    done BOOL,
    children TEXT
);"""
            )
            # Create the special root node
            con.execute(
                "INSERT OR IGNORE INTO tasks (rowid, title, children) VALUES (0, 'ROOT', '[]')"
            )

    def get_task(self, task_id):
        """

        :return: dict with keys from FIELDS
        """
        title, body, done, children = self.con.execute(
            f"SELECT title, body, done, children FROM tasks WHERE rowid=?",
            (task_id,),
        ).fetchone()
        return dict(
            title=title,
            body=body or "",
            done=bool(done),
            children=tuple(json.loads(children)),
        )

    def add_hook(self, task_id, callback):
        """
        Run callback with
        Execution order is not guaranteed.
        Do not edit data passed to hooks.
        A hook WILL NOT run if a previous hook raises an Exception,
        a different TaskDatabase is used to make the change,
        or if hooks are explicitly suppressed in the function call.
        :param task_id:
        :param callback:
        :return:
        """
        self.hooks.setdefault(task_id, weakref.WeakSet()).add(callback)

    def new_task(self, title="New Task", children=(), parent_id=0):
        """
        Create a task
        :param title: Title of new task
        :param children: Children of new task
        :param parent_id: parent task (None to create unreferenced task)
        :return:
        """
        with self.con as con:
            con.execute(
                "INSERT INTO tasks (title, children) VALUES (?, ?)",
                (
                    title,
                    json.dumps(children),
                ),
            )
            rowid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            if parent_id is not None:
                self.add_child(parent_id, rowid, hooks=False)
        return rowid

    def add_child(self, parent_id, child_id, position=-1, hooks=True):
        """
        Add child to parent's children list
        :param position: where to insert child (negative values are wrapped to end)
        :param parent_id: id of parent
        :param child_id: id of child
        :param hooks: Whether to run hooks
        """
        children = json.loads(
            self.con.execute(
                "SELECT children FROM tasks WHERE rowid=?", (parent_id,)
            ).fetchone()[0]
        )
        children.insert(
            position if position >= 0 else len(children) + 1 + position, child_id
        )
        return self.set_children(parent_id, children)

    def remove_child(self, parent_id, child_id):
        children = json.loads(
            self.con.execute(
                "SELECT children FROM tasks WHERE rowid=?", (parent_id,)
            ).fetchone()[0]
        )
        children.remove(child_id)
        return self.set_children(parent_id, children)

    def __delete_task(self, task_id):
        """
        Delete task with id (does not update parents' child lists)
        You should generally remove all references and then use cleanup,
        instead of ever calling this directly.
        :param task_id: Id of task to delete
        """
        with self.con as con:
            con.execute("DELETE FROM tasks WHERE rowid=?", (task_id,))

    def set_title(self, task_id, title, hooks=True):
        with self.con as con:
            con.execute("UPDATE tasks SET title=? WHERE rowid=?", (title, task_id))
        if hooks:
            self.run_hooks(task_id)

    def set_done(self, task_id, done, hooks=True):
        with self.con as con:
            con.execute("UPDATE tasks SET done=? WHERE rowid=?", (done, task_id))
        if hooks:
            self.run_hooks(task_id)

    def set_body(self, task_id, body, hooks=True):
        with self.con as con:
            con.execute("UPDATE tasks SET body=? WHERE rowid=?", (body, task_id))
        if hooks:
            self.run_hooks(task_id)

    def set_children(self, parent_id, children, hooks=True):
        with self.con as con:
            con.execute(
                "UPDATE tasks SET children=? WHERE rowid=?",
                (json.dumps(children), parent_id),
            )
        if hooks:
            self.run_hooks(parent_id)

    def run_hooks(self, task_id):
        data = self.get_task(task_id)
        for hook in self.hooks.get(task_id, ()):
            hook(data)

    def clean(self):
        used_ids = set()
        pending = [0]
        while pending:
            current = pending.pop()
            if current in used_ids:
                continue
            used_ids.add(current)
            pending.extend(self.get_task(current)["children"])
        with self.con as con:
            con.execute(
                f"DELETE FROM tasks WHERE rowid NOT IN ({','.join('?'*len(used_ids))})",
                tuple(used_ids),
            )
