# bot.py
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import random
import re
from datetime import datetime, timedelta
from sqlalchemy import func
from threading import Thread
import time

# Импорт модулей проекта
from config import VK_TOKEN, GROUP_ID, ADMIN_IDS, ADMIN_PASSWORD, DATABASE_URL
from database import (
    Session, Player, AdminTransaction, BattleLog, PvPLog,
    get_player, create_player, update_player, get_all_players, get_top_players, get_player_rank,
    init_db
)
from models import (
    MONSTERS, get_random_monster, get_gear_hp_bonus, get_upgrade_cost, get_castle_upgrade_cost,
    calculate_power, update_power, get_pet_bonus, get_pet_upgrade_cost, 
    CHESTS, get_chest_cooldown_info, open_chest_with_timer,
    EPIC_BOSSES, get_epic_boss, get_epic_boss_limit_info, update_epic_boss_attack,
    RANDOM_EVENTS, trigger_random_event
)

# Импорт админ-панели и статистики
from admin_panel import handle_admin_command, admin_login, promocodes, use_promocode
from statistics import get_player_stats, format_player_stats

# ==================== ИНИЦИАЛИЗАЦИЯ БОТА ====================
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# Глобальные состояния
active_battles = {}
active_pvp = {}
pending_refs = {}

# ==================== КЛАВИАТУРЫ ====================
def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⚔️ В бой", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🛡️ Экипировка", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🏰 Ратуша", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("👫 Друзья", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🏆 Рейтинг", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🎒 Инвентарь", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🐉 Питомец", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🎁 Сундуки", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🔥 Эпические боссы", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button("📜 Квесты", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("⚔️ Арена", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🏆 Достижения", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("📊 Моя статистика", color=VkKeyboardColor.PRIMARY)
    return keyboard

def get_back_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_battle_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⚔️ Атаковать", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🏃 Сбежать", color=VkKeyboardColor.NEGATIVE)
    return keyboard

def get_locations_keyboard():
    keyboard = VkKeyboard(one_time=False)
    for location in MONSTERS.keys():
        keyboard.add_button(location, color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

def get_gear_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("🔨 Улучшить меч", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🔨 Улучшить щит", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🔨 Улучшить броню", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🔨 Улучшить сапоги", color=VkKeyboardColor.PRIMARY)
    return keyboard

def get_castle_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🔨 Улучшить ратушу", color=VkKeyboardColor.POSITIVE)
    return keyboard

def get_pvp_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🎲 Случайный бой", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🏆 Рейтинг арены", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    return keyboard

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def send_msg(user_id, text, keyboard=None):
    try:
        vk.messages.send(
            user_id=user_id,
            message=text,
            random_id=random.randint(1, 10**9),
            keyboard=keyboard.get_keyboard() if keyboard else None
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def send_all_message(text):
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

def update_player_nick_from_vk(user_id, player):
    try:
        user_info = vk.users.get(user_ids=user_id, fields="first_name")
        if user_info and len(user_info) > 0:
            current_vk_name = user_info[0].get("first_name", "")
            if current_vk_name and current_vk_name != player.nick:
                player.nick = current_vk_name
                update_player(player)
                print(f"✅ Обновлён ник {user_id}: {current_vk_name}")
                return True
    except Exception as e:
        print(f"Ошибка получения имени из VK: {e}")
    return False

# ==================== ОСНОВНЫЕ ЭКРАНЫ ====================
def show_main_menu(user_id):
    player = get_player(user_id)
    if not player:
        send_msg(user_id, "❌ Персонаж не найден! Напишите /start для создания персонажа.")
        return

    update_player_nick_from_vk(user_id, player)

    player.last_login = datetime.utcnow()
    player.total_power = calculate_power(player)
    update_player(player)

    gear_bonus = get_gear_hp_bonus(player)

    text = f"""
🏰 Средневековье

━━━━━━━━━━━━━━━━━━━━━━
❤️ Hp: {player.hp}/{player.max_hp}
⚔️ Сила атаки: {player.attack_power}
🛡️ Защита: {player.defense}
🏰 Ратуша: {player.castle_level} ур. (+{player.castle_level * 20} Hp)
🛡️ Экипировка: +{gear_bonus} Hp
━━━━━━━━━━━━━━━━━━━━━━
💰 Золото: {player.gold}
💎 Кристаллы: {player.crystals}
━━━━━━━━━━━━━━━━━━━━━━
📍 Сила (рейтинг): {player.total_power}
👥 Привел друзей: {player.referral_count}
🏆 Уровень: {player.level}
📊 Опыт: {player.exp}/{player.exp_to_next}
    """
    send_msg(user_id, text, get_main_keyboard())

# ==================== ПИТОМЕЦ ====================
def show_pet(user_id, player):
    pet_bonus = get_pet_bonus(player.pet_level)
    next_cost = get_pet_upgrade_cost(player.pet_level)
    can_upgrade = player.gold >= next_cost and player.pet_level < 10
    
    collection_text = ""
    if player.last_pet_collected:
        hours_passed = (datetime.utcnow() - player.last_pet_collected).total_seconds() / 3600
        if hours_passed >= 1:
            gold_gain = int(pet_bonus["gold_per_hour"] * min(hours_passed, 24))
            exp_gain = int(pet_bonus["exp_per_hour"] * min(hours_passed, 24))
            crystal_gain = 1 if random.random() < pet_bonus["crystal_chance"] * min(hours_passed, 24) else 0
            
            player.gold += gold_gain
            player.exp += exp_gain
            player.crystals += crystal_gain
            player.last_pet_collected = datetime.utcnow()
            update_player(player)
            update_power(user_id)
            collection_text = f"\n\n🎁 Собрано: +{gold_gain}🪙, +{exp_gain}📈, +{crystal_gain}💎"
    
    text = f"""
🐉 Твой питомец (Дракончик, ур.{player.pet_level}/10)

━━━━━━━━━━━━━━━━━━━━━━
📊 Бонусы питомца:
   ➤ 🪙 +{pet_bonus['gold_per_hour']} золота в час
   ➤ 📈 +{pet_bonus['exp_per_hour']} опыта в час
   ➤ 💎 +{int(pet_bonus['crystal_chance']*100)}% шанс на кристалл

📈 Уровень: {player.pet_level}/10
🍖 Голод: {player.pet_hunger}%
   ➤ Кормление: 100🪙 → +20% сытости +10 опыта питомцу

🔨 Улучшить до {player.pet_level + 1} уровня: {next_cost}🪙
   ➤ Увеличивает все бонусы{collection_text}
    """
    
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🍖 Покормить", color=VkKeyboardColor.SECONDARY)
    if can_upgrade:
        keyboard.add_button("🔨 Улучшить", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    
    send_msg(user_id, text, keyboard)

def feed_pet(user_id):
    player = get_player(user_id)
    if not player:
        return
    
    if player.gold >= 100:
        player.gold -= 100
        player.pet_hunger = min(100, player.pet_hunger + 20)
        player.pet_exp += 10
        
        exp_needed = player.pet_level * 50
        if player.pet_exp >= exp_needed and player.pet_level < 10:
            player.pet_exp -= exp_needed
            player.pet_level += 1
            send_msg(user_id, f"🎉 Твой дракончик повысил уровень до {player.pet_level}!")
        
        update_player(player)
        update_power(user_id)
        send_msg(user_id, f"🍖 Ты покормил дракончика! Сытость +20%, опыт питомца +10")
    else:
        send_msg(user_id, "❌ Недостаточно золота для кормления! Нужно 100🪙")
    
    show_pet(user_id, player)

def upgrade_pet(user_id):
    player = get_player(user_id)
    if not player:
        return
    
    if player.pet_level >= 10:
        send_msg(user_id, "❌ Питомец уже достиг максимального уровня!")
        show_pet(user_id, player)
        return
    
    cost = get_pet_upgrade_cost(player.pet_level)
    if player.gold >= cost:
        player.gold -= cost
        player.pet_level += 1
        update_player(player)
        update_power(user_id)
        send_msg(user_id, f"✅ Дракончик улучшен до {player.pet_level} уровня!\n📊 Бонусы увеличены!")
    else:
        send_msg(user_id, f"❌ Недостаточно золота! Нужно {cost}🪙")
    
    show_pet(user_id, player)

# ==================== СУНДУКИ ====================
def show_chests(user_id, player):
    text = "🎁 СУНДУКИ И ЛУТБОКСЫ\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for chest_type, chest in CHESTS.items():
        cooldown_info = get_chest_cooldown_info(chest_type, player)
        
        if cooldown_info and cooldown_info["available"]:
            status = "✅ ГОТОВ"
        elif cooldown_info:
            hours = int(cooldown_info["remaining"])
            minutes = int((cooldown_info["remaining"] - hours) * 60)
            status = f"⏰ {hours}ч {minutes}мин"
        else:
            status = "❌ ОШИБКА"
        
        text += f"{chest_type}\n"
        text += f"   ➤ Перезарядка: {chest['cooldown_hours']} ч\n"
        text += f"   ➤ Статус: {status}\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━━\n💡 Нажми на кнопку, чтобы открыть сундук!"
    
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🎲 Открыть обычный", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🎲 Открыть редкий", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🎲 Открыть эпический", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🎲 Открыть легендарный", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    
    send_msg(user_id, text, keyboard)

def open_chest_command(user_id, chest_name):
    player = get_player(user_id)
    if not player:
        return
    
    chest_map = {
        "обычный": "🟢 Обычный",
        "редкий": "🔵 Редкий",
        "эпический": "🟣 Эпический",
        "легендарный": "🟠 Легендарный"
    }
    
    chest_key = chest_map.get(chest_name.lower())
    if not chest_key or chest_key not in CHESTS:
        send_msg(user_id, "❌ Неизвестный тип сундука! Доступны: обычный, редкий, эпический, легендарный")
        return
    
    rewards, error = open_chest_with_timer(chest_key, player)
    
    if error:
        send_msg(user_id, error, get_back_keyboard())
        return
    
    if rewards:
        rewards_text = "\n".join(rewards)
    else:
        rewards_text = "😢 В сундуке ничего не оказалось..."
    
    text = f"""
🎉 ТЫ ОТКРЫЛ {chest_key} СУНДУК!

━━━━━━━━━━━━━━━━━━━━━━
{rewards_text}
━━━━━━━━━━━━━━━━━━━━━━
    """
    send_msg(user_id, text, get_back_keyboard())

# ==================== РАТУША И ЭКИПИРОВКА ====================
def show_castle(user_id, player):
    next_cost = get_castle_upgrade_cost(player.castle_level)
    can_upgrade = next_cost and player.crystals >= next_cost and player.castle_level < 15

    text = f"""
🏰 Ратуша (уровень {player.castle_level})

━━━━━━━━━━━━━━━━━━━━━━
❤️ Бонус к Hp: +{player.castle_level * 20}
📊 Следующий уровень: {player.castle_level + 1}
   ➕ Бонус: +20 Hp

💎 Стоимость улучшения: {next_cost if next_cost else 'Достигнут максимум'} кристаллов

━━━━━━━━━━━━━━━━━━━━━━
💰 Твои кристаллы: {player.crystals}
    """

    keyboard = get_castle_keyboard()
    if not can_upgrade:
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)

    send_msg(user_id, text, keyboard)

def upgrade_castle(user_id):
    player = get_player(user_id)
    if not player:
        return

    cost = get_castle_upgrade_cost(player.castle_level)
    if not cost:
        send_msg(user_id, "❌ Ратуша уже достигла максимального уровня (15)!")
        show_castle(user_id, player)
        return

    if player.crystals >= cost:
        player.crystals -= cost
        player.castle_level += 1
        player.max_hp += 20
        player.hp = player.max_hp
        update_player(player)
        update_power(user_id)
        send_msg(user_id, f"✅ Ратуша улучшена до {player.castle_level} уровня!\n❤️ Максимальное Hp увеличено на 20!")
    else:
        send_msg(user_id, f"❌ Недостаточно кристаллов! Нужно {cost}💎, у тебя {player.crystals}💎")

    show_castle(user_id, player)

def show_gear(user_id, player):
    hp_bonus = get_gear_hp_bonus(player)

    text = f"""
🛡️ Твоя экипировка

━━━━━━━━━━━━━━━━━━━━━━
🗡️ Меч (ур.{player.sword_level}/10)
   ➕ Hp: +{10 + (player.sword_level-1)*5}
   🔨 Улучшить: {get_upgrade_cost(player.sword_level, 'sword')}🪙

🛡️ Щит (ур.{player.shield_level}/10)
   ➕ Hp: +{10 + (player.shield_level-1)*5}
   🔨 Улучшить: {get_upgrade_cost(player.shield_level, 'shield')}🪙

🧥 Броня (ур.{player.armor_level}/10)
   ➕ Hp: +{15 + (player.armor_level-1)*7}
   🔨 Улучшить: {get_upgrade_cost(player.armor_level, 'armor')}🪙

👢 Сапоги (ур.{player.boots_level}/10)
   ➕ Hp: +{5 + (player.boots_level-1)*3}
   🔨 Улучшить: {get_upgrade_cost(player.boots_level, 'boots')}🪙

━━━━━━━━━━━━━━━━━━━━━━
📊 Всего от экипировки: +{hp_bonus} Hp
💰 Твое золото: {player.gold}
    """
    send_msg(user_id, text, get_gear_keyboard())

def upgrade_gear_item(user_id, item_type):
    player = get_player(user_id)
    if not player:
        return

    attr_name = f"{item_type}_level"
    current_level = getattr(player, attr_name)

    if current_level >= 10:
        send_msg(user_id, f"❌ {item_type.upper()} уже достиг максимального уровня (10)!")
        show_gear(user_id, player)
        return

    cost = get_upgrade_cost(current_level, item_type)

    if player.gold >= cost:
        player.gold -= cost
        setattr(player, attr_name, current_level + 1)
        player.max_hp = 100 + player.castle_level * 20 + get_gear_hp_bonus(player)
        player.hp = player.max_hp
        update_player(player)
        update_power(user_id)
        send_msg(user_id, f"✅ {item_type.upper()} улучшен до {current_level + 1} уровня!")
    else:
        send_msg(user_id, f"❌ Недостаточно золота! Нужно {cost}🪙, у тебя {player.gold}🪙")

    show_gear(user_id, player)

# ==================== БОИ В ЛОКАЦИЯХ ====================
def show_locations(user_id, player):
    text = "🗺️ Доступные локации\n━━━━━━━━━━━━━━━━━━━━━━\n\n"

    for location, data in MONSTERS.items():
        min_power = data["min_power"]
        status = "✅" if player.total_power >= min_power else "⚠️"
        text += f"{status} {location}\n   ➤ Требуется силы: {min_power}\n\n"

    send_msg(user_id, text, get_locations_keyboard())

def start_battle(user_id, location):
    player = get_player(user_id)
    if not player:
        return

    if location not in MONSTERS:
        send_msg(user_id, "❌ Неизвестная локация!")
        return

    min_power = MONSTERS[location]["min_power"]
    if player.total_power < min_power:
        send_msg(user_id, f"⚠️ Твоя сила ({player.total_power}) ниже требуемой ({min_power}) для этой локации!\nПрокачайся в более легких местах.", get_back_keyboard())
        return

    monster = get_random_monster(location)
    
    # Рандомное событие
    event_text, monster = trigger_random_event(player, monster)
    event_message = "\n\n" + event_text if event_text else ""

    active_battles[user_id] = {
        "monster": monster,
        "monster_name": monster["name"],
        "monster_current_hp": monster["hp"],
        "monster_max_hp": monster["hp"],
        "monster_attack": monster["attack"],
        "location": location,
        "exp_reward": monster["exp"],
        "gold_min": monster["gold_min"],
        "gold_max": monster["gold_max"],
        "crystal_chance": monster["crystal_chance"],
        "is_epic": False
    }

    text = f"""
⚔️ Начало боя!

━━━━━━━━━━━━━━━━━━━━━━
📍 Локация: {location}
😈 Противник: {monster['name']}
❤️ Hp врага: {monster['hp']}
⚔️ Сила врага: {monster['attack']}

━━━━━━━━━━━━━━━━━━━━━━
Твои параметры:
❤️ Hp: {player.hp}/{player.max_hp}
⚔️ Сила атаки: {player.attack_power}
🛡️ Защита: {player.defense}

💡 Атакуй, чтобы победить!{event_message}
    """
    send_msg(user_id, text, get_battle_keyboard())

def continue_battle(user_id):
    player = get_player(user_id)
    battle = active_battles.get(user_id)

    if not battle or battle.get("is_epic"):
        return False

    if player.hp <= 0:
        del active_battles[user_id]
        send_msg(user_id, "💀 Ты слишком слаб для боя... Восстанови Hp в главном меню.", get_back_keyboard())
        show_main_menu(user_id)
        return True

    monster = battle["monster"]

    player_damage = max(1, player.attack_power - 5 + random.randint(-3, 8))
    if random.random() < 0.1:
        player_damage = int(player_damage * 1.5)
        crit_text = "💥 Критический удар! "
    else:
        crit_text = ""

    # Учитываем временные бонусы от событий
    if "temp_attack_bonus" in monster:
        player_damage += monster["temp_attack_bonus"]
    if "temp_defense_bonus" in monster:
        # Временно увеличиваем защиту на этот раунд
        player.defense += monster["temp_defense_bonus"]

    battle["monster_current_hp"] -= player_damage
    monster_damage = max(1, battle["monster_attack"] - player.defense + random.randint(-3, 5))
    player.hp -= monster_damage
    update_player(player)

    text = f"""
⚔️ Раунд!

━━━━━━━━━━━━━━━━━━━━━━
{crit_text}🗡️ Ты нанес: {player_damage} урона
😈 Враг нанес: {monster_damage} урона

━━━━━━━━━━━━━━━━━━━━━━
❤️ Твой Hp: {max(0, player.hp)}/{player.max_hp}
❤️ Hp врага: {max(0, battle['monster_current_hp'])}/{battle['monster_max_hp']}
    """

    if battle["monster_current_hp"] <= 0:
        gold_earned = random.randint(battle["gold_min"], battle["gold_max"])
        exp_earned = battle["exp_reward"]
        crystal_earned = 1 if random.random() < battle["crystal_chance"] else 0

        player.gold += gold_earned
        player.exp += exp_earned
        player.crystals += crystal_earned
        player.total_battles += 1
        player.total_wins += 1
        player.monsters_killed += 1

        level_up_text = ""
        while player.exp >= player.exp_to_next:
            player.exp -= player.exp_to_next
            player.level += 1
            player.attack_power += 3
            player.max_hp += 10
            player.hp = player.max_hp
            player.exp_to_next = player.level * 100
            level_up_text += f"\n\n🌟 Повышение уровня! Ты теперь {player.level} уровень! 🌟\n❤️ Hp +10, ⚔️ Сила +3"

        update_player(player)
        update_power(user_id)

        session = Session()
        battle_log = BattleLog(
            player_id=user_id,
            monster_name=battle["monster_name"],
            result="win",
            gold_earned=gold_earned,
            crystals_earned=crystal_earned
        )
        session.add(battle_log)
        session.commit()
        session.close()

        text += f"""
\n🎉 Победа!

━━━━━━━━━━━━━━━━━━━━━━
🏆 Награда:
💰 +{gold_earned} золота
📈 +{exp_earned} опыта
💎 +{crystal_earned} кристаллов{level_up_text}
        """
        del active_battles[user_id]
        send_msg(user_id, text, get_back_keyboard())
        show_main_menu(user_id)

    elif player.hp <= 0:
        player.hp = player.max_hp // 2
        update_player(player)

        session = Session()
        battle_log = BattleLog(
            player_id=user_id,
            monster_name=battle["monster_name"],
            result="loss",
            gold_earned=0,
            crystals_earned=0
        )
        session.add(battle_log)
        session.commit()
        session.close()

        text += f"""
\n💀 Поражение!

Ты пал в бою... Восстановлено 50% Hp.
        """
        del active_battles[user_id]
        send_msg(user_id, text, get_back_keyboard())
        show_main_menu(user_id)
    else:
        update_player(player)
        send_msg(user_id, text, get_battle_keyboard())
        return True
    
    return True

# ==================== ЭПИЧЕСКИЕ БОССЫ ====================
def show_epic_bosses_menu(user_id, player):
    text = "🔥 **ЭПИЧЕСКИЕ БОССЫ** 🔥\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for boss_name, boss in EPIC_BOSSES.items():
        limit_info = get_epic_boss_limit_info(boss_name, player)
        required = boss["required_power"]
        status = "✅" if player.total_power >= required else "⚠️"
        
        text += f"{boss_name}\n"
        text += f"   ➤ ❤️ HP: {boss['hp']} | ⚔️ Атака: {boss['attack']}\n"
        text += f"   ➤ Требуется силы: {required}\n"
        text += f"   ➤ Атак сегодня: {limit_info['used']}/{limit_info['limit']}\n"
        text += f"   ➤ Статус: {status}\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━━━\n"
    text += "⚔️ Нажми на кнопку с боссом, чтобы атаковать!\n"
    
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🧟 Гнилой тролль", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🧙 Лих-некромант", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🐉 Древний дракон", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)
    
    send_msg(user_id, text, keyboard)

def start_epic_boss_battle(user_id, boss_name):
    player = get_player(user_id)
    if not player:
        return
    
    boss_name_normalized = None
    for name in EPIC_BOSSES.keys():
        if boss_name in name or name in boss_name:
            boss_name_normalized = name
            break
    
    if not boss_name_normalized:
        send_msg(user_id, "❌ Неизвестный босс! Доступны:\n• Гнилой тролль\n• Лих-некромант\n• Древний дракон")
        return
    
    boss_data = EPIC_BOSSES[boss_name_normalized]
    
    if player.total_power < boss_data["required_power"]:
        send_msg(user_id, f"⚠️ Твоя сила ({player.total_power}) ниже требуемой ({boss_data['required_power']}) для этого босса!\nПрокачайся и возвращайся!", get_back_keyboard())
        return
    
    limit_info = get_epic_boss_limit_info(boss_name_normalized, player)
    if not limit_info["available"]:
        send_msg(user_id, f"❌ Ты уже использовал все {limit_info['limit']} атаки на {boss_name_normalized} сегодня!\n💡 Жди завтра!", get_back_keyboard())
        return
    
    if player.hp <= 0:
        send_msg(user_id, "💀 Твоё HP слишком низкое! Восстанови его в главном меню.", get_back_keyboard())
        return
    
    active_battles[user_id] = {
        "monster": get_epic_boss(boss_name_normalized),
        "monster_name": boss_name_normalized,
        "monster_current_hp": boss_data["hp"],
        "monster_max_hp": boss_data["hp"],
        "monster_attack": boss_data["attack"],
        "monster_defense": boss_data["defense"],
        "is_epic": True,
        "exp_reward": boss_data["exp"],
        "gold_min": boss_data["gold_min"],
        "gold_max": boss_data["gold_max"],
        "crystals_min": boss_data["crystals_min"],
        "crystals_max": boss_data["crystals_max"],
        "rewards": boss_data["rewards"]
    }
    
    text = f"""
🔥 **ЭПИЧЕСКАЯ БИТВА!** 🔥

━━━━━━━━━━━━━━━━━━━━━━
🐉 **Босс:** {boss_name_normalized}
❤️ **HP босса:** {boss_data['hp']}
⚔️ **Сила босса:** {boss_data['attack']}
🛡️ **Защита босса:** {boss_data['defense']}

━━━━━━━━━━━━━━━━━━━━━━
Твои параметры:
❤️ **HP:** {player.hp}/{player.max_hp}
⚔️ **Сила атаки:** {player.attack_power}
🛡️ **Защита:** {player.defense}

━━━━━━━━━━━━━━━━━━━━━━
⚔️ **ПОБЕДИ И ПОЛУЧИ ЭПИЧЕСКУЮ НАГРАДУ!**
💡 У тебя осталось {limit_info['remaining']-1} атак на сегодня
    """
    send_msg(user_id, text, get_battle_keyboard())

def continue_epic_battle(user_id):
    player = get_player(user_id)
    battle = active_battles.get(user_id)
    
    if not battle or not battle.get("is_epic"):
        return False
    
    if player.hp <= 0:
        del active_battles[user_id]
        send_msg(user_id, "💀 Ты слишком слаб для этого босса... Восстанови HP.", get_back_keyboard())
        show_epic_bosses_menu(user_id, player)
        return True
    
    monster = battle["monster"]
    
    player_damage = max(1, player.attack_power - monster.get("defense", 10) + random.randint(-5, 15))
    if random.random() < 0.1:
        player_damage = int(player_damage * 1.5)
        crit_text = "💥 КРИТИЧЕСКИЙ УДАР! "
    else:
        crit_text = ""
    
    battle["monster_current_hp"] -= player_damage
    monster_damage = max(1, battle["monster_attack"] - player.defense + random.randint(-5, 15))
    player.hp -= monster_damage
    update_player(player)
    
    text = f"""
⚔️ **РАУНД!**

━━━━━━━━━━━━━━━━━━━━━━
{crit_text}🗡️ Ты нанес: {player_damage} урона
😈 Босс нанес: {monster_damage} урона

━━━━━━━━━━━━━━━━━━━━━━
❤️ Твой HP: {max(0, player.hp)}/{player.max_hp}
❤️ HP босса: {max(0, battle['monster_current_hp'])}/{battle['monster_max_hp']}
    """
    
    if battle["monster_current_hp"] <= 0:
        gold_earned = random.randint(battle["gold_min"], battle["gold_max"])
        crystals_earned = random.randint(battle["crystals_min"], battle["crystals_max"])
        exp_earned = battle["exp_reward"]
        
        player.gold += gold_earned
        player.crystals += crystals_earned
        player.exp += exp_earned
        player.total_battles += 1
        player.total_wins += 1
        player.monsters_killed += 1
        
        update_epic_boss_attack(battle["monster_name"], player)
        
        extra_rewards = []
        
        if random.random() < battle["rewards"].get("item_upgrade", 0):
            items = ["sword", "shield", "armor", "boots"]
            item = random.choice(items)
            attr_name = f"{item}_level"
            current = getattr(player, attr_name)
            if current < 10:
                setattr(player, attr_name, current + 1)
                player.max_hp = 100 + player.castle_level * 20 + get_gear_hp_bonus(player)
                player.hp = player.max_hp
                extra_rewards.append(f"✨ {item.upper()} +1 уровень! (бесплатно)")
        
        if random.random() < battle["rewards"].get("legendary_chance", 0):
            extra_rewards.append("🌟 **ЛЕГЕНДАРНЫЙ ПРЕДМЕТ!** +10 к атаке, +50 HP, +5 к защите")
            player.attack_power += 10
            player.max_hp += 50
            player.defense += 5
            player.hp = player.max_hp
        
        if battle["rewards"].get("rare_title", False) and random.random() < 0.2:
            extra_rewards.append("👑 **ТИТУЛ 'ИСТРЕБИТЕЛЬ НЕЧИСТИ'!** +5% к силе")
            player.attack_power = int(player.attack_power * 1.05)
        
        if battle["rewards"].get("legendary_title", False) and random.random() < 0.1:
            extra_rewards.append("👑 **ЛЕГЕНДАРНЫЙ ТИТУЛ 'ДРАКОНОБОРЕЦ'!** +15% ко всем характеристикам")
            player.attack_power = int(player.attack_power * 1.15)
            player.max_hp = int(player.max_hp * 1.15)
            player.defense = int(player.defense * 1.15)
            player.hp = player.max_hp
        
        level_up_text = ""
        while player.exp >= player.exp_to_next:
            player.exp -= player.exp_to_next
            player.level += 1
            player.attack_power += 3
            player.max_hp += 10
            player.hp = player.max_hp
            player.exp_to_next = player.level * 100
            level_up_text += f"\n\n🌟 **ПОВЫШЕНИЕ УРОВНЯ!** Ты теперь {player.level} уровень! 🌟\n❤️ HP +10, ⚔️ Сила +3"
        
        update_player(player)
        update_power(user_id)
        
        extra_text = "\n".join(extra_rewards) if extra_rewards else "✨ Ничего особенного"
        
        text += f"""
\n🎉 **ЭПИЧЕСКАЯ ПОБЕДА!**

━━━━━━━━━━━━━━━━━━━━━━
🏆 **НАГРАДА:**
💰 +{gold_earned} золота
💎 +{crystals_earned} кристаллов
📈 +{exp_earned} опыта
🎁 {extra_text}{level_up_text}
        """
        
        del active_battles[user_id]
        send_msg(user_id, text, get_back_keyboard())
        show_main_menu(user_id)
        return True
        
    elif player.hp <= 0:
        player.hp = player.max_hp // 2
        update_player(player)
        
        text += f"""
\n💀 **ПОРАЖЕНИЕ!**

Ты пал в бою с эпическим боссом... Восстановлено 50% HP.
        """
        del active_battles[user_id]
        send_msg(user_id, text, get_back_keyboard())
        show_epic_bosses_menu(user_id, player)
        return True
    else:
        update_player(player)
        send_msg(user_id, text, get_battle_keyboard())
        return True
    
    return False

# ==================== РЕЙТИНГ ====================
def show_rating(user_id, player):
    session = Session()
    top_players = session.query(Player).filter_by(is_banned=False).order_by(Player.total_power.desc()).limit(15).all()

    text = "💪 Топ-15 сильнейших игроков\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, p in enumerate(top_players, 1):
        medal = medals[i-1] if i <= 5 else f"{i}."
        link = f"[id{p.vk_id}|{p.nick}]"
        text += f"{medal} {link}\n   ➤ Сила: {p.total_power} | Уровень: {p.level} | Класс: {p.class_type}\n\n"

    all_players = session.query(Player).filter_by(is_banned=False).order_by(Player.total_power.desc()).all()
    rank = next((i for i, p in enumerate(all_players, 1) if p.vk_id == user_id), 0)
    session.close()

    text += f"━━━━━━━━━━━━━━━━━━━━━━\n📍 Твоё место: #{rank} из {len(all_players)}\n💪 Твоя сила: {player.total_power}"

    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("👥 Топ друзей", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)

    send_msg(user_id, text, keyboard)

def show_friends_rating(user_id, player):
    session = Session()
    friends = session.query(Player).filter_by(referrer_id=user_id).order_by(Player.total_power.desc()).all()

    if not friends:
        send_msg(user_id, "👥 У тебя пока нет приглашённых друзей.\n\nПриглашай друзей и получай кристаллы!", get_back_keyboard())
        return

    text = "👥 Топ приглашённых друзей\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, friend in enumerate(friends[:15], 1):
        link = f"[id{friend.vk_id}|{friend.nick}]"
        text += f"{i}. {link}\n   ➤ Сила: {friend.total_power} | Уровень: {friend.level}\n\n"

    session.close()
    send_msg(user_id, text, get_back_keyboard())

# ==================== ИНВЕНТАРЬ И МАГАЗИН ====================
def show_inventory(user_id, player):
    text = f"""
🎒 Инвентарь

━━━━━━━━━━━━━━━━━━━━━━
🧪 Малое зелье Hp
   ➤ Восстанавливает 50 Hp в бою
   ➤ В наличии: {player.small_potions}

💎 Великое зелье Hp
   ➤ Восстанавливает 120 Hp в бою
   ➤ В наличии: {player.big_potions}

━━━━━━━━━━━━━━━━━━━━━━
💡 Используй зелье командой:
   • "зелье малое"
   • "зелье великое"
    """

    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("🛒 Магазин", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)

    send_msg(user_id, text, keyboard)

def use_potion(user_id, potion_type):
    player = get_player(user_id)
    if not player:
        return

    if potion_type == "small":
        if player.small_potions <= 0:
            send_msg(user_id, "❌ У тебя нет малых зелий! Купи их в магазине.")
            return
        if player.hp >= player.max_hp:
            send_msg(user_id, "❌ У тебя уже полное Hp!")
            return

        heal = 50
        player.hp = min(player.max_hp, player.hp + heal)
        player.small_potions -= 1
        update_player(player)
        send_msg(user_id, f"🧪 Ты использовал малое зелье и восстановил {heal} Hp!\n❤️ Текущее Hp: {player.hp}/{player.max_hp}")

    elif potion_type == "big":
        if player.big_potions <= 0:
            send_msg(user_id, "❌ У тебя нет великих зелий! Купи их в магазине.")
            return
        if player.hp >= player.max_hp:
            send_msg(user_id, "❌ У тебя уже полное Hp!")
            return

        heal = 120
        player.hp = min(player.max_hp, player.hp + heal)
        player.big_potions -= 1
        update_player(player)
        send_msg(user_id, f"💎 Ты использовал великое зелье и восстановил {heal} Hp!\n❤️ Текущее Hp: {player.hp}/{player.max_hp}")

def show_shop(user_id, player):
    text = f"""
🛒 Лавка торговца

━━━━━━━━━━━━━━━━━━━━━━
🧪 Малое зелье Hp
   ➤ Восстанавливает 50 Hp
   ➤ Цена: 100 золота

💎 Великое зелье Hp
   ➤ Восстанавливает 120 Hp
   ➤ Цена: 250 золота

━━━━━━━━━━━━━━━━━━━━━━
💰 Твое золото: {player.gold}

Для покупки напиши:
• "купить малое"
• "купить великое"
    """
    send_msg(user_id, text, get_back_keyboard())

def buy_item(user_id, item):
    player = get_player(user_id)
    if not player:
        return

    if item == "small":
        cost = 100
        if player.gold >= cost:
            player.gold -= cost
            player.small_potions += 1
            update_player(player)
            send_msg(user_id, f"✅ Ты купил малое зелье за 100 золота!\n🧪 Теперь у тебя {player.small_potions} малых зелий.")
        else:
            send_msg(user_id, f"❌ Недостаточно золота! Нужно 100🪙, у тебя {player.gold}🪙")

    elif item == "big":
        cost = 250
        if player.gold >= cost:
            player.gold -= cost
            player.big_potions += 1
            update_player(player)
            send_msg(user_id, f"✅ Ты купил великое зелье за 250 золота!\n💎 Теперь у тебя {player.big_potions} великих зелий.")
        else:
            send_msg(user_id, f"❌ Недостаточно золота! Нужно 250🪙, у тебя {player.gold}🪙")

def show_quests(user_id, player):
    text = """
📜 Ежедневные квесты

━━━━━━━━━━━━━━━━━━━━━━
⚔️ Сразиться 5 раз → +200 золота
🏆 Победить 3 врага → +1 кристалл
👫 Пригласить друга → +5 кристаллов

━━━━━━━━━━━━━━━━━━━━━━
💡 Квесты обновляются каждый день!
    """
    send_msg(user_id, text, get_back_keyboard())

# ==================== PVP АРЕНА ====================
def show_arena(user_id, player):
    text = f"""
⚔️ Pvp арена

━━━━━━━━━━━━━━━━━━━━━━
🏆 Твой рейтинг: {player.total_power // 10} (бронзовая лига)

📊 Статистика арены:
   ➤ Всего боёв: {player.total_battles}
   ➤ Побед: {player.total_wins}
   ➤ Проигрышей: {player.total_battles - player.total_wins}

💡 Случайный бой подберёт соперника по силе!
    """
    send_msg(user_id, text, get_pvp_keyboard())

def start_pvp_battle(user_id):
    player = get_player(user_id)
    if not player:
        return

    if player.hp < player.max_hp * 0.5:
        send_msg(user_id, "⚠️ Твоё Hp слишком низкое для PvP! Восстанови его с помощью зелий.")
        return

    session = Session()
    min_power = player.total_power - 50
    max_power = player.total_power + 50

    opponent = session.query(Player).filter(
        Player.vk_id != user_id,
        Player.is_banned == False,
        Player.total_power.between(min_power, max_power),
        Player.hp > Player.max_hp * 0.5
    ).first()

    if not opponent:
        opponent = session.query(Player).filter(
            Player.vk_id != user_id,
            Player.is_banned == False,
            Player.hp > Player.max_hp * 0.5
        ).order_by(func.abs(Player.total_power - player.total_power)).first()

    session.close()

    if not opponent:
        send_msg(user_id, "❌ Не удалось найти соперника! Попробуй позже.")
        return

    active_pvp[user_id] = {
        "opponent_id": opponent.vk_id,
        "opponent_nick": opponent.nick,
        "opponent_hp": opponent.hp,
        "opponent_max_hp": opponent.max_hp,
        "opponent_power": opponent.attack_power,
        "opponent_defense": opponent.defense,
        "player_hp_start": player.hp
    }

    text = f"""
⚔️ PvP бой найден!

━━━━━━━━━━━━━━━━━━━━━━
👤 Твой противник: {opponent.nick}
💪 Сила противника: {opponent.total_power}
❤️ Hp противника: {opponent.hp}/{opponent.max_hp}
⚔️ Атака противника: {opponent.attack_power}
🛡️ Защита противника: {opponent.defense}

━━━━━━━━━━━━━━━━━━━━━━
Твои параметры:
❤️ Hp: {player.hp}/{player.max_hp}
⚔️ Атака: {player.attack_power}
🛡️ Защита: {player.defense}

💡 Атакуй, чтобы победить!
    """

    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("⚔️ Атаковать в pvp", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🏃 Отступить", color=VkKeyboardColor.NEGATIVE)
    send_msg(user_id, text, keyboard)

def continue_pvp(user_id):
    player = get_player(user_id)
    pvp = active_pvp.get(user_id)

    if not pvp:
        send_msg(user_id, "❌ Нет активного PvP боя!", get_back_keyboard())
        show_main_menu(user_id)
        return

    opponent = get_player(pvp["opponent_id"])
    if not opponent:
        del active_pvp[user_id]
        send_msg(user_id, "❌ Противник больше не в игре!")
        show_main_menu(user_id)
        return

    player_damage = max(1, player.attack_power - opponent.defense + random.randint(-3, 8))
    if random.random() < 0.1:
        player_damage = int(player_damage * 1.5)

    opponent_damage = max(1, pvp["opponent_power"] - player.defense + random.randint(-3, 5))

    pvp["opponent_hp"] -= player_damage
    player.hp -= opponent_damage

    update_player(player)
    opponent.hp = pvp["opponent_hp"]
    update_player(opponent)

    text = f"""
⚔️ PvP раунд!

━━━━━━━━━━━━━━━━━━━━━━
🗡️ Ты нанес: {player_damage} урона
😈 Противник нанес: {opponent_damage} урона

━━━━━━━━━━━━━━━━━━━━━━
❤️ Твой Hp: {max(0, player.hp)}/{player.max_hp}
❤️ Hp {opponent.nick}: {max(0, pvp['opponent_hp'])}/{pvp['opponent_max_hp']}
    """

    if pvp["opponent_hp"] <= 0:
        player.crystals += 1
        player.total_wins += 1
        update_player(player)
        update_power(user_id)

        send_msg(opponent.vk_id, f"💀 Ты проиграл в PvP бою против {player.nick}!")

        text += f"\n\n🎉 Победа в PvP!\n\n🏆 Награда:\n💰 +50 золота\n💎 +1 кристалл"

        session = Session()
        pvp_log = PvPLog(
            player_id=user_id,
            opponent_id=opponent.vk_id,
            result="win",
            rating_change=10
        )
        session.add(pvp_log)
        session.commit()
        session.close()

        del active_pvp[user_id]
        send_msg(user_id, text, get_back_keyboard())
        show_main_menu(user_id)

    elif player.hp <= 0:
        opponent.crystals += 1
        update_player(opponent)

        send_msg(opponent.vk_id, f"🎉 Ты победил в PvP бою против {player.nick}!")

        text += f"\n\n💀 Поражение в PvP!\n\nУдачи в следующий раз!"

        session = Session()
        pvp_log = PvPLog(
            player_id=user_id,
            opponent_id=opponent.vk_id,
            result="loss",
            rating_change=0
        )
        session.add(pvp_log)
        session.commit()
        session.close()

        del active_pvp[user_id]
        send_msg(user_id, text, get_back_keyboard())
        show_main_menu(user_id)
    else:
        update_player(player)
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button("⚔️ Атаковать в pvp", color=VkKeyboardColor.POSITIVE)
        keyboard.add_button("🏃 Отступить", color=VkKeyboardColor.NEGATIVE)
        send_msg(user_id, text, keyboard)

# ==================== ДОСТИЖЕНИЯ ====================
def show_achievements(user_id, player):
    achievements_data = [
        {"name": "🥇 Первый бой", "desc": "Одержать первую победу", "completed": player.total_wins >= 1, "reward": "50 золота"},
        {"name": "⚔️ Воин", "desc": "Выиграть 10 боёв", "completed": player.total_wins >= 10, "reward": "100 золота"},
        {"name": "🏅 Герой", "desc": "Выиграть 50 боёв", "completed": player.total_wins >= 50, "reward": "5 кристаллов"},
        {"name": "👑 Легенда", "desc": "Выиграть 100 боёв", "completed": player.total_wins >= 100, "reward": "15 кристаллов"},
        {"name": "🔨 Кузнец", "desc": "Улучшить любой предмет до 5 уровня", "completed": any(l >= 5 for l in [player.sword_level, player.shield_level, player.armor_level, player.boots_level]), "reward": "100 золота"},
        {"name": "🏰 Строитель", "desc": "Улучшить ратушу до 5 уровня", "completed": player.castle_level >= 5, "reward": "10 кристаллов"},
        {"name": "🤝 Дружный", "desc": "Привести 3 друзей", "completed": player.referral_count >= 3, "reward": "20 кристаллов"},
        {"name": "💰 Богач", "desc": "Накопить 5000 золота", "completed": player.gold >= 5000, "reward": "5 кристаллов"},
        {"name": "💎 Коллекционер", "desc": "Накопить 50 кристаллов", "completed": player.crystals >= 50, "reward": "1000 золота"},
        {"name": "🐉 Драконовод", "desc": "Прокачать питомца до 5 уровня", "completed": player.pet_level >= 5, "reward": "10 кристаллов"},
    ]

    completed_count = sum(1 for a in achievements_data if a["completed"])

    text = f"🏆 Достижения ({completed_count}/{len(achievements_data)})\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for ach in achievements_data:
        status = "✅" if ach["completed"] else "🔒"
        text += f"{status} {ach['name']}\n   ➤ {ach['desc']}\n   ➤ Награда: {ach['reward']}\n\n"

    send_msg(user_id, text, get_back_keyboard())

# ==================== ДРУЗЬЯ ====================
def show_friends(user_id, player):
    ref_link = f"https://vk.me/public{GROUP_ID}?ref={player.referral_code}"
    
    text = f"""
👫 Пригласить друга

━━━━━━━━━━━━━━━━━━━━━━
Твоя реферальная ссылка:
{ref_link}

━━━━━━━━━━━━━━━━━━━━━━
📊 Твоя статистика:
👥 Привел друзей: {player.referral_count}
💎 Получено кристаллов: +{player.referral_count * 50}

━━━━━━━━━━━━━━━━━━━━━━
🎁 Награды за друзей:
1 друг → 50💎
3 друга → 100💎 + эпический меч
5 друзей → 200💎 + легендарный дракон-помощник

💡 Поделись ссылкой с друзьями и получай кристаллы!
    """

    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Скопировать ссылку", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("⬅️ Назад", color=VkKeyboardColor.SECONDARY)

    send_msg(user_id, text, keyboard)

# ==================== РЕГИСТРАЦИЯ ====================
def register_player(user_id, first_name, ref_code=None):
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("⚔️ Рыцарь", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🏹 Лучник", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("🔮 Маг", color=VkKeyboardColor.PRIMARY)

    if ref_code:
        print(f"📌 Регистрация с реферальным кодом: {ref_code}")
        pending_refs[user_id] = ref_code

    send_msg(user_id, f"""
✨ Добро пожаловать в Средневековье, {first_name}!

Выбери свой класс:

━━━━━━━━━━━━━━━━━━━━━━
⚔️ Рыцарь
   ➤ Много Hp, крепкая броня
   ➤ Начальные параметры: Hp 130, Сила 15

🏹 Лучник
   ➤ Высокий урон, критические удары
   ➤ Начальные параметры: Hp 100, Сила 22

🔮 Маг
   ➤ Магические атаки
   ➤ Начальные параметры: Hp 110, Сила 18
    """, keyboard)

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================
def handle_message(user_id, text, first_name):
    if text.lower() == "/start" or text.lower() == "начать":
        player = get_player(user_id)
        if not player:
            ref_code = None
            parts = text.split()
            if len(parts) > 1:
                ref_code = parts[1]
                print(f"🔗 Найден реферальный код: {ref_code}")
            register_player(user_id, first_name, ref_code)
        else:
            show_main_menu(user_id)
        return

    player = get_player(user_id)
    if player and player.is_banned:
        send_msg(user_id, "🚫 Ваш аккаунт заблокирован администратором!")
        return

    # Промокоды
    if text.lower().startswith("промокод"):
        code = text[8:].strip()
        use_promocode(vk, user_id, code)
        return

    if text == "/admin" and user_id in ADMIN_IDS:
        admin_login(vk, user_id)
        return
    
    if user_id in ADMIN_IDS and handle_admin_command(vk, user_id, text):
        return

    if not player:
        if text in ["⚔️ Рыцарь", "🏹 Лучник", "🔮 Маг", "Рыцарь", "Лучник", "Маг"]:
            class_type = text.replace("⚔️ ", "").replace("🏹 ", "").replace("🔮 ", "")
            ref_code = pending_refs.pop(user_id, None)
            create_player(user_id, first_name, class_type, ref_code)
            show_main_menu(user_id)
        else:
            send_msg(user_id, "❌ Сначала зарегистрируйся! Напиши /start")
        return

    # Навигация
    if text == "⬅️ Назад":
        show_main_menu(user_id)
        return

    # Ратуша
    if text == "🏰 Ратуша" or text == "Ратуша":
        show_castle(user_id, player)
        return
    if text == "🔨 Улучшить ратушу":
        upgrade_castle(user_id)
        return

    # Экипировка
    if text == "🛡️ Экипировка" or text == "Экипировка":
        show_gear(user_id, player)
        return
    if text == "🔨 Улучшить меч":
        upgrade_gear_item(user_id, "sword")
        return
    if text == "🔨 Улучшить щит":
        upgrade_gear_item(user_id, "shield")
        return
    if text == "🔨 Улучшить броню":
        upgrade_gear_item(user_id, "armor")
        return
    if text == "🔨 Улучшить сапоги":
        upgrade_gear_item(user_id, "boots")
        return

    # Бои в локациях
    if text == "⚔️ В бой" or text == "В бой":
        show_locations(user_id, player)
        return
    if text in MONSTERS.keys():
        start_battle(user_id, text)
        return
    if text == "⚔️ Атаковать" and user_id in active_battles:
        if active_battles[user_id].get("is_epic"):
            continue_epic_battle(user_id)
        else:
            continue_battle(user_id)
        return

    # Эпические боссы
    if text == "🔥 Эпические боссы" or text == "Эпические боссы":
        show_epic_bosses_menu(user_id, player)
        return
    
    if text in ["🧟 Гнилой тролль", "Гнилой тролль"]:
        start_epic_boss_battle(user_id, "Гнилой тролль")
        return
    if text in ["🧙 Лих-некромант", "Лих-некромант"]:
        start_epic_boss_battle(user_id, "Лих-некромант")
        return
    if text in ["🐉 Древний дракон", "Древний дракон"]:
        start_epic_boss_battle(user_id, "Древний дракон")
        return

    # PvP
    if text == "⚔️ Атаковать в pvp" and user_id in active_pvp:
        continue_pvp(user_id)
        return

    # Побег/отступление
    if text in ("🏃 Сбежать", "Сбежать", "🏃 Отступить", "Отступить"):
        if user_id in active_battles:
            del active_battles[user_id]
            send_msg(user_id, "🏃 Ты сбежал с поля боя!", get_back_keyboard())
        elif user_id in active_pvp:
            del active_pvp[user_id]
            send_msg(user_id, "🏃 Ты отступил с арены!", get_back_keyboard())
        else:
            send_msg(user_id, "🏃 Ты отступил!", get_back_keyboard())
        show_main_menu(user_id)
        return

    # Рейтинг
    if text == "🏆 Рейтинг" or text == "Рейтинг":
        show_rating(user_id, player)
        return
    if text == "👥 Топ друзей":
        show_friends_rating(user_id, player)
        return

    # Инвентарь
    if text == "🎒 Инвентарь" or text == "Инвентарь":
        show_inventory(user_id, player)
        return
    if text == "🛒 Магазин" or text == "Магазин":
        show_shop(user_id, player)
        return

    # Питомец
    if text == "🐉 Питомец" or text == "Питомец":
        show_pet(user_id, player)
        return
    if text == "🍖 Покормить":
        feed_pet(user_id)
        return
    if text == "🔨 Улучшить":
        upgrade_pet(user_id)
        return

    # Сундуки
    if text == "🎁 Сундуки" or text == "Сундуки":
        show_chests(user_id, player)
        return
    if text.startswith("открыть") or text.startswith("🎲 Открыть"):
        chest_type = text.replace("открыть", "").replace("🎲 Открыть", "").strip()
        open_chest_command(user_id, chest_type)
        return

    # Квесты
    if text == "📜 Квесты" or text == "Квесты":
        show_quests(user_id, player)
        return

    # Арена
    if text == "⚔️ Арена" or text == "Арена":
        show_arena(user_id, player)
        return
    if text == "🎲 Случайный бой":
        start_pvp_battle(user_id)
        return

    # Достижения
    if text == "🏆 Достижения" or text == "Достижения":
        show_achievements(user_id, player)
        return

    # Друзья
    if text == "👫 Друзья" or text == "Друзья":
        show_friends(user_id, player)
        return

    # Моя статистика
    if text == "📊 Моя статистика" or text == "Моя статистика":
        stats = get_player_stats(user_id)
        send_msg(user_id, format_player_stats(stats), get_back_keyboard())
        return

    # Зелья
    if text.lower() in ("зелье малое", "малое зелье"):
        use_potion(user_id, "small")
        return
    if text.lower() in ("зелье великое", "великое зелье"):
        use_potion(user_id, "big")
        return

    # Покупки
    if text.lower() in ("купить малое", "купить малое зелье"):
        buy_item(user_id, "small")
        return
    if text.lower() in ("купить великое", "купить великое зелье"):
        buy_item(user_id, "big")
        return

    # Неизвестная команда
    send_msg(user_id, "❓ Неизвестная команда! Используй кнопки меню.")

# ==================== ЗАПУСК БОТА ====================
def main():
    print("🤖 Бот 'Средневековье' запущен!")
    print(f"📊 База данных: {DATABASE_URL}")
    print("🟢 Ожидание сообщений...")

    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            if event.message and event.message.text:
                user_id = event.message.from_id
                text = event.message.text
                first_name = event.message.get("from", {}).get("first_name", "Игрок")
                try:
                    handle_message(user_id, text, first_name)
                except Exception as e:
                    print(f"Ошибка обработки сообщения от {user_id}: {e}")
                    send_msg(user_id, "❌ Произошла ошибка. Попробуйте позже.")

if __name__ == "__main__":
    main()
