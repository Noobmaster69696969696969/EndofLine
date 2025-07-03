import json
import time
import RPi.GPIO as GPIO
import can
import board
import busio
from PyQt5.QtCore import QObject, pyqtSignal
import threading
from collections import deque
from dac_controller import DACController
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_ads1x15.ads1115 as ADS
from PyQt5.QtCore import QEventLoop, QTimer

def non_blocking_sleep(seconds):
    loop = QEventLoop()
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    loop.exec_()

class CANTestRunner(QObject):

    sweep_step_signal = pyqtSignal(str, float, float, float)  # signal_name, raw_applied, can_feedback, adc_voltage



    tests_completed = pyqtSignal(list)  # Signal to emit when all tests are completed

    RELAY_GPIO_MAP = {
        "Key Switch": 17,
        "Reverse": 27,
        "Boost": 22,
        "Forward": 23
    }

    # GPIO pins for MUX select lines (adjust these to your actual wiring)
    # Assuming S0 is LSB, S1 is middle, S2 is MSB
    MUX_SELECT_PINS = [5, 6, 26] # Example GPIO pins: S0 (GPIO5), S1 (GPIO6), S2 (GPIO13)
    
    # New: Single CAN ID for all relay feedback
    RELAY_FEEDBACK_CAN_ID = 0x30 # Using 0x30 (decimal 48) as the common CAN ID for relay feedback

    def __init__(self, relay_controller, dac_controllers=None, can_bus=None, config_file='parameters.json'):
        super().__init__()   # Initialize QObject(standard practice to properly initialize paarent class)
        self.relay = relay_controller
        self.dac = dac_controllers[0] if dac_controllers else None # Expect a list with a single DAC

       # Safe ADC Initialization
        self.ads = None
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            self.ads = ADS.ADS1115(i2c, address=0x48)
            self.ads.gain = 2/3  # Accepts 0–4.096V input
            print("[ADC] ✅ ADS1115 detected and initialized.")
        except ValueError as e:
            print(f"[ADC] ❌ ADS1115 not detected at 0x48: {e}")
        except Exception as e:
            print(f"[ADC] ❌ Unexpected error initializing ADS1115: {e}")

        # Store the CAN bus reference
        self.can_bus = can_bus

        print(f"[DEBUG] DAC controller provided: {hex(self.dac.address) if self.dac else 'None'}")
        print(f"[DEBUG] CANTestRunner received CAN bus: {self.can_bus}")
        # Initialize the single DAC (set to 0V)
        if self.dac:
            try:
                print(f"[CANTestRunner] Initializing DAC {hex(self.dac.address)} to 0V...")
                self.dac.write_voltage(0.0)
            except Exception as e:
                print(f"[CANTestRunner] ⚠️ DAC {hex(self.dac.address)} initialization failed: {e}")

        try:
            GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
        except ValueError:
            pass

        # Setup Relay GPIOs
        for pin in self.RELAY_GPIO_MAP.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH) # Ensure relays are off initially

        # Setup MUX GPIOs
        for pin in self.MUX_SELECT_PINS:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW) # Set all MUX select lines to LOW (channel 0) initially
        time.sleep(0.05) # Small delay for GPIO to settle

        with open(config_file, 'r') as f:  # Load the JSON configuration file
            self.params = json.load(f)    # Load parameters from JSON file

        # Mapping from signal names to MUX channels
        self.dac_map = {}
        for signal in self.params['signals']:
            if signal.get('category') == 'analog':
                mux_channel = signal.get('mux_channel')
                if mux_channel is not None:
                    self.dac_map[signal['name']] = mux_channel
                    print(f"[Init] Mapping {signal['name']} → MUX Channel {mux_channel}")
                else:
                    print(f"[Init] ⚠️ Analog signal '{signal['name']}' missing 'mux_channel' in config.")

        # START CAN LISTENER ONLY if bus was provided

        self.can_messages = deque(maxlen=100)  # Using deque for efficient message storage
        self.can_msg_lock = threading.Lock()   # Lock for thread-safe access to CAN messages


        if self.can_bus:
            self._start_can_listener()
        else:
            print("[CANTestRunner] ❌ No CAN bus passed into CANTestRunner. CAN listener will not start.")

        # Flatten test list from config
        self.tests = []   # List to store all tests from the configuration file
        for signal in self.params['signals']:
            for test in signal.get('tests', []):
                self.tests.append({
                    "Signal": signal['name'],
                    "Category": signal['category'],
                    "test_name": test['test_name'],
                    "method": test['method'],
                    "config": test['config']
                })
        self._stop_requested = False
    

    def request_stop(self):
        print("[CANTestRunner] Stop requested by thread.")
        self._stop_requested = True

    def read_reference_voltage(self):
        if self.ads is None:
            print("[ADC] ❌ Cannot read reference voltage: ADS1115 not initialized.")
            return None

        try: 
            chan = AnalogIn(self.ads, ADS.P0)
            voltage = chan.voltage*2.0052
            print(f"[ADC] 📏 IPC Reference Voltage (P0): {voltage:.5f} V")
            return voltage
        except Exception as e:
            print(f"[ADC] ❌ Error reading reference voltage: {e}")
            return None


    def _start_can_listener(self):
        def listener():
            while True:
                try:
                    if self.can_bus:
                        # Listen for any message, then filter for relay feedback ID or analog feedback ID in processing
                        msg = self.can_bus.recv(timeout=1.0)
                        if msg:
                            with self.can_msg_lock:
                                # Append to the left (newest at right)
                                self.can_messages.append(msg)
                                # print(f"[Listener] Buffered CAN message: ID=0x{msg.arbitration_id:X}, Data={msg.data.hex()}") # Debugging
                except can.CanError as e:
                    print(f"[CANTestRunner] CAN error in listener: {e}")
                    break # Exit thread on CAN error
                except Exception as e:
                    if hasattr(e, 'errno') and e.errno == 19:   # USB error 19 indicates device not found
                        print("⚠️ CANalyst-II was disconnected (USB errno 19). Listener stopping.")
                    else:
                        print(f"[CANTestRunner] CAN listener error: {e}")
                    # Don't set self.can_bus to None here, let the main thread handle reconnection
                    break

        # Check if listener thread is already running
        if not hasattr(self, 'listener_thread') or not self.listener_thread.is_alive():
            print("[CANTestRunner] Starting CAN listener thread...")
            self.listener_thread = threading.Thread(target=listener, daemon=True)   # Create a daemon thread for the CAN listener
            self.listener_thread.start()
        else:
            print("[CANTestRunner] CAN listener thread already running.")

    def cleanup(self):
        for pin in self.RELAY_GPIO_MAP.values():
            GPIO.output(pin, GPIO.HIGH) # Ensure relays are off
        # Ensure MUX pins are also reset
        for pin in self.MUX_SELECT_PINS:
            GPIO.output(pin, GPIO.LOW)
        GPIO.cleanup() # Clean up GPIOs only once at the very end of application shutdown

    def _read_can_feedback(self, expected_can_id, timeout):
        """
        Waits for a NEW CAN message with the given ID within timeout.
        Compares against current newest in deque and waits for a fresher one.
        """
        if not self.can_bus:
            print("[CANTestRunner] CAN bus not initialized for feedback.")
            return None

        start_time = time.time()
        initial_last = None

        # Snapshot last known message with same ID (if any)
        with self.can_msg_lock:
            for msg in reversed(self.can_messages):
                if msg.arbitration_id == expected_can_id:
                    initial_last = msg
                    break

        while time.time() - start_time < timeout:
            with self.can_msg_lock:
                for msg in reversed(self.can_messages):
                    if msg.arbitration_id == expected_can_id:
                        # Found a message, check if it's NEW
                        if initial_last is None or msg.timestamp > initial_last.timestamp:
                            return msg
            time.sleep(0.01)

        print(f"[DEBUG] No new message for ID {hex(expected_can_id)} within timeout")
        return None


    def _set_mux_channel(self, channel_id):
        """Sets the MUX select pins for the given channel ID (0-7)."""
        if not (0 <= channel_id <= 7):
            print(f"[MUX Control] Invalid MUX channel ID: {channel_id}. Must be 0-7.")
            return False

        # Iterate through pins, setting them based on the binary representation of channel_id
        # MUX_SELECT_PINS[0] = S0 (LSB), MUX_SELECT_PINS[1] = S1, MUX_SELECT_PINS[2] = S2 (MSB)
        for i, pin in enumerate(self.MUX_SELECT_PINS):
            state = (channel_id >> i) & 1 # Get the i-th bit
            GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
        non_blocking_sleep(0.01) # Small delay for MUX to settle
        print(f"[MUX Control] Set MUX to channel {channel_id}")
        return True

    def _run_dac_voltage_sweep_test(self, signal_name, config, dac, mux_channel, step_mv=100, delay=0.2):
        """Sweeps DAC from 0V to max voltage and compares CAN & ADC feedback (all in volts)."""
        if not dac:
            print("[Sweep Test] ❌ DAC not initialized.")
            return False, [], "DAC not initialized"

        if not self._set_mux_channel(mux_channel):
            return False, [], f"Failed to set MUX to channel {mux_channel}"

        # CAN feedback config
        can_fb = config.get("can_feedback", {})
        can_id = can_fb.get("can_id")
        data_index = can_fb.get("data_index", 0)
        byte_length = can_fb.get("byte_length", 2)
        tolerance_volt = config.get("tolerance_volt", 0.1)  # voltage tolerance

        if isinstance(can_id, str) and can_id.startswith("0x"):
            can_id = int(can_id, 16)

        results = []
        print(f"[Sweep Test] 🚦 Starting DAC voltage sweep for '{signal_name}' on MUX channel {mux_channel}...")

        # Voltage sweep loop
        voltages = [round(v, 3) for v in self._frange(0.0, dac.max_voltage, step_mv / 1000.0)]

        for voltage in voltages:
            if self._stop_requested:
                print(f"[Sweep Test] ⏹ Aborted sweep for '{signal_name}' due to stop request.")
                break

            raw_value = int((voltage / dac.max_voltage) * 4095)
            print(f"[DAC WRITE] {voltage:.3f}V → DAC (raw: {raw_value}) on MUX channel {mux_channel}")
            dac.write_voltage(voltage)
            non_blocking_sleep(delay)

            # ADC feedback (read voltage)
            adc_voltage = None
            if hasattr(self, 'ads'):
                try:
                    adc_channel_str = config.get("adc_channel", "P0")
                    adc_pin = getattr(ADS, adc_channel_str)
                    analog_channel = AnalogIn(self.ads, adc_pin)
                    adc_voltage = analog_channel.voltage
                    print(f"[ADC FEEDBACK] {signal_name} on {adc_channel_str}: {adc_voltage:.3f}V")
                except Exception as e:
                    print(f"⚠️ ADC read error for {signal_name}: {e}")

            # CAN feedback (convert bits → voltage)
            can_voltage = None
            msg = self._read_can_feedback(can_id, timeout=0.3)
            if msg:
                try:
                    data = msg.data
                    raw = None
                    if byte_length == 2:
                        raw = (data[data_index] << 8) | data[data_index + 1]
                    elif byte_length == 1:
                        raw = data[data_index]
                    if raw is not None:
                        can_voltage = round((raw / 4095.0) * dac.max_voltage, 3)
                        print(f"[CAN FEEDBACK] raw: {raw} → {can_voltage:.3f}V")
                except Exception as e:
                    print(f"[Sweep Test] ❌ CAN decode error: {e}")

            # 🔴 Emit sweep step signal (all in volts)
            self.sweep_step_signal.emit(
                signal_name,
                float(voltage),
                float(can_voltage if can_voltage is not None else -1),
                float(adc_voltage if adc_voltage is not None else -1)
            )

            results.append((voltage, can_voltage, adc_voltage))

        # Final pass/fail logic (CAN feedback only)
        if all(r[1] is None for r in results):
            print("[Sweep Test] ❌ No valid CAN feedback received.")
            all_passed = False
        else:
            all_passed = all(
                (can_v is not None and abs(voltage - can_v) <= tolerance_volt)
                for voltage, can_v, _ in results
            )

        return all_passed, results, None


    def _frange(self, start, stop, step):
        """Floating point range generator."""
        while start <= stop:
            yield round(start, 4)
            start += step



    def run_tests(self):   # Runs all tests defined in the JSON configuration file.
        results = [] # EMPTY LIST TO STORE RESULTS
        # Ensure all relays are OFF initially
        for pin in self.RELAY_GPIO_MAP.values():
            GPIO.output(pin, GPIO.HIGH)
        # Ensure MUX is on a safe default channel (e.g., 0)
        self._set_mux_channel(0)
        non_blocking_sleep(1.0)  # Wait for system to stabilize

        print("\n[CANTestRunner] Starting tests sequence...")

        # Removed the initial pre-fetch of relay_feedback_msg.
        # Each relay test will now explicitly poll for the latest message AFTER the relay state change.

        for signal in self.params['signals']: # Iterates through each signal in the loaded parameters

            if self._stop_requested:
                print("[CANTestRunner] ⏹ Test run aborted by user.")
                break
            name = signal['name']
            category = signal['category']
            test_defs = signal.get('tests', [])  # For each signal, iterates through its tests

            print(f"\n[CANTestRunner] Testing {name}...")

            signal_result = {
                "name": name,
                "category": category,
                "tests": [],
                "status": "PASS"
            }

            is_relay = name in self.RELAY_GPIO_MAP  # Checks if the signal is a relay

            for test in test_defs:  # Iterates through each test definition for the current signal

                if self._stop_requested:
                    print(f"[CANTestRunner] ⏹ Skipping remaining tests for '{name}'.")
                    break
                test_name = test['test_name']
                method = test['method']
                config = test['config']
                passed = False
                value = None

                if is_relay and method == 'digital_write':   # If the signal is a relay and the method is digital_write
                    pin = self.RELAY_GPIO_MAP[name]   # Gets the GPIO pin for the relay

                    print(f"[CANTestRunner] Activating {name} (GPIO {pin}) - Setting LOW")

                    # Turn relay ON (set to LOW)
                    GPIO.output(pin, GPIO.LOW)
                    non_blocking_sleep(0.1)  # slight debounce before reading/feedback

                    # Get CAN feedback config
                    can_fb = config.get('can_feedback', {})
                    # For relays, we now use the common RELAY_FEEDBACK_CAN_ID
                    can_id = self.RELAY_FEEDBACK_CAN_ID
                    data_index = can_fb.get('data_index', 0)
                    expected_data = can_fb.get('expected_data_bytes', [])

                    # We expect the ECU to send the updated CAN message after relay state changes.
                    # Poll for the latest message with the common ID.
                    # This call will wait for a new message to appear after the relay state change.
                    msg = self._read_can_feedback(can_id, timeout=0.5) # Increased timeout slightly for feedback

                    # Turn relay OFF (set to HIGH) after checking (important to reset for next test)
                    GPIO.output(pin, GPIO.HIGH)
                    non_blocking_sleep(0.1) # Debounce after turning off

                    if msg:
                        print(f"[CANTestRunner] Received feedback - ID: {hex(msg.arbitration_id)}, Data: {[hex(x) for x in msg.data]}")
                        try:
                            # Check the specific byte for this relay
                            received_value = msg.data[data_index]
                            expected_value = expected_data[0] # Assuming expected_data_bytes will always have one element for digital
                            passed = received_value == expected_value
                            value = received_value
                            print(f"[CANTestRunner] Test result: {'PASS' if passed else 'FAIL'} "
                                f"(Received: {hex(received_value)}, Expected: {hex(expected_value)} at byte {data_index})")
                        except IndexError:
                            print(f"[CANTestRunner] Data index {data_index} out of range for received CAN data. Message length: {len(msg.data)}")
                            passed = False
                            value = None
                        except Exception as e:
                            print(f"[CANTestRunner] Error processing relay CAN feedback: {e}")
                            passed = False
                            value = None
                    else:
                        print(f"[CANTestRunner] No relevant CAN feedback received for {name} with ID {hex(can_id)} after toggling.")
                        passed = False
                        value = None

                    signal_result["tests"].append({
                        "test_name": test_name,
                        "value": value,
                        "passed": passed
                    })
                    if not passed:
                        signal_result["status"] = "FAIL"

                # Analog signal test (e.g., Throttle, Temp) using single DAC and MUX
                elif category == "analog" and method == "analog_output" and self.dac:
                    print(f"[CANTestRunner] Running analog sweep for {name}...")

                    mux_channel = self.dac_map.get(name) # Get the MUX channel for this signal
                    if mux_channel is None:
                        print(f"[CANTestRunner] ⚠️ Analog signal '{name}' missing 'mux_channel' in config or not mapped.")
                        signal_result["status"] = "FAIL"
                        signal_result["tests"].append({
                            "test_name": test_name,
                            "value": None,
                            "passed": False,
                            "sweep_results": [],
                            "error": "MUX channel not defined for signal"
                        })
                        continue

                    # Run sweep test, passing the single DAC and the MUX channel
                    passed, sweep_data, error = self._run_dac_voltage_sweep_test(name, config, self.dac, mux_channel)

                    # Last received value for quick summary (can also be None)
                    value = sweep_data[-1][1] if sweep_data else None

                    if not passed:
                        signal_result["status"] = "FAIL"

                    signal_result["tests"].append({
                        "test_name": test_name,
                        "value": value,
                        "passed": passed,
                        "sweep_results": sweep_data,
                        "error": error # Include error from sweep test
                    })


            results.append(signal_result)
            non_blocking_sleep(0.5)  # Delay between testing different signals

        # Ensure all relays are OFF and MUX is reset after testing
        for pin in self.RELAY_GPIO_MAP.values():
            GPIO.output(pin, GPIO.HIGH)
        self._set_mux_channel(0) # Reset MUX to channel 0

        # Ensure DAC is at a safe 0V state after all tests
        if self.dac:
            try:
                self.dac.write_voltage(0.0)
                print("[CANTestRunner] DAC reset to 0V after all tests.")
            except Exception as e:
                print(f"[CANTestRunner] ⚠️ Failed to reset DAC to 0V: {e}")

        print("\n[CANTestRunner] All tests completed.")
        self.tests_completed.emit(results)
        return results

    def shutdown(self):
        if self.can_bus:
            try:
                self.can_bus.shutdown()
                print("[CANTestRunner] CAN bus shut down cleanly.")
            except Exception as e:
                print(f"[CANTestRunner] Error shutting down CAN bus: {e}")
            self.can_bus = None
        # Clean up GPIOs on shutdown
        self.cleanup()