from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Header, Footer
from textual.widgets.data_table import CellDoesNotExist
from rich.text import Text
from rich.console import ConsoleRenderable

import sys
import numpy as np

from catkit2.catkit_bindings import SharedMemory, LocalMessageBroker, get_timestamp

def human_readable_time(seconds):
    seconds = round(seconds)
    if seconds < 0:
        return "in the future"
    time_units = [('day', 86400), ('hr', 3600), ('min', 60), ('sec', 1)]
    for unit, unit_seconds in time_units:
        if seconds >= unit_seconds:
            quantity = seconds // unit_seconds

            return f"{' ' if quantity < 10 else ''}{quantity} {unit}{'s' if quantity != 1 else ''} ago"
    return "<1 sec ago"

class HumanReadableTime(ConsoleRenderable):
    def __init__(self, timestamp):
        self.timestamp = timestamp

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp

    def __rich_console__(self, console, options):
        elapsed = (get_timestamp() - self.timestamp) / 1e9
        yield Text(human_readable_time(elapsed))

def generate_data(broker):
    topics = broker.get_all_message_topics()
    res = {}

    for topic in topics:
        message = broker.get_current_message(topic)

        if message.topic != topic:
            continue

        value = str(message.payload[0]) if np.allclose(message.array_info.shape, [1]) else '[...]'

        res[topic] = {
            'topic': topic,
            'pid': message.producer_pid,
            'last_updated': HumanReadableTime(message.producer_timestamp),
            'frame_rate': f'{broker.get_message_rate(topic):.1f}',
            'shape': message.array_info.shape,
            'dtype': np.dtype(message.array_info.dtype).name,
            'value': value
        }

    return res

class MTopApp(App):
    CSS_PATH = None
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("t", "sort_by_topic", "Sort by topic"),
        ("u", "sort_by_last_updated", "Sort by last updated"),
        ("r", "sort_by_frame_rate", "Sort by frame rate"),
        ("p", "sort_by_pid", "Sort by PID"),
    ]

    COLUMNS = {
        'topic': 'Topic',
        'pid': 'PID',
        'last_updated': 'Last Updated',
        'frame_rate': 'Frame Rate',
        'shape': 'Shape',
        'dtype': 'Dtype',
        'value': 'Value',
    }

    def __init__(self, broker):
        super().__init__()

        self.broker = broker
        self.current_sort_column = 'topic'

    def compose(self) -> ComposeResult:
        yield Header()

        self.table = DataTable(id="datatable")
        yield Container(self.table)

        yield Footer()

    async def on_mount(self):
        self.title = 'Message Broker Viewer'

        for key, label in self.COLUMNS.items():
            self.table.add_column(label, key=key)

        self.refresh_data()
        self.set_interval(1, self.refresh_data)

        self.table.cursor_type = 'row'

    def refresh_data(self):
        data = generate_data(self.broker)

        for topic, columns in data.items():
            try:
                for column, value in columns.items():
                    self.table.update_cell(topic, column, value)
            except CellDoesNotExist:
                cells = (columns[column] for column in self.COLUMNS.keys())
                self.table.add_row(*cells, key=topic)

        self.sort()

    def sort(self):
        key = None
        reverse = False

        if self.current_sort_column == 'last_updated':
            def key(u):
                return u.timestamp
            reverse = True
        elif self.current_sort_column == 'frame_rate':
            reverse = True

        self.table.sort(self.current_sort_column, key=key, reverse=reverse)

    def action_sort_by_topic(self):
        self.current_sort_column = 'topic'
        self.sort()

    def action_sort_by_last_updated(self):
        self.current_sort_column = 'last_updated'
        self.sort()

    def action_sort_by_frame_rate(self):
        self.current_sort_column = 'frame_rate'
        self.sort()

    def action_sort_by_pid(self):
        self.current_sort_column = 'pid'
        self.sort()

def usage():
    print("Usage: mtop <shared_memory_id>")

def main():
    args = sys.argv
    if len(args) != 2:
        usage()
        sys.exit(1)

    shared_memory_id = args[1]

    header = SharedMemory.open(shared_memory_id)
    broker = LocalMessageBroker.open(header)

    app = MTopApp(broker)
    app.run()
