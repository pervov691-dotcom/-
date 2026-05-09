# config.py
import os

# Токен VK группы (получить: https://vkhost.github.io/)
VK_TOKEN = "vk1.a.qUyg4SYpR2414W6nHk3hZB4ggpljiji-rBo3P2TBcXlmuEc-jOtXEc_T5BqoKGcIExwbmn5nAyEUTh5NkMMdqVb2qumib8fjaA2JrW1MUBbTyptBks0Khp4QgzvER2gGm9U485X1rnIQ3B3S4lu_BmGFf_tsO6zY5Slr2kC6x5GcKR5C1xzl-CqoTytONqeUyw8RUYys0RQSD7DOaSZQSg"  # ЗАМЕНИТЕ НА СВОЙ ТОКЕН!

# ID группы (можно найти в настройках группы)
GROUP_ID = 237951367  # ЗАМЕНИТЕ НА СВОЙ ID!

# ID администраторов (твой VK ID)
ADMIN_IDS = [1024252142]  # ЗАМЕНИТЕ НА СВОЙ ID!

# Пароль для админ-панели
ADMIN_PASSWORD = "130278Mama"

# База данных
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///medieval.db")
