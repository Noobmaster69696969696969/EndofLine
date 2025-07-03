# import can

# def main():
#     try:
#         bus = can.interface.Bus(interface='canalystii', channel=0, bitrate=500000)

#         print("[INFO] Connected to CAN interface 'can0'. Listening for CAN frames...\n")

#         while True:
#             msg = bus.recv(timeout=5.0)
#             if msg:
#                 print(f"[RECV] ID: 0x{msg.arbitration_id:X}, DLC: {msg.dlc}, Data: {' '.join(f'{b:02X}' for b in msg.data)}")
#             else:
#                 print("[WAIT] No message received.")

#     except KeyboardInterrupt:
#         print("\n[EXIT] Stopped by user.")
#     except Exception as e:
#         print(f"[ERROR] {e}")
#     finally:
#         try:
#             bus.shutdown()
#             print("[INFO] CAN interface shut down cleanly.")
#         except:
#             pass

# if __name__ == "__main__":
#     main()
