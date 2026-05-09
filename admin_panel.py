# admin_panel.py
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from datetime import datetime, timedelta
import random
import re
from sqlalchemy import func

from config import GROUP_ID
from database import Session, Player, AdminTransaction
from models import calculate_power

# Глобальные состояния
admin_sessions = {}

# ==================== КЛАВИАТУРЫ ====================
def get_admin_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📊 Статистика", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🎁 Выдать ресурсы", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("🎉 Массовый подарок", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("📢 Вывести топ-15", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🚪 Выйти", color=VkKeyboardColor.NEGATIVE)
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

def send_all_message(vk, text):
    """Отправка сообщения всем игрокам"""
    session = Session()
    try:
        players = session.query(Player).filter_by(is_banned=False).all()
        for player in players:
            try:
                vk.messages.send(
                    user_id=player.vk_id,
                    message=text,
                    random_id=random.randint(1, 10**9)
                )
            except:
                pass
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

def give_resources(vk, user_id, data):
    """Выдать ресурсы игроку"""
    print(f"📌 Выдача ресурсов. Ввод: {data}")
    
    parts = data.split()
    if not parts:
        send_msg(vk, user_id, "❌ Неверный формат!\nПример: `123456 золото:500 кристаллы:10`", get_admin_keyboard())
        return
    
    # Поиск ID игрока
    player_id = None
    for part in parts:
        if part.lower().startswith("id"):
            try:
                player_id = int(part[2:])
                break
            except:
                pass
        elif part.isdigit():
            player_id = int(part)
            break
    
    if not player_id:
        send_msg(vk, user_id, f"❌ Не указан ID игрока! В вводе: {parts}\nПример: `123456 золото:500`", get_admin_keyboard())
        return
    
    print(f"📌 Найден ID игрока: {player_id}")
    
    # Поиск золота и кристаллов
    gold = 0
    crystals = 0
    reason = "Выдача от администратора"
    
    for part in parts:
        part_lower = part.lower()
        if part_lower.startswith("золото:") or part_lower.startswith("gold:"):
            try:
                gold = int(part.split(":")[1])
                print(f"📌 Золото: {gold}")
            except:
                pass
        elif part_lower.startswith("кристаллы:") or part_lower.startswith("crystals:"):
            try:
                crystals = int(part.split(":")[1])
                print(f"📌 Кристаллы: {crystals}")
            except:
                pass
        elif part_lower.startswith("причина:"):
            reason = part.split(":", 1)[1]
            print(f"📌 Причина: {reason}")
    
    if gold == 0 and crystals == 0:
        send_msg(vk, user_id, "❌ Укажите, что выдавать! Пример: `123456 золото:500 кристаллы:10`", get_admin_keyboard())
        return
    
    session = Session()
    try:
        player = session.query(Player).filter_by(vk_id=player_id).first()
        
        if not player:
            send_msg(vk, user_id, f"❌ Игрок с ID {player_id} не найден в базе!", get_admin_keyboard())
            return
        
        print(f"📌 Игрок найден: {player.nick}")
        print(f"📌 Было: золото={player.gold}, кристаллы={player.crystals}")
        
        # Выдаём ресурсы
        if gold > 0:
            player.gold += gold
        if crystals > 0:
            player.crystals += crystals
        
        player.total_power = calculate_power(player)
        
        # Логируем
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
        
        print(f"📌 Стало: золото={player_gold}, кристаллы={player_crystals}")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при выдаче: {e}")
        send_msg(vk, user_id, f"❌ Ошибка при выдаче: {e}", get_admin_keyboard())
        return
    finally:
        session.close()
    
    # Уведомление админу
    send_msg(vk, user_id, f"""
✅ **ВЫДАНО!**

👤 Игрок: {player_nick} (ID: {player_vk_id})
💰 +{gold} золота
💎 +{crystals} кристаллов
📝 Причина: {reason}

Теперь у игрока:
💰 Золото: {player_gold}
💎 Кристаллы: {player_crystals}
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
        print(f"📌 Уведомление отправлено игроку {player_vk_id}")
    except Exception as e:
        print(f"❌ Не удалось отправить уведомление игроку: {e}")

def mass_gift(vk, user_id, data):
    """Массовая выдача ресурсов всем игрокам"""
    print(f"📌 Массовая выдача. Ввод: {data}")
    
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
        send_msg(vk, user_id, "❌ Укажите, что выдавать!\nПример: `золото:500 кристаллы:10`", get_admin_keyboard())
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
        print(f"📌 Выдано {count} игрокам: +{gold}🪙 +{crystals}💎")
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка при массовой выдаче: {e}")
        send_msg(vk, user_id, f"❌ Ошибка: {e}", get_admin_keyboard())
        return
    finally:
        session.close()
    
    # Оповещение всех игроков
    send_all_message(vk, f"""
🎉 **МАССОВЫЙ ПОДАРОК!**

💰 +{gold} золота
💎 +{crystals} кристаллов

📝 Причина: {reason}

Спасибо, что играете с нами! 🏰
""")
    
    send_msg(vk, user_id, f"""
✅ **МАССОВЫЙ ПОДАРОК ВЫПОЛНЕН!**

Получили: {count} игроков
💰 +{gold} золота
💎 +{crystals} кристаллов
📝 Причина: {reason}
""", get_admin_keyboard())

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
    
    if text == "🚪 Выйти" or text == "Выйти":
        del admin_sessions[user_id]
        send_msg(vk, user_id, "👋 Вы вышли из админ-панели.")
        return True
    
    elif text == "📊 Статистика" or text == "Статистика":
        show_statistics(vk, user_id)
        return True
    
    elif text == "🎁 Выдать ресурсы" or text == "Выдать ресурсы":
        admin_sessions[user_id]["state"] = "give"
        send_msg(vk, user_id, """
🎁 **ВЫДАТЬ РЕСУРСЫ**

Введите ID игрока и что выдать:

📌 **Формат:**
`ID золото:XXX кристаллы:YYY причина:Текст`

📌 **Примеры:**
• `123456 золото:500`
• `123456 кристаллы:10`
• `123456 золото:500 кристаллы:10 причина:Бонус`

💡 ID игрока можно найти в ссылке на профиль vk.com/id123456
""", get_back_keyboard())
        return True
    
    elif text == "🎉 Массовый подарок" or text == "Массовый подарок":
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
    
    elif text == "📢 Вывести топ-15" or text == "Вывести топ-15":
        post_top15(vk, user_id)
        return True
    
    elif admin_sessions.get(user_id, {}).get("state") == "give":
        give_resources(vk, user_id, text)
        admin_sessions[user_id]["state"] = None
        send_msg(vk, user_id, "🛠️ Админ-панель", get_admin_keyboard())
        return True
    
    elif admin_sessions.get(user_id, {}).get("state") == "mass":
        mass_gift(vk, user_id, text)
        admin_sessions[user_id]["state"] = None
        send_msg(vk, user_id, "🛠️ Админ-панель", get_admin_keyboard())
        return True
    
    elif text == "⬅️ Назад":
        send_msg(vk, user_id, "🛠️ Админ-панель", get_admin_keyboard())
        return True
    
    return False
