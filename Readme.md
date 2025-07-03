# 🧪 EOL Testing App

This is a **PyQt5-based End-of-Line (EOL) Testing Application** built for Raspberry Pi 5.  
It performs both **digital (relay)** and **analog (DAC/MUX/ADC)** signal tests with CAN feedback from an IPC.

---

## 📁 Project Structure

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


