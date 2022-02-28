"""
Copyright 2022, epiccakeking

This file is part of YAGTA.

YAGTA is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version.

YAGTA is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with YAGTA.
If not, see <https://www.gnu.org/licenses/>.
"""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib
from pkg_resources import resource_string
import json
import datetime
from pathlib import Path

APP_ID = "io.github.epiccakeking.YAGTA"
settings = None
today = datetime.date.today()


def main():
    global settings
    settings = Settings(Path(GLib.get_user_config_dir()) / APP_ID / "settings.json")
    app = Gtk.Application(application_id=APP_ID)
    app.connect(
        "activate",
        lambda _: MainWindow(
            app, Path(GLib.get_user_data_dir()) / APP_ID / "tasks.json"
        ),
    )
    app.run()


def templated(c):
    return Gtk.Template(
        string=resource_string(__name__, f"ui/{c.__gtype_name__}.ui"),
    )(c)


class Settings:
    DEFAULTS = {
        "hide_done": False,
        "hide_future": False,
    }

    def __init__(self, file_name):
        self.file_name = Path(file_name)
        self.data = None
        self.load()

    def load(self):
        try:
            with self.file_name.open() as f:
                self.data = self.DEFAULTS | json.load(f)
        except FileNotFoundError:
            pass

    def save(self):
        tmp = self.file_name.with_suffix(self.file_name.suffix + ".tmp")
        self.file_name.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("w") as f:
            json.dump(self.data, f)
        tmp.replace(self.file_name)

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, item, value):
        self.data[item] = value
        self.save()


@templated
class CalendarOverlay(Gtk.Dialog):
    __gtype_name__ = "CalendarOverlay"
    clear_button = Gtk.Template.Child("clear_button")
    calendar = Gtk.Template.Child("calendar")

    def __init__(self, date, callback, **kwargs):
        super().__init__(modal=True, **kwargs)
        self.callback = callback
        if date:
            self.calendar.select_day(
                GLib.DateTime(
                    GLib.TimeZone.new_local(),
                    *datetime.datetime.fromisoformat(date).timetuple()[:6],
                )
            )
        self.clear_button.connect("clicked", self.on_clear_button)
        self.calendar.connect("day-selected", self.on_calendar_select)
        self.present()

    def on_clear_button(self, _):
        self.callback(None)
        self.close()

    def on_calendar_select(self, _):
        self.callback(datetime.date(*self.calendar.get_date().get_ymd()))


class CalendarEntry(Gtk.Button):
    __gtype_name__ = "CalendarEntry"
    callback = None

    def __init__(self, date=None):
        super().__init__()
        self.set_date(str(date))
        self.connect(
            "clicked",
            lambda _: CalendarOverlay(
                self.get_date(),
                self.set_date,
                transient_for=self.get_ancestor(Gtk.ApplicationWindow.__gtype__),
            ),
        )

    def get_date(self):
        date = self.get_label()
        if date == "None":
            return None
        return date

    def set_date(self, date):
        self.set_label(str(date))
        if self.callback:
            self.callback(date)


@templated
class Task(Gtk.Box):
    __gtype_name__ = "Task"
    add_child = Gtk.Template.Child("add_child")
    delete_button = Gtk.Template.Child("delete_button")
    child_tasks = Gtk.Template.Child("child_tasks")
    title = Gtk.Template.Child("title")
    done_toggle = Gtk.Template.Child("done_toggle")
    start = Gtk.Template.Child("start")
    due = Gtk.Template.Child("due")

    def __init__(
        self,
        title="",
        children=[],
        done=False,
        start=None,
        due=None,
    ):
        super().__init__()
        self.add_child.connect("clicked", lambda _: self.child_tasks.prepend(Task()))
        self.title.get_buffer().set_text(title, len(title))
        self.done_toggle.set_active(done)
        self.done_toggle.connect("toggled", lambda _: self.reload())
        self.start.set_date(start)
        self.due.set_date(due)
        for child in children:
            self.child_tasks.append(child)
        self.delete_button.connect("clicked", lambda _: self.get_parent().remove(self))
        self.title.connect("activate", self.create_next)
        self.start.callback = lambda _: self.reload()
        self.due.callback = lambda _: self.reload()

    def repr_dict(self):
        return dict(
            title=self.get_title(),
            children=[task.repr_dict() for task in self.iter_children()],
            done=self.done_toggle.get_active(),
            start=self.start.get_date(),
            due=self.due.get_date(),
        )

    def iter_children(self):
        child = self.child_tasks.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()

    def get_title(self):
        return self.title.get_buffer().get_text()

    @classmethod
    def from_dict(cls, data):
        return cls(
            **(
                data
                | {
                    "children": (
                        Task.from_dict(child_data) for child_data in data["children"]
                    )
                }
            )
        )

    def create_next(self, _):
        new_task = Task()
        self.get_parent().insert_child_after(new_task, self)
        new_task.title.grab_focus()

    def reload(self):
        due_date = self.due.get_date()
        if due_date:
            due_date = datetime.date.fromisoformat(due_date)
            if today >= due_date:
                urgency = "urgency_high"
            elif today + datetime.timedelta(5) > due_date:
                urgency = "urgency_medium"
            else:
                urgency = "urgency_low"
        else:
            urgency = None
        self.set_css_classes(("task", urgency) if urgency else ("task",))
        start_date = self.start.get_date()
        if start_date:
            start_date = datetime.date.fromisoformat(start_date)
        if settings["hide_done"] and self.done_toggle.get_active():
            self.hide()
        elif start_date and settings["hide_future"] and today < start_date:
            self.hide()
        else:
            self.show()
        for child in self.iter_children():
            child.reload()


@templated
class TaskList(Gtk.Box):
    __gtype_name__ = "TaskList"
    add_child = Gtk.Template.Child("add_child")
    child_tasks = Gtk.Template.Child("child_tasks")
    entry = Gtk.Template.Child("entry")

    def __init__(self):
        super().__init__()
        self.add_child.connect("clicked", lambda _: self.child_tasks.prepend(Task()))

    def repr_list(self):
        return [task.repr_dict() for task in self.iter_children()]

    def iter_children(self):
        child = self.child_tasks.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()

    def reload(self):
        for child in self.iter_children():
            child.reload()


@templated
class MainWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "MainWindow"
    task_list = Gtk.Template.Child("task_list")
    filter_popover_content = Gtk.Template.Child("filter_popover_content")

    def __init__(self, app, data_file):
        super().__init__(application=app)
        self.data_file = Path(data_file)
        self.load_task_file(self.data_file)
        self.task_list.reload()
        self.connect("close-request", self.on_close_request)

        # Filter menu
        for filter, label in (
            ("hide_done", "Hide finished tasks"),
            ("hide_future", "Hide future tasks"),
        ):
            check_button = Gtk.CheckButton(label=label)
            check_button.set_active(settings[filter])
            check_button.connect(
                "toggled",
                (
                    lambda filter, button: lambda _: self.filter_menu_handler(
                        filter, button.get_active()
                    )
                )(filter, check_button),
            )
            self.filter_popover_content.append(check_button)
        # Add CSS
        css = Gtk.CssProvider()
        css.load_from_data(resource_string(__name__, "css/main.css"))
        Gtk.StyleContext().add_provider_for_display(
            self.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER
        )
        self.present()

    def on_close_request(self, _):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump(self.task_list.repr_list(), f)

    def load_task_file(self, file_name):
        try:
            with open(file_name) as f:
                for task_data in json.load(f):
                    self.task_list.child_tasks.append(Task.from_dict(task_data))
        except FileNotFoundError:
            pass

    def filter_menu_handler(self, filter, status):
        settings[filter] = status
        self.task_list.reload()


if __name__ == "__main__":
    main()
