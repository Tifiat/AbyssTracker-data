import os
from typing import Optional, Dict, List, Tuple

from tools.build_common import (
    rarity_from_quality,
    weapon_type_short,
    normalize_element,
    textmap_lookup,
    fallback_name_from_avatar_icon,
)

N_CHARACTERS = int(os.environ.get("N_CHARACTERS", "300"))


def build_skill_maps(skill_depots: list, avatar_skills: list) -> Tuple[Dict[int, dict], Dict[int, dict]]:
    depot_map = {}
    skill_map = {}

    for d in skill_depots:
        _id = d.get("id")
        if _id is not None:
            depot_map[int(_id)] = d

    for s in avatar_skills:
        _id = s.get("id")
        if _id is not None:
            skill_map[int(_id)] = s

    return depot_map, skill_map


def get_depot_skill_ids(depot: dict) -> List[int]:
    ids = []

    energy_skill = depot.get("energySkill")
    if energy_skill:
        try:
            ids.append(int(energy_skill))
        except Exception:
            pass

    for skill_id in depot.get("skills", []) or []:
        if skill_id:
            try:
                ids.append(int(skill_id))
            except Exception:
                pass

    for skill_id in depot.get("subSkills", []) or []:
        if skill_id:
            try:
                ids.append(int(skill_id))
            except Exception:
                pass

    return ids


def infer_element_from_skill_depot(skill_depot_id, depot_map: Dict[int, dict], skill_map: Dict[int, dict]) -> Optional[str]:
    if not skill_depot_id:
        return None

    depot = depot_map.get(int(skill_depot_id))
    if not depot:
        return None

    for skill_id in get_depot_skill_ids(depot):
        skill = skill_map.get(skill_id)
        if not skill:
            continue

        elem = normalize_element(skill.get("costElemType"))
        if elem:
            return elem

    return None


def is_candidate_avatar(a: dict) -> bool:
    icon = str(a.get("iconName", ""))
    if not icon.startswith("UI_AvatarIcon_"):
        return False
    if "_Side_" in icon:
        return False

    rarity = rarity_from_quality(str(a.get("qualityType", "")))
    if rarity is None:
        return False

    weapon_type = weapon_type_short(str(a.get("weaponType", "")))
    if not weapon_type:
        return False

    return True


def candidate_score_for_duplicate(a: dict, element: Optional[str], has_textmap_name: bool) -> tuple:
    _id = int(a.get("id", 0) or 0)
    promote_id = int(a.get("avatarPromoteId", 0) or 0)
    feature_tag_group_id = int(a.get("featureTagGroupID", 0) or 0)
    skill_depot_id = int(a.get("skillDepotId", 0) or 0)

    id_suffix = _id % 1000
    depot_prefix = skill_depot_id // 100 if skill_depot_id else 0

    return (
        1 if str(a.get("useType", "")) == "AVATAR_FORMAL" else 0,
        1 if str(a.get("avatarIdentityType", "")) == "AVATAR_IDENTITY_NORMAL" else 0,
        1 if feature_tag_group_id == _id else 0,
        1 if promote_id == id_suffix else 0,
        1 if skill_depot_id and depot_prefix == promote_id else 0,
        1 if element else 0,
        1 if has_textmap_name else 0,
        1 if _id < 10000900 else 0,
        -_id,
    )


def build_characters(avatars: list, textmap: dict, depot_map: Dict[int, dict], skill_map: Dict[int, dict]) -> dict:
    grouped: Dict[str, List[dict]] = {}

    avatars_sorted = sorted(avatars, key=lambda x: int(x.get("id", 0) or 0))

    for a in avatars_sorted:
        if not is_candidate_avatar(a):
            continue

        icon = str(a.get("iconName"))
        if icon == "UI_AvatarIcon_Kate":
            continue

        if icon.startswith("UI_AvatarIcon_Player"):
            continue
        grouped.setdefault(icon, []).append(a)

    selected = []
    for icon_name, group in grouped.items():
        best_entry = None
        best_payload = None
        best_score = None

        for a in group:
            _id = int(a.get("id", 0) or 0)
            rarity = rarity_from_quality(str(a.get("qualityType", "")))
            weapon_type = weapon_type_short(str(a.get("weaponType", "")))
            element = infer_element_from_skill_depot(a.get("skillDepotId"), depot_map, skill_map)

            if rarity is None or not weapon_type or not element:
                continue

            text_name = textmap_lookup(textmap, a.get("nameTextMapHash"))
            name = text_name or fallback_name_from_avatar_icon(icon_name)

            payload = {
                "id": _id,
                "name": name,
                "rarity": rarity,
                "element": element,
                "weapon_type": weapon_type,
                "icon_name": icon_name,
            }

            score = candidate_score_for_duplicate(a, element, has_textmap_name=bool(text_name))

            if best_score is None or score > best_score:
                best_score = score
                best_entry = a
                best_payload = payload

        if best_entry is not None and best_payload is not None:
            selected.append(best_payload)

    selected.sort(key=lambda x: x["id"])

    out = {}
    for item in selected[:N_CHARACTERS]:
        out[str(item["id"])] = {
            "name": item["name"],
            "rarity": item["rarity"],
            "element": item["element"],
            "weapon_type": item["weapon_type"],
            "icon_name": item["icon_name"],
        }

    return out
