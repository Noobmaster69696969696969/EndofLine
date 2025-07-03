# import can

# with can.Bus(interface='canalystii', channel=0, bitrate=500000) as bus:
#     print("Connected to CANalyst-II!")

#     msg = bus.recv(timeout=5)
#     if msg:
#         print(f"Received: {msg}")
#     else:
#         print("No message received.")
