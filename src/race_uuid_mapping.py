# -*- coding: utf-8 -*-
"""
BG3原版种族UUID映射
"""

# 原版种族UUID映射
VANILLA_RACE_MAPPING = {
    # 人类
    "0eb594cb-8820-4be6-a58d-8be7a1a98fba": {
        "name_en": "Human",
        "name_zh": "人类",
        "localization_key": "race_human",
        "subrace": None
    },
    
    # 精灵
    "6c038dcb-7eb5-431d-84f8-cecfaf1c0c5a": {
        "name_en": "Elf",
        "name_zh": "精灵",
        "localization_key": "race_elf",
        "subrace": None
    },
    
    # 卓尔精灵
    "4f5d1434-5175-4fa9-b7dc-ab24fba37929": {
        "name_en": "Drow",
        "name_zh": "卓尔精灵",
        "localization_key": "race_drow",
        "subrace": None
    },
    
    # 提夫林
    "b6dccbed-30f3-424b-a181-c4540cf38197": {
        "name_en": "Tiefling",
        "name_zh": "提夫林",
        "localization_key": "race_tiefling",
        "subrace": None
    },
    
    # 矮人
    "0ab2874d-cfdc-405e-8a97-d37bfbb23c52": {
        "name_en": "Dwarf",
        "name_zh": "矮人",
        "localization_key": "race_dwarf",
        "subrace": None
    },
    
    # 半身人
    "78cd3bcc-1c43-4a2a-aa80-c34322c16a04": {
        "name_en": "Halfling",
        "name_zh": "半身人",
        "localization_key": "race_halfling",
        "subrace": None
    },
    
    # 侏儒
    "f1b3f884-4029-4f0f-b158-1f9fe0ae5a0d": {
        "name_en": "Gnome",
        "name_zh": "侏儒",
        "localization_key": "race_gnome",
        "subrace": None
    },
    
    # 半精灵
    "45f4ac10-3c89-4fb2-b37d-f973bb9110c0": {
        "name_en": "Half-Elf",
        "name_zh": "半精灵",
        "localization_key": "race_half_elf",
        "subrace": None
    },
    
    # 半兽人
    "5c39a726-71c8-4748-ba8d-f768b3c11a91": {
        "name_en": "Half-Orc",
        "name_zh": "半兽人",
        "localization_key": "race_half_orc",
        "subrace": None
    },
    
    # 龙裔
    "9c61a74a-20df-4119-89c5-d996956b6c66": {
        "name_en": "Dragonborn",
        "name_zh": "龙裔",
        "localization_key": "race_dragonborn",
        "subrace": None
    },
    
    # 吉斯洋基人
    "bdf9b779-002c-4077-b377-8ea7c1faa795": {
        "name_en": "Githyanki",
        "name_zh": "吉斯洋基人",
        "localization_key": "race_githyanki",
        "subrace": None
    }
}

def get_race_info(uuid: str) -> dict:
    """根据UUID获取种族信息"""
    return VANILLA_RACE_MAPPING.get(uuid.lower())

def is_vanilla_race(uuid: str) -> bool:
    """检查是否为原版种族"""
    return uuid.lower() in VANILLA_RACE_MAPPING

def get_all_vanilla_race_uuids() -> list:
    """获取所有原版种族UUID"""
    return list(VANILLA_RACE_MAPPING.keys())

def get_race_options(localization_manager=None) -> list:
    """获取种族选择选项"""
    options = []
    for uuid, info in VANILLA_RACE_MAPPING.items():
        if localization_manager and 'localization_key' in info:
            # 本地化名称
            display_name = localization_manager.get_text(info['localization_key'])
        else:
            # 默认格式
            display_name = f"{info['name_zh']} ({info['name_en']})"
        
        if info['subrace']:
            display_name += f" - {info['subrace']}"
        options.append((display_name, uuid))
    
    # 排序
    options.sort(key=lambda x: x[0])
    return options