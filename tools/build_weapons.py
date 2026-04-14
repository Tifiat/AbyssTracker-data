import os

from tools.build_common import (
    weapon_type_short,
    textmap_lookup,
    fallback_name_from_weapon_icon,
)

N_WEAPONS = int(os.environ.get("N_WEAPONS", "300"))


def build_weapons(weapons: list, textmap: dict) -> dict:
    out = {}
    weapons_sorted = sorted(weapons, key=lambda x: int(x.get("id", 0) or 0))

    for w in weapons_sorted:
        if len(out) >= N_WEAPONS:
            break

        _id = w.get("id")
        icon = w.get("icon")
        wt = w.get("weaponType")
        rank_level = w.get("rankLevel")
        name_hash = w.get("nameTextMapHash")

        if not _id or not icon:
            continue

        icon = str(icon)
        if not icon.startswith("UI_EquipIcon_"):
            continue

        try:
            rarity = int(rank_level)
        except Exception:
            continue

        weapon_type = weapon_type_short(str(wt))
        if not weapon_type:
            continue

        if rarity < 1 or rarity > 5:
            continue

        name = textmap_lookup(textmap, name_hash) or fallback_name_from_weapon_icon(icon)

        out[str(_id)] = {
            "name": name,
            "rarity": rarity,
            "type": weapon_type,
            "icon_name": icon,
        }

    return out
