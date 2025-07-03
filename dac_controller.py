from smbus2 import SMBus
import time  # unused here but sometimes used for delays
from threading import Lock  # Ensures thread-safe access to I2C (important if multiple threads write to DAC).

class DACController: # Class to control a DAC via I2C 
    def __init__(self, address, max_voltage=5.0, bus_id=1): 
        self.address = address
        self.max_voltage = max_voltage
        self.bus_id = bus_id # I2C bus ID (1 for Raspberry Pi)
        self.lock = Lock()   # Lock for thread-safe access to the DAC

    def write_voltage(self, voltage):
        if voltage < 0 or voltage > self.max_voltage:
            raise ValueError(f"Voltage must be between 0 and {self.max_voltage}V")

        value = int((voltage / self.max_voltage) * 4095)
        high_byte = (value >> 4) & 0xFF # contains the upper 8 bits (MSBs).
        low_byte = (value << 4) & 0xFF  # contains the lower 4 bits, shifted to left to fit 8-bit 

        print(f"Setting DAC to {voltage:.2f}V (value={value}, bytes={high_byte:#04x} {low_byte:#04x})")

        with self.lock:
            try:
                with SMBus(self.bus_id) as bus:
                    bus.write_i2c_block_data(self.address, 0x40, [high_byte, low_byte])  # 0x40 is the command byte for MCP4725
                    print("✅ DAC voltage written")
            except Exception as e:
                print("⚠️ DAC write failed:", e)
