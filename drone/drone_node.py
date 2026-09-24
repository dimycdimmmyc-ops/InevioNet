"""
InevioNet Drone Node — Лёгкий узел для дронов
Оптимизирован для Raspberry Pi/Jetson Nano
"""
import sys
import time
import threading
import json
from pathlib import Path

# Добавляем корень проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

from inevionet import InevioNet
from inevionet.core.logger import get_logger

logger = get_logger("drone_node")

class DroneNode:
    """Лёгкий узел для дрона."""
    
    def __init__(self, drone_id: str, password: str = "drone_secret"):
        self.drone_id = drone_id
        self.password = password
        self.network = None
        self._running = False
        
        # Телеметрия дрона
        self.telemetry = {
            "battery": 100,
            "altitude": 0,
            "speed": 0,
            "position": {"lat": 0, "lon": 0},
            "status": "idle"
        }
    
    def start(self):
        """Запуск узла."""
        logger.info(f"🚁 Запуск drone node: {self.drone_id}")
        
        # Инициализация сети
        self.network = InevioNet(
            password=self.password,
            node_id=self.drone_id,
            auto_start=True,
            mode="lightweight"  # Лёгкий режим
        )
        
        self._running = True
        
        # Запуск цикла телеметрии
        telemetry_thread = threading.Thread(target=self._telemetry_loop)
        telemetry_thread.daemon = True
        telemetry_thread.start()
        
        logger.info("✅ Drone node запущен")
    
    def stop(self):
        """Остановка узла."""
        self._running = False
        if self.network:
            self.network.stop()
        logger.info("🛑 Drone node остановлен")
    
    def _telemetry_loop(self):
        """Цикл отправки телеметрии."""
        while self._running:
            try:
                # Симуляция телеметрии (в реальности — чтение с датчиков)
                self.telemetry["battery"] = max(0, self.telemetry["battery"] - 0.1)
                self.telemetry["altitude"] += 0.1
                self.telemetry["speed"] = 5.0
                
                # Отправка телеметрии в сеть
                if self.network:
                    self.network.send(
                        receiver="ground_station",
                        payload={"type": "telemetry", "data": self.telemetry},
                        priority=9
                    )
                
                time.sleep(1)  # Каждую секунду
            except Exception as e:
                logger.error(f"Ошибка телеметрии: {e}")
                time.sleep(5)
    
    def send_command(self, command: str, target: str):
        """Отправить команду."""
        if self.network:
            self.network.send(
                receiver=target,
                payload={"type": "command", "command": command},
                priority=10
            )
    
    def get_status(self):
        """Получить статус."""
        return {
            "drone_id": self.drone_id,
            "running": self._running,
            "telemetry": self.telemetry,
            "network_stats": self.network.get_stats() if self.network else {}
        }

# ===== ЗАПУСК =====
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="InevioNet Drone Node")
    parser.add_argument("--id", default="drone_001", help="ID дрона")
    parser.add_argument("--password", default="drone_secret", help="Пароль")
    
    args = parser.parse_args()
    
    drone = DroneNode(args.id, args.password)
    
    try:
        drone.start()
        logger.info("🚁 Drone node работает. Нажмите Ctrl+C для остановки.")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Остановка по Ctrl+C")
    finally:
        drone.stop()
