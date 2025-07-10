# 🧪 End-of-Line (EOL) Testing Application

A robust, extensible, and user-friendly **PyQt5-based End-of-Line (EOL) Testing Application** for Raspberry Pi 5.  
It automates both **digital (relay)** and **analog (DAC/MUX/ADC)** signal tests, validating results via CAN bus feedback from an IPC/ECU.

---

## 📂 Project Structure

```
.
├── main.py               # Entry point: launches the GUI and manages screens
├── can_test_ui.py        # Main PyQt5 GUI, test orchestration, and user interaction
├── test_runner.py        # Core test logic: runs digital/analog tests, CAN/ADC feedback, MUX/DAC control
├── dac_controller.py     # I2C DAC (MCP4725) control for analog signal generation
├── parameters.json       # All test definitions and signal configuration (digital/analog)
├── requirements.txt      # All Python dependencies (for pip)
├── ergon.jpg             # Logo/background for the UI
├── test_relay.py         # (Example) Standalone relay GPIO test (commented)
├── test_can.py           # (Example) Standalone CAN bus test (commented)
├── read_socketcan.py     # (Example) CAN frame reader (commented)
└── .gitignore            # Git ignore rules
```

---

## 🖥️ Application Overview

- **Graphical User Interface:**  
  Built with PyQt5, featuring a modern, responsive UI for test control, live plotting, and result review.

- **Digital (Relay) Testing:**  
  Controls relays via GPIO, verifies state via CAN feedback.

- **Analog Testing:**  
  Uses a DAC (MCP4725) and analog multiplexer (MUX) to sweep voltages, reads feedback via CAN and ADC (ADS1115).

- **Live Plotting:**  
  Real-time voltage sweep plots for analog signals.

- **Configurable Tests:**  
  All test logic, signal names, and parameters are defined in `parameters.json`—no code changes needed to add new signals/tests.

- **Result Export:**  
  Save test results as text or CSV.

---

## ⚙️ Setup & Installation

### 1. Hardware Requirements

- **Raspberry Pi 5** (or compatible Pi with I2C, GPIO, CAN)
- **MCP4725 DAC** (I2C, for analog output)
- **ADS1115 ADC** (I2C, for analog feedback)
- **CANalyst-II** or **SocketCAN** compatible CAN interface
- **Relays** connected to GPIO pins (see below)
- **Wiring:**  
  - Relays: GPIO17, GPIO27, GPIO22, GPIO23 (default, configurable)
  - MUX select: GPIO5, GPIO6, GPIO26 (default, configurable)

### 2. Software Setup

```bash
git clone <your-repo-url>
cd EndOfLine-Testing

# (Recommended) Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Run the application
python3 main.py
```

---

## 🧩 Configuration: `parameters.json`

All test signals and their logic are defined in `parameters.json`.  
**Example structure:**

```json
{
  "signals": [
    {
      "name": "Key Switch",
      "category": "digital",
      "tests": [
        {
          "test_name": "on_off_test",
          "method": "digital_write",
          "config": {
            "can_feedback": {
              "can_id": 48,
              "expected_data_bytes": [1],
              "data_index": 0
            }
          }
        }
      ]
    },
    {
      "name": "Analog Signal 1",
      "category": "analog",
      "mux_channel": 0,
      "tests": [
        {
          "test_name": "voltage_check",
          "method": "analog_output",
          "config": {
            "output_voltage": 2.0,
            "adc_channel": "P3",
            "can_feedback": {
              "can_id": 56,
              "data_index": 0,
              "byte_length": 2,
              "max_raw": 4095
            }
          }
        }
      ]
    }
  ]
}
```

- **Digital signals:**  
  - `method`: `"digital_write"`
  - `can_feedback`: CAN ID, expected data, and byte index for relay state feedback

- **Analog signals:**  
  - `mux_channel`: MUX channel for the signal
  - `method`: `"analog_output"`
  - `adc_channel`: ADC pin (e.g., `"P3"`)
  - `can_feedback`: CAN ID, data index, byte length, and max raw value

**To add a new signal:**  
Add a new object to the `signals` array with the appropriate fields.

---

## 🖱️ Usage Guide

1. **Launch the App:**  
   `python3 main.py`

2. **Welcome Screen:**  
   Click "Get Started" to enter the main test UI.

3. **Main UI Features:**
   - **Run Tests:**  
     Click "Run Tests" to execute all configured tests.  
     Live logs and plots will appear.
   - **Relay Control:**  
     Manual relay ON/OFF control for diagnostics.
   - **Export Report:**  
     Save results after tests complete.
   - **Status Indicators:**  
     CAN connection and reference voltage are shown live.

4. **Test Results:**  
   - Double-click any result for detailed feedback, including sweep plots for analog signals.

---

## 🛠️ Code Architecture

- **main.py:**  
  - Launches the PyQt5 app, manages welcome and main screens.

- **can_test_ui.py:**  
  - Main GUI logic:  
    - Handles user actions, test thread management, live plotting, relay controls, and result export.
    - Monitors CAN bus status and reference voltage.
    - Integrates with `CANTestRunner` for test execution.

- **test_runner.py:**  
  - Core test logic:  
    - Loads test definitions from `parameters.json`.
    - Controls relays, DAC, MUX, and reads ADC.
    - Listens for CAN feedback, validates results.
    - Emits signals for live plotting and UI updates.

- **dac_controller.py:**  
  - Simple class for controlling MCP4725 DAC via I2C.

- **parameters.json:**  
  - All test definitions and signal configuration.

- **test_relay.py, test_can.py, read_socketcan.py:**  
  - Example scripts for standalone hardware/CAN testing (commented out).

---

## 🧑‍💻 Extending the App

- **Add new signals/tests:**  
  Edit `parameters.json`—no code changes needed for most new signals.

- **Change relay/MUX pin mapping:**  
  Update the relevant dictionaries in `can_test_ui.py` and `test_runner.py`.

- **Support new hardware:**  
  - Add new controller classes (e.g., for different DAC/ADC chips).
  - Update test logic in `test_runner.py` as needed.

---

## 🐞 Troubleshooting

- **CAN bus not detected:**  
  - Ensure your CANalyst-II or SocketCAN device is connected and drivers are installed.
  - Check wiring and power.

- **I2C errors:**  
  - Ensure correct wiring for DAC/ADC.
  - Use `i2cdetect -y 1` to verify device addresses.

- **GPIO errors:**  
  - Run as root if needed (`sudo python3 main.py`).
  - Check pin numbers and wiring.

---

## 📜 License

(C) 2025 Ergon Mobility. All rights reserved.

---

## 🙏 Acknowledgements

- [PyQt5](https://riverbankcomputing.com/software/pyqt/intro)
- [python-can](https://python-can.readthedocs.io/)
- [Adafruit CircuitPython](https://circuitpython.org/)
- [RPi.GPIO](https://pypi.org/project/RPi.GPIO/)
- [MCP4725 DAC](https://www.adafruit.com/product/935)
- [ADS1115 ADC](https://www.adafruit.com/product/1085)

---

**For questions or contributions, please open an issue or pull request.**

---

