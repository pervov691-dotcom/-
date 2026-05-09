# database.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime
from config import DATABASE_URL

# Создаём подключение к БД
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# ==================== МОДЕЛЬ ИГРОКА ====================
class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, unique=True, nullable=False)
    nick = Column(String(50), default="Воин")
    class_type = Column(String(20), default="Рыцарь")
    
    # Уровень и опыт
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    exp_to_next = Column(Integer, default=100)
    
    # Характеристики
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
    attack_power = Column(Integer, default=15)
    defense = Column(Integer, default=5)
    
    # Ресурсы
    gold = Column(Integer, default=500)
    crystals = Column(Integer, default=5)
    
    # Прогресс
    castle_level = Column(Integer, default=1)
    total_power = Column(Integer, default=0)
    
    # Экипировка
    sword_level = Column(Integer, default=1)
    shield_level = Column(Integer, default=1)
    armor_level = Column(Integer, default=1)
    boots_level = Column(Integer, default=1)
    
    # Инвентарь
    small_potions = Column(Integer, default=3)
    big_potions = Column(Integer, default=1)
    
    # Реферальная система
    referrer_id = Column(Integer, default=None)
    referral_count = Column(Integer, default=0)
    referral_code = Column(String(50), default=None)
    
    # Статистика
    total_battles = Column(Integer, default=0)
    total_wins = Column(Integer, default=0)
    monsters_killed = Column(Integer, default=0)
    
    # Достижения
    achievements = Column(Text, default="[]")
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, default=datetime.utcnow)
    last_daily_quest = Column(DateTime, default=None)
    last_pvp = Column(DateTime, default=None)
    
    # Питомец
    pet_level = Column(Integer, default=1)
    pet_exp = Column(Integer, default=0)
    pet_hunger = Column(Integer, default=100)
    last_pet_collected = Column(DateTime, default=None)
    
    # Таймеры сундуков
    last_common_chest = Column(DateTime, default=None)
    last_rare_chest = Column(DateTime, default=None)
    last_epic_chest = Column(DateTime, default=None)
    last_legendary_chest = Column(DateTime, default=None)
    
    # Эпические боссы (счётчики атак)
    boss_troll_attacks = Column(Integer, default=0)
    boss_lich_attacks = Column(Integer, default=0)
    boss_dragon_attacks = Column(Integer, default=0)
    last_boss_troll_attack = Column(DateTime, default=None)
    last_boss_lich_attack = Column(DateTime, default=None)
    last_boss_dragon_attack = Column(DateTime, default=None)
    
    # Бан
    is_banned = Column(Boolean, default=False)

# ==================== МОДЕЛЬ ТРАНЗАКЦИЙ АДМИНА ====================
class AdminTransaction(Base):
    __tablename__ = 'admin_transactions'
    
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, nullable=False)
    player_id = Column(Integer, nullable=False)
    gold_given = Column(Integer, default=0)
    crystals_given = Column(Integer, default=0)
    reason = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)

# ==================== МОДЕЛЬ ЛОГОВ БОЁВ ====================
class BattleLog(Base):
    __tablename__ = 'battle_logs'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, nullable=False)
    monster_name = Column(String(50))
    result = Column(String(20))
    gold_earned = Column(Integer)
    crystals_earned = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

# ==================== МОДЕЛЬ PVP БОЁВ ====================
class PvPLog(Base):
    __tablename__ = 'pvp_logs'
    
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, nullable=False)
    opponent_id = Column(Integer, nullable=False)
    result = Column(String(20))
    rating_change = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

# ==================== СОЗДАНИЕ ТАБЛИЦ ====================
def init_db():
    Base.metadata.create_all(engine)
    print("✅ База данных инициализирована!")

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С ИГРОКАМИ ====================
def get_player(vk_id):
    session = Session()
    player = session.query(Player).filter_by(vk_id=vk_id).first()
    session.close()
    return player

def create_player(vk_id, nick, class_type, referrer_code=None):
    session = Session()
    
    referrer_id = None
    if referrer_code:
        referrer = session.query(Player).filter_by(referral_code=referrer_code).first()
        if referrer:
            referrer_id = referrer.vk_id
            referrer.referral_count += 1
            referrer.crystals += 50
            session.commit()
            print(f"✅ Реферал: {referrer.nick} получил +50 кристаллов за приглашение {nick}")
    
    player = Player(
        vk_id=vk_id,
        nick=nick,
        class_type=class_type,
        referral_code=f"REF{vk_id}",
        referrer_id=referrer_id
    )
    
    if class_type == "Рыцарь":
        player.max_hp = 130
        player.hp = 130
        player.attack_power = 15
        player.defense = 10
    elif class_type == "Лучник":
        player.max_hp = 100
        player.hp = 100
        player.attack_power = 22
        player.defense = 5
    elif class_type == "Маг":
        player.max_hp = 110
        player.hp = 110
        player.attack_power = 18
        player.defense = 8
    
    session.add(player)
    session.commit()
    
    if referrer_id:
        player.crystals += 50
        session.commit()
    
    session.close()
    return player

def update_player(player):
    session = Session()
    session.merge(player)
    session.commit()
    session.close()

def get_all_players():
    session = Session()
    players = session.query(Player).filter_by(is_banned=False).all()
    session.close()
    return players

def get_top_players(limit=15):
    session = Session()
    top = session.query(Player).filter_by(is_banned=False).order_by(Player.total_power.desc()).limit(limit).all()
    session.close()
    return top

def get_player_rank(vk_id):
    session = Session()
    players = session.query(Player).filter_by(is_banned=False).order_by(Player.total_power.desc()).all()
    rank = next((i for i, p in enumerate(players, 1) if p.vk_id == vk_id), 0)
    session.close()
    return rank

init_db()
