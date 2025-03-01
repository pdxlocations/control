import contextlib
import curses
import io
import logging
import os
import re
import sys
import textwrap
import traceback

import default_config as config
from save_to_radio import save_changes
from utilities.config_io import config_export, config_import
from input_handlers import get_repeated_input, get_text_input, get_fixed32_input, get_list_input
from menus import generate_menu_from_protobuf
from ui.colors import setup_colors, get_color
from utilities.arg_parser import setup_parser
from utilities.interfaces import initialize_interface
from user_config import json_editor


width = 80
max_help_lines = 0
save_option = "Save Changes"
sensitive_settings = ["Reboot", "Reset Node DB", "Shutdown", "Factory Reset"]
help_win = None  # Ensures it's defined globally before usage

locals_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
translation_file = os.path.join(locals_dir, "localisations", "en.ini")


def transform_menu_path(menu_path):
    """Applies path replacements and normalizes entries in the menu path."""
    path_replacements = {
        "Radio Settings": "config",
        "Module Settings": "module"
    }

    transformed_path = []
    for part in menu_path[1:]:  # Skip 'Main Menu'
        # Apply fixed replacements
        part = path_replacements.get(part, part)

        # Normalize entries like "Channel 1", "Channel 2", etc.
        if re.match(r'Channel\s+\d+', part, re.IGNORECASE):
            part = "channel"

        transformed_path.append(part)

    return transformed_path


def parse_ini_file(ini_file_path):
    field_mapping = {}
    help_text = {}
    current_section = None

    with open(ini_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith(';') or line.startswith('#'):
                continue

            # Handle sections like [config.device]
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                continue

            # Parse lines like: key, "Human-readable name", "helptext"
            parts = [p.strip().strip('"') for p in line.split(',', 2)]
            if len(parts) >= 2:
                key = parts[0]

                # If key is 'title', map directly to the section
                if key == 'title':
                    full_key = current_section
                else:
                    full_key = f"{current_section}.{key}" if current_section else key

                # Use the provided human-readable name or fallback to key
                human_readable_name = parts[1] if parts[1] else key
                field_mapping[full_key] = human_readable_name

                # Handle help text or default
                help = parts[2] if len(parts) == 3 and parts[2] else "No help available."
                help_text[full_key] = help

            else:
                # Handle cases with only the key present
                full_key = f"{current_section}.{key}" if current_section else key
                field_mapping[full_key] = key
                help_text[full_key] = "No help available."

    return field_mapping, help_text

# Load human-readable field mappings
field_mapping, help_text = parse_ini_file(translation_file)



def display_menu(current_menu, menu_path, selected_index, show_save_option, help_text):
    num_items = len(current_menu) + (1 if show_save_option else 0)

    # Determine the available height for the menu
    max_menu_height = curses.LINES - 2  # Leave some space at the top and bottom
    menu_height = min(max_menu_height - 6, num_items + 5)  
    start_y = (curses.LINES - menu_height) // 2 - 2
    start_x = (curses.COLS - width) // 2

    # Calculate remaining space for help window
    global max_help_lines
    remaining_space = curses.LINES - (start_y + menu_height + 2)  # +2 for padding
    max_help_lines = max(remaining_space, 1)  # Ensure at least 1 lines for help

    menu_win = curses.newwin(menu_height, width, start_y, start_x)
    menu_win.erase()
    menu_win.bkgd(get_color("background"))
    menu_win.attrset(get_color("window_frame"))
    menu_win.border()
    menu_win.keypad(True)

    menu_pad = curses.newpad(len(current_menu) + 1, width - 8)
    menu_pad.bkgd(get_color("background"))

    header = " > ".join(word.title() for word in menu_path)
    if len(header) > width - 4:
        header = header[:width - 7] + "..."
    menu_win.addstr(1, 2, header, get_color("settings_breadcrumbs", bold=True))

    transformed_path = transform_menu_path(menu_path)

    for idx, option in enumerate(current_menu):
        field_info = current_menu[option]
        current_value = field_info[1] if isinstance(field_info, tuple) else ""
        full_key = '.'.join(transformed_path + [option])
        display_name = field_mapping.get(full_key, option)

        display_option = f"{display_name}"[:width // 2 - 2]
        display_value = f"{current_value}"[:width // 2 - 4]

        try:
            color = get_color("settings_sensitive" if option in sensitive_settings else "settings_default", reverse=(idx == selected_index))
            menu_pad.addstr(idx, 0, f"{display_option:<{width // 2 - 2}} {display_value}".ljust(width - 8), color)
        except curses.error:
            pass

    if show_save_option:
        save_position = menu_height - 2
        menu_win.addstr(save_position, (width - len(save_option)) // 2, save_option, get_color("settings_save", reverse=(selected_index == len(current_menu))))

    # Draw help window with dynamically updated max_help_lines
    draw_help_window(start_y, start_x, menu_height, max_help_lines, current_menu, selected_index, transformed_path)

    menu_win.refresh()
    menu_pad.refresh(
        0, 0,
        menu_win.getbegyx()[0] + 3, menu_win.getbegyx()[1] + 4,
        menu_win.getbegyx()[0] + 3 + menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0),
        menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 8
    )

    return menu_win, menu_pad




def draw_help_window(menu_start_y, menu_start_x, menu_height, max_help_lines, current_menu, selected_index, transformed_path):
    global help_win

    if 'help_win' not in globals():
        help_win = None  # Initialize if it does not exist

    selected_option = list(current_menu.keys())[selected_index] if current_menu else None
    help_y = menu_start_y + menu_height

    help_win = update_help_window(help_win, help_text, transformed_path, selected_option, max_help_lines, width, help_y, menu_start_x)


def update_help_window(help_win, help_text, transformed_path, selected_option, max_help_lines, width, help_y, help_x):
    """Handles rendering the help window consistently."""
    wrapped_help = get_wrapped_help_text(help_text, transformed_path, selected_option, width, max_help_lines)

    # Dynamically set help window height
    help_height = min(len(wrapped_help) + 2, max_help_lines + 2)  # +2 for border
    help_height = max(help_height, 3)  # Ensure at least 3 rows (1 text + border)

    # Ensure help window does not exceed screen size
    if help_y + help_height > curses.LINES:
        help_y = curses.LINES - help_height

    # Create or update the help window
    if help_win is None:
        help_win = curses.newwin(help_height, width, help_y, help_x)
    else:
        help_win.erase()
        help_win.refresh()
        help_win.resize(help_height, width)
        help_win.mvwin(help_y, help_x)

    help_win.bkgd(get_color("background"))
    help_win.attrset(get_color("window_frame"))
    help_win.border()

    for idx, line in enumerate(wrapped_help):
        try:
            help_win.addstr(1 + idx, 2, line, get_color("settings_default"))
        except curses.error:
            pass  # Prevent crashes

    help_win.refresh()
    return help_win

def get_wrapped_help_text(help_text, transformed_path, selected_option, width, max_lines):
    """Fetches and formats help text for display, ensuring it fits within the allowed lines."""
    
    full_help_key = '.'.join(transformed_path + [selected_option]) if selected_option else None
    help_content = help_text.get(full_help_key, "No help available.")

    wrap_width = max(width - 6, 10)  # Ensure a valid wrapping width
    wrapped_help = textwrap.wrap(help_content, width=wrap_width)

    if len(wrapped_help) > max_lines:
        wrapped_help = wrapped_help[:max_lines]  # Trim to max lines
        wrapped_help[-1] = wrapped_help[-1][: wrap_width - 3] + "..."  # Append ellipsis

    return wrapped_help


def move_highlight(old_idx, new_idx, options, show_save_option, menu_win, menu_pad, help_win, help_text, menu_path, max_help_lines):
    # global help_win

    if old_idx == new_idx:  # No-op
        return

    max_index = len(options) + (1 if show_save_option else 0) - 1

    if show_save_option and old_idx == max_index:  # Special case un-highlight "Save" option
        menu_win.chgat(menu_win.getmaxyx()[0] - 2, (width - len(save_option)) // 2, len(save_option), get_color("settings_save"))
    else:
        menu_pad.chgat(old_idx, 0, menu_pad.getmaxyx()[1], get_color("settings_sensitive") if options[old_idx] in sensitive_settings else get_color("settings_default"))

    if show_save_option and new_idx == max_index:  # Special case highlight "Save" option
        menu_win.chgat(menu_win.getmaxyx()[0] - 2, (width - len(save_option)) // 2, len(save_option), get_color("settings_save", reverse=True))
    else:
        menu_pad.chgat(new_idx, 0, menu_pad.getmaxyx()[1], get_color("settings_sensitive", reverse=True) if options[new_idx] in sensitive_settings else get_color("settings_default", reverse=True))

    menu_win.refresh()

    start_index = max(0, new_idx - (menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0)) - (1 if show_save_option and new_idx == max_index else 0))
    menu_pad.refresh(start_index, 0,
                     menu_win.getbegyx()[0] + 3, menu_win.getbegyx()[1] + 4,
                     menu_win.getbegyx()[0] + 3 + menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0), 
                     menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 8)

    # Transform menu path
    transformed_path = transform_menu_path(menu_path)
    selected_option = options[new_idx] if new_idx < len(options) else None
    help_y = menu_win.getbegyx()[0] + menu_win.getmaxyx()[0]

    # Call helper function to update the help window
    help_win = update_help_window(help_win, help_text, transformed_path, selected_option, max_help_lines, width, help_y, menu_win.getbegyx()[1])



def settings_menu(stdscr, interface):
    curses.update_lines_cols()

    menu = generate_menu_from_protobuf(interface)
    current_menu = menu["Main Menu"]
    menu_path = ["Main Menu"]
    menu_index = []
    selected_index = 0
    modified_settings = {}
    
    need_redraw = True
    show_save_option = False

    while True:
        if(need_redraw):
            options = list(current_menu.keys())

            show_save_option = (
                len(menu_path) > 2 and ("Radio Settings" in menu_path or "Module Settings" in menu_path)
            ) or (
                len(menu_path) == 2 and "User Settings" in menu_path 
            ) or (
                len(menu_path) == 3 and "Channels" in menu_path
            )

            # Display the menu
            menu_win, menu_pad = display_menu(current_menu, menu_path, selected_index, show_save_option, help_text)

            need_redraw = False

        # Capture user input
        key = menu_win.getch()

        max_index = len(options) + (1 if show_save_option else 0) - 1
        # max_help_lines = 4

        if key == curses.KEY_UP:
            old_selected_index = selected_index
            selected_index = max_index if selected_index == 0 else selected_index - 1
            move_highlight(old_selected_index, selected_index, options, show_save_option, menu_win, menu_pad, help_win, help_text, menu_path,max_help_lines)
            
        elif key == curses.KEY_DOWN:
            old_selected_index = selected_index
            selected_index = 0 if selected_index == max_index else selected_index + 1
            move_highlight(old_selected_index, selected_index, options, show_save_option, menu_win, menu_pad, help_win, help_text, menu_path, max_help_lines)

        elif key == curses.KEY_RESIZE:
            need_redraw = True
            curses.update_lines_cols()

        elif key == ord("\t") and show_save_option:
            old_selected_index = selected_index
            selected_index = max_index
            move_highlight(old_selected_index, selected_index, options, show_save_option, menu_win, menu_pad, help_win, help_text, menu_path, max_help_lines)

        elif key == curses.KEY_RIGHT or key == ord('\n'):
            need_redraw = True
            menu_win.erase()
            help_win.erase()

            # draw_help_window(menu_win.getbegyx()[0], menu_win.getbegyx()[1], menu_win.getmaxyx()[0], max_help_lines, current_menu, selected_index, transform_menu_path(menu_path))

            menu_win.refresh()
            help_win.refresh()
            if show_save_option and selected_index == len(options):
                save_changes(interface, menu_path, modified_settings)
                modified_settings.clear()
                logging.info("Changes Saved")

                if len(menu_path) > 1:
                    menu_path.pop()
                    current_menu = menu["Main Menu"]
                    for step in menu_path[1:]:
                        current_menu = current_menu.get(step, {})
                    selected_index = 0

                continue

            selected_option = options[selected_index]

            if selected_option == "Exit":
                break


            elif selected_option == "Export Config":
                filename = get_text_input("Enter a filename for the config file")

                if not filename:
                    logging.warning("Export aborted: No filename provided.")
                    continue  # Go back to the menu

                if not filename.lower().endswith(".yaml"):
                    filename += ".yaml"

                try:
                    config_text = config_export(interface)
                    app_directory = os.path.dirname(os.path.abspath(__file__))
                    config_folder = "node-configs"
                    yaml_file_path = os.path.join(app_directory, config_folder, filename)

                    if os.path.exists(yaml_file_path):
                        overwrite = get_list_input(f"{filename} already exists. Overwrite?", None, ["Yes", "No"])
                        if overwrite == "Yes":
                            logging.info("Export cancelled: User chose not to overwrite.")
                            continue  # Return to menu
                    os.makedirs(os.path.dirname(yaml_file_path), exist_ok=True)
                    with open(yaml_file_path, "w", encoding="utf-8") as file:
                        file.write(config_text)
                    logging.info(f"Config file saved to {yaml_file_path}")
                    continue
                except PermissionError:
                    logging.error(f"Permission denied: Unable to write to {yaml_file_path}")
                except OSError as e:
                    logging.error(f"OS error while saving config: {e}")
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                continue

            elif selected_option == "Load Config":
                app_directory = os.path.dirname(os.path.abspath(__file__))
                config_folder = "node-configs"
                folder_path = os.path.join(app_directory, config_folder)
                file_list = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
                filename = get_list_input("Choose a config file", None, file_list)
                if filename:
                    file_path = os.path.join(app_directory, config_folder, filename)
                    overwrite = get_list_input(f"Are you sure you want to load {filename}?", None,  ["Yes", "No"])
                    if overwrite == "Yes":
                        config_import(interface, file_path)
                continue

            elif selected_option == "Reboot":
                confirmation = get_list_input("Are you sure you want to Reboot?", None,  ["Yes", "No"])
                if confirmation == "Yes":
                    interface.localNode.reboot()
                    logging.info(f"Node Reboot Requested by menu")
                continue
            elif selected_option == "Reset Node DB":
                confirmation = get_list_input("Are you sure you want to Reset Node DB?", None,  ["Yes", "No"])
                if confirmation == "Yes":
                    interface.localNode.resetNodeDb()
                    logging.info(f"Node DB Reset Requested by menu")
                continue
            elif selected_option == "Shutdown":
                confirmation = get_list_input("Are you sure you want to Shutdown?", None, ["Yes", "No"])
                if confirmation == "Yes":
                    interface.localNode.shutdown()
                    logging.info(f"Node Shutdown Requested by menu")
                continue
            elif selected_option == "Factory Reset":
                confirmation = get_list_input("Are you sure you want to Factory Reset?", None,  ["Yes", "No"])
                if confirmation == "Yes":
                    interface.localNode.factoryReset()
                    logging.info(f"Factory Reset Requested by menu")
                continue
            # elif selected_option == "App Settings":
            #     menu_win.clear()
            #     menu_win.refresh()
            #     json_editor(stdscr)  # Open the App Settings menu
            #     continue
            #     # need_redraw = True
                
            field_info = current_menu.get(selected_option)
            if isinstance(field_info, tuple):
                field, current_value = field_info

                # Transform the menu path to get the full key
                transformed_path = transform_menu_path(menu_path)
                full_key = '.'.join(transformed_path + [selected_option])

                # Fetch human-readable name from field_mapping
                human_readable_name = field_mapping.get(full_key, selected_option)

                if selected_option in ['longName', 'shortName', 'isLicensed']:
                    if selected_option in ['longName', 'shortName']:
                        new_value = get_text_input(f"{human_readable_name} is currently: {current_value}")
                        new_value = current_value if new_value is None else new_value
                        current_menu[selected_option] = (field, new_value)

                    elif selected_option == 'isLicensed':
                        new_value = get_list_input(f"{human_readable_name} is currently: {current_value}", str(current_value),  ["True", "False"])
                        new_value = new_value == "True"
                        current_menu[selected_option] = (field, new_value)

                    for option, (field, value) in current_menu.items():
                        modified_settings[option] = value

                elif selected_option in ['latitude', 'longitude', 'altitude']:
                    new_value = get_text_input(f"{human_readable_name} is currently: {current_value}")
                    new_value = current_value if new_value is None else new_value
                    current_menu[selected_option] = (field, new_value)

                    for option in ['latitude', 'longitude', 'altitude']:
                        if option in current_menu:
                            modified_settings[option] = current_menu[option][1]

                elif field.type == 8:  # Handle boolean type
                    new_value = get_list_input(human_readable_name, str(current_value),  ["True", "False"])
                    new_value = new_value == "True" or new_value is True

                elif field.label == field.LABEL_REPEATED:  # Handle repeated field
                    new_value = get_repeated_input(current_value)
                    new_value = current_value if new_value is None else [int(item) for item in new_value]

                elif field.enum_type:  # Enum field
                    enum_options = {v.name: v.number for v in field.enum_type.values}
                    new_value_name = get_list_input(human_readable_name, current_value, list(enum_options.keys()))
                    new_value = enum_options.get(new_value_name, current_value)

                elif field.type == 7: # Field type 7 corresponds to FIXED32
                    new_value = get_fixed32_input(current_value)

                elif field.type == 13: # Field type 13 corresponds to UINT32
                    new_value = get_text_input(f"{human_readable_name} is currently: {current_value}")
                    new_value = current_value if new_value is None else int(new_value)

                elif field.type == 2: # Field type 13 corresponds to INT64
                    new_value = get_text_input(f"{human_readable_name} is currently: {current_value}")
                    new_value = current_value if new_value is None else float(new_value)

                else:  # Handle other field types
                    new_value = get_text_input(f"{human_readable_name} is currently: {current_value}")
                    new_value = current_value if new_value is None else new_value
                
                for key in menu_path[3:]:  # Skip "Main Menu"
                    modified_settings = modified_settings.setdefault(key, {})

                # Add the new value to the appropriate level
                modified_settings[selected_option] = new_value

                # Convert enum string to int
                if field and field.enum_type:
                    enum_value_descriptor = field.enum_type.values_by_number.get(new_value)
                    new_value = enum_value_descriptor.name if enum_value_descriptor else new_value

                current_menu[selected_option] = (field, new_value)
            else:
                current_menu = current_menu[selected_option]
                menu_path.append(selected_option)
                menu_index.append(selected_index)
                selected_index = 0

        elif key == curses.KEY_LEFT:
            need_redraw = True

            menu_win.erase()
            help_win.erase()

            # max_help_lines = 4
            # draw_help_window(menu_win.getbegyx()[0], menu_win.getbegyx()[1], menu_win.getmaxyx()[0], max_help_lines, current_menu, selected_index, transform_menu_path(menu_path))

            menu_win.refresh()
            help_win.refresh()

            if len(menu_path) < 2:
                modified_settings.clear()

            # Navigate back to the previous menu
            if len(menu_path) > 1:
                menu_path.pop()
                current_menu = menu["Main Menu"]
                for step in menu_path[1:]:
                    current_menu = current_menu.get(step, {})
                selected_index = menu_index.pop()

        elif key == 27:  # Escape key
            menu_win.erase()
            menu_win.refresh()
            break

def set_region(interface):
    node = interface.getNode('^local')
    device_config = node.localConfig
    lora_descriptor = device_config.lora.DESCRIPTOR

    # Get the enum mapping of region names to their numerical values
    region_enum = lora_descriptor.fields_by_name["region"].enum_type
    region_name_to_number = {v.name: v.number for v in region_enum.values}

    regions = list(region_name_to_number.keys())

    new_region_name = get_list_input('Select your region:', 'UNSET', regions)

    # Convert region name to corresponding enum number
    new_region_number = region_name_to_number.get(new_region_name, 0)  # Default to 0 if not found

    node.localConfig.lora.region = new_region_number
    node.writeConfig("lora")
    

def main(stdscr):

    output_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):

   
            setup_colors()
            curses.curs_set(0)
            stdscr.keypad(True)

            parser = setup_parser()
            args = parser.parse_args()
            interface = initialize_interface(args)

            if interface.localNode.localConfig.lora.region == 0:
                confirmation = get_list_input("Your region is UNSET.  Set it now?", "Yes",  ["Yes", "No"])
                if confirmation == "Yes":
                    set_region(interface)
                    interface.close()
                    interface = initialize_interface(args)
            settings_menu(stdscr, interface)

    except Exception as e:
        console_output = output_capture.getvalue()
        logging.error("An error occurred: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())
        logging.error("Console output before crash:\n%s", console_output)
        raise  # Re-raise only unexpected errors


logging.basicConfig( # Run `tail -f client.log` in another terminal to view live
    filename=config.log_file_path,
    level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    log_file = config.log_file_path
    log_f = open(log_file, "a", buffering=1)  # Enable line-buffering for immediate log writes

    sys.stdout = log_f
    sys.stderr = log_f

    with contextlib.redirect_stderr(log_f), contextlib.redirect_stdout(log_f):
        try:
            curses.wrapper(main)
        except KeyboardInterrupt:
            logging.info("User exited with Ctrl+C or Ctrl+X")  # Clean exit logging
            sys.exit(0)  # Ensure a clean exit
        except Exception as e:
            logging.error("Fatal error in curses wrapper: %s", e)
            logging.error("Traceback: %s", traceback.format_exc())
            sys.exit(1)  # Exit with an error code