import curses
import textwrap
from ui.colors import get_color

def dialog(window, title, message):
    height, width = window.getmaxyx()  # Get terminal size

    max_width = 80  # Apply max width of 80 but never exceed terminal width
    border_padding = 2

    # Wrap text within max width, considering padding and borders
    max_text_width = max_width - (2 * border_padding) - 4  # Account for padding and borders
    wrapped_message = []
    
    message_lines = message.splitlines()
    for line in message_lines:
        wrapped_message.extend(textwrap.wrap(line, max_text_width) if len(line) > max_text_width else [line])

    # Compute max line width after wrapping
    max_line_length = max(len(l) for l in wrapped_message) if wrapped_message else 0

    # Compute dialog dimensions
    # dialog_width = min(max_width, max(len(title) + 6, max_line_length + 2 * border_padding + 4))  # Ensure within max_width
    dialog_height = len(wrapped_message) + 2 * border_padding + 4  # +4 for borders

    # Ensure dialog is centered
    x = max(0, (width - max_width) // 2)
    y = max(0, (height - dialog_height) // 2)

    # Create dialog window
    win = curses.newwin(dialog_height, max_width, y, x)
    win.bkgd(get_color("background"))
    win.attrset(get_color("window_frame"))
    win.border(0)

    # Add title with padding
    win.addstr(1, 2, f" {title} ", get_color("settings_default"))

    # Add message with correct padding
    for i, line in enumerate(wrapped_message):
        win.addstr(3 + i, border_padding, line, get_color("settings_default"))  # Indent message

    # Add "Ok" button at bottom, centered
    button_text = " Ok "
    button_x = (max_width - len(button_text)) // 2
    win.addstr(dialog_height - 2, button_x, button_text, get_color("settings_default", reverse=True))

    # Refresh dialog window
    win.refresh()

    # Get user input to close dialog
    while True:
        char = win.getch()
        if char in (curses.KEY_ENTER, 10, 13, 32, 27):  # Enter, Space, or Esc
            win.erase()
            win.refresh()
            return