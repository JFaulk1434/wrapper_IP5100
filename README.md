# IP5100 Wrapper

A Python wrapper for controlling IP5100 ASpeed encoders and decoders via Telnet.

## Installation

```bash
pip install ip5100-wrapper
```

## Features

- Control IP5100 encoders and decoders via Telnet
- Support for both encoder and decoder operations
- Automatic device type detection
- Comprehensive API for all device functions
- Debug mode for detailed operation logging

## Basic Usage

```python
from IP5100 import IP5100_Device

# Create a device instance
device = IP5100_Device("192.168.1.100", port=24, login="root", debug=False)

# Get device information
print(device)  # Prints device name, alias, IP, MAC, type, and version

# Get device status
print(device.get_version())
print(device.get_alias())
print(device.get_ip_mode())
print(device.get_multicast_ip())

# Control device
device.set_alias("My Device")
device.reboot()
```

## Device Types

The wrapper automatically detects if the device is an encoder or decoder based on the model prefix:
- `IPE` prefix: Encoder
- `IPD` prefix: Decoder

## Encoder-Specific Features

```python
# Set input source (HDMI1, HDMI2, USB-C)
device.set_input("hdmi1")

# Set audio source (auto, hdmi, analog)
device.set_audio_source("hdmi")

# Get audio information
print(device.get_audio_input_info())
print(device.audio_specs)

# EDID management
device.edid_read()
device.edid_write(edid_data)
device.edid_reset()
```

## Decoder-Specific Features

```python
# Connect to encoder
device.set_source(mac="00:11:22:33:44:55")

# Video wall configuration
device.set_video_wall_v1(rows=2, columns=2, row_location=0, column_location=0)
device.set_video_wall_scale(1.5)
device.set_video_wall_rotate(90)

# Audio control
device.set_audio_out_source("native")
device.set_audio_hdmi_mute(False)

# Get status
print(device.get_audio_output_info())
print(device.get_video_output_info())
```

## Advanced Features

- HDCP control (1.4 and 2.2)
- Serial port configuration
- CEC commands
- Video wall configuration
- Audio routing and control
- Factory reset
- Network configuration

## Debug Mode

Enable debug mode to get detailed information about each operation:

```python
device = IP5100_Device("192.168.1.100", debug=True)
result = device.get_version()
print(result)  # Includes function name, command, and response
```

## Error Handling

All methods return a dictionary with status and message:

```python
result = device.set_alias("New Name")
if result["status"] == "success":
    print("Operation successful")
else:
    print(f"Error: {result['message']}")
```

## License

MIT License