import os
import subprocess
import can
import time
import RPi.GPIO as GPIO

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QLabel, QDialog, QTextEdit, QFileDialog, QMessageBox, QProgressBar
)
from PyQt5.QtGui import QColor, QPainter, QBrush
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
import sys
from PyQt5 import QtGui
from PyQt5.QtWidgets import QPlainTextEdit, QTabWidget
from PyQt5.QtCore import pyqtSlot



from test_runner import CANTestRunner
from dac_controller import DACController
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
# import usb.core

def can0_exists():
    """Check if can0 interface exists in sysfs."""
    return os.path.exists("/sys/class/net/can0")

def bring_up_can0():
    """Attempt to bring up can0 if available."""
    if not can0_exists():
        print("❌ can0 interface not found — skipping bring-up.")
        return
    try:
        subprocess.run(
            ["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "500000"],
            check=True
        )
        print("✅ can0 brought up successfully.")
    except subprocess.CalledProcessError as e:
        print("❌ Failed to bring up can0:", e)

# GPIO Pin Mapping for relays
RELAY_PINS = {
    "Relay 1": 17,
    "Relay 2": 27,
    "Relay 3": 22,
    "Relay 4": 23
}

class RelayController: # Class to control relays via GPIO pins
    def __init__(self, relay_pins):   # Initialization
        self.relay_pins = relay_pins
        for pin in self.relay_pins.values():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)   # Set up each pin as input with pull-up resistor(to avoid floating state)
            time.sleep(0.05)  # Small delay to ensure GPIO setup is stable
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.05)

    def set_relay_state(self, label, state):
        if label in self.relay_pins:
            pin = self.relay_pins[label]
            GPIO.output(pin, GPIO.LOW if state else GPIO.HIGH)   # Set pin LOW for ON, HIGH for OFF
            print(f"[RelayController] Set {label} ({pin}) to {'ON' if state else 'OFF'}")
        else:
            print(f"[RelayController] Unknown relay label: {label}")

    def toggle_relay(self, label, on):
        if label in self.relay_pins:
            GPIO.output(self.relay_pins[label], GPIO.LOW if on else GPIO.HIGH)

    def cleanup(self):
        GPIO.cleanup()

class StatusDot(QLabel):
    def __init__(self):
        super().__init__()
        self._color = Qt.red
        self._visible = True
        self.setFixedSize(14, 14)
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_visibility)
        self.blink_timer.start(500)

    def toggle_visibility(self):
        self._visible = not self._visible
        self.repaint()

    def set_color(self, color):
        self._color = color
        self.repaint()

    def paintEvent(self, event):
        if not self._visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self.width(), self.height())

class LivePlotWidget(QWidget):
    def __init__(self, title="Live Signal Sweep"):
        super().__init__()
        self.fig = Figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title(title)
        self.ax.set_xlabel("DAC Applied Voltage (V)")
        self.ax.set_ylabel("Feedback Voltage (V)")

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.canvas)

        self.applied_vals = []
        self.can_vals = []
        self.adc_vals = []

        # Default lines for Analog 1
        self.line_can, = self.ax.plot([], [], label="Analog 1 CAN FEEDBACK", marker='o')
        self.line_adc, = self.ax.plot([], [], label="ADC Voltage", linestyle='--')

        # Extra lines for Analog 2 in green
        self.analog2_can_line, = self.ax.plot([], [], label="Analog 2 CAN FEEDBACK", color='green', marker='o')
        self.analog2_adc_line, = self.ax.plot([], [], label="ADC Voltage", color='green', linestyle='--')

        self.ax.legend()
        self.ax.grid(True)

    @pyqtSlot(str, float, float, float)
    def update_data(self, signal_name, applied, can_val, adc_val):
        if not self.isVisible():  # avoid updating if window is closed
            return
        self.applied_vals.append(applied)
        self.can_vals.append(can_val if can_val >= 0 else None)
        self.adc_vals.append(adc_val if adc_val >= 0 else None)

        if signal_name.lower() == "analog 2":
            self.analog2_can_line.set_data(self.applied_vals, self.can_vals)
            self.analog2_adc_line.set_data(self.applied_vals, self.adc_vals)
        else:
            self.line_can.set_data(self.applied_vals, self.can_vals)
            self.line_adc.set_data(self.applied_vals, self.adc_vals)

        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

class TestDetailDialog(QDialog):
    def __init__(self, signal_result):
        super().__init__()
        self.setWindowTitle(f"Details - {signal_result['name']}")
        self.resize(600, 500)

        layout = QVBoxLayout(self)

        title = QLabel(f"{signal_result['name']} ({signal_result['category']}) - {signal_result['status']}")
        title.setStyleSheet("font-size:16pt; font-weight:bold;")
        layout.addWidget(title)

        for test in signal_result.get("tests", []):
            test_name = test.get("test_name")
            value = test.get("value")
            passed = test.get("passed")
            sweep = test.get("sweep_results", [])

            summary = QLabel(f"• {test_name} → Value: {value} | Result: {'✅ PASS' if passed else '❌ FAIL'}")
            summary.setStyleSheet("font-weight:bold; margin-top:10px;")
            layout.addWidget(summary)

            if sweep:
                # --- Textual Results ---
                sweep_label = QLabel("  Sweep Results (Applied → Feedback):")
                sweep_label.setStyleSheet("color:#005792; font-style:italic;")
                layout.addWidget(sweep_label)

                sweep_box = QTextEdit()
                sweep_box.setReadOnly(True)
                sweep_box.setStyleSheet("""
                    QTextEdit {
                        background-color: #1e1e1e;
                        color: #cccccc;
                        font-family: Consolas, 'Courier New', monospace;
                        font-size: 12px;
                        border: 1px solid #444;
                        padding: 6px;
                    }
                """)

                lines = []
                for entry in sweep:
                    if isinstance(entry, tuple) and len(entry) == 3:
                        applied, feedback, adc = entry
                        if feedback is None:
                            adc_str = f"{adc}" if adc is not None else "❌"
                            lines.append(f"{applied:.3f} V → CAN: ❌ No Feedback | ADC: {adc_str:.3f} V" if isinstance(adc_str, float) else f"{applied:.3f} V → CAN: ❌ No Feedback | ADC: {adc_str}")

                        else:
                            error = abs(applied - feedback)
                            mark = "✅" if error <= 0.1 else "❌"
                            adc_str = f"{adc}" if adc is not None else "❌"
                            lines.append(f"{applied:.3f} V → CAN: {feedback:.3f} V   (error: {error:.3f}) {mark} | ADC: {adc_str:.3f} V" if isinstance(adc_str, float) else f"{applied:.3f} V → CAN: {feedback:.3f} V   (error: {error:.3f}) {mark} | ADC: {adc_str}")

                    elif isinstance(entry, tuple) and len(entry) == 2:
                        applied, feedback = entry
                        if feedback is None:
                            lines.append(f"{applied:>5} →  ❌ No Feedback")
                        else:
                            error = abs(applied - feedback)
                            mark = "✅" if error <= 0.1 else "❌"
                            lines.append(f"{applied:>5} → {feedback:>5}   (error: {error:>3}) {mark}")

                sweep_box.setText("\n".join(lines))
                layout.addWidget(sweep_box)

                # --- Graph Plotting ---
                fig = Figure(figsize=(6, 3))
                canvas = FigureCanvas(fig)
                ax = fig.add_subplot(111)

                applied = []
                feedback = []

                for entry in sweep:
                    if isinstance(entry, tuple) and len(entry) >= 2:
                        applied.append(entry[0])
                        feedback.append(entry[1] if entry[1] is not None else 0)

                adc_vals = [entry[2] if len(entry) > 2 and entry[2] is not None else 0 for entry in sweep]
                ax.plot(applied, adc_vals, linestyle="-.", color='orange', label="ADC Voltage")



                ax.plot(applied, feedback, label="Received", marker='o')
                ax.plot(applied, applied, linestyle="--", color='gray', label="Ideal")

                ax.set_title("Analog Feedback vs DAC Voltage")
                ax.set_xlabel("Applied Voltage (V)")
                ax.set_ylabel("Feedback Voltage (V)")
                ax.grid(True)
                ax.legend()

                layout.addWidget(canvas)

        # --- Close Button ---
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class TestRunnerThread(QThread):
    test_result_signal = pyqtSignal(dict)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)

    def __init__(self, runner, relay_controller):
        super().__init__()
        self.runner = runner
        self.relay = relay_controller
        self._stop_requested = False
    
    def stop(self):
        print("[Thread] Stop requested by UI.")
        self._stop_requested = True
        if hasattr(self.runner, "request_stop"):
            self.runner.request_stop()

    def run(self):
        try:
            print(f"[DEBUG] TestRunnerThread CAN bus: {self.runner.can_bus}")
            if self.runner.can_bus is None:
                self.error_signal.emit("CAN bus is not initialized. Please check your CANalyst-II interface.")
                return

            self.progress_signal.emit("Starting relay tests...")
            if self._stop_requested:
                self.progress_signal.emit("Tests aborted.")
                return

            results = self.runner.run_tests()

            if self._stop_requested:
                self.progress_signal.emit("Tests aborted by user.")
                return

            for result in results:
                self.test_result_signal.emit(result)
                self.progress_signal.emit(f"Completed test: {result['name']}")
        except Exception as e:
            self.error_signal.emit(f"Test thread error: {e}")
        finally:
            self.progress_signal.emit("Tests completed.")
            self.finished_signal.emit()

    def bring_up_can0():
        try:
            subprocess.run(
                ["sudo", "ip", "link", "set", "can0", "up", "type", "can", "bitrate", "500000"],
                check=True
            )
            print("✅ can0 brought up automatically (bitrate=500000)")
        except subprocess.CalledProcessError as e:
            print("❌ Failed to bring up can0:", e)

class LogDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Logs")
        self.resize(600, 300)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)

        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)
        self.setLayout(layout)

        self.logger = QTextEditLogger(self.text_edit)
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

    def start_logging(self):
        sys.stdout = self.logger
        sys.stderr = self.logger

    def stop_logging(self):
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr



class QTextEditLogger(QObject):
    log_signal = pyqtSignal(str)

    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit
        self.log_signal.connect(self._append_text)

    def write(self, message):
        self.log_signal.emit(str(message))

    def flush(self):
        pass

    def _append_text(self, message):
        self.text_edit.moveCursor(QtGui.QTextCursor.End)
        self.text_edit.insertPlainText(message)
        self.text_edit.ensureCursorVisible()


class CANTestApp(QWidget):
    def __init__(self, can_bus=None):
        super().__init__()
        self.setWindowTitle("CAN Signal Test Runner")
        self.showMaximized()

        self.bus = can_bus
        self.relay = None
        self.dac = None
        self.runner = None
        self.results = []
        self.SENT_ID = 0x123

        # UI setup only — fast and non-blocking
        self.mainLayout = QVBoxLayout(self)
        self._build_header()
        self._build_buttons()
        self._build_progress()
        self._build_results_list()
        self._build_footer()

        # Setup timer to monitor CAN status every 1 second
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._update_can_status)
        self.status_timer.start(1000)

        # Log output area
        # self.log_output = QPlainTextEdit()
        # self.log_output.setReadOnly(True)

        # self.tabs = QTabWidget()
        # self.tabs.addTab(self.log_output, "Logs")
        # self.layout().addWidget(self.tabs)

        # self.log_stream = QTextEditLogger(self.log_output)
        # sys.stdout = self.log_stream
        # sys.stderr = self.log_stream



    def start_initialization(self):
        """Heavy init: DAC, CAN, Runner setup"""
        print("[CANTestApp] Starting full initialization...")

        self.relay = RelayController(RELAY_PINS)

        try:
            self.dac = DACController(address=0x61)
            print("✅ DAC controller initialized")
            dac_list = [self.dac]
        except Exception as e:
            print(f"❌ DAC controller initialization failed: {e}")
            self.dac = None
            dac_list = []

        self._setup_can_bus()
        QTimer.singleShot(2000, self._update_can_status)

        self.runner = CANTestRunner(self.relay, dac_list, can_bus=self.bus)
        print(f"[DEBUG] CANTestApp fully initialized with CAN bus: {self.bus}")
        self._start_can_polling()


    def show_error_message(self, message):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("CAN Bus Error")
        msg_box.setText(message)
        msg_box.exec_()

    def _build_header(self):
        h = QVBoxLayout()

        # Title
        title = QLabel("CAN Signal Test Runner", alignment=Qt.AlignCenter)
        title.setStyleSheet("font-size:24pt;font-weight:bold;color:#003366;")
        h.addWidget(title)

        # CAN Status Row (green dot + label)
        status_h = QHBoxLayout()
        self.statusDot = StatusDot()
        self.statusLabel = QLabel("Checking...", alignment=Qt.AlignLeft)
        self.statusLabel.setStyleSheet("color:orange;font-weight:bold;")
        status_h.addStretch()
        status_h.addWidget(self.statusDot)
        status_h.addSpacing(6)
        status_h.addWidget(self.statusLabel)

        # Add status row
        h.addLayout(status_h)

        # 👇 NEW LINE BELOW STATUS (IPC Ref 5V)
        self.ref_voltage_label = QLabel("Ref 5V ADC Reading: -- V", alignment=Qt.AlignRight)
        self.ref_voltage_label.setStyleSheet("color:red;font-weight:bold;")
        h.addWidget(self.ref_voltage_label)

        # Apply to main layout
        self.mainLayout.addLayout(h)

    def _build_buttons(self):
        h = QHBoxLayout()
        self.runBtn = QPushButton("\u25b6 Run Tests")
        self.exportBtn = QPushButton("\ud83d\udcc4 Export Report")
        self.sendBtn = QPushButton("\ud83d\udea1 Send CAN Frame")
        self.relayBtn = QPushButton("Relay Control")

        for b in (self.runBtn, self.exportBtn, self.sendBtn, self.relayBtn):
            b.setFixedHeight(40)
            if b == self.relayBtn:
                b.setStyleSheet(
                    "background-color:#444;color:white;padding:10px 20px;"
                    "font-weight:bold;border-radius:8px;"
                    "QPushButton:hover{background-color:#666;}"
                )
            else:
                b.setStyleSheet(
                    "background-color:#005792;color:white;padding:10px 20px;"
                    "font-weight:bold;border-radius:8px;"
                    "QPushButton:hover{background-color:#007ab8;}"
                )

        self.runBtn.clicked.connect(self._on_run)
        self.exportBtn.clicked.connect(self._export_report)
        self.relayBtn.clicked.connect(self._show_relay_controls)

        h.addWidget(self.runBtn)
        h.addWidget(self.exportBtn)
        h.addWidget(self.sendBtn)
        h.addWidget(self.relayBtn)
        h.addStretch()
        self.mainLayout.addLayout(h)

    def _show_relay_controls(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Manual Signal Control")
        dlg.resize(400, 300)
        layout = QVBoxLayout(dlg)

        # --- RELAY CONTROLS (existing) ---
        relay_label = QLabel("Relay Controls:")
        relay_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #005792;")
        layout.addWidget(relay_label)

        for label in self.relay.relay_pins.keys():
            row = QHBoxLayout()
            on_btn = QPushButton(f"{label} ON")
            off_btn = QPushButton(f"{label} OFF")
            on_btn.clicked.connect(lambda _, l=label: self.relay.toggle_relay(l, True))
            off_btn.clicked.connect(lambda _, l=label: self.relay.toggle_relay(l, False))

            # Style the relay buttons
            for btn in [on_btn, off_btn]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #005792;
                        color: white;
                        padding: 5px 10px;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #007ab8;
                    }
                """)

            row.addWidget(on_btn)
            row.addWidget(off_btn)
            layout.addLayout(row)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        layout.addWidget(close_btn)

        dlg.exec_()

    def _build_results_list(self):
        self.list = QListWidget()
        self.list.setStyleSheet("font-size:16px;")
        self.list.itemDoubleClicked.connect(self._show_details)
        self.mainLayout.addWidget(self.list, stretch=1)

    def _build_footer(self):
        footer = QLabel("\u00a9 2025 Ergon Mobility | All rights reserved.",
                        alignment=Qt.AlignCenter)
        footer.setStyleSheet("color:gray;font-size:10pt;")
        self.mainLayout.addWidget(footer)

    def _build_progress(self):
        self.progress_label = QLabel("Ready to start tests...", alignment=Qt.AlignCenter)
        self.progress_label.setStyleSheet("color:#666;font-size:14px;margin:10px;")
        self.mainLayout.addWidget(self.progress_label)
    
    def _shutdown_can_bus(self):
        """Properly shuts down the CAN bus and releases USB-CAN-B resource."""
        if self.bus:
            try:
                print("[INFO] Attempting clean CAN bus shutdown...")
                self.bus.shutdown()
                self.bus = None
            except Exception as e:
                print(f"[WARN] CAN bus shutdown failed: {e}")
                self.bus = None
    
    def _force_can_reset():
        try:
            import canalystii
            print("[CAN Reset] Forcing USB-CAN-B reset...")
            for dev in canalystii.find_all_devices():
                dev.reset()
            time.sleep(0.5)
        except Exception as e:
            print(f"[CAN Reset] Skipped (device not available): {e}")



    def _setup_can_bus(self):
        """Attempts to detect and initialize the appropriate CAN interface."""
        self._shutdown_can_bus()  # Always clean before new init

        # Try PEAK CAN first
        if can0_exists():
            try:
                bring_up_can0()
                self.bus = can.interface.Bus(interface='socketcan', channel='can0', bitrate=500000)
                print("✅ Connected to PEAK CAN via SocketCAN (can0)")
                return
            except Exception as e:
                print(f"❌ SocketCAN (can0) failed: {e}")
                self._shutdown_can_bus()

        # Try CANalyst-II next
        for attempt in range(2):  # Retry once if it fails
            try:
                _force_can_reset()
                self.bus = can.interface.Bus(interface='canalystii', channel=0, bitrate=500000)

                print("✅ Connected to USB-CAN-B (CANalyst-II)" + (" (on retry)" if attempt == 1 else ""))
                return
            except Exception as e:
                print(f"❌ CANalyst-II attempt {attempt + 1} failed: {e}")
                self._shutdown_can_bus()
                time.sleep(1)  # Let USB settle before retry

        print("❌ No working CAN interface found.")



    def _start_can_polling(self):
        self.read_timer = QTimer(self)
        # self.read_timer.timeout.connect(self._read_can)
        # self.read_timer.start(10)

    def _read_can(self):
        if not self.bus:
            return
        try:
            msg = self.bus.recv(timeout=0.01)
            if msg and msg.arbitration_id != self.SENT_ID:
                print(f"📥 ID=0x{msg.arbitration_id:X} Data={msg.data.hex()}")
        except Exception as e:
            print("⚠️ CAN read error:", e)

    def _update_can_status(self):
        ok = False
        # Check if current bus exists and is usable
        if self.bus:
            try:
                m = can.Message(arbitration_id=self.SENT_ID, data=[0xAA], is_extended_id=False)
                self.bus.send(m)
                ok = True
            except Exception as e:
                print(f"❌ [CAN] Send error: {e} — assuming bus is down.")
                try:
                    self.bus.shutdown()
                except Exception:
                    pass
                self.bus = None
                ok = False

        # If bus is None, try reconnecting
        if not self.bus:
            print("[INFO] Attempting to reconnect CAN bus...")
            self._shutdown_can_bus()

            try:
                bring_up_can0()
                self.bus = can.interface.Bus(interface='socketcan', channel='can0', bitrate=500000)
                print("✅ Reconnected to PEAK CAN via SocketCAN (can0)")
                self.runner.can_bus = self.bus
                self.runner._start_can_listener()
                ok = True
            except Exception as e1:
                print(f"❌ SocketCAN reconnect failed: {e1}")
                self._shutdown_can_bus()
                time.sleep(0.5)
                try:
                    self.bus = can.interface.Bus(interface='canalystii', channel=0, bitrate=500000)
                    print("✅ Reconnected to USB-CAN-B (CANalyst-II)")
                    self.runner.can_bus = self.bus
                    self.runner._start_can_listener()
                    ok = True
                except Exception as e2:
                    print(f"❌ USB-CAN-B reconnect failed: {e2}")
                    self._shutdown_can_bus()
                    self.bus = None
                    ok = False


        # Update UI status
        self._set_status(ok)

        # Update Ref 5V ADC Reading label in UI
        if self.runner:
            ref_voltage = self.runner.read_reference_voltage()
            if ref_voltage is not None:
                self.ref_voltage_label.setText(f"Ref 5V ADC Reading: {ref_voltage:.5f} V")
            else:
                self.ref_voltage_label.setText("Ref 5V ADC Reading: N/A")

    def _set_status(self, ok):
        if ok:
            self.statusLabel.setText("CAN Connected")
            self.statusLabel.setStyleSheet("color:green;font-weight:bold;")
            self.statusDot.set_color(Qt.green)
        else:
            self.statusLabel.setText("CAN Not Connected")
            self.statusLabel.setStyleSheet("color:red;font-weight:bold;")
            self.statusDot.set_color(Qt.red)

    def _on_run(self):

        if hasattr(self, "test_thread") and self.test_thread is not None and self.test_thread.isRunning():
            QMessageBox.warning(self, "Test Already Running", "Please wait for the current test to finish.")
            return

        self.runBtn.setEnabled(False)  # Disable the button until test completes
        self.list.clear()
        self.results = []
        self.progress_label.setText("Initializing tests...")

        self.live_plot = LivePlotWidget("Live Analog Sweep")
        self.live_plot.show()
        self.runner.sweep_step_signal.connect(self.live_plot.update_data, Qt.QueuedConnection)


        # self.runBtn.setEnabled(False)
        # self.exportBtn.setEnabled(False)
        # self.sendBtn.setEnabled(False)
        # self.relayBtn.setEnabled(False)

        # 👉 Create and show the live log window
        self.log_dialog = LogDialog()
        self.log_dialog.start_logging()
        self.log_dialog.show()

        # Start test thread
        self.thread = TestRunnerThread(self.runner, self.relay)
        self.thread.test_result_signal.connect(self._handle_test_result)
        self.thread.finished_signal.connect(self._handle_tests_finished)
        self.thread.error_signal.connect(self.show_error_message)
        self.thread.progress_signal.connect(self._update_progress)

        # Stop log redirection when done
        self.thread.finished_signal.connect(self.log_dialog.stop_logging)

        # 🔁 Stop test if either window is closed
        def stop_tests():
            if self.thread and self.thread.isRunning():
                self.thread.stop()

        self.live_plot.stop_callback = stop_tests
        self.log_dialog.stop_callback = stop_tests

        self.thread.start()


    def _update_progress(self, message):
        self.progress_label.setText(message)

    def _handle_test_result(self, result):
        self.results.append(result)
        item = QListWidgetItem(
            f"{result['name']} ({result['category']}) - {result['status']}"
        )
        color = QColor("#4CAF50") if result['status'] == "PASS" else QColor("#F44336")
        item.setBackground(color)
        item.setForeground(QColor("white"))
        item.setData(1000, result)
        self.list.addItem(item)

    def _handle_tests_finished(self):
        # ✅ Re-enable buttons after test thread finishes
        self.runBtn.setEnabled(True)
        self.exportBtn.setEnabled(True)
        self.sendBtn.setEnabled(True)
        self.relayBtn.setEnabled(True)

        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['status'] == "PASS")
        self.progress_label.setText(
            f"Tests completed: {passed_tests}/{total_tests} passed"
        )

        # ✅ Safely disconnect and close live plot if it's still visible
        try:
            if self.runner:
                self.runner.sweep_step_signal.disconnect()
            if self.live_plot and self.live_plot.isVisible():
                self.live_plot.close()
        except Exception as e:
            print(f"[Plot Disconnect Error] {e}")


    def _show_details(self, item):
        sig = item.data(1000)
        TestDetailDialog(sig).exec_()

    def _export_report(self):
        if not self.results:
            QMessageBox.warning(self, "Export Report", "No test results to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "report.txt",
            "Text Files (*.txt);;CSV Files (*.csv)"
        )
        if not path:
            return
        with open(path,'w') as f:
            for sig in self.results:
                f.write(f"{sig['name']} ({sig['category']}) - {sig['status']}\n")
                for t in sig['tests']:
                    st = "PASS" if t['passed'] else "FAIL"
                    v = (f"{t['value']:.2f}"
                         if isinstance(t['value'],float)
                         else str(t['value']))
                    f.write(f"  {t['test_name']}: {v} -> {st}\n")
                f.write("\n")

    def closeEvent(self, event):
        print("[CANTestApp] Window is closing. Shutting down CAN bus...")
        self._shutdown_can_bus()
        if self.runner:
            self.runner.shutdown()
        event.accept()
