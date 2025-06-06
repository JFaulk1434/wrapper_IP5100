import unittest
from IP5100.ip5100 import IP5100_Device
from IP5100.aspeed import search_nodes
import time


class TestIP5100Functions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test devices before running tests."""
        print("\nDiscovering devices...")
        devices = search_nodes()
        cls.devices = []

        # Create a single log file for all devices
        log_file = "test_ip5100.log"

        for device in devices:
            if device["MODEL"].startswith("IPD51") or device["MODEL"].startswith(
                "IPE51"
            ):
                print(f"Found {device['MODEL']} at {device['ADDRESS']}")
                ip5100 = IP5100_Device(
                    device["ADDRESS"],
                    debug=True,
                    log_file=log_file,  # Use the same log file for all devices
                )
                cls.devices.append(ip5100)

    def setUp(self):
        """Ensure devices are connected before each test."""
        for device in self.devices:
            if not device.connected:
                device.connect().result()

    def tearDown(self):
        """Clean up after each test."""
        for device in self.devices:
            if device.connected:
                device.disconnect().result()

    @classmethod
    def tearDownClass(cls):
        """Clean up all devices after all tests."""
        for device in cls.devices:
            if device.connected:
                device.disconnect().result()

    def test_01_basic_info(self):
        """Test basic device information retrieval."""
        print("\nTesting basic device information...")
        for device in self.devices:
            # Test model and version
            self.assertIsNotNone(device.model)
            self.assertIsNotNone(device.mac)

            # Test version retrieval
            version_info = device.get_version().result()
            self.assertIsNotNone(version_info)
            self.assertIn("version", version_info)

            # Test alias retrieval
            alias_info = device.get_alias().result()
            self.assertIsNotNone(alias_info)
            self.assertIn("alias", alias_info)

            # Test IP settings
            ip_mode = device.get_ip_mode().result()
            self.assertIsNotNone(ip_mode)
            self.assertIn("ip_mode", ip_mode)

            if ip_mode["ip_mode"] == "static":
                subnet = device.get_subnet_mask().result()
                self.assertIsNotNone(subnet)
                self.assertIn("netmask", subnet)

                gateway = device.get_gateway_ip().result()
                self.assertIsNotNone(gateway)
                self.assertIn("gateway_ip", gateway)

    def test_02_encoder_specific(self):
        """Test encoder-specific functions."""
        print("\nTesting encoder-specific functions...")
        for device in self.devices:
            if device.device_type == "encoder":
                # Test audio input info
                audio_info = device.get_audio_input_info().result()
                self.assertIsNotNone(audio_info)
                self.assertIn("audio_input", audio_info)

                # Test video input info
                video_info = device.get_video_input_info().result()
                self.assertIsNotNone(video_info)
                self.assertIn("video_input", video_info)

    def test_03_decoder_specific(self):
        """Test decoder-specific functions."""
        print("\nTesting decoder-specific functions...")
        for device in self.devices:
            if device.device_type == "decoder":
                # Test audio output info
                audio_info = device.get_audio_output_info().result()
                self.assertIsNotNone(audio_info)
                self.assertIn("audio_output", audio_info)

                # Test video output info
                video_info = device.get_video_output_info().result()
                self.assertIsNotNone(video_info)
                self.assertIn("video_output", video_info)

    def test_04_video_wall(self):
        """Test video wall functions."""
        print("\nTesting video wall functions...")
        for device in self.devices:
            if device.device_type == "decoder":
                # Test video wall disable
                result = device.set_vwall_disable().result()
                self.assertIsNotNone(result)
                self.assertIn("status", result)

                # Test video wall rotate
                result = device.set_vwall_rotate("0").result()
                self.assertIsNotNone(result)
                self.assertIn("status", result)

    def test_05_serial_operations(self):
        """Test serial port operations."""
        print("\nTesting serial port operations...")
        for device in self.devices:
            # Test serial enable
            result = device.set_serial_enabled(True).result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

            # Test serial baudrate
            result = device.set_serial_baudrate().result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

    def test_06_hdcp_operations(self):
        """Test HDCP operations."""
        print("\nTesting HDCP operations...")
        for device in self.devices:
            # Test HDCP 1.4
            result = device.set_hdcp_1_4("0").result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

            # Test HDCP 2.2
            result = device.set_hdcp_2_2("0").result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

    def test_07_cec_operations(self):
        """Test CEC operations."""
        print("\nTesting CEC operations...")
        for device in self.devices:
            # Test CEC enable
            result = device.set_cec_enable(True).result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

            # Test CEC standby
            result = device.cec_standby().result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

    def test_08_system_operations(self):
        """Test system operations."""
        print("\nTesting system operations...")
        for device in self.devices:
            # Test dump
            result = device.dump().result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

            # Test save
            result = device.save().result()
            self.assertIsNotNone(result)
            self.assertIn("status", result)

    def test_09_performance(self):
        """Test performance of parallel operations."""
        print("\nTesting performance of parallel operations...")

        # Sequential operations
        start_time = time.time()
        versions_seq = [device.get_version().result() for device in self.devices]
        seq_time = time.time() - start_time

        # Parallel operations
        start_time = time.time()
        futures = [device.get_version() for device in self.devices]
        versions_par = [future.result() for future in futures]
        par_time = time.time() - start_time

        # Compare results
        self.assertEqual(len(versions_seq), len(versions_par))
        print(f"\nSequential time: {seq_time:.2f}s")
        print(f"Parallel time: {par_time:.2f}s")
        print(f"Speedup: {seq_time / par_time:.2f}x")


if __name__ == "__main__":
    unittest.main(verbosity=2)
