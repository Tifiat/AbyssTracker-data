import os

from build_common import (
    weapon_type_short,
    textmap_lookup,
    fallback_name_from_weapon_icon,
)


TECHNICAL_ICON_SUBSTRINGS = (
    "_Template",
    "FishingRod",
)


def is_candidate_weapon(w: dict) -> bool:
    _id = w.get("id")
    icon = w.get("icon")
    wt = w.get("weaponType")
    rank_level = w.get("rankLevel")

    if not _id or not icon:
        return False

    icon = str(icon)
    if not icon.startswith("UI_EquipIcon_"):
        return False

    for bad in TECHNICAL_ICON_SUBSTRINGS:
        if bad in icon:
            return False

    try:
        rarity = int(rank_level)
    except Exception:
        return False

    if rarity < 1 or rarity > 5:
        return False

    weapon_type = weapon_type_short(str(wt))
    if not weapon_type:
        return False

    return True


def build_weapons(weapons: list, textmap: dict) -> dict:
    out = {}
    weapons_sorted = sorted(weapons, key=lambda x: int(x.get("id", 0) or 0))

    for w in weapons_sorted:
        if not is_candidate_weapon(w):
            continue

        _id = int(w.get("id"))
        icon = str(w.get("icon"))
        weapon_type = weapon_type_short(str(w.get("weaponType")))
        rarity = int(w.get("rankLevel"))
        name_hash = w.get("nameTextMapHash")

        name = textmap_lookup(textmap, name_hash) or fallback_name_from_weapon_icon(icon)

        out[str(_id)] = {
            "name": name,
            "rarity": rarity,
            "type": weapon_type,
            "icon_name": icon,
        }

    return out
