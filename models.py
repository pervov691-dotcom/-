# models.py
import random
from datetime import datetime

# ==================== ДАННЫЕ О МОНСТРАХ ====================
MONSTERS = {
    "Лесная тропа": {
        "monsters": [
            {"name": "Гоблин", "hp": 40, "attack": 10, "exp": 40, "gold_min": 30, "gold_max": 60, "crystal_chance": 0.01},
            {"name": "Лесной волк", "hp": 50, "attack": 12, "exp": 50, "gold_min": 40, "gold_max": 70, "crystal_chance": 0.01}
        ],
        "min_power": 0
    },
    "Темный лес": {
        "monsters": [
            {"name": "Лесной тролль", "hp": 90, "attack": 20, "exp": 80, "gold_min": 100, "gold_max": 180, "crystal_chance": 0.03},
            {"name": "Леший", "hp": 100, "attack": 18, "exp": 90, "gold_min": 120, "gold_max": 200, "crystal_chance": 0.03}
        ],
        "min_power": 80
    },
    "Горный перевал": {
        "monsters": [
            {"name": "Горный великан", "hp": 180, "attack": 35, "exp": 150, "gold_min": 250, "gold_max": 400, "crystal_chance": 0.05},
            {"name": "Каменный голем", "hp": 200, "attack": 30, "exp": 160, "gold_min": 280, "gold_max": 420, "crystal_chance": 0.05}
        ],
        "min_power": 150
    },
    "Заброшенный замок": {
        "monsters": [
            {"name": "Призрак", "hp": 250, "attack": 40, "exp": 200, "gold_min": 400, "gold_max": 600, "crystal_chance": 0.08},
            {"name": "Скелет-воин", "hp": 280, "attack": 45, "exp": 220, "gold_min": 450, "gold_max": 650, "crystal_chance": 0.08}
        ],
        "min_power": 220
    },
    "Драконьи горы": {
        "monsters": [
            {"name": "Молодой дракон", "hp": 400, "attack": 60, "exp": 350, "gold_min": 700, "gold_max": 1000, "crystal_chance": 0.12},
            {"name": "Огненный змей", "hp": 450, "attack": 65, "exp": 380, "gold_min": 750, "gold_max": 1100, "crystal_chance": 0.12}
        ],
        "min_power": 300
    },
    "Цитадель тьмы": {
        "monsters": [
            {"name": "Древний демон", "hp": 650, "attack": 85, "exp": 500, "gold_min": 1200, "gold_max": 2000, "crystal_chance": 0.20},
            {"name": "Повелитель тьмы", "hp": 800, "attack": 100, "exp": 600, "gold_min": 1500, "gold_max": 2500, "crystal_chance": 0.25}
        ],
        "min_power": 500
    }
}

# ==================== ФУНКЦИИ МОНСТРОВ ====================
def get_random_monster(location):
    if location not in MONSTERS:
        location = "Лесная тропа"
    monsters = MONSTERS[location]["monsters"]
    monster = random.choice(monsters).copy()
    monster["current_hp"] = monster["hp"]
    return monster

# ==================== ЭКИПИРОВКА ====================
def get_gear_hp_bonus(player):
    bonus = 0
    bonus += 10 + (player.sword_level - 1) * 5
    bonus += 10 + (player.shield_level - 1) * 5
    bonus += 15 + (player.armor_level - 1) * 7
    bonus += 5 + (player.boots_level - 1) * 3
    return bonus

def get_upgrade_cost(item_level, item_type):
    base_cost = 100
    multiplier = {"sword": 1.0, "shield": 1.2, "armor": 1.5, "boots": 0.8}
    return int(base_cost * multiplier.get(item_type, 1.0) * item_level)

def get_castle_upgrade_cost(castle_level):
    costs = [5, 8, 10, 15, 20, 30, 40, 55, 75, 100, 130, 160, 200, 250, 300]
    if castle_level <= len(costs):
        return costs[castle_level - 1]
    return None

# ==================== СИЛА ПЕРСОНАЖА ====================
def calculate_power(player):
    hp_power = player.max_hp // 10
    atk_power = player.attack_power * 2
    def_power = int(player.defense * 1.5)
    castle_power = player.castle_level * 15
    gear_power = (player.sword_level + player.shield_level + 
                  player.armor_level + player.boots_level) * 5
    
    total = hp_power + atk_power + def_power + castle_power + gear_power
    return total

def update_power(vk_id):
    try:
        from database import get_player, update_player
        player = get_player(vk_id)
        if player:
            player.total_power = calculate_power(player)
            update_player(player)
            return True
    except Exception as e:
        print(f"Ошибка обновления силы: {e}")
        return False

# ==================== ПИТОМЕЦ ====================
def get_pet_bonus(pet_level):
    return {
        "gold_per_hour": 50 + (pet_level - 1) * 10,
        "crystal_chance": 0.01 + (pet_level - 1) * 0.002,
        "exp_per_hour": 5 + (pet_level - 1) * 2
    }

def get_pet_upgrade_cost(pet_level):
    return pet_level * 100

# ==================== СУНДУКИ ====================
CHESTS = {
    "🟢 Обычный": {
        "cost": 0,
        "cooldown_hours": 1,
        "gold": (50, 150),
        "crystals": (0, 1, 0.3),
        "small_potion": (0, 1, 0.3),
        "big_potion": (0, 1, 0.05)
    },
    "🔵 Редкий": {
        "cost": 0,
        "cooldown_hours": 3,
        "gold": (200, 500),
        "crystals": (1, 3, 0.7),
        "small_potion": (1, 2, 0.7),
        "big_potion": (0, 1, 0.2),
        "upgrade_item": 0.1
    },
    "🟣 Эпический": {
        "cost": 0,
        "cooldown_hours": 5,
        "gold": (500, 1000),
        "crystals": (3, 10, 0.9),
        "small_potion": (2, 3, 1.0),
        "big_potion": (1, 2, 0.5),
        "upgrade_item": 0.3,
        "legendary_chance": 0.05
    },
    "🟠 Легендарный": {
        "cost": 0,
        "cooldown_hours": 7,
        "gold": (1000, 3000),
        "crystals": (10, 30, 1.0),
        "small_potion": (3, 5, 1.0),
        "big_potion": (2, 3, 1.0),
        "upgrade_item": 0.8,
        "legendary_chance": 0.3,
        "title": True
    }
}

def get_chest_cooldown_info(chest_type, player):
    chest = CHESTS.get(chest_type)
    if not chest:
        return None
    
    chest_key = chest_type.replace("🟢 ", "").replace("🔵 ", "").replace("🟣 ", "").replace("🟠 ", "").lower()
    
    if chest_key == "обычный":
        last_field = "last_common_chest"
    elif chest_key == "редкий":
        last_field = "last_rare_chest"
    elif chest_key == "эпический":
        last_field = "last_epic_chest"
    elif chest_key == "легендарный":
        last_field = "last_legendary_chest"
    else:
        return None
    
    last_time = getattr(player, last_field, None)
    
    if last_time:
        time_passed = (datetime.utcnow() - last_time).total_seconds() / 3600
        if time_passed >= chest["cooldown_hours"]:
            return {"available": True, "remaining": 0}
        else:
            remaining = chest["cooldown_hours"] - time_passed
            return {"available": False, "remaining": remaining}
    else:
        return {"available": True, "remaining": 0}

def open_chest_with_timer(chest_type, player):
    from database import update_player
    
    chest = CHESTS.get(chest_type)
    if not chest:
        return None, "❌ Неизвестный тип сундука!"
    
    chest_key = chest_type.replace("🟢 ", "").replace("🔵 ", "").replace("🟣 ", "").replace("🟠 ", "").lower()
    
    if chest_key == "обычный":
        last_field = "last_common_chest"
    elif chest_key == "редкий":
        last_field = "last_rare_chest"
    elif chest_key == "эпический":
        last_field = "last_epic_chest"
    elif chest_key == "легендарный":
        last_field = "last_legendary_chest"
    else:
        return None, "❌ Неизвестный тип сундука!"
    
    last_time = getattr(player, last_field, None)
    
    if last_time:
        time_passed = (datetime.utcnow() - last_time).total_seconds() / 3600
        if time_passed < chest["cooldown_hours"]:
            remaining = chest["cooldown_hours"] - time_passed
            hours = int(remaining)
            minutes = int((remaining - hours) * 60)
            return None, f"⏰ Сундук ещё не готов! Осталось: {hours}ч {minutes}мин"
    
    setattr(player, last_field, datetime.utcnow())
    
    rewards = []
    
    gold_earned = random.randint(chest["gold"][0], chest["gold"][1])
    player.gold += gold_earned
    rewards.append(f"💰 +{gold_earned} золота")
    
    if len(chest["crystals"]) == 3:
        if random.random() < chest["crystals"][2]:
            crystals_earned = random.randint(chest["crystals"][0], chest["crystals"][1])
            player.crystals += crystals_earned
            rewards.append(f"💎 +{crystals_earned} кристаллов")
    else:
        crystals_earned = random.randint(chest["crystals"][0], chest["crystals"][1])
        player.crystals += crystals_earned
        rewards.append(f"💎 +{crystals_earned} кристаллов")
    
    if len(chest["small_potion"]) == 3:
        if random.random() < chest["small_potion"][2]:
            potion_earned = random.randint(chest["small_potion"][0], chest["small_potion"][1])
            player.small_potions += potion_earned
            rewards.append(f"🧪 +{potion_earned} малое зелье")
    else:
        potion_earned = random.randint(chest["small_potion"][0], chest["small_potion"][1])
        player.small_potions += potion_earned
        rewards.append(f"🧪 +{potion_earned} малое зелье")
    
    if len(chest["big_potion"]) == 3:
        if random.random() < chest["big_potion"][2]:
            big_potion_earned = random.randint(chest["big_potion"][0], chest["big_potion"][1])
            player.big_potions += big_potion_earned
            rewards.append(f"💊 +{big_potion_earned} великое зелье")
    else:
        big_potion_earned = random.randint(chest["big_potion"][0], chest["big_potion"][1])
        player.big_potions += big_potion_earned
        rewards.append(f"💊 +{big_potion_earned} великое зелье")
    
    if random.random() < chest.get("upgrade_item", 0):
        items = ["sword", "shield", "armor", "boots"]
        item = random.choice(items)
        attr_name = f"{item}_level"
        current = getattr(player, attr_name)
        if current < 10:
            setattr(player, attr_name, current + 1)
            player.max_hp = 100 + player.castle_level * 20 + get_gear_hp_bonus(player)
            player.hp = player.max_hp
            rewards.append(f"✨ {item.upper()} +1 уровень!")
    
    if random.random() < chest.get("legendary_chance", 0):
        rewards.append("🌟 ЛЕГЕНДАРНЫЙ ПРЕДМЕТ! +10 к атаке, +50 HP, +3 к защите навсегда")
        player.attack_power += 10
        player.max_hp += 50
        player.defense += 3
        player.hp = player.max_hp
    
    if chest.get("title", False) and random.random() < 0.1:
        rewards.append("👑 ТИТУЛ 'ИЗБРАННЫЙ'! +10% ко всем характеристикам")
        player.attack_power = int(player.attack_power * 1.1)
        player.max_hp = int(player.max_hp * 1.1)
        player.defense = int(player.defense * 1.1)
        player.hp = player.max_hp
    
    update_player(player)
    update_power(player.vk_id)
    
    return rewards, None

# ==================== ЭПИЧЕСКИЕ БОССЫ ====================
EPIC_BOSSES = {
    "🧟 Гнилой тролль": {
        "hp": 500,
        "attack": 40,
        "defense": 15,
        "exp": 300,
        "gold_min": 500,
        "gold_max": 1000,
        "crystals_min": 2,
        "crystals_max": 5,
        "required_power": 100,
        "daily_limit": 3,
        "rewards": {
            "item_upgrade": 0.3,
            "legendary_chance": 0.05
        }
    },
    "🧙 Лих-некромант": {
        "hp": 1200,
        "attack": 70,
        "defense": 25,
        "exp": 600,
        "gold_min": 1000,
        "gold_max": 2000,
        "crystals_min": 5,
        "crystals_max": 12,
        "required_power": 250,
        "daily_limit": 2,
        "rewards": {
            "item_upgrade": 0.5,
            "legendary_chance": 0.15,
            "rare_title": True
        }
    },
    "🐉 Древний дракон": {
        "hp": 3000,
        "attack": 120,
        "defense": 40,
        "exp": 1500,
        "gold_min": 2000,
        "gold_max": 5000,
        "crystals_min": 15,
        "crystals_max": 30,
        "required_power": 500,
        "daily_limit": 1,
        "rewards": {
            "item_upgrade": 0.8,
            "legendary_chance": 0.5,
            "legendary_title": True
        }
    }
}

def get_epic_boss(boss_name):
    boss = EPIC_BOSSES.get(boss_name, EPIC_BOSSES["🧟 Гнилой тролль"]).copy()
    boss["current_hp"] = boss["hp"]
    return boss

def get_epic_boss_limit_info(boss_name, player):
    boss = EPIC_BOSSES.get(boss_name)
    if not boss:
        return {"available": True, "remaining": 0, "used": 0, "limit": 0}
    
    if "тролль" in boss_name:
        count_field = "boss_troll_attacks"
        last_field = "last_boss_troll_attack"
    elif "лих" in boss_name.lower() or "некромант" in boss_name:
        count_field = "boss_lich_attacks"
        last_field = "last_boss_lich_attack"
    else:
        count_field = "boss_dragon_attacks"
        last_field = "last_boss_dragon_attack"
    
    last_time = getattr(player, last_field, None)
    today = datetime.utcnow().date()
    
    if last_time:
        if last_time.date() == today:
            used = getattr(player, count_field, 0)
            remaining = max(0, boss["daily_limit"] - used)
            return {"available": remaining > 0, "remaining": remaining, "used": used, "limit": boss["daily_limit"]}
    
    return {"available": True, "remaining": boss["daily_limit"], "used": 0, "limit": boss["daily_limit"]}

def update_epic_boss_attack(boss_name, player):
    from database import update_player
    
    if "тролль" in boss_name:
        count_field = "boss_troll_attacks"
        last_field = "last_boss_troll_attack"
    elif "лих" in boss_name.lower() or "некромант" in boss_name:
        count_field = "boss_lich_attacks"
        last_field = "last_boss_lich_attack"
    else:
        count_field = "boss_dragon_attacks"
        last_field = "last_boss_dragon_attack"
    
    today = datetime.utcnow().date()
    last_time = getattr(player, last_field, None)
    
    if not last_time or last_time.date() != today:
        setattr(player, count_field, 1)
        setattr(player, last_field, datetime.utcnow())
    else:
        setattr(player, count_field, getattr(player, count_field, 0) + 1)
    
    update_player(player)

# ==================== РАНДОМНЫЕ СОБЫТИЯ ====================
RANDOM_EVENTS = [
    {
        "name": "🍀 Находка",
        "description": "Ты нашёл забытый кошелёк!",
        "gold_bonus": (50, 150),
        "crystal_bonus": (0, 1),
        "chance": 0.1
    },
    {
        "name": "🧙 Странствующий торговец",
        "description": "Торговец продал тебе редкое зелье дёшево!",
        "small_potion": 1,
        "big_potion": 0,
        "chance": 0.08
    },
    {
        "name": "🛡️ Благословение",
        "description": "Боги временно усилили твою защиту на этот бой!",
        "defense_bonus": 10,
        "chance": 0.05
    },
    {
        "name": "⚔️ Ярость берсерка",
        "description": "Ты впал в ярость! Урон увеличен на время боя!",
        "attack_bonus": 15,
        "chance": 0.05
    },
    {
        "name": "💀 Проклятие",
        "description": "Ты наступил на проклятую ловушку! HP уменьшено на время боя.",
        "hp_penalty": -30,
        "chance": 0.04
    },
    {
        "name": "🐉 След дракона",
        "description": "Ты нашёл чешую дракона!",
        "crystals": (1, 3),
        "chance": 0.03
    }
]

def trigger_random_event(player, monster):
    """Триггер случайного события при входе в бой"""
    event = None
    for e in RANDOM_EVENTS:
        if random.random() < e["chance"]:
            event = e.copy()
            break
    
    if not event:
        return None, monster
    
    event_text = f"✨ **СЛУЧАЙНОЕ СОБЫТИЕ!** ✨\n{event['description']}\n"
    bonuses = []
    
    if "gold_bonus" in event:
        gold = random.randint(event["gold_bonus"][0], event["gold_bonus"][1])
        player.gold += gold
        bonuses.append(f"💰 +{gold} золота")
    
    if "crystal_bonus" in event:
        crystals = random.randint(event["crystal_bonus"][0], event["crystal_bonus"][1])
        player.crystals += crystals
        bonuses.append(f"💎 +{crystals} кристаллов")
    
    if "crystals" in event:
        crystals = random.randint(event["crystals"][0], event["crystals"][1])
        player.crystals += crystals
        bonuses.append(f"💎 +{crystals} кристаллов")
    
    if "small_potion" in event:
        player.small_potions += event["small_potion"]
        bonuses.append(f"🧪 +{event['small_potion']} малое зелье")
    
    if "big_potion" in event:
        player.big_potions += event["big_potion"]
        bonuses.append(f"💊 +{event['big_potion']} великое зелье")
    
    if "attack_bonus" in event:
        monster["temp_attack_bonus"] = event["attack_bonus"]
        bonuses.append(f"⚔️ Урон увеличен на {event['attack_bonus']} в этом бою!")
    
    if "defense_bonus" in event:
        monster["temp_defense_bonus"] = event["defense_bonus"]
        bonuses.append(f"🛡️ Защита увеличена на {event['defense_bonus']} в этом бою!")
    
    if "hp_penalty" in event:
        player.max_hp += event["hp_penalty"]
        player.hp = min(player.hp, player.max_hp)
        bonuses.append(f"❤️ Максимальное HP уменьшено на {-event['hp_penalty']} (только на этот бой)")
    
    event_text += "\n".join(bonuses) if bonuses else "✨ Приятный сюрприз!"
    
    from database import update_player
    update_player(player)
    
    return event_text, monster
