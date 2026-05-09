# admin_panel.py
import time
import random
import re
from datetime import datetime, timedelta
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from sqlalchemy import func

from config import GROUP_ID
from database import Session, Player, AdminTransaction
from models import calculate_power

# Глобальные состояния
admin_sessions = {}
promocodes = {}

# ==================== КЛАВИАТУРЫ ====================
def get_admin_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📊 Статистика", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🎁 Выдать ресурсы", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🎉 Массовый подарок", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🎫 Создать промокод", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("📢 Вывести топ-15", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🚪 Выйти", color=VkKeyboardColor.NEGATIVE)
    return keyboard

def get_give_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("💰 Выдать золото", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("💎 Выдать кристаллы", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🎁 Выдать всё", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_back_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def send_msg(vk, user_id, text, keyboard=None):
    try:
        vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=random.randint(1, 10**9),
            keyboard=keyboard.get_keyboard() if keyboard else None
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def get_player_by_id(vk_id):
    session = Session()
    try:
        player = session.query(Player).filter_by(vk_id=vk_id).first()
        if player:
            # Принудительно загружаем данные
            _ = player.nick
            _ = player.gold
            _ = player.crystals
        return player
    finally:
        session.close()

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
def admin_login(vk, user_id):
    if user_id not in admin_sessions:
        admin_sessions[user_id] = {"logged_in": True}
    send_msg(vk, user_id, """
🛠️ **АДМИН-ПАНЕЛЬ**

Добро пожаловать!

━━━━━━━━━━━━━━━━━━━━━━
📊 **Статистика** - просмотр информации об игре
🎁 **Выдать ресурсы** - выдать кристаллы/золото игроку
🎉 **Массовый подарок** - выдать всем игрокам
🎫 **Создать промокод** - создать промокод для игроков
📢 **Вывести топ-15** - опубликовать в группе
🚪 **Выйти** - закрыть админку
""", get_admin_keyboard())

def show_statistics(vk, user_id):
    session = Session()
    try:
        total_players = session.query(Player).count()
        active_today = session.query(Player).filter(Player.last_login > datetime.utcnow() - timedelta(days=1)).count()
        total_gold = session.query(func.sum(Player.gold)).scalar() or 0
        total_crystals = session.query(func.sum(Player.crystals)).scalar() or 0
        avg_power = session.query(func.avg(Player.total_power)).scalar() or 0
        top_player = session.query(Player).order_by(Player.total_power.desc()).first()
        
        top_player_nick = top_player.nick if top_player else '-'
        top_player_power = top_player.total_power if top_player else 0
    finally:
        session.close()
    
    text = f"""
📊 **СТАТИСТИКА ИГРЫ**

━━━━━━━━━━━━━━━━━━━━━━
👥 **Игроков:** {total_players}
🟢 **Заходили сегодня:** {active_today}
💰 **Золота в обороте:** {total_gold:,}
💎 **Кристаллов в обороте:** {total_crystals:,}
📈 **Средняя сила:** {int(avg_power)}
🏆 **Сильнейший:** {top_player_nick} ({top_player_power})
    """
    send_msg(vk, user_id, text, get_admin_keyboard())

def give_resources_step1(vk, user_id):
    """Первый шаг - запрос ID игрока"""
    admin_sessions[user_id]["state"] = "give_get_id"
    send_msg(vk, user_id, """
🎁 **ВЫДАТЬ РЕСУРСЫ**

📌 **Шаг 1:** Введите ID игрока

💡 **Где взять ID?**
• Откройте профиль игрока ВКонтакте
• В ссылке будет vk.com/id123456
• Число после id — это и есть ID

**Пример:** `123456`
""", get_back_keyboard())

def give_resources_step2(vk, user_id, player_id):
    """Второй шаг - выбор ресурсов после получения ID"""
    player = get_player_by_id(player_id)
    if not player:
        send_msg(vk, user_id, f"❌ Игрок с ID {player_id} не найден в базе данных!\nПроверьте ID и попробуйте снова.", get_admin_keyboard())
        admin_sessions[user_id]["state"] = None
        return
    
    admin_sessions[user_id]["give_player_id"] = player_id
    admin_sessions[user_id]["give_player_nick"] = player.nick
    admin_sessions[user_id]["state"] = "give_choose"
    
    send_msg(vk, user_id, f"""
✅ **ИГРОК НАЙДЕН!**

👤 {player.nick} (ID: {player_id})
💰 Текущее золото: {player.gold}
💎 Текущие кристаллы: {player.crystals}

━━━━━━━━━━━━━━━━━━━━━━
📌 **Шаг 2:** Что хотите выдать?
""", get_give_keyboard())

def give_resources_execute(vk, user_id, resource_type):
    """Третий шаг - ввод суммы и причины"""
    player_id = admin_sessions[user_id].get("give_player_id")
    if not player_id:
        send_msg(vk, user_id, "❌ Ошибка: игрок не выбран. Начните заново.", get_admin_keyboard())
        admin_sessions[user_id]["state"] = None
        return
    
    admin_sessions[user_id]["give_resource_type"] = resource_type
    admin_sessions[user_id]["state"] = "give_amount"
    
    if resource_type == "gold":
        send_msg(vk, user_id, "💰 Введите количество золота и причину:\n\n`500 причина:Бонус за активность`", get_back_keyboard())
    elif resource_type == "crystals":
        send_msg(vk, user_id, "💎 Введите количество кристаллов и причину:\n\n`10 причина:Бонус за активность`", get_back_keyboard())
    elif resource_type == "both":
        send_msg(vk, user_id, "🎁 Введите золото, кристаллы и причину:\n\n`золото:500 кристаллы:10 причина:Праздник`", get_back_keyboard())

def give_resources_finish(vk, user_id, data):
    """Финальный шаг - выполнение выдачи"""
    player_id = admin_sessions[user_id].get("give_player_id")
    resource_type = admin_sessions[user_id].get("give_resource_type")
    
    if not player_id:
        send_msg(vk, user_id, "❌ Ошибка: игрок не выбран. Начните заново.", get_admin_keyboard())
        admin_sessions[user_id]["state"] = None
        return
    
    # Парсинг данных
    gold = 0
    crystals = 0
    reason = "Выдача от администратора"
    
    if resource_type == "gold":
        match = re.search(r'(\d+)', data)
        if match:
            gold = int(match.group(1))
        reason_match = re.search(r'причина:(.+)', data, re.IGNORECASE)
        if reason_match:
            reason = reason_match.group(1)
    elif resource_type == "crystals":
        match = re.search(r'(\d+)', data)
        if match:
            crystals = int(match.group(1))
        reason_match = re.search(r'причина:(.+)', data, re.IGNORECASE)
        if reason_match:
            reason = reason_match.group(1)
    elif resource_type == "both":
        gold_match = re.search(r'золото:(\d+)', data, re.IGNORECASE)
        crystals_match = re.search(r'кристаллы:(\d+)', data, re.IGNORECASE)
        reason_match = re.search(r'причина:(.+)', data, re.IGNORECASE)
        if gold_match:
            gold = int(gold_match.group(1))
        if crystals_match:
            crystals = int(crystals_match.group(1))
        if reason_match:
            reason = reason_match.group(1)
    
    if gold == 0 and crystals == 0:
        send_msg(vk, user_id, "❌ Укажите корректную сумму!\nПример: `500` или `золото:500 кристаллы:10`", get_back_keyboard())
        return
    
    # Выдача ресурсов
    session = Session()
    try:
        player = session.query(Player).filter_by(vk_id=player_id).first()
        if not player:
            send_msg(vk, user_id, f"❌ Игрок с ID {player_id} не найден!", get_admin_keyboard())
            return
        
        old_gold = player.gold
        old_crystals = player.crystals
        
        if gold > 0:
            player.gold += gold
        if crystals > 0:
            player.crystals += crystals
        
        player.total_power = calculate_power(player)
        
        transaction = AdminTransaction(
            admin_id=user_id,
            player_id=player.vk_id,
            gold_given=gold,
            crystals_given=crystals,
            reason=reason
        )
        session.add(transaction)
        session.commit()
        
        player_nick = player.nick
        player_gold = player.gold
        player_crystals = player.crystals
        player_vk_id = player.vk_id
        
    except Exception as e:
        session.rollback()
        send_msg(vk, user_id, f"❌ Ошибка при выдаче: {e}", get_admin_keyboard())
        return
    finally:
        session.close()
    
    # Уведомление админу
    send_msg(vk, user_id, f"""
✅ **ВЫДАЧА ВЫПОЛНЕНА!**

👤 Игрок: {player_nick} (ID: {player_vk_id})
💰 +{gold} золота ({old_gold} → {player_gold})
💎 +{crystals} кристаллов ({old_crystals} → {player_crystals})
📝 Причина: {reason}
""", get_admin_keyboard())
    
    # Уведомление игроку
    try:
        vk.messages.send(
            user_id=player_vk_id,
            message=f"""
🎁 **АДМИНИСТРАТОР ВЫДАЛ БОНУС!**

💰 +{gold} золота
💎 +{crystals} кристаллов

📝 Причина: {reason}
""",
            random_id=random.randint(1, 10**9)
        )
    except:
        pass
    
    # Сброс состояния
    admin_sessions[user_id]["state"] = None
    admin_sessions[user_id]["give_player_id"] = None
    admin_sessions[user_id]["give_player_nick"] = None
    admin_sessions[user_id]["give_resource_type"] = None

def mass_gift(vk, user_id, data):
    """Массовая выдача ресурсов всем игрокам"""
    gold = 0
    crystals = 0
    reason = "Массовый подарок"
    
    parts = data.split()
    for part in parts:
        part_lower = part.lower()
        if part_lower.startswith("золото:") or part_lower.startswith("gold:"):
            try:
                gold = int(part.split(":")[1])
            except:
                pass
        elif part_lower.startswith("кристаллы:") or part_lower.startswith("crystals:"):
            try:
                crystals = int(part.split(":")[1])
            except:
                pass
        elif part_lower.startswith("причина:"):
            reason = part.split(":", 1)[1]
    
    if gold == 0 and crystals == 0:
        send_msg(vk, user_id, "❌ Укажите, что выдавать!\nПример: `золото:500`", get_admin_keyboard())
        return
    
    session = Session()
    try:
        players = session.query(Player).filter_by(is_banned=False).all()
        count = 0
        
        for player in players:
            if gold > 0:
                player.gold += gold
            if crystals > 0:
                player.crystals += crystals
            player.total_power = calculate_power(player)
            count += 1
        
        session.commit()
    except Exception as e:
        session.rollback()
        send_msg(vk, user_id, f"❌ Ошибка: {e}", get_admin_keyboard())
        return
    finally:
        session.close()
    
    # Фоновый поток для рассылки (чтобы не блокировать)
    def send_rewards():
        for player in players:
            try:
                vk.messages.send(
                    user_id=player.vk_id,
                    message=f"""
🎉 **МАССОВЫЙ ПОДАРОК!**

💰 +{gold} золота
💎 +{crystals} кристаллов

📝 Причина: {reason}

Спасибо, что играете с нами! 🏰
""",
                    random_id=random.randint(1, 10**9)
                )
                time.sleep(0.05)
            except:
                pass
    
    import threading
    threading.Thread(target=send_rewards, daemon=True).start()
    
    send_msg(vk, user_id, f"""
✅ **МАССОВЫЙ ПОДАРОК ВЫПОЛНЕН!**

Получили: {count} игроков
💰 +{gold} золота
💎 +{crystals} кристаллов
📝 Причина: {reason}
""", get_admin_keyboard())

def create_promocode(vk, admin_id, data):
    """Создать промокод"""
    import string
    parts = data.split()
    code = None
    gold = 0
    crystals = 0
    expires_in_days = 7
    
    for part in parts:
        if part.startswith("код:") or part.startswith("code:"):
            code = part.split(":")[1].upper()
        elif part.startswith("золото:") or part.startswith("gold:"):
            gold = int(part.split(":")[1])
        elif part.startswith("кристаллы:") or part.startswith("crystals:"):
            crystals = int(part.split(":")[1])
        elif part.startswith("дней:") or part.startswith("days:"):
            expires_in_days = int(part.split(":")[1])
    
    if not code:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    promocodes[code] = {
        "gold": gold,
        "crystals": crystals,
        "expires": datetime.utcnow() + timedelta(days=expires_in_days),
        "used_by": [],
        "creator": admin_id
    }
    
    send_msg(vk, admin_id, f"""
✅ **ПРОМОКОД СОЗДАН!**

📌 Код: `{code}`
💰 Золото: +{gold}
💎 Кристаллы: +{crystals}
⏰ Действует: {expires_in_days} дней

Игроки могут активировать командой: `промокод {code}`
""", get_admin_keyboard())

def use_promocode(vk, user_id, code):
    """Активация промокода игроком"""
    code = code.upper().strip()
    
    if code not in promocodes:
        send_msg(vk, user_id, "❌ Неверный или устаревший промокод!")
        return
    
    promo = promocodes[code]
    
    if promo["expires"] < datetime.utcnow():
        send_msg(vk, user_id, "❌ Срок действия промокода истёк!")
        return
    
    if user_id in promo["used_by"]:
        send_msg(vk, user_id, "❌ Вы уже активировали этот промокод!")
        return
    
    session = Session()
    try:
        player = session.query(Player).filter_by(vk_id=user_id).first()
        if not player:
            send_msg(vk, user_id, "❌ Персонаж не найден!")
            return
        
        if promo["gold"] > 0:
            player.gold += promo["gold"]
        if promo["crystals"] > 0:
            player.crystals += promo["crystals"]
        player.total_power = calculate_power(player)
        session.commit()
        
        promo["used_by"].append(user_id)
        
        send_msg(vk, user_id, f"""
🎉 **ПРОМОКОД АКТИВИРОВАН!**

💰 +{promo['gold']} золота
💎 +{promo['crystals']} кристаллов

Спасибо, что играете с нами!
""")
    except Exception as e:
        session.rollback()
        send_msg(vk, user_id, f"❌ Ошибка: {e}")
    finally:
        session.close()

def post_top15(vk, user_id):
    """Вывести топ-15 в группу ВК"""
    session = Session()
    try:
        top_players = session.query(Player).filter_by(is_banned=False).order_by(Player.total_power.desc()).limit(15).all()
        
        if not top_players:
            send_msg(vk, user_id, "❌ Нет игроков для вывода!", get_admin_keyboard())
            return
        
        text = "🏆 **ТОП-15 СИЛЬНЕЙШИХ ИГРОКОВ** 🏆\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, p in enumerate(top_players, 1):
            medal = medals[i-1] if i <= 5 else f"{i}."
            text += f"{medal} **{p.nick}**\n"
            text += f"   💪 Сила: {p.total_power} | 🏆 Уровень: {p.level}\n"
            text += f"   🏰 Ратуша: {p.castle_level} | 👥 Друзей: {p.referral_count}\n\n"
        
    finally:
        session.close()
    
    try:
        vk.wall.post(
            owner_id=-GROUP_ID,
            message=text,
            from_group=1
        )
        send_msg(vk, user_id, "✅ Топ-15 успешно опубликован в сообществе!", get_admin_keyboard())
    except Exception as e:
        send_msg(vk, user_id, f"❌ Ошибка публикации: {e}", get_admin_keyboard())

def handle_admin_command(vk, user_id, text):
    """Обработка команд админ-панели"""
    if user_id not in admin_sessions:
        return False
    
    # Выход
    if text == "🚪 Выйти" or text == "Выйти":
        del admin_sessions[user_id]
        send_msg(vk, user_id, "👋 Вы вышли из админ-панели.")
        return True
    
    # Статистика
    if text == "📊 Статистика" or text == "Статистика":
        show_statistics(vk, user_id)
        return True
    
    # Выдать ресурсы - начало
    if text == "🎁 Выдать ресурсы" or text == "Выдать ресурсы":
        give_resources_step1(vk, user_id)
        return True
    
    # Возврат в главное меню из выдачи
    if text == "⬅️ Назад" and admin_sessions.get(user_id, {}).get("state") in ["give_get_id", "give_choose", "give_amount"]:
        admin_sessions[user_id]["state"] = None
        admin_sessions[user_id]["give_player_id"] = None
        admin_sessions[user_id]["give_player_nick"] = None
        admin_sessions[user_id]["give_resource_type"] = None
        send_msg(vk, user_id, "🛠️ Админ-панель", get_admin_keyboard())
        return True
    
    # Шаг 1: ввод ID игрока
    if admin_sessions.get(user_id, {}).get("state") == "give_get_id":
        if text.isdigit():
            give_resources_step2(vk, user_id, int(text))
        else:
            send_msg(vk, user_id, "❌ ID игрока должен состоять только из цифр!\nПример: `123456`", get_back_keyboard())
        return True
    
    # Шаг 2: выбор типа ресурса
    if admin_sessions.get(user_id, {}).get("state") == "give_choose":
        if text == "💰 Выдать золото":
            give_resources_execute(vk, user_id, "gold")
        elif text == "💎 Выдать кристаллы":
            give_resources_execute(vk, user_id, "crystals")
        elif text == "🎁 Выдать всё":
            give_resources_execute(vk, user_id, "both")
        else:
            send_msg(vk, user_id, "❌ Выберите действие из меню!", get_give_keyboard())
        return True
    
    # Шаг 3: ввод суммы
    if admin_sessions.get(user_id, {}).get("state") == "give_amount":
        give_resources_finish(vk, user_id, text)
        return True
    
    # Массовый подарок
    if text == "🎉 Массовый подарок" or text == "Массовый подарок":
        admin_sessions[user_id]["state"] = "mass"
        send_msg(vk, user_id, """
🎉 **МАССОВЫЙ ПОДАРОК**

Введите что выдать всем игрокам:

📌 **Формат:**
`золото:XXX кристаллы:YYY причина:Текст`

📌 **Примеры:**
• `золото:500`
• `кристаллы:10`
• `золото:500 кристаллы:10 причина:С праздником!`
""", get_back_keyboard())
        return True
    
    if admin_sessions.get(user_id, {}).get("state") == "mass":
        mass_gift(vk, user_id, text)
        admin_sessions[user_id]["state"] = None
        send_msg(vk, user_id, "🛠️ Админ-панель", get_admin_keyboard())
        return True
    
    # Создать промокод
    if text == "🎫 Создать промокод" or text == "Создать промокод":
        admin_sessions[user_id]["state"] = "promocode"
        send_msg(vk, user_id, """
🎫 **СОЗДАНИЕ ПРОМОКОДА**

Введите параметры:

📌 **Формат:**
`золото:XXX кристаллы:YYY дней:7 код:МОЙКОД`

📌 **Примеры:**
• `золото:500` (код сгенерируется сам)
• `золото:1000 кристаллы:20 дней:14 код:НОВЫЙГОД`
""", get_back_keyboard())
        return True
    
    if admin_sessions.get(user_id, {}).get("state") == "promocode":
        create_promocode(vk, user_id, text)
        admin_sessions[user_id]["state"] = None
        send_msg(vk, user_id, "🛠️ Админ-панель", get_admin_keyboard())
        return True
    
    # Вывести топ-15
    if text == "📢 Вывести топ-15" or text == "Вывести топ-15":
        post_top15(vk, user_id)
        return True
    
    return False
