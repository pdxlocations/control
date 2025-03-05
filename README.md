# Control - A console-based configuration tool for Meshtastic nodes

<img width="573" alt="Screenshot 2025-03-04 at 4 30 50 PM" src="https://github.com/user-attachments/assets/bc6a6590-f026-440c-9408-b26a644a2906" />

## Arguments

You can pass the following arguments to the client:

### Connection Arguments

Optional arguments to specify a device to connect to and how.

- `--port`, `--serial`, `-s`: The port to connect to via serial, e.g. `/dev/ttyUSB0`.
- `--host`, `--tcp`, `-t`: The hostname or IP address to connect to using TCP, will default to localhost if no host is passed.
- `--ble`, `-b`: The BLE device MAC address or name to connect to.

If no connection arguments are specified, the client will attempt a serial connection and then a TCP connection to localhost.

### Example Usage

```sh
python main.py --port /dev/ttyUSB0
python main.py --host 192.168.1.1
python main.py --ble BlAddressOfDevice
```
To quickly connect to localhost, use:
```sh
python main.py -t
```
