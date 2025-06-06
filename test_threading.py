import time
from IP5100.ip5100 import IP5100_Device
from concurrent.futures import wait, FIRST_COMPLETED, as_completed
from IP5100.aspeed import search_nodes


def test_threading():
    # Discover devices
    print("Discovering devices...")
    discovered_devices = search_nodes()

    # Filter for IPD51xx and IPE51xx devices
    filtered_devices = [
        device
        for device in discovered_devices
        if device["MODEL"].startswith(("IPD51", "IPE51"))
    ]

    if not filtered_devices:
        print("No IPD51xx or IPE51xx devices found!")
        return

    print(f"\nFound {len(filtered_devices)} devices:")
    for device in filtered_devices:
        print(f"- {device['MODEL']} at {device['ADDRESS']} ({device['HOSTNAME']})")

    # Create device instances
    devices = [
        IP5100_Device(
            device["ADDRESS"], debug=True, log_file=f"{device['HOSTNAME']}.log"
        )
        for device in filtered_devices
    ]

    try:
        # Test 1: Simultaneous connection
        print("\nTest 1: Testing simultaneous connection...")
        start_time = time.time()
        futures = [device.connect() for device in devices]
        # Wait for all connections to complete
        for future in as_completed(futures):
            result = future.result()
            if not result:
                print(f"Warning: Connection failed for one or more devices")
        end_time = time.time()
        print(f"Connection time: {end_time - start_time:.2f} seconds")

        # Test 2: Get device information
        print("\nTest 2: Getting device information...")
        start_time = time.time()
        futures = []
        for device in devices:
            futures.extend(
                [
                    device.get_version(),
                    device.get_alias(),
                    device.get_ip_mode(),
                    device.get_multicast_ip(),
                    device.get_subnet_mask(),
                    device.get_gateway_ip(),
                ]
            )
        # Wait for all operations to complete
        for future in as_completed(futures):
            result = future.result()
            if isinstance(result, dict) and "version" in result:
                print(f"Device version: {result['version']}")
            elif isinstance(result, dict) and "alias" in result:
                print(f"Device alias: {result['alias']}")
        end_time = time.time()
        print(f"Device info gathering time: {end_time - start_time:.2f} seconds")

        # Test 3: Get status information
        print("\nTest 3: Getting status information...")
        start_time = time.time()
        futures = []
        for device in devices:
            if device.device_type == "encoder":
                futures.extend(
                    [device.get_audio_input_info(), device.get_video_input_info()]
                )
            else:  # decoder
                futures.extend(
                    [device.get_audio_output_info(), device.get_video_output_info()]
                )
        # Wait for all operations to complete
        for future in as_completed(futures):
            result = future.result()
            if isinstance(result, dict) and "State" in result:
                print(f"Device state: {result['State']}")
        end_time = time.time()
        print(f"Status gathering time: {end_time - start_time:.2f} seconds")

        # Test 4: Sequential vs Parallel comparison
        print("\nTest 4: Comparing sequential vs parallel operations...")

        # Sequential
        start_time = time.time()
        for device in devices:
            version = device.get_version().result()
            alias = device.get_alias().result()
            ip_mode = device.get_ip_mode().result()
            if device.device_type == "encoder":
                audio = device.get_audio_input_info().result()
                video = device.get_video_input_info().result()
            else:  # decoder
                audio = device.get_audio_output_info().result()
                video = device.get_video_output_info().result()
            print(f"Device {device.ip} info gathered")
        seq_time = time.time() - start_time
        print(f"Sequential time: {seq_time:.2f} seconds")

        # Parallel
        start_time = time.time()
        futures = []
        for device in devices:
            futures.extend(
                [device.get_version(), device.get_alias(), device.get_ip_mode()]
            )
            if device.device_type == "encoder":
                futures.extend(
                    [device.get_audio_input_info(), device.get_video_input_info()]
                )
            else:  # decoder
                futures.extend(
                    [device.get_audio_output_info(), device.get_video_output_info()]
                )
        # Wait for all operations to complete
        for future in as_completed(futures):
            result = future.result()
            if isinstance(result, dict) and "version" in result:
                print(f"Device version retrieved: {result['version']}")
        par_time = time.time() - start_time
        print(f"Parallel time: {par_time:.2f} seconds")
        print(f"Speedup: {seq_time / par_time:.2f}x")

    finally:
        # Cleanup
        print("\nCleaning up connections...")
        for device in devices:
            try:
                device.disconnect()
            except Exception as e:
                print(f"Error disconnecting device {device.ip}: {e}")


if __name__ == "__main__":
    test_threading()
