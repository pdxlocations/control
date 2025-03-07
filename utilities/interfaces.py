import logging
import meshtastic.serial_interface
import meshtastic.tcp_interface
import meshtastic.ble_interface

def initialize_interface(args):
    try:
        if args.ble:
            return meshtastic.ble_interface.BLEInterface(args.ble if args.ble != "any" else None)
        elif args.host:
            return meshtastic.tcp_interface.TCPInterface(args.host)
        else:
            try:
                return meshtastic.serial_interface.SerialInterface(args.port)
            except PermissionError as ex:
                logging.error(f"You probably need to add yourself to the `dialout` group to use a serial connection. {ex}")
            except Exception as ex:
                logging.error(f"Unexpected error initializing serial interface: {ex}")

            # Fallback to meshtastic.local, then localhost if it fails
            try:
                logging.info("Attempting to connect to meshtastic.local")
                return meshtastic.tcp_interface.TCPInterface("meshtastic.local")
            except Exception as ex:
                logging.warning(f"Failed to connect to meshtastic.local: {ex}")
                logging.info("Falling back to localhost")
                return meshtastic.tcp_interface.TCPInterface("localhost")

    except Exception as ex:
        logging.critical(f"Fatal error initializing interface: {ex}")
        return None  # Explicitly return None to indicate failure