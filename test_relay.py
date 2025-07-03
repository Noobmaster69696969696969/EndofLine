# import lgpio
# import time

# # --- Configuration ---
# # The GPIO pin number (BCM numbering is typically used with lgpio)
# # For example, GPIO17 (physical pin 11)
# # IMPORTANT: Refer to a Raspberry Pi 5 pinout diagram for correct numbers.
# GPIO_PIN = 22

# # How long to keep the pin HIGH/LOW in seconds
# TOGGLE_DELAY = 1

# # --- Setup ---
# # Open the GPIO chip
# # For Raspberry Pi 5, the default chip is 0
# try:
#     h = lgpio.gpiochip_open(0) # Open gpiochip 0

#     if h < 0:
#         raise RuntimeError(f"Failed to open GPIO chip 0: {h}")

#     print(f"Setting up GPIO pin {GPIO_PIN} as an output.")
#     # Set the pin as output
#     lgpio.gpio_claim_output(h, GPIO_PIN)

#     print("Starting GPIO toggle. Press Ctrl+C to stop.")
#     while True:
#         # Turn the pin HIGH
#         lgpio.gpio_write(h, GPIO_PIN, 1)
#         print(f"GPIO {GPIO_PIN} is HIGH (ON)")
#         time.sleep(TOGGLE_DELAY)

#         # Turn the pin LOW
#         lgpio.gpio_write(h, GPIO_PIN, 0)
#         print(f"GPIO {GPIO_PIN} is LOW (OFF)")
#         time.sleep(TOGGLE_DELAY)

# except KeyboardInterrupt:
#     print("\nStopping GPIO toggle.")
# except Exception as e:
#     print(f"An error occurred: {e}")
# finally:
#     if 'h' in locals() and h >= 0:
#         # Release the GPIO pin and close the chip
#         lgpio.gpio_free(h, GPIO_PIN)
#         lgpio.gpiochip_close(h)
#         print("GPIO cleanup complete.")