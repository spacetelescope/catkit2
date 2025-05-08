import curses
import time
import sys
import numpy as np

from catkit2.catkit_bindings import SharedMemory, MessageBroker, get_timestamp

def human_readable_time(seconds):
    seconds = round(seconds)
    if seconds < 0:
        return "in the future"

    time_units = [
        ('day', 86400),
        ('hr', 3600),
        ('min', 60),
        ('sec', 1),
    ]

    for unit, unit_seconds in time_units:
        if seconds >= unit_seconds:
            quantity = seconds // unit_seconds

            return f"{quantity} {unit}{'s' if quantity != 1 else ''} ago"

            break
    else:
        return "<1 sec ago"

    return f"{quantity} {unit}{'s' if quantity != 1 else ''} ago"

def generate_data(broker):
    topics = broker.get_all_message_topics()

    res = []

    for topic in topics:
        last_message_id = broker.get_newest_message_id(topic)
        if last_message_id == 0:
            continue

        message = broker.get_newest_message(topic)

        if message.topic != topic:
            continue

        shape = message.array_info.shape
        dtype = message.array_info.dtype
        frame_rate = f'{broker.get_message_rate(topic):.1f}'
        pid = message.producer_pid
        time_since = get_timestamp() - message.producer_timestamp
        timestamp = human_readable_time(time_since / 1e9)

        if np.allclose(shape, [1]):
            value = str(message.payload[0])
        else:
            value = '[...]'

        res.append({
            'topic': topic,
            'pid': pid,
            'last_updated': timestamp,
            'frame_rate': frame_rate,
            'shape': shape,
            'dtype': np.dtype(dtype).name,
            'value': value
        })

    return res

def usage():
    print("Usage: mtop <shared_memory_id>")

def main():
    args = sys.argv
    if len(args) != 2:
        usage()
        sys.exit(1)

    shared_memory_id = args[1]
    buffer_id = 'buffer'

    try:
        header = SharedMemory.create(shared_memory_id, 1024 * 1024 * 512)
    except Exception:
        header = SharedMemory.open(shared_memory_id)

    try:
        buffer = SharedMemory.create(buffer_id, 1024 * 1024 * 512)
    except Exception:
        buffer = SharedMemory.open(buffer_id)
    broker = MessageBroker.create(header, [buffer])

    DATA_KEYS = ["topic", "pid", "last_updated", "frame_rate", "shape", "dtype", "value"]
    SORT_OPTIONS = DATA_KEYS.copy()
    SORT_LABELS = {"topic": "Topic                                   ", "pid": "PID", "last_updated": "Last Updated     ", "frame_rate": "FPS  ", "shape": "Shape    ", "dtype": "Dtype   ", "value": "Value"}
    DEFAULT_SORT_ORDER = {"topic": False, "pid": False, "last_updated": True, "frame_rate": True, "shape": True, "dtype": False, "value": False}  # Default sort order

    update_interval = 0.1


    def draw_ui(stdscr):
        curses.curs_set(0)  # Hide cursor
        curses.use_default_colors()
        stdscr.timeout(100)
        curses.halfdelay(1)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN)  # Header color
        curses.init_pair(2, -1, -1)  # Data color
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_CYAN)  # Highlighted row

        start_index = 0
        cursor_position = 0
        sort_index = 0

        last_update = time.time()
        data = generate_data(broker)

        while True:
            if time.time() - last_update > update_interval:
                data = generate_data(broker)
                last_update = time.time()

            stdscr.clear()
            height, width = stdscr.getmaxyx()

            max_display_rows = max(0, height - 6)
            stdscr.border()

            title = " Topic Monitor - Use ↑↓ to Navigate, ←→ to Sort, 'q' to Quit "
            stdscr.addstr(0, (width // 2) - (len(title) // 2), title)

            current_sort = SORT_OPTIONS[sort_index]
            headers = [(key, label.replace('▲', '')) for key, label in SORT_LABELS.items()]
            header_str = ""
            col_widths = {}

            for i, (key, label) in enumerate(headers):
                if key == current_sort:
                    header_str += f'{label} ▲'
                else:
                    header_str += f'{label}  '

                col_widths[key] = len(label) + 2

            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(2, 2, header_str)
            stdscr.attroff(curses.color_pair(1))

            sort_key = SORT_OPTIONS[sort_index]
            reverse_sort = DEFAULT_SORT_ORDER[sort_key]
            data.sort(key=lambda x: x[sort_key], reverse=reverse_sort)

            total_items = len(data)

            for i, entry in enumerate(data[start_index:start_index + max_display_rows]):
                y_position = i + 4

                row_data = [str(entry[key]).ljust(col_widths[key]) for key in DATA_KEYS]

                stdscr.attron(curses.color_pair(3 if i == cursor_position - start_index else 2))
                stdscr.addstr(y_position, 2, " ".join(row_data))
                stdscr.attroff(curses.color_pair(3 if i == cursor_position - start_index else 2))

            key = stdscr.getch()
            if key == ord('q'):
                return
            elif key == curses.KEY_DOWN:
                if cursor_position < total_items - 1:
                    cursor_position += 1
                    if cursor_position >= start_index + max_display_rows:
                        start_index += 1  # Scroll down
            elif key == curses.KEY_UP:
                if cursor_position > 0:
                    cursor_position -= 1
                    if cursor_position < start_index:
                        start_index -= 1  # Scroll up
            elif key == curses.KEY_LEFT:
                sort_index = (sort_index - 1) % len(SORT_OPTIONS)
            elif key == curses.KEY_RIGHT:
                sort_index = (sort_index + 1) % len(SORT_OPTIONS)

    curses.wrapper(draw_ui)
