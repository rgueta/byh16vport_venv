#!/usr/bin/env python3
import time
import board, busio
from digitalio import DigitalInOut
from adafruit_pn532.spi import PN532_SPI
from server import unlock_action  # importa la función (o publica a /unlock endpoint)

# SPI wiring: adjust cs pin
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
cs = DigitalInOut(board.D8)  # CE0
pn532 = PN532_SPI(spi, cs, debug=False)
pn532.SAM_configuration()

# whitelist of UIDs (hex)
AUTHORIZED = {"04AABBCCDD": "Ricardo", "04BBCCDDEE": "Invitado"}

print("NFC reader started.")
while True:
    uid = pn532.read_passive_target(timeout=0.5)
    if uid:
        uid_hex = "".join("{:02X}".format(x) for x in uid)
        print("Tag:", uid_hex)
        if uid_hex in AUTHORIZED:
            print("Autorizado:", AUTHORIZED[uid_hex])
            unlock_action(f"nfc:{AUTHORIZED[uid_hex]}")
        else:
            print("No autorizado")
        time.sleep(1)
