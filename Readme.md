# 🧪 EOL Testing App

This is a **PyQt5-based End-of-Line (EOL) Testing Application** built for Raspberry Pi 5.  
It performs both **digital (relay)** and **analog (DAC/MUX/ADC)** signal tests with CAN feedback from an IPC.

---

## 📁 Project Structure

eol_testingapp/
├── main.py # Entry point to launch the app
├── can_test_ui.py # PyQt5-based GUI implementation
├── test_runner.py # Core test execution logic
├── dac_controller.py # I2C DAC control for analog signal generation
├── parameters.json # Configuration for all signal tests
├── ergon.jpg # Logo used in UI
├── .gitignore # Ignore unnecessary files in Git
└── requirements.txt # Python dependencies (generated via pip freeze)
---

## 🚀 Features

- ✅ GPIO Relay Control
- ✅ Analog Voltage Sweeps via DAC
- ✅ CAN Feedback Validation (CANalyst-II supported)
- ✅ ADS1115 ADC Logging
- ✅ Auto-generated Test UI from JSON
- ✅ Result Summary and Export

---

## 🛠 Setup Instructions (for developers)

```bash
git clone https://github.com/Noobmaster69696969696969/EndofLine.git
cd EndofLine

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python3 main.py


