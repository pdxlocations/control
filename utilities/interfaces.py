import logging
import meshtastic.serial_interface, meshtastic.tcp_interface, meshtastic.ble_interface

def initialize_interface(args, interface = None):
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
                logging.error(f"Unexpected error initializing interface: {ex}")
            if interface.devPath is None:
                return meshtastic.tcp_interface.TCPInterface("meshtastic.local")
    
    except Exception as ex:
        logging.critical(f"Fatal error initializing interface: {ex}")
    