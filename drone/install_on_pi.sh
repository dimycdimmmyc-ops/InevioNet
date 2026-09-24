#!/bin/bash
# Установка InevioNet Drone Node на Raspberry Pi

echo "🚁 InevioNet Drone Node Installer"
echo "=================================="

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo " Python3 не найден"
    echo "Установите: sudo apt install python3 python3-pip"
    exit 1
fi

# Создание venv
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Установка как systemd service
sudo cp drone_node.service /etc/systemd/system/
sudo systemctl enable drone_node
sudo systemctl start drone_node

echo "✅ Установка завершена!"
echo "Запуск: sudo systemctl start drone_node"
echo "Статус: sudo systemctl status drone_node"
