import RPi.GPIO as GPIO
import time
import threading


class BuzzerManager:
    def __init__(self, buzzer_pin=18):
        self.buzzer_pin = buzzer_pin
        self.setup_buzzer()

    def setup_buzzer(self):
        """Configura el GPIO para el buzzer"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.buzzer_pin, GPIO.OUT)
            GPIO.output(self.buzzer_pin, GPIO.LOW)
            print(f"✅ Buzzer configurado en pin GPIO {self.buzzer_pin}")
        except Exception as e:
            print(f"❌ Error configurando buzzer: {e}")

    def beep(self, duration=0.1, times=1, delay=0.1):
        """Emite sonido del buzzer"""

        def beep_thread():
            for _ in range(times):
                GPIO.output(self.buzzer_pin, GPIO.HIGH)
                time.sleep(duration)
                GPIO.output(self.buzzer_pin, GPIO.LOW)
                time.sleep(delay)

        threading.Thread(target=beep_thread, daemon=True).start()

    def alert_pattern(self, pattern_type="success"):
        """Patrones predefinidos de sonido"""
        patterns = {
            "success": [(0.1, 1)],  # Un beep corto
            "error": [(0.3, 3, 0.05)],  # Tres beeps largos
            "warning": [(0.2, 2, 0.1)],  # Dos beeps medios
            "notification": [(0.05, 2, 0.02)],  # Doble beep rápido
            "startup": [(0.1, 1), (0.05, 0), (0.1, 1)],  # Beep-doble-beep
        }

        if pattern_type in patterns:
            for pattern in patterns[pattern_type]:
                self.beep(*pattern)

    def cleanup(self):
        """Limpia los recursos GPIO"""
        GPIO.output(self.buzzer_pin, GPIO.LOW)
