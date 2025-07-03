import RPi.GPIO as GPIO
import sys
import os
import subprocess

GPIO.setwarnings(False)  # Suppress GPIO warnings
GPIO.setmode(GPIO.BCM)   # Use BCM pin numbering

from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QLabel, QStackedWidget, 
    QHBoxLayout, QTextEdit, QDialog,QMessageBox
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt,QTimer
from can_test_ui import CANTestApp

class WelcomeScreen(QWidget):
    def __init__(self, on_start_callback):
        super().__init__()
        self.on_start_callback = on_start_callback  # Callback to start the app
        self.setWindowTitle("Welcome") 
        self.resize(1000, 700)

        self.layout = QVBoxLayout(self)             
        self.layout.setContentsMargins(0, 0, 0, 0)  

        # Background image
        self.background = QLabel(self)
        self.background.setScaledContents(True)
        self.background.setGeometry(0, 0, self.width(), self.height())
        pixmap = QPixmap("ergon.jpg")
        if pixmap.isNull():
            print("⚠️ 'ergon.jpg' not found. Using gray fallback.")
            pixmap = QPixmap(1000, 700)
            pixmap.fill(Qt.gray)
        self.background.setPixmap(pixmap)
        self.background.lower()  # Ensure background is behind other widgets

        # Overlay widget
        overlay = QWidget(self)  # Create an overlay widget(above background image for buttons and all)
        overlay_layout = QVBoxLayout(overlay)   
        overlay_layout.setContentsMargins(0, 0, 0, 0) 
        overlay_layout.addStretch()   

        # Button layout
        button_layout = QHBoxLayout()
        # Get Started button
        self.start_btn = QPushButton("Get Started")  # <-- Add this line
        self.start_btn.setFixedSize(180, 50)
        self.start_btn.setFont(QFont("Arial", 14, QFont.Bold))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #005792;
                color: white;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #007ab8;
            }
        """)
        self.start_btn.clicked.connect(self.on_start_callback)

        button_layout.addStretch()
        # button_layout.addWidget(self.diagnostics_btn)
        button_layout.addSpacing(20)
        button_layout.addWidget(self.start_btn)
        button_layout.addStretch()

        overlay_layout.addLayout(button_layout)
        overlay_layout.addStretch()

        self.layout.addWidget(overlay)

    def resizeEvent(self, event):
        # Auto-resize the background image when the window size changes
        pixmap = QPixmap("ergon.jpg")
        if not pixmap.isNull():
            self.background.setPixmap(pixmap.scaled(
                self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            ))
        self.background.setGeometry(0, 0, self.width(), self.height())


class MainApp(QStackedWidget):  # MainApp inherits from QStackedWidget to manage multiple screens
    def __init__(self):
        super().__init__()    # Initialize the base class
        self.setWindowTitle("EOL TESTING APP")

        self.welcome = WelcomeScreen(self.start_app)
        self.test_app = None  # Delay CANTestApp creation(lazy initialization)

        self.addWidget(self.welcome)
        self.setCurrentWidget(self.welcome)

    def start_app(self):
        if self.test_app is None:
            print("[MainApp] Creating CANTestApp UI...")
            self.test_app = CANTestApp()
            self.addWidget(self.test_app)

            # 🧠 Now defer initialization (e.g., CAN detection) after page loads
            QTimer.singleShot(100, self.test_app.start_initialization)  # slight delay

        self.setCurrentWidget(self.test_app)  # ✅ Instantly switch page

if __name__ == "__main__":
    # Run system diagnostics first
    # run_system_diagnostics()
    app = QApplication(sys.argv)
    window = MainApp()
    window.showMaximized()
    
    sys.exit(app.exec_())  