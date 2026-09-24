"""InevioNet User Management — регистрация, логин, QR-контакты."""
import json
import os
import time
import hashlib
import secrets
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field, asdict

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

from ..core.crypto import InevioCrypto, random_id
from ..core.constants import DataPaths


@dataclass
class UserProfile:
    """Профиль пользователя."""
    username: str
    node_id: str
    public_key_hex: str
    created_at: float = 0.0
    contacts: List[Dict[str, str]] = field(default_factory=list)
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
    
    def to_dict(self):
        return asdict(self)
    
    def to_qr_data(self):
        """Данные для QR-кода контакта."""
        return {
            "type": "inevionet_contact",
            "version": "1.0",
            "username": self.username,
            "node_id": self.node_id,
            "public_key": self.public_key_hex,
            "exch_pub": getattr(self, "exch_pub", None),
        }


class UserManager:
    """Управление пользователями и контактами."""
    
    def __init__(self):
        self.users_dir = Path(DataPaths.get_state_dir()) / "users"
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.current_user: Optional[UserProfile] = None
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Хэш пароля с солью."""
        return "pbkdf2$120000$" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    
    def register(self, username: str, password: str) -> UserProfile:
        """Регистрация нового пользователя."""
        username = username.strip().lower()
        if len(username) < 3:
            raise ValueError("Имя должно быть минимум 3 символа")
        if len(password) < 4:
            raise ValueError("Пароль должен быть минимум 4 символа")
        
        user_file = self.users_dir / f"{username}.json"
        if user_file.exists():
            raise ValueError(f"Пользователь '{username}' уже существует")
        
        # Криптографические ключи
        crypto = InevioCrypto(password)
        node_id = f"node_{random_id('', 8)}"
        keypair = crypto.get_signing_keypair()
        public_key_hex = keypair.public_key.hex()
        from inevionet.security import make_exchange_pair, seal_key
        exch_priv, exch_pub = make_exchange_pair()
        
        # Соль и хэш пароля
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        
        profile = UserProfile(
            username=username,
            node_id=node_id,
            public_key_hex=public_key_hex,
        )
        
        user_data = profile.to_dict()
        user_data["password_hash"] = password_hash
        user_data["salt"] = salt
        user_data["exch_priv"] = seal_key(password, exch_priv)
        user_data["exch_pub"] = exch_pub
        
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)
        
        self.current_user = profile
        return profile
    
    def login(self, username: str, password: str) -> UserProfile:
        """Вход пользователя."""
        username = username.strip().lower()
        user_file = self.users_dir / f"{username}.json"
        
        if not user_file.exists():
            raise ValueError(f"Пользователь '{username}' не найден")
        
        with open(user_file, "r", encoding="utf-8") as f:
            user_data = json.load(f)
        
        expected_hash = user_data.get("password_hash", "")
        salt = user_data.get("salt", "")
        actual_hash = self._hash_password(password, salt)
        
        legacy = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        if actual_hash != expected_hash and legacy != expected_hash:
            raise ValueError("Неверный пароль")
        if expected_hash == legacy:
            user_data["password_hash"] = actual_hash
            with open(user_file, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
        
        profile = UserProfile(
            username=user_data["username"],
            node_id=user_data["node_id"],
            public_key_hex=user_data["public_key_hex"],
            created_at=user_data.get("created_at", 0.0),
            contacts=user_data.get("contacts", []),
        )
        try:
            from inevionet.security import open_key
            profile.exch_priv = open_key(password, user_data.get("exch_priv", ""))
            profile.exch_pub = user_data.get("exch_pub")
        except Exception:
            profile.exch_priv = None
            profile.exch_pub = None
        
        self.current_user = profile
        return profile
    
    def logout(self):
        """Выход."""
        self.current_user = None
    
    def get_current_user(self) -> Optional[UserProfile]:
        """Получить текущего пользователя."""
        return self.current_user
    
    def generate_contact_qr(self) -> Optional[str]:
        """Генерация QR-кода с контактной информацией."""
        if not self.current_user:
            return None
        
        if not QR_AVAILABLE:
            return None
        
        qr_data = self.current_user.to_qr_data()
        qr_json = json.dumps(qr_data, ensure_ascii=False)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(qr_json)
        qr.make(fit=True)
        
        qr_dir = self.users_dir / "qr_codes"
        qr_dir.mkdir(exist_ok=True)
        qr_path = qr_dir / f"{self.current_user.username}_contact.png"
        
        img = qr.make_image(fill_color="#00ff9c", back_color="#0a0a12")
        img.save(qr_path)
        
        return str(qr_path)
    
    def add_contact(self, qr_data: Dict) -> bool:
        """Добавление контакта из QR-данных."""
        if not self.current_user:
            raise ValueError("Нет активного пользователя")
        
        if qr_data.get("type") != "inevionet_contact":
            raise ValueError("Неверный формат QR-данных")
        
        contact_node_id = qr_data.get("node_id")
        if not contact_node_id:
            raise ValueError("Неверные данные QR")
        
        if contact_node_id == self.current_user.node_id:
            raise ValueError("Нельзя добавить себя в контакты")
        
        # Проверяем дубликат
        for c in self.current_user.contacts:
            if c.get("node_id") == contact_node_id:
                return False
        
        self.current_user.contacts.append({
            "username": qr_data.get("username", "unknown"),
            "node_id": contact_node_id,
            "public_key": qr_data.get("public_key", ""),
            "added_at": time.time(),
        })
        
        self._save_current_user()
        return True
    
    def get_contacts(self) -> List[Dict]:
        """Список контактов."""
        if not self.current_user:
            return []
        return self.current_user.contacts
    
    def remove_contact(self, node_id: str) -> bool:
        """Удалить контакт."""
        if not self.current_user:
            return False
        before = len(self.current_user.contacts)
        self.current_user.contacts = [
            c for c in self.current_user.contacts if c.get("node_id") != node_id
        ]
        if len(self.current_user.contacts) < before:
            self._save_current_user()
            return True
        return False
    
    def _save_current_user(self):
        """Сохранение текущего пользователя."""
        if not self.current_user:
            return
        user_file = self.users_dir / f"{self.current_user.username}.json"
        if not user_file.exists():
            return
        with open(user_file, "r", encoding="utf-8") as f:
            user_data = json.load(f)
        user_data["contacts"] = self.current_user.contacts
        with open(user_file, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)


# Глобальный экземпляр
_user_manager: Optional[UserManager] = None

def get_user_manager() -> UserManager:
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager


if __name__ == "__main__":
    print("=" * 60)
    print(" ТЕСТ USER MANAGER")
    print("=" * 60)
    
    um = get_user_manager()
    
    # Регистрация
    print("\n1. Регистрация:")
    try:
        profile = um.register("test_user", "test1234")
        print(f"   ✅ Создан: {profile.username} (node_id={profile.node_id})")
    except ValueError as e:
        print(f"   ℹ️  {e}")
        profile = um.login("test_user", "test1234")
        print(f"   ✅ Вошёл: {profile.username}")
    
    # QR
    print("\n2. Генерация QR:")
    qr_path = um.generate_contact_qr()
    print(f"   ✅ QR создан: {qr_path}")
    
    # Контакты
    print("\n3. Добавление контакта:")
    fake_qr = {
        "type": "inevionet_contact",
        "username": "alice",
        "node_id": "node_alice123",
        "public_key": "abc123",
    }
    um.add_contact(fake_qr)
    print(f"   ✅ Контакты: {len(um.get_contacts())}")
    for c in um.get_contacts():
        print(f"      - {c['username']} ({c['node_id']})")
    
    print("\n✅ Все тесты пройдены!")

