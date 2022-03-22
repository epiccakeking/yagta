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
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from pkg_resources import resource_string
from . import APP_ID


def main(db):
    app = Gtk.Application(application_id=APP_ID)
    app.connect(
        "activate",
        lambda _: MainWindow(app, db),
    )
    app.run()


def templated(c):
    return Gtk.Template(
        string=resource_string(__name__, f"ui/{c.__gtype_name__}.ui"),
    )(c)


@templated
class Task(Gtk.Box):
    __gtype_name__ = "Task"
    child_tasks = Gtk.Template.Child("child_tasks")
    add_child = Gtk.Template.Child("add_child")
    delete_button = Gtk.Template.Child("delete_button")
    edit_button = Gtk.Template.Child("edit_button")
    title = Gtk.Template.Child("title")
    header = Gtk.Template.Child("header")
    done = Gtk.Template.Child("done")

    def __init__(self, db, task_id, parent_id=None):
        super().__init__()
        self.id = task_id
        self.parent_id = parent_id
        # We can't delete if we don't have a parent.
        if parent_id is None:
            self.delete_button.hide()
            # Customizations for root task
            if self.id == 0:
                self.set_css_classes(("root_task",))
                self.remove(self.header)
        self.db = db
        self.hook_handler = self.hook_handler  # Needed to have a reference
        self.db.add_hook(self.id, self.hook_handler)
        self.hook_handler(self.db.get_task(self.id))
        self.edit_button.connect("clicked", self.on_edit)
        self.add_child.connect("clicked", self.on_add_child)
        self.delete_button.connect("clicked", self.on_delete)
        self.done.connect("toggled", self.on_toggle)
        self.title.connect(
            "changed", lambda *_: self.db.set_title(self.id, self.title.get_text())
        )
        self.title.connect("activate", self.on_title_activate)

    def hook_handler(self, data):
        if self.title.get_text() != data["title"]:
            self.title.set_text(data["title"])
        self.done.set_active(data["done"])
        self.update_children(data)

    def update_children(self, data):
        old_children = {}
        # Index children
        child = self.child_tasks.get_first_child()
        while child:
            old_children[child.id] = child
            child = child.get_next_sibling()
        for child in reversed(data["children"]):
            # Reuse existing children, removing them from the deletion queue
            if child in old_children:
                self.child_tasks.reorder_child_after(old_children.pop(child))
            else:
                self.child_tasks.prepend(Task(self.db, child, self.id))
        # What remains are the no longer used children
        for child in old_children.values():
            self.child_tasks.remove(child)

    def on_add_child(self, *_):
        self.db.new_task(parent_id=self.id)

    def on_delete(self, *_):
        if self.parent_id is not None:
            self.db.remove_child(self.parent_id, self.id)

    def on_toggle(self, *_):
        self.db.set_done(self.id, self.title.get_active())

    def on_edit(self, *_):
        EditWindow(self.db, self.id, transient_for=self.get_ancestor(Gtk.Window))

    def on_title_activate(self, *_):
        # Insert a new note at top
        self.db.add_child(self.id, self.db.new_task(parent_id=None), 0)
        # We need to wait for the ui to actually be updated
        GLib.idle_add(
            lambda: self.child_tasks.get_first_child().title.grab_focus() and False
        )


@templated
class EditWindow(Gtk.Window):
    __gtype_name__ = "EditWindow"
    title = Gtk.Template.Child("title")
    body = Gtk.Template.Child("body")
    title_focus_button = Gtk.Template.Child("title_focus_button")

    def __init__(self, db, task_id, **kwargs):
        super().__init__(**kwargs)
        self.db = db
        self.id = task_id
        data = self.db.get_task(self.id)
        self.title.set_text(data["title"])
        self.title.connect("changed", self.on_title_edit)
        buffer = self.body.get_buffer()
        buffer.set_text(data["body"], len(data["body"]))
        buffer.connect("changed", self.on_body_edit)
        self.body.grab_focus()
        self.title.connect(
            "state-flags-changed",
            lambda _w, flags: (
                self.title_focus_button.hide
                if flags & 16384
                else self.title_focus_button.show
            )(),
        )
        self.title_focus_button.connect(
            "clicked",
            lambda *_: (self.title.grab_focus(), self.title_focus_button.hide()),
        )
        self.hook_handler = self.hook_handler  # Needed to have a reference
        self.db.add_hook(self.id, self.hook_handler)
        self.present()

    def hook_handler(self, data):
        if self.title.get_text() != data["title"]:
            self.title.set_text(data["title"])

    def on_title_edit(self, *_):
        self.db.set_title(self.id, self.title.get_text())

    def on_body_edit(self, *_):
        buffer = self.body.get_buffer()
        self.db.set_body(self.id, buffer.get_text(*buffer.get_bounds(), True))


@templated
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "MainWindow"
    scroller = Gtk.Template.Child("scroller")
    add_child = Gtk.Template.Child("add_child")

    def __init__(self, app, db):
        super().__init__(application=app)
        self.root_task = Task(db, 0)
        self.scroller.set_child(self.root_task)
        self.add_child.connect("clicked", self.on_add_child)
        # Add CSS
        css = Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, "css/main.css"))
        Gtk.StyleContext().add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.present()

    def on_add_child(self, *_):
        self.root_task.on_add_child()
        vadjust = self.scroller.get_vadjustment()
        GLib.idle_add(lambda: vadjust.set_value(vadjust.get_upper()) and False)
