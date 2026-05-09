# statistics.py
from datetime import datetime, timedelta
from sqlalchemy import func
from database import Session, Player, BattleLog

def get_player_stats(vk_id):
    """Получить расширенную статистику игрока"""
    session = Session()
    try:
        player = session.query(Player).filter_by(vk_id=vk_id).first()
        if not player:
            return None
        
        stats = {
            "nick": player.nick,
            "level": player.level,
            "total_power": player.total_power,
            "gold": player.gold,
            "crystals": player.crystals,
            "total_battles": player.total_battles,
            "total_wins": player.total_wins,
            "win_rate": round(player.total_wins / max(1, player.total_battles) * 100, 1),
            "monsters_killed": player.monsters_killed,
            "referral_count": player.referral_count,
            "castle_level": player.castle_level,
            "pet_level": player.pet_level,
            "gear": {
                "sword": player.sword_level,
                "shield": player.shield_level,
                "armor": player.armor_level,
                "boots": player.boots_level
            }
        }
        
        daily_battles = []
        for i in range(7):
            day_start = datetime.utcnow() - timedelta(days=i+1)
            day_end = datetime.utcnow() - timedelta(days=i)
            count = session.query(BattleLog).filter(
                BattleLog.player_id == vk_id,
                BattleLog.created_at.between(day_start, day_end)
            ).count()
            daily_battles.append(count)
        stats["daily_battles"] = list(reversed(daily_battles))
        
        return stats
    finally:
        session.close()

def format_player_stats(stats):
    """Форматирование статистики для отправки"""
    if not stats:
        return "❌ Персонаж не найден!"
    
    hp_percent = int(stats["total_power"] / max(1, stats["level"] * 100) * 100)
    hp_bar = "█" * (hp_percent // 10) + "░" * (10 - hp_percent // 10)
    
    days = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]
    battle_chart = ""
    max_battles = max(stats["daily_battles"]) if stats["daily_battles"] else 1
    for i, count in enumerate(stats["daily_battles"]):
        bar_len = min(10, int(count / max(1, max_battles) * 10))
        bar = "▰" * bar_len + "▱" * (10 - bar_len)
        battle_chart += f"{days[i]} {bar} {count}\n"
    
    text = f"""
📊 **СТАТИСТИКА ПЕРСОНАЖА**

━━━━━━━━━━━━━━━━━━━━━━
👤 **{stats['nick']}**
🏆 Уровень: {stats['level']}
💪 Сила: {stats['total_power']}
📈 Прогресс: [{hp_bar}] {hp_percent}%

━━━━━━━━━━━━━━━━━━━━━━
**💰 РЕСУРСЫ:**
🪙 Золото: {stats['gold']:,}
💎 Кристаллы: {stats['crystals']:,}

━━━━━━━━━━━━━━━━━━━━━━
**⚔️ БОЕВАЯ СТАТИСТИКА:**
• Всего боёв: {stats['total_battles']}
• Побед: {stats['total_wins']}
• Проигрышей: {stats['total_battles'] - stats['total_wins']}
• Процент побед: {stats['win_rate']}%
• Убито монстров: {stats['monsters_killed']}

━━━━━━━━━━━━━━━━━━━━━━
**🏰 ПРОГРЕСС:**
• Ратуша: {stats['castle_level']} ур. (+{stats['castle_level'] * 20} HP)
• Питомец: {stats['pet_level']} ур.
• 👥 Привел друзей: {stats['referral_count']}

━━━━━━━━━━━━━━━━━━━━━━
**🗡️ ЭКИПИРОВКА:**
🗡️ Меч: {stats['gear']['sword']}/10
🛡️ Щит: {stats['gear']['shield']}/10
🧥 Броня: {stats['gear']['armor']}/10
👢 Сапоги: {stats['gear']['boots']}/10

━━━━━━━━━━━━━━━━━━━━━━
**📅 АКТИВНОСТЬ ЗА НЕДЕЛЮ:**
{battle_chart}
    """
    return text
