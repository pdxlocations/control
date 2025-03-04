import curses
import base64
import ipaddress
import binascii
from ui.colors import get_color

def get_text_input(prompt):
    # Calculate the dynamic height and width for the input window
    height = 7  # Fixed height for input prompt
    width = 80
    start_y = (curses.LINES - height) // 2 - 2
    start_x = (curses.COLS - width) // 2

    # Create a new window for user input
    input_win = curses.newwin(height, width, start_y, start_x)
    input_win.bkgd(get_color("background"))
    input_win.attrset(get_color("window_frame"))
    input_win.border()

    # Display the prompt
    input_win.addstr(1, 2, prompt, get_color("settings_default", bold=True))
    input_win.addstr(3, 2, "Enter new value: ", get_color("settings_default"))
    input_win.refresh()

    # Check if "shortName" is in the prompt, and set max length accordingly
    max_length = 4 if "shortName" in prompt else None

    curses.curs_set(1)

    user_input = ""
    input_position = (3, 19)
    row, col = input_position
    while True:
        key = input_win.get_wch(row, col + len(user_input))  # Adjust cursor position dynamically
        if key == chr(27) or key == curses.KEY_LEFT:  # ESC or Left Arrow
            input_win.erase()
            input_win.refresh()
            curses.curs_set(0)
            return None  # Exit without returning a value
        elif key in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            break
        elif key in (curses.KEY_BACKSPACE, chr(127)):  # Backspace
            user_input = user_input[:-1]
            input_win.addstr(row, col, " " * (len(user_input) + 1), get_color("settings_default"))
            input_win.addstr(row, col, user_input, get_color("settings_default"))
        elif max_length is None or len(user_input) < max_length:  # Enforce max length if applicable
            # Append typed character to input text
            if(isinstance(key, str)):
                user_input += key
            else:
                user_input += chr(key)
            input_win.addstr(3, 19, user_input, get_color("settings_default"))

    curses.curs_set(0)

    # Clear the input window
    input_win.erase()
    input_win.refresh()
    return user_input





def get_repeated_input(current_value):
    def to_base64(byte_strings):
        """Convert byte values to Base64-encoded strings."""
        return [base64.b64encode(b).decode() for b in byte_strings]

    def is_valid_base64(s):
        """Check if a string is valid Base64."""
        try:
            base64.b64decode(s, validate=True)
            return True
        except binascii.Error:
            return False

    def to_bytes(base64_strings):
        """Convert valid Base64 strings to byte values."""
        return [base64.b64decode(s) for s in base64_strings if is_valid_base64(s)]

    cvalue = to_base64(current_value)  # Convert current values to Base64
    height = 8
    width = 80
    start_y = (curses.LINES - height) // 2 - 2
    start_x = (curses.COLS - width) // 2

    repeated_win = curses.newwin(height, width, start_y, start_x)
    repeated_win.bkgd(get_color("background"))
    repeated_win.attrset(get_color("window_frame"))
    repeated_win.keypad(True)  # Enable keypad for special keys

    curses.echo()
    curses.curs_set(1)

    # Editable list of values (max 3 values)
    user_values = cvalue[:3]
    cursor_pos = 0  # Track which value is being edited
    error_message = ""

    while True:
        repeated_win.erase()
        repeated_win.border()
        repeated_win.addstr(1, 2, "Edit up to 3 Admin Keys:", get_color("settings_default", bold=True))

        # Display current values, allowing editing
        for i, line in enumerate(user_values):
            prefix = "→ " if i == cursor_pos else "  "  # Highlight the current line
            repeated_win.addstr(3 + i, 2, f"{prefix}Admin Key {i + 1}: {line}", get_color("settings_default", bold=(i == cursor_pos)))

        # Show error message if needed
        if error_message:
            repeated_win.addstr(8, 2, error_message, get_color("error", bold=True))

        repeated_win.refresh()
        key = repeated_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow -> Cancel and return original
            repeated_win.erase()
            repeated_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            return ", ".join(cvalue)  # Return original Base64 strings
        elif key == ord('\n'):  # Enter key to save and return
            if all(is_valid_base64(val) for val in user_values):  # Ensure all values are valid Base64
                curses.noecho()
                curses.curs_set(0)
                return ", ".join(user_values)  # ✅ Directly return the edited Base64 values
            else:
                error_message = "Error: One or more values are not valid Base64!"
        elif key == curses.KEY_UP:  # Move cursor up
            cursor_pos = (cursor_pos - 1) % len(user_values)
        elif key == curses.KEY_DOWN:  # Move cursor down
            cursor_pos = (cursor_pos + 1) % len(user_values)
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace key
            user_values[cursor_pos] = user_values[cursor_pos][:-1]  # Remove last character
        else:
            try:
                user_values[cursor_pos] += chr(key)  # Append valid character input to the selected field
                error_message = ""  # Clear error if user starts fixing input
            except ValueError:
                pass  # Ignore invalid character inputs


def get_fixed32_input(current_value):
    cvalue = current_value
    current_value = str(ipaddress.IPv4Address(current_value))
    height = 10
    width = 80
    start_y = (curses.LINES - height) // 2 - 2
    start_x = (curses.COLS - width) // 2

    fixed32_win = curses.newwin(height, width, start_y, start_x)
    fixed32_win.bkgd(get_color("background"))
    fixed32_win.attrset(get_color("window_frame"))
    fixed32_win.keypad(True)

    curses.echo()
    curses.curs_set(1)
    user_input = ""

    while True:
        fixed32_win.erase()
        fixed32_win.border()
        fixed32_win.addstr(1, 2, "Enter an IP address (xxx.xxx.xxx.xxx):", curses.A_BOLD)
        fixed32_win.addstr(3, 2, f"Current: {current_value}")
        fixed32_win.addstr(5, 2, f"New value: {user_input}")
        fixed32_win.refresh()

        key = fixed32_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow to cancel
            fixed32_win.erase()
            fixed32_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            return cvalue  # Return the current value unchanged
        elif key == ord('\n'):  # Enter key to validate and save
            # Validate IP address
            octets = user_input.split(".")
            if len(octets) == 4 and all(octet.isdigit() and 0 <= int(octet) <= 255 for octet in octets):
                curses.noecho()
                curses.curs_set(0)
                fixed32_address = ipaddress.ip_address(user_input)
                return int(fixed32_address)  # Return the valid IP address
            else:
                fixed32_win.addstr(7, 2, "Invalid IP address. Try again.", curses.A_BOLD | curses.color_pair(5))
                fixed32_win.refresh()
                curses.napms(1500)  # Wait for 1.5 seconds before refreshing
                user_input = ""  # Clear invalid input
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace key
            user_input = user_input[:-1]
        else:
            try:
                char = chr(key)
                if char.isdigit() or char == ".":
                    user_input += char  # Append only valid characters (digits or dots)
            except ValueError:
                pass  # Ignore invalid inputs


def get_list_input(prompt, current_option, list_options):
    """
    Displays a scrollable list of list_options for the user to choose from.
    """
    selected_index = list_options.index(current_option) if current_option in list_options else 0

    height = min(len(list_options) + 5, curses.LINES - 2)
    width = 80
    start_y = (curses.LINES - height) // 2 - 2
    start_x = (curses.COLS - width) // 2

    list_win = curses.newwin(height, width, start_y, start_x)
    list_win.bkgd(get_color("background"))
    list_win.attrset(get_color("window_frame"))
    list_win.keypad(True)

    list_pad = curses.newpad(len(list_options) + 1, width - 8)
    list_pad.bkgd(get_color("background"))

    # Render header
    list_win.erase()
    list_win.border()
    list_win.addstr(1, 2, prompt, get_color("settings_default", bold=True))

    # Render options on the pad
    for idx, color in enumerate(list_options):
        if idx == selected_index:
            list_pad.addstr(idx, 0, color.ljust(width - 8), get_color("settings_default", reverse=True))
        else:
            list_pad.addstr(idx, 0, color.ljust(width - 8), get_color("settings_default"))

    # Initial refresh
    list_win.refresh()
    list_pad.refresh(0, 0,
                    list_win.getbegyx()[0] + 3, list_win.getbegyx()[1] + 4,
                    list_win.getbegyx()[0] + list_win.getmaxyx()[0] - 2, list_win.getbegyx()[1] + list_win.getmaxyx()[1] - 4)

    while True:
        key = list_win.getch()

        if key == curses.KEY_UP:
            old_selected_index = selected_index
            selected_index = max(0, selected_index - 1)
            move_highlight(old_selected_index, selected_index, list_options, list_win, list_pad)
        elif key == curses.KEY_DOWN:
            old_selected_index = selected_index
            selected_index = min(len(list_options) - 1, selected_index + 1)
            move_highlight(old_selected_index, selected_index, list_options, list_win, list_pad)
        elif key == ord('\n'):  # Enter key
            return list_options[selected_index]
        elif key == 27 or key == curses.KEY_LEFT:  # ESC or Left Arrow
            return current_option


def move_highlight(old_idx, new_idx, options, list_win, list_pad):
    if old_idx == new_idx:
        return # no-op

    list_pad.chgat(old_idx, 0, list_pad.getmaxyx()[1], get_color("settings_default"))
    list_pad.chgat(new_idx, 0, list_pad.getmaxyx()[1], get_color("settings_default", reverse = True))

    list_win.refresh()

    start_index = max(0, new_idx - (list_win.getmaxyx()[0] - 4))

    list_win.refresh()
    list_pad.refresh(start_index, 0,
                     list_win.getbegyx()[0] + 3, list_win.getbegyx()[1] + 4,
                     list_win.getbegyx()[0] + list_win.getmaxyx()[0] - 2, list_win.getbegyx()[1] + 4 + list_win.getmaxyx()[1] - 4)
    