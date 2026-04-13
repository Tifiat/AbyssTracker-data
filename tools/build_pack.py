import os
import json
import hashlib
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from typing import Optional, Dict, List, Tuple

import cv2
import numpy as np

# ====== CONFIG ======
N_CHARACTERS = int(os.environ.get("N_CHARACTERS", "300"))
N_WEAPONS = int(os.environ.get("N_WEAPONS", "300"))

ANIMEGAMEDATA_BASE = "https://raw.githubusercontent.com/DimbreathBot/AnimeGameData/master"
URL_AVATARS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarExcelConfigData.json"
URL_AVATAR_SKILL_DEPOTS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarSkillDepotExcelConfigData.json"
URL_AVATAR_SKILLS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarSkillExcelConfigData.json"
URL_WEAPONS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/WeaponExcelConfigData.json"
URL_TEXTMAP_EN = f"{ANIMEGAMEDATA_BASE}/TextMap/TextMapEN.json"

ENKA_UI = "https://enka.network/ui"

OUT_DIR = "."
OUT_CHAR = os.path.join(OUT_DIR, "characters.json")
OUT_WEAP = os.path.join(OUT_DIR, "weapons.json")
OUT_HIDX_CHAR = os.path.join(OUT_DIR, "hash_index_characters.json")
OUT_HIDX_WEAP = os.path.join(OUT_DIR, "hash_index_weapons.json")
OUT_MANIFEST = os.path.join(OUT_DIR, "manifest.json")


# ====== UTILS ======
def http_get_json(url: str) -> object:
    req = Request(url, headers={"User-Agent": "AbyssTracker-data-bot/1.0"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def http_get_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "AbyssTracker-data-bot/1.0"})
    with urlopen(req, timeout=60) as r:
        return r.read()


def save_json(path: str, obj: object):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rarity_from_quality(q: str) -> Optional[int]:
    m = {
        "QUALITY_ORANGE": 5,
        "QUALITY_PURPLE": 4,
        "QUALITY_BLUE": 3,
        "QUALITY_GREEN": 2,
        "QUALITY_WHITE": 1,
    }
    return m.get(q)


def weapon_type_short(wt: str) -> Optional[str]:
    m = {
        "WEAPON_SWORD_ONE_HAND": "Sword",
        "WEAPON_CLAYMORE": "Claymore",
        "WEAPON_POLE": "Polearm",
        "WEAPON_CATALYST": "Catalyst",
        "WEAPON_BOW": "Bow",
    }
    return m.get(wt)


def normalize_element(elem: Optional[str]) -> Optional[str]:
    m = {
        "Fire": "Pyro",
        "Water": "Hydro",
        "Wind": "Anemo",
        "Electric": "Electro",
        "Grass": "Dendro",
        "Rock": "Geo",
        "Ice": "Cryo",
    }
    if not elem:
        return None
    return m.get(str(elem))


def textmap_lookup(textmap: dict, key) -> Optional[str]:
    if key is None:
        return None

    value = textmap.get(str(key))
    if value is None:
        value = textmap.get(key)

    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None
    if value.startswith("#"):
        return None

    return value


def fallback_name_from_avatar_icon(icon_name: str) -> str:
    prefix = "UI_AvatarIcon_"
    name = str(icon_name)
    if name.startswith(prefix):
        name = name[len(prefix):]
    return name.replace("_", " ").strip() or str(icon_name)


def fallback_name_from_weapon_icon(icon_name: str) -> str:
    prefix = "UI_EquipIcon_"
    name = str(icon_name)
    if name.startswith(prefix):
        name = name[len(prefix):]
    return name.replace("_", " ").strip() or str(icon_name)


def dhash_hex(img_bgr: np.ndarray, hash_size: int = 8) -> str:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = diff.flatten()

    val = 0
    for b in bits:
        val = (val << 1) | int(bool(b))

    width = (hash_size * hash_size + 3) // 4
    return f"{val:0{width}x}"


def to_bgr(img):
    if img is None:
        return None

    if len(img.shape) == 3 and img.shape[2] == 4:
        b, g, r, a = cv2.split(img)
        alpha = a.astype(np.float32) / 255.0
        bg = np.full_like(b, 180, dtype=np.uint8)

        def comp(ch):
            return (
                ch.astype(np.float32) * alpha
                + bg.astype(np.float32) * (1 - alpha)
            ).astype(np.uint8)

        return cv2.merge([comp(b), comp(g), comp(r)])

    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    return img


# ====== CHARACTER HELPERS ======
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


# ====== BUILDERS ======
def build_characters(avatars: list, textmap: dict, depot_map: Dict[int, dict], skill_map: Dict[int, dict]) -> dict:
    grouped: Dict[str, List[dict]] = {}

    avatars_sorted = sorted(avatars, key=lambda x: int(x.get("id", 0) or 0))

    for a in avatars_sorted:
        if not is_candidate_avatar(a):
            continue

        icon = str(a.get("iconName"))
        if icon_name == "UI_AvatarIcon_Kate":
            continue

        if icon_name.startswith("UI_AvatarIcon_Player"):
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


def build_hash_index(items: dict) -> dict:
    idx = {}
    for _id, meta in items.items():
        icon_name = meta.get("icon_name")
        if not icon_name:
            continue

        url = f"{ENKA_UI}/{icon_name}.png"
        try:
            png = http_get_bytes(url)
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            img = to_bgr(img)
            idx[str(_id)] = dhash_hex(img)
        except Exception:
            continue

    return idx


def main():
    print("Downloading AnimeGameData JSON...")
    avatars = http_get_json(URL_AVATARS)
    avatar_skill_depots = http_get_json(URL_AVATAR_SKILL_DEPOTS)
    avatar_skills = http_get_json(URL_AVATAR_SKILLS)
    weapons = http_get_json(URL_WEAPONS)
    textmap = http_get_json(URL_TEXTMAP_EN)

    depot_map, skill_map = build_skill_maps(avatar_skill_depots, avatar_skills)

    print("Building characters/weapons pack...")
    chars = build_characters(avatars, textmap, depot_map, skill_map)
    weaps = build_weapons(weapons, textmap)

    print(f"Characters selected: {len(chars)} / N={N_CHARACTERS}")
    print(f"Weapons selected:    {len(weaps)} / N={N_WEAPONS}")

    print("Building hash indexes via Enka icons...")
    hidx_char = build_hash_index(chars)
    hidx_weap = build_hash_index(weaps)

    print(f"HashIndex characters: {len(hidx_char)}")
    print(f"HashIndex weapons:    {len(hidx_weap)}")

    save_json(OUT_CHAR, chars)
    save_json(OUT_WEAP, weaps)
    save_json(OUT_HIDX_CHAR, hidx_char)
    save_json(OUT_HIDX_WEAP, hidx_weap)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": now,
        "source": {
            "repo": "DimbreathBot/AnimeGameData",
            "avatars": URL_AVATARS,
            "avatar_skill_depots": URL_AVATAR_SKILL_DEPOTS,
            "avatar_skills": URL_AVATAR_SKILLS,
            "weapons": URL_WEAPONS,
            "textmap_en": URL_TEXTMAP_EN,
        },
        "counts": {
            "characters": len(chars),
            "weapons": len(weaps),
            "hash_characters": len(hidx_char),
            "hash_weapons": len(hidx_weap),
        },
        "files": {},
    }

    for p in [OUT_CHAR, OUT_WEAP, OUT_HIDX_CHAR, OUT_HIDX_WEAP]:
        manifest["files"][os.path.basename(p)] = {
            "sha256": sha256_file(p)
        }

    save_json(OUT_MANIFEST, manifest)
    print("Done. Wrote:", OUT_MANIFEST)


if __name__ == "__main__":
    main()
