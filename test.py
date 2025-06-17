from IP5100.ip5100 import IP5100_Device

device_ip = "192.168.50.138"
device = IP5100_Device(device_ip, debug=True)
print(device, "\n")
