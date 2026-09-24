"""
InevioNet Mobile — Kivy приложение для Android
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.metrics import dp
import requests
import json

class InevioNetMobile(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(20)
        self.spacing = dp(10)
        
        self.server_url = "http://192.168.1.100:8080"  # IP сервера
        
        # Заголовок
        self.add_widget(Label(
            text="🌌 InevioNet Mobile",
            font_size=dp(24),
            bold=True,
            size_hint_y=None,
            height=dp(50)
        ))
        
        # Статус
        self.status_label = Label(
            text="🔴 Не подключено",
            size_hint_y=None,
            height=dp(30)
        )
        self.add_widget(self.status_label)
        
        # Список узлов
        self.add_widget(Label(
            text="📡 Узлы сети:",
            size_hint_y=None,
            height=dp(30)
        ))
        
        # ScrollView для узлов
        scroll = ScrollView(size_hint=(1, 0.6))
        self.nodes_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(5)
        )
        self.nodes_layout.bind(minimum_height=self.nodes_layout.setter('height'))
        scroll.add_widget(self.nodes_layout)
        self.add_widget(scroll)
        
        # Кнопка обновления
        refresh_btn = Button(
            text="🔄 Обновить",
            size_hint_y=None,
            height=dp(50)
        )
        refresh_btn.bind(on_press=self.refresh_nodes)
        self.add_widget(refresh_btn)
        
        # Запускаем обновление
        Clock.schedule_interval(self.refresh_nodes, 5)
        Clock.schedule_once(lambda dt: self.refresh_nodes(None), 1)
    
    def refresh_nodes(self, instance):
        """Обновить список узлов."""
        try:
            response = requests.get(f"{self.server_url}/api/network/nodes", timeout=5)
            data = response.json()
            
            if data.get('success'):
                self.nodes_layout.clear_widgets()
                nodes = data.get('nodes', {})
                
                for node_id, node in nodes.items():
                    trust = node.get('trust', 0)
                    color = (0, 1, 0, 1) if trust >= 70 else (1, 1, 0, 1) if trust >= 40 else (1, 0, 0, 1)
                    
                    node_card = BoxLayout(
                        orientation='vertical',
                        padding=dp(10),
                        size_hint_y=None,
                        height=dp(80)
                    )
                    
                    node_id_label = Label(
                        text=f"🆔 {node_id[:16]}...",
                        halign='left',
                        size_hint_y=None,
                        height=dp(30)
                    )
                    
                    info_label = Label(
                        text=f"📡 {node.get('ip', '?')}:{node.get('port', '?')} | Надежность: {trust:.1f}%",
                        halign='left',
                        size_hint_y=None,
                        height=dp(30)
                    )
                    
                    node_card.add_widget(node_id_label)
                    node_card.add_widget(info_label)
                    self.nodes_layout.add_widget(node_card)
                
                self.status_label.text = f"🟢 Подключено ({len(nodes)} узлов)"
        except Exception as e:
            self.status_label.text = f"🔴 Ошибка: {str(e)[:30]}"

class InevioNetMobileApp(App):
    def build(self):
        self.title = "InevioNet Mobile"
        return InevioNetMobile()

if __name__ == '__main__':
    InevioNetMobileApp().run()
