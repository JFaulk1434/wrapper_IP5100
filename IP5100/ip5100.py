"""Python wrapper for IP5100 ASpeed"""

from telnetlib import Telnet
import re


# Helper functions
def string_to_dict(input_string):
    """
    Convert a string of key-value pairs to a dictionary.

    :param input_string: A string containing key-value pairs separated by '=' or ':'.
    :return: A dictionary representation of the input string.
    """
    try:
        # Split the string into lines
        lines = input_string.split("\n")

        # Split each line into a key-value pair and add it to the dictionary
        result_dict = {}
        for line in lines:
            separator = "=" if "=" in line else ":"
            if separator in line:
                key, value = line.split(
                    separator, 1
                )  # Only split on the first occurrence of the separator
                # Strip whitespace and carriage return characters from the key and value
                key = key.strip()
                value = value.strip().rstrip("\r")
                result_dict[key] = value

        return result_dict
    except Exception as e:
        print(f"Error converting string to dictionary: {e}")
        return {}


def audio_string_to_dict(input_string):
    """
    Convert a string of key-value pairs to a dictionary.

    :param input_string: A string containing key-value pairs separated by '=' or ':'.
    :return: A dictionary representation of the input string.
    """
    try:
        # Split the string into lines
        lines = input_string.split("\n")

        # Split each line into a key-value pair and add it to the dictionary
        result_dict = {}
        for line in lines:
            if "Sample Freq" in line and "Sample Size" in line:
                # Handle the case where Sample Freq and Sample Size are on the same line
                parts = line.split()
                sample_freq_value = parts[2]
                sample_size_value = parts[5] + " " + parts[6]

                result_dict["Sample Freq"] = sample_freq_value
                result_dict["Sample Size"] = sample_size_value
            else:
                separator = "=" if "=" in line else ":"
                if separator in line:
                    key, value = line.split(
                        separator, 1
                    )  # Only split on the first occurrence of the separator
                    # Strip whitespace and carriage return characters from the key and value
                    key = key.strip()
                    value = value.strip().rstrip("\r")
                    result_dict[key] = value

        return result_dict
    except Exception as e:
        print(f"Error converting string to dictionary: {e}")
        return {}


def format_pretty_audio_info(audio_info):
    try:
        # Extract the type and clean it by removing all text within parentheses and extracting channel info if present
        type_match = re.search(r"^(.*?)(?: \[.*\])?(?: \(.*\))?$", audio_info["Type"])
        audio_type = type_match.group(1) if type_match else audio_info["Type"]

        # Check for channel info in the type field
        channel_info_match = re.search(r"\[(.*?) Ch\]", audio_info["Type"])
        if channel_info_match:
            channel_info = (
                channel_info_match.group(1) + "Ch"
            )  # Appends 'Ch' directly to the number
        else:
            channel_info = (
                audio_info["Valid Ch"].split(" ")[0] + "Ch"
            )  # Adds 'Ch' if only a number is provided

        # Clean up frequency and sample size
        freq = audio_info["Sample Freq"].replace(" ", "")
        size = audio_info["Sample Size"].replace(" ", "")

        # Format the final string
        pretty_string = f"{channel_info} {audio_type} {freq}KHz {size}"

        return pretty_string
    except Exception as e:
        print(f"Error formatting audio info: {e}")


class IP5100_Device:
    """Python class for controlling the IP5100 encoder/decoder via Telnet."""

    def __init__(self, ip, port=24, timeout=3, login="root", debug=False):
        """Create the class using the IP address, port, and login credentials."""
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.login = login
        self.debug = debug
        self.tn = None

        self._model = None
        self._mac = None
        self.trueName = None
        self.version = None
        self.alias = None
        self._device_type = None

        self.connected = False

        # Attempt initial connection
        self.connect()

        self.url = f"http://{self.ip}/settings.html"
        self.stream = f"http://{self.ip}:8080/?action=stream"

    @property
    def device_type(self):
        """Property to determine if device is an encoder or decoder based on model prefix."""
        if not self.connected:
            self.connect()
        if self._device_type is None and self._model:
            if self._model.startswith("IPE"):
                self._device_type = "encoder"
            elif self._model.startswith("IPD"):
                self._device_type = "decoder"
            else:
                self._device_type = "unknown"
        return self._device_type

    @property
    def model(self):
        """Property to ensure connection when accessing model."""
        if not self.connected:
            self.connect()
        return self._model

    @property
    def mac(self):
        """Property to ensure connection when accessing mac."""
        if not self.connected:
            self.connect()
        return self._mac

    @mac.setter
    def mac(self, value):
        """Setter for mac property."""
        self._mac = value

    def __str__(self):
        return f"{self.trueName} - {self.alias} - {self.ip} - {self.mac} - {self.device_type.capitalize()} - {self.version}"

    def connect(self):
        """
        Attempts to connect to the device, handling cases where the device might be offline or not responding.
        """
        if self.tn is None:
            self.tn = Telnet()
            self.tn.set_debuglevel(0)
        try:
            self.tn.open(self.ip, self.port, timeout=1.0)
            response = self.tn.read_until(b"login:")
            response_str = response.decode("utf-8").strip()
            parts = response_str.split("-")
            self._model = parts[0].strip()
            self._mac = parts[1].strip().split(" ")[0]
            self.trueName = f"{self._model}-{self._mac}"
            self.tn.write(self.login.encode() + b"\r\n")
            self.tn.read_until(b"/ #")
            self.get_alias()
            self.get_version()
            self.connected = True
            return True
        except Exception as e:
            print(f"Failed to connect to {self.ip}. Error: {e}")
            self.tn = None  # Reset the connection
            self.connected = False
            return False

    def ensure_connection(self):
        """
        Ensures that the device is connected before sending commands.
        """
        if self.tn is None or self.tn.get_socket() is None:
            return self.connect()
        return True

    def send(self, message: str, function_name: str = "send") -> str | tuple[str, dict]:
        """
        Sends a message to the Controller and returns the response, ensuring the device is connected.
        Includes a retry mechanism if the initial send fails due to a connection issue.

        Args:
            message: The command to send to the device
            function_name: The name of the calling function for debug information

        Returns:
            If debug is False: str - The response from the device
            If debug is True: tuple[str, dict] - The response and debug information
        """
        if not self.ensure_connection():
            if self.debug:
                return "Failed to establish connection", {
                    "function": function_name,
                    "command": message,
                    "response": "Failed to establish connection",
                }
            return "Failed to establish connection"

        try:
            message_bytes = f"{message}\n".encode()
            self.tn.write(message_bytes)
            self.tn.write(b"")
            stdout = self.tn.read_until(b"/ #").decode()
            response = stdout.strip("/ #")
            if response.startswith(message):
                response = response[len(message) :].strip()

            if self.debug:
                return response, {
                    "function": function_name,
                    "command": message,
                    "response": response,
                }
            return response
        except Exception as e:
            error_msg = f"Failed to send command to {self.ip}. Error: {e}"
            print(error_msg)
            self.disconnect()  # Ensure disconnection before retrying
            self.tn = None  # Reset the Telnet connection
            if self.debug:
                return "Failed to send command", {
                    "function": function_name,
                    "command": message,
                    "response": error_msg,
                }
            return "Failed to send command"

    def disconnect(self):
        """
        Safely closes the Telnet connection if it exists.
        """
        if self.tn is not None:
            try:
                self.tn.close()
            except Exception as e:
                print(f"Error closing Telnet connection: {e}")
            finally:
                self.tn = None
                self.connected = False

    def _format_response(
        self, status: str, message: str, function_name: str, command: str, response: str
    ) -> dict:
        """
        Format the response dictionary with debug information if enabled.
        """
        result = {"status": status, "message": message}
        if self.debug:
            result.update(
                {"function": function_name, "command": command, "response": response}
            )
        return result

    def get_version(self) -> dict:
        """
        Returns a dictionary with the version information.
        If debug is enabled, includes function name, command, and response.
        """
        command = "cat /etc/version"
        if self.debug:
            response, debug_info = self.send(command, "get_version")
        else:
            response = self.send(command)

        lines = response.strip().split("\n")

        if len(lines) >= 2:
            self.version = lines[1].strip()
        else:
            self.version = None

        result = {"version": self.version}
        if self.debug:
            result.update(debug_info)
        return result

    def get_ip_mode(self) -> dict:
        """
        Get the IP mode of the device.
        Returns a dictionary containing the IP mode.
        """
        command = "astparam g ip_mode"
        if self.debug:
            response, debug_info = self.send(command, "get_ip_mode")
        else:
            response = self.send(command)

        if "not defined" in response.lower():
            self.ip_mode = None
        else:
            self.ip_mode = response.strip()

        result = {"ip_mode": self.ip_mode}
        if self.debug:
            result.update(debug_info)
        return result

    def get_multicast_ip(self) -> dict:
        """
        Get the multicast IP of the device.
        Returns a dictionary containing the multicast IP.
        """
        command = "astparam g multicast_ip"
        if self.debug:
            response, debug_info = self.send(command, "get_multicast_ip")
        else:
            response = self.send(command)

        if "not defined" in response.lower():
            self.multicast_ip = None
        else:
            self.multicast_ip = response.strip()

        result = {"multicast_ip": self.multicast_ip}
        if self.debug:
            result.update(debug_info)
        return result

    def get_subnet_mask(self) -> dict:
        """
        Get the subnet mask of the device.
        Returns a dictionary containing the subnet mask.
        """
        command = "ifconfig|grep Mask|sed -n 1p|awk -F : '{print $4}'"
        if self.debug:
            response, debug_info = self.send(command, "get_subnet_mask")
        else:
            response = self.send(command)

        if "not defined" in response.lower():
            self.netmask = None
        else:
            self.netmask = response.strip()

        result = {"subnet_mask": self.netmask}
        if self.debug:
            result.update(debug_info)
        return result

    def get_gateway_ip(self) -> dict:
        """
        Get the gateway IP of the device.
        Returns a dictionary containing the gateway IP.
        """
        command = "route -n | grep UG | awk '{print $2}'"
        if self.debug:
            response, debug_info = self.send(command, "get_gateway_ip")
        else:
            response = self.send(command)

        if "not defined" in response.lower():
            self.gateway_ip = None
        else:
            self.gateway_ip = response.strip()

        result = {"gateway_ip": self.gateway_ip}
        if self.debug:
            result.update(debug_info)
        return result

    def dump(self) -> dict:
        """
        Get all parameters from the device.
        Returns a dictionary containing all device parameters.
        """
        command = "astparam dump"
        if self.debug:
            response, debug_info = self.send(command, "dump")
        else:
            response = self.send(command)

        result = string_to_dict(response)
        if self.debug:
            result.update(debug_info)
        return result

    def flush(self) -> dict:
        """
        Flush all parameters from the device.
        Returns a dictionary containing the operation status.
        """
        command = "astparam flush"
        if self.debug:
            response, debug_info = self.send(command, "flush")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def save(self) -> dict:
        """
        Save all parameters to the device.
        Returns a dictionary containing the operation status.
        """
        command = "astparam save"
        if self.debug:
            response, debug_info = self.send(command, "save")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def reboot(self) -> dict:
        """
        Reboot the device.
        Returns a dictionary containing the operation status.
        """
        self.save()
        command = "reboot"
        if self.debug:
            response, debug_info = self.send(command, "reboot")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_astparam(self, key, value) -> dict:
        """
        Set a specific astparam key-value pair.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s {key} {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_astparam")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def remove_astparam(self, key, value) -> dict:
        """
        Remove a specific astparam key-value pair.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s {key}={value}"
        if self.debug:
            response, debug_info = self.send(command, "remove_astparam")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_no_video(self, status: bool = True) -> dict:
        """
        Enable or Disable the video of the device. Unit will reboot after this command.
        Returns a dictionary containing the operation status.
        """
        if status:
            command = "astparam s no_video y; astparam save; reboot"
        else:
            command = "astparam s no_video n; astparam save; reboot"
        if self.debug:
            response, debug_info = self.send(command, "set_no_video")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def video_wall(self, value) -> dict:
        """
        Set the video wall of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s video_wall {value}"
        if self.debug:
            response, debug_info = self.send(command, "video_wall")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_ip(self, gateway, netmask, ipaddr) -> dict:
        """
        Set the IP of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s gatewayip {gateway}; astparam s netmask {netmask}; astparam s ipaddr {ipaddr}; astparam s ip_mode static"
        if self.debug:
            response, debug_info = self.send(command, "set_ip")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_ip_mode(self, mode) -> dict:
        """
        Set the IP mode of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s ip_mode {mode}"
        if self.debug:
            response, debug_info = self.send(command, "set_ip_mode")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_hdcp_1_4(self, value) -> dict:
        """
        Set the HDCP 1.4 of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s hdcp_always_on {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_hdcp_1_4")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_hdcp_2_2(self, value) -> dict:
        """
        Set the HDCP 2.2 of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s hdcp_2_2 {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_hdcp_2_2")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_hdcp(self, status: int = 1) -> dict:
        """
        Set the HDCP of the device.
        Returns a dictionary containing the operation status.
        """
        if status == 0:
            command = "astparam s hdcp_enable n"
        else:
            command = "astparam s hdcp_enable y"
        if self.debug:
            response, debug_info = self.send(command, "set_hdcp")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_addon(self, value) -> dict:
        """
        Set the addon of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s a_addon {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_addon")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_analog_in_volume(self, value) -> dict:
        """
        Set the analog in volume of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"echo {value} > /sys/devices/platform/1500_i2s/analog_in_vol"
        if self.debug:
            response, debug_info = self.send(command, "set_analog_in_volume")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_analog_out_volume(self, value) -> dict:
        """
        Set the analog out volume of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"echo {value} > /sys/devices/platform/1500_i2s/analog_out_vol"
        if self.debug:
            response, debug_info = self.send(command, "set_analog_out_volume")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_bridge_enable(self, value) -> dict:
        """
        Set the bridge of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s a_bridge_en {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_bridge_enable")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_serial_enabled(self, status: bool = True) -> dict:
        """
        Set the serial of the device.
        Returns a dictionary containing the operation status.
        """
        if status:
            command = "astparam s no_soip n"
        else:
            command = "astparam s no_soip y"
        if self.debug:
            response, debug_info = self.send(command, "set_serial_enabled")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_serial_baudrate(
        self,
        baudrate: int = 115200,
        data_bits: int = 8,
        stop_bits: int = 1,
        parity: str = "n",
    ) -> dict:
        """
        Set the serial baudrate of the device.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s s0_baudrate {baudrate}-{data_bits}{parity}{stop_bits}"
        if self.debug:
            response, debug_info = self.send(command, "set_serial_baudrate")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_serial_feedback(self, value) -> dict:
        """
        Serial feedback data describe string as HEX mode or printable ASCII mode.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s soip_feedback_hex {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_serial_feedback")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_serial_feedback_mode(self, value) -> dict:
        """
        Feedback mode is get serial data to multicast group to controller
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s soip_feedback_mode {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_serial_feedback_mode")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_serial_feedback_wait(self, value) -> dict:
        """
        Set the serial feedback wait of the device in miliseconds.
        Returns a dictionary containing the operation status.
        """
        command = f"astparam s soip_feedback_wait {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_serial_feedback_wait")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def send_serial_data(
        self, rs232_param, content, is_hex=False, append_cr=True, append_lf=True
    ) -> dict:
        """
        Send data to serial when feedback mode is enabled.
        Returns a dictionary containing the operation status.
        """
        command = f'soip2 -f /dev/ttyS0 -b {rs232_param} -s "{content}"'
        if is_hex:
            command += " -H"
        if append_cr:
            command += " -r"
        if append_lf:
            command += " -n"
        if self.debug:
            response, debug_info = self.send(command, "send_serial_data")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_cec_enable(self, status: bool = True) -> dict:
        """
        Enable or disable CEC on the device.
        Returns a dictionary containing the operation status.
        """
        if status:
            command = "astparam s no_cec n"
        else:
            command = "astparam s no_cec y"
        if self.debug:
            response, debug_info = self.send(command, "set_cec_enable")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def find_me(self, time) -> dict:
        """
        Find me command
        Returns a dictionary containing the operation status.
        """
        command = f"e e_find_me::{time}"
        if self.debug:
            response, debug_info = self.send(command, "find_me")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def cec_send(self, command) -> dict:
        """
        Send CEC command
        Returns a dictionary containing the operation status.
        """
        command = f"cec_send {command}"
        if self.debug:
            response, debug_info = self.send(command, "cec_send")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def factory_reset(self) -> dict:
        """
        Factory reset the device.
        Returns a dictionary containing the operation status.
        """
        command = "reset_to_default.sh"
        if self.debug:
            response, debug_info = self.send(command, "factory_reset")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_alias(self, alias: str) -> dict:
        """
        Set the alias of the device.
        Returns a dictionary containing the operation status.
        """
        self.alias = alias.replace("_", "-").replace(" ", "-")
        command = f'astparam s name "{self.alias}"; astparam save'
        if self.debug:
            response, debug_info = self.send(command, "set_alias")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def get_alias(self) -> dict:
        """
        Get the alias of the device.
        Returns a dictionary containing the device alias.
        """
        command = "astparam g name"
        if self.debug:
            response, debug_info = self.send(command, "get_alias")
        else:
            response = self.send(command)

        if response.startswith('"name" not defined'):
            self.alias = None
        else:
            self.alias = response

        result = {"alias": self.alias}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_quality(self, value) -> dict:
        """
        Set the video quality of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "encoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for encoders",
                    "function": "set_video_quality",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for encoders",
            }
        command = f"astparam s ast_video_quality_mode {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_quality")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_input(self, input: str) -> dict:
        """
        Set the input source of the device (encoder only).
        Valid inputs are: hdmi1, hdmi2, usb-c
        Returns a dictionary containing the operation status.
        """
        valid_inputs = ["hdmi1", "hdmi2", "usb-c"]
        if input.lower() not in valid_inputs:
            if self.debug:
                return {
                    "status": "error",
                    "message": f"Invalid input. Must be one of: {', '.join(valid_inputs)}",
                    "function": "set_input",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": f"Invalid input. Must be one of: {', '.join(valid_inputs)}",
            }

        if self.device_type != "encoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for encoders. Current device is a decoder.",
                    "function": "set_input",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for encoders. Current device is a decoder.",
            }

        command = f"e e_v_switch_in::{input.lower()}"
        if self.debug:
            response, debug_info = self.send(command, "set_input")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_output_timing(self, value) -> dict:
        """
        Set the output timing of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_output_timing",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        value = self.timing[value]["hex"]
        command = f"echo {value} > /sys/devices/platform/videoip/output_timing_convert"
        if self.debug:
            response, debug_info = self.send(command, "set_output_timing")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_source(self, mac=None, channels="z") -> dict:
        """
        Connect to encoder with mac address or disconnect if no mac provided.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "edid": None,
                    "function": "set_source",
                    "command": "",
                    "response": "",
                }
            return {"edid": None}

        if mac:
            mac = mac.replace(":", "").strip().upper()
            command = f"e e_reconnect::{mac}::{channels}"
        else:
            command = "e e_reconnect::NULL"

        self.send(command, "set_source")
        result = {"mac": mac if mac else "NULL"}
        if self.debug:
            result.update({"function": "set_source", "command": command})
        return result

    def set_audio_direction(self, direction: str) -> dict:
        """
        Set analog audio as input or output, for encoder with programable analog audio connector.
        Valid directions are: in, out
        Returns a dictionary containing the operation status.
        """
        valid_directions = ["in", "out"]
        if direction.lower() not in valid_directions:
            if self.debug:
                return {
                    "status": "error",
                    "message": f"Invalid direction. Must be one of: {', '.join(valid_directions)}",
                    "function": "set_audio_direction",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": f"Invalid direction. Must be one of: {', '.join(valid_directions)}",
            }

        if self.device_type != "encoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for encoders. Current device is a decoder.",
                    "function": "set_audio_direction",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for encoders. Current device is a decoder.",
            }

        command = f"e e_a_direction::{direction.lower()}"
        if self.debug:
            response, debug_info = self.send(command, "set_audio_direction")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_audio_source(self, source: str) -> dict:
        """
        Set the audio source of the device (encoder only).
        Valid sources are: auto, hdmi, analog
        Returns a dictionary containing the operation status.
        """
        valid_sources = ["auto", "hdmi", "analog"]
        if source.lower() not in valid_sources:
            if self.debug:
                return {
                    "status": "error",
                    "message": f"Invalid source. Must be one of: {', '.join(valid_sources)}",
                    "function": "set_audio_source",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": f"Invalid source. Must be one of: {', '.join(valid_sources)}",
            }

        if self.device_type != "encoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for encoders. Current device is a decoder.",
                    "function": "set_audio_source",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for encoders. Current device is a decoder.",
            }

        command = f"e e_a_input::{source.lower()}"
        if self.debug:
            response, debug_info = self.send(command, "set_audio_source")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def edid_write(self, edid) -> dict:
        """
        Write EDID to the device.
        Returns a dictionary containing the EDID data that was written.
        """
        if self.device_type != "encoder":
            if self.debug:
                return {
                    "edid": None,
                    "function": "edid_write",
                    "command": "",
                    "response": "",
                }
            return {"edid": None}

        # Clean the EDID data by removing any extra whitespace and newlines
        cleaned_edid = edid.replace("\r", "").replace("\n", "").strip()
        # Normalize all spaces to single spaces
        while "  " in cleaned_edid:
            cleaned_edid = cleaned_edid.replace("  ", " ")

        command = (
            f'echo "{cleaned_edid}" > /sys/devices/platform/videoip/eeprom_content'
        )
        self.send(command, "edid_write")

        result = {"edid": cleaned_edid}
        if self.debug:
            result.update({"function": "edid_write", "command": command})
        return result

    def edid_read(self) -> dict:
        """
        Read EDID from the device.
        Returns a dictionary containing the EDID data with single spaces between bytes.
        """
        if self.device_type == "encoder":
            command = "cat /sys/devices/platform/videoip/edid_cache"
        elif self.device_type == "decoder":
            command = "cat /sys/devices/platform/display/monitor_edid"
        else:
            if self.debug:
                return {
                    "edid": None,
                    "function": "edid_read",
                    "command": "",
                    "response": "",
                }
            return {"edid": None}

        if self.debug:
            response, debug_info = self.send(command, "edid_read")
        else:
            response = self.send(command)

        # Clean the EDID data by removing formatting characters and normalizing spaces
        cleaned_edid = (
            response.replace("|", "").replace("\r\n", " ").replace("   ", " ").strip()
        )
        # Normalize all spaces to single spaces
        while "  " in cleaned_edid:
            cleaned_edid = cleaned_edid.replace("  ", " ")

        result = {"edid": cleaned_edid}
        if self.debug:
            result.update(debug_info)
        return result

    def edid_reset(self) -> dict:
        """
        Reset the EDID
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "encoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for encoders",
                    "function": "edid_reset",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for encoders",
            }
        command = "cat /sys/devices/platform/display/default_edid_hdmi > /sys/devices/platform/videoip/eeprom_content"
        if self.debug:
            response, debug_info = self.send(command, "edid_reset")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def get_audio_input_info(self) -> dict:
        """
        Get audio information from the device.
        Returns a dictionary containing audio input information.
        """
        if self.device_type != "encoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for encoders",
                    "function": "get_audio_input_info",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for encoders",
            }

        command = "cat /sys/devices/platform/1500_i2s/input_audio_info"
        if self.debug:
            response, debug_info = self.send(command, "get_audio_input_info")
        else:
            response = self.send(command)

        result = audio_string_to_dict(response)
        if self.debug:
            result.update(debug_info)
        return result

    def get_video_input_info(self) -> dict:
        """
        Get video information from the device.
        Returns a dictionary containing video input information.
        """

        command = "gbstatus"
        if self.debug:
            response, debug_info = self.send(command, "get_video_input_info")
        else:
            response = self.send(command)

        result = string_to_dict(response)
        if self.debug:
            result.update(debug_info)
        return result

    @property
    def audio_specs(self) -> str:
        """Returns a string of audio information from the device."""
        if self.device_type != "encoder":
            return "This command is only available for encoders"
        response = self.get_audio_input_info()
        if response["State"] == "On":
            return format_pretty_audio_info(response)
        else:
            return "No Audio"

    def set_ui_resolution(self, width, height, fps) -> dict:
        """
        Set the UI resolution of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_ui_resolution",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"astparam s ui_default_res {width}x{height}@{fps}"
        if self.debug:
            response, debug_info = self.send(command, "set_ui_resolution")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def ui_show_text(self, status: bool = True) -> dict:
        """
        Show text on the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "ui_show_text",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        if status:
            command = "astparam s ui_show_text y"
        else:
            command = "astparam s ui_show_text n"
        if self.debug:
            response, debug_info = self.send(command, "ui_show_text")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_channel(self, channel, value) -> dict:
        """
        Set the channel of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_channel",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"astparam s ch_select_{channel} {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_channel")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_genlock_scaling(self, enable: bool) -> dict:
        """
        Enable genlock scaling mode, which always scaling timing width higher than 1080 to 1080P,
        but keep frame rate as input stream. For Decoder only.

        Args:
            enable (bool): True to enable genlock scaling, False to disable

        Returns:
            dict: Operation result
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "edid": None,
                    "function": "set_video_genlock_scaling",
                    "command": "",
                    "response": "",
                }
            return {"edid": None}

        value = "y" if enable else "n"
        command = f"astparam s video_genlock_scaling {value}"
        self.send(command, "set_video_genlock_scaling")

        result = {"enabled": enable}
        if self.debug:
            result.update({"function": "set_video_genlock_scaling", "command": command})
        return result

    def set_hdr_drop(self, enable: bool) -> dict:
        """
        Set decoder HDMI output HDR to off, or pass thru. For Decoder only.

        Args:
            enable (bool): True to enable HDR pass thru (1), False to disable HDR (0)

        Returns:
            dict: Operation result
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "edid": None,
                    "function": "set_hdr_drop",
                    "command": "",
                    "response": "",
                }
            return {"edid": None}

        value = "1" if enable else "0"
        command = f"astparam s v_hdmi_hdr_mode {value}"
        self.send(command, "set_hdr_drop")

        result = {"enabled": enable}
        if self.debug:
            result.update({"function": "set_hdr_drop", "command": command})
        return result

    def set_vwall_disable(self) -> dict:
        """
        Disable Video wall
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_vwall_disable",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command1 = "e e_vw_enable_0_0_0_0"
        command2 = "e e_vw_enable_0_0_0_0_2"
        if self.debug:
            response1, debug_info1 = self.send(command1, "set_vwall_disable")
            response2, debug_info2 = self.send(command2, "set_vwall_disable")
        else:
            response1 = self.send(command1)
            response2 = self.send(command2)

        status = (
            "success"
            if not (response1.startswith("Failed") or response2.startswith("Failed"))
            else "error"
        )
        result = {
            "status": status,
            "message": f"Response 1: {response1}, Response 2: {response2}",
        }
        if self.debug:
            result.update(
                {
                    "function": "set_vwall_disable",
                    "command": f"{command1}; {command2}",
                    "response": f"{response1}; {response2}",
                }
            )
        return result

    def set_vwall_rotate(self, value) -> dict:
        """
        Set the video wall rotation of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_vwall_rotate",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_rotate_0_0_0_0 {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_vwall_rotate")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_vwall_scale(self, value) -> dict:
        """
        Set the video wall scale of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_vwall_scale",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_scale_0_0_0_0 {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_vwall_scale")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_vwall_scale_rotate(self, value) -> dict:
        """
        Set the video wall scale and rotation of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_vwall_scale_rotate",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_scale_rotate_0_0_0_0 {value}"
        if self.debug:
            response, debug_info = self.send(command, "set_vwall_scale_rotate")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_audio_out_source(self, source: str) -> dict:
        """
        Source selection for I2S output. For Decoder only.

        Args:
            source (str): Audio source, must be either "native" or "addon"

        Returns:
            dict: Operation result
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_audio_out_source",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }

        valid_sources = ["native", "addon"]
        if source.lower() not in valid_sources:
            if self.debug:
                return {
                    "status": "error",
                    "message": f"Invalid source. Must be one of: {', '.join(valid_sources)}",
                    "function": "set_audio_out_source",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": f"Invalid source. Must be one of: {', '.join(valid_sources)}",
            }

        command = f"e e_a_out_src_sel::{source.lower()}"
        self.send(command, "set_audio_out_source")

        result = {"status": "success", "source": source.lower()}
        if self.debug:
            result.update({"function": "set_audio_out_source", "command": command})
        return result

    def set_audio_hdmi_mute(self, status: bool) -> dict:
        """
        Set the audio HDMI mute of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_audio_hdmi_mute",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = "e e_hdmi_audio_mute::y" if status else "e e_hdmi_audio_mute::n"
        if self.debug:
            response, debug_info = self.send(command, "set_audio_hdmi_mute")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def get_audio_output_info(self) -> dict:
        """
        Get audio information from the device. For Decoder only.

        Returns:
            dict: Audio output information with fields:
                - State: Audio state (On/Off)
                - Source: Audio source (HDMI/Analog)
                - format: Audio format (I2S)
                - Type: Audio type (LPCM)
                - Sample Freq: Sample frequency
                - Sample Size: Sample size in bits
                - Valid Ch: Number of valid channels
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "get_audio_output_info",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }

        command = "cat /sys/devices/platform/1500_i2s/output_audio_info"
        if self.debug:
            response, debug_info = self.send(command, "get_audio_output_info")
        else:
            response = self.send(command)

        result = string_to_dict(response)
        if not result:
            if self.debug:
                return {
                    "status": "error",
                    "message": "Failed to get audio output info",
                    "function": "get_audio_output_info",
                    "command": command,
                    "response": response,
                }
            return {"status": "error", "message": "Failed to get audio output info"}

        if self.debug:
            result.update(debug_info)
        return result

    def get_video_output_info(self) -> dict:
        """
        Get video information from the device. For Decoder only.

        Returns:
            dict: Video output information with fields:
                - State: Video state (On/Off)
                - Source: Video source (HDMI/Analog)
                - Resolution: Current resolution
                - Frame Rate: Current frame rate
                - Color Space: Current color space
                - HDR: HDR status
                - EDID: Current EDID status
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "get_video_output_info",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }

        command = "gbstatus"
        if self.debug:
            response, debug_info = self.send(command, "get_video_output_info")
        else:
            response = self.send(command)

        result = string_to_dict(response)
        if not result:
            if self.debug:
                return {
                    "status": "error",
                    "message": "Failed to get video output info",
                    "function": "get_video_output_info",
                    "command": command,
                    "response": response,
                }
            return {"status": "error", "message": "Failed to get video output info"}

        if self.debug:
            result.update(debug_info)
        return result

    def set_monitor_info(self, ow, oh, vw, vh) -> dict:
        """
        Set monitor information.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_monitor_info",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_moninfo_{vw}_{ow}_{vh}_{oh}"
        if self.debug:
            response, debug_info = self.send(command, "set_monitor_info")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_v1(self, rows, columns, row_location, column_location) -> dict:
        """
        Set video wall configuration.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_v1",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        rows = rows - 1 if isinstance(rows, int) else rows
        columns = columns - 1 if isinstance(columns, int) else columns
        row_location = (
            row_location - 1 if isinstance(row_location, int) else row_location
        )
        column_location = (
            column_location - 1 if isinstance(column_location, int) else column_location
        )
        command = f"e e_vw_enable_{rows}_{columns}_{row_location}_{column_location}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_v1")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_v2(self, x_top, y_top, x_bot, y_bot) -> dict:
        """
        Set video wall configuration version 2.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_v2",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_enable_{x_top}_{y_top}_{x_bot}_{y_bot}_2"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_v2")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_vshift(self, direction, value) -> dict:
        """
        Set video wall vertical shift.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_vshift",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_vshift_{direction}_{value}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_vshift")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_hshift(self, direction, value) -> dict:
        """
        Set video wall horizontal shift.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_hshift",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_hshift_{direction}_{value}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_hshift")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_hscale(self, value) -> dict:
        """
        Set video wall horizontal scale.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_hscale",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_hscale_{value}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_hscale")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_vscale(self, value) -> dict:
        """
        Set video wall vertical scale.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_vscale",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_vscale_{value}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_vscale")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def set_video_wall_delay_kick(self, value) -> dict:
        """
        Set video wall delay kick.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_video_wall_delay_kick",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"e e_vw_delay_kick_{value}"
        if self.debug:
            response, debug_info = self.send(command, "set_video_wall_delay_kick")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def cec_onetouch_play(self) -> dict:
        """
        Send CEC one touch play command.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "cec_onetouch_play",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = "e e_cec_one_touch_play"
        if self.debug:
            response, debug_info = self.send(command, "cec_onetouch_play")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def cec_standby(self) -> dict:
        """
        Send CEC standby command.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "cec_standby",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = "e e_cec_system_standby"
        if self.debug:
            response, debug_info = self.send(command, "cec_standby")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result

    def disable_hdmi_out(self, value) -> dict:
        """
        Disable the HDMI out of the device.
        Returns a dictionary containing the operation status.
        """
        if self.device_type != "decoder":
            if self.debug:
                return {
                    "status": "error",
                    "message": "This command is only available for decoders",
                    "function": "set_hdmi_out",
                    "command": "",
                    "response": "",
                }
            return {
                "status": "error",
                "message": "This command is only available for decoders",
            }
        command = f"echo {value} > /sys/devices/platform/display/screen_off"
        if self.debug:
            response, debug_info = self.send(command, "set_hdmi_out")
        else:
            response = self.send(command)

        status = "success" if not response.startswith("Failed") else "error"
        result = {"status": status, "message": response}
        if self.debug:
            result.update(debug_info)
        return result


if __name__ == "__main__":
    device_ip = "10.0.30.31"
    device = IP5100_Device(device_ip, debug=True)
    print(device, "\n")
    device.cec_standby()
