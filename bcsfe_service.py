from __future__ import annotations

from bcsfe import core
import datetime

class BCSFEService:
    def __init__(self):
        core.core_data.init_data()

        self.handler: core.ServerHandler | None = None
        self.save: core.SaveFile | None = None

    def _require_save(self) -> core.SaveFile:
        if self.save is None: raise RuntimeError("먼저 download()를 호출하세요.")
        return self.save

    def _require_handler(self) -> core.ServerHandler:
        if self.handler is None: raise RuntimeError("먼저 download()를 호출하세요.")
        return self.handler

    def download(self, transfer_code: str, confirmation_code: str, country: str = "kr", game_version: str = "15.5.0") -> bool:
        handler, result = core.ServerHandler.from_codes(
            transfer_code, confirmation_code, core.CountryCode(country), core.GameVersion.from_string(game_version),
        )
        if handler is None: return False
        self.handler = handler
        self.save = handler.save_file
        return True

    def upload(self) -> tuple[str, str]:
        return self._require_handler().get_codes()

    # =========================
    # 🔒 재화 안전 제한 세팅
    # =========================
    def get_catfood(self): return self._require_save().catfood
    def set_catfood(self, value: int, is_vip: bool = False): 
        if is_vip:
            self._require_save().catfood = min(value, 1000000) 
        else:
            self._require_save().catfood = min(value, 17000)   

    def get_xp(self): return self._require_save().xp
    def set_xp(self, value: int, is_vip: bool = False): 
        if is_vip:
            self._require_save().xp = min(value, 100000000)    
        else:
            self._require_save().xp = min(value, 20000000)     

    def get_np(self): return self._require_save().np
    def set_np(self, value: int): self._require_save().np = min(value, core.core_data.max_value_manager.np)

    def get_leadership(self): return self._require_save().leadership
    def set_leadership(self, value: int): self._require_save().leadership = min(value, core.core_data.max_value_manager.leadership)

    def get_normal_tickets(self): return self._require_save().normal_tickets
    def set_normal_tickets(self, value: int, is_vip: bool = False): 
        if is_vip:
            self._require_save().normal_tickets = min(value, 999) 
        else:
            self._require_save().normal_tickets = min(value, 50) 

    def get_rare_tickets(self): return self._require_save().rare_tickets
    def set_rare_tickets(self, value: int): self._require_save().rare_tickets = min(value, core.core_data.max_value_manager.rare_tickets)

    def get_platinum_tickets(self): return self._require_save().platinum_tickets
    def set_platinum_tickets(self, value: int, is_vip: bool = False): 
        if is_vip:
            self._require_save().platinum_tickets = min(value, 999) 
        else:
            self._require_save().platinum_tickets = min(value, 9) 

    def get_legend_tickets(self): return self._require_save().legend_tickets
    def set_legend_tickets(self, value: int, is_vip: bool = False): 
        if is_vip:
            self._require_save().legend_tickets = min(value, 999) 
        else:
            self._require_save().legend_tickets = min(value, core.core_data.max_value_manager.legend_tickets)

    def get_platinum_shards(self): return self._require_save().platinum_shards
    def set_platinum_shards(self, value: int): self._require_save().platinum_shards = value

    def get_catfruit(self) -> list[int]: return self._require_save().catfruit
    
    # 🔥 단일 값으로 모든 종류의 개다래 일괄 변경
    def set_catfruit_all(self, value: int, is_vip: bool = False): 
        limit = 998 if is_vip else 50
        val = min(value, limit)
        save = self._require_save()
        save.catfruit = [val for _ in range(len(save.catfruit))]

    def get_catseyes(self) -> list[int]: return self._require_save().catseyes
    def set_catseyes(self, values: list[int]): 
        max_val = core.core_data.max_value_manager.catseyes
        self._require_save().catseyes = [min(v, max_val) for v in values]

    def get_battle_items(self) -> list[int]:
        try: return [item.amount for item in self._require_save().battle_items.items]
        except: return [0]*6

    def set_battle_items(self, values: list[int]):
        max_val = core.core_data.max_value_manager.battle_items
        try:
            items = self._require_save().battle_items.items
            for i, val in enumerate(values):
                if i < len(items): items[i].amount = min(val, max_val)
        except: pass

    def get_gamatoto_level(self):
        try: return getattr(self._require_save().gamatoto, 'level', 0)
        except: return 0

    def set_gamatoto_level(self, value: int):
        try:
            save = self._require_save()
            if hasattr(save.gamatoto, 'level'): save.gamatoto.level = min(value, 136)
            elif hasattr(save.gamatoto, 'level_'): save.gamatoto.level_ = min(value, 136)
        except: pass

    def summary(self):
        mvm = core.core_data.max_value_manager
        return {
            "current": {
                "catfood": self.get_catfood(), "xp": self.get_xp(), "np": self.get_np(),
                "leadership": self.get_leadership(), "normal_tickets": self.get_normal_tickets(),
                "rare_tickets": self.get_rare_tickets(), "platinum_tickets": self.get_platinum_tickets(),
                "legend_tickets": self.get_legend_tickets(), "platinum_shards": self.get_platinum_shards(),
                "catfruit": self.get_catfruit(), "catseyes": self.get_catseyes(),
                "battle_items": self.get_battle_items(), "gamatoto_level": self.get_gamatoto_level()
            },
            "max": {
                "catfood": mvm.catfood, "xp": mvm.xp, "np": mvm.np,
                "leadership": mvm.leadership, "normal_tickets": mvm.normal_tickets,
                "rare_tickets": mvm.rare_tickets, "platinum_tickets": mvm.platinum_tickets,
                "legend_tickets": mvm.legend_tickets, "platinum_shards": mvm.platinum_tickets * 10,
                "catfruit": 998, "catseyes": mvm.catseyes, 
                "battle_items": mvm.battle_items, "gamatoto_level": 136
            }
        }

    # =========================
    # 🐾 Cats Management
    # =========================
    def get_cat_name(self, cat_id: int) -> str:
        try:
            save_file = self._require_save()
            cats = save_file.cats.cats
            if 0 <= cat_id < len(cats):
                names = cats[cat_id].get_names_cls(save_file)
                if names and len(names) > 0: return f"{names[0]} ({cat_id})"
        except Exception: pass
        return f"알 수 없는 고양이 ({cat_id})"

    def search_cats_by_name(self, query: str) -> list[dict]:
        save_file = self._require_save()
        found_cats = save_file.cats.get_cats_name(save_file, query)
        result = []
        for cat in found_cats:
            names = cat.get_names_cls(save_file)
            name = names[0] if names else "알 수 없음"
            result.append({"id": cat.id, "name": f"{name} ({cat.id})"})
        return result

    def unlock_cat(self, cat_id: int):
        cats = self._require_save().cats.cats
        if 0 <= cat_id < len(cats): cats[cat_id].unlocked = True

    def remove_cat(self, cat_id: int):
        cats = self._require_save().cats.cats
        if 0 <= cat_id < len(cats): cats[cat_id].unlocked = False

    def upgrade_cat(self, cat_id: int, base_level: int, plus_level: int, is_max: bool = False):
        cats = self._require_save().cats.cats
        if 0 <= cat_id < len(cats):
            cat = cats[cat_id]
            if is_max:
                power_up = core.PowerUpHelper(cat, self._require_save())
                cat.upgrade.base = max(0, power_up.get_max_possible_base() - 1)
                cat.upgrade.plus = max(0, power_up.get_max_possible_plus())
            else:
                cat.upgrade.base = max(0, base_level - 1)
                cat.upgrade.plus = max(0, plus_level)

    def evolve_cat(self, cat_id: int, form: int):
        cats = self._require_save().cats.cats
        if 0 <= cat_id < len(cats):
            cat = cats[cat_id]
            safe_form = form
            if hasattr(cat, 'unlocked_forms') and isinstance(cat.unlocked_forms, list):
                safe_form = min(form, len(cat.unlocked_forms) - 1)
                for i in range(safe_form + 1): cat.unlocked_forms[i] = True
            cat.current_form = safe_form
            if safe_form >= 2 and hasattr(cat, 'true_form'): cat.true_form = True
            if safe_form >= 3 and hasattr(cat, 'fourth_form'): cat.fourth_form = True

    # =========================
    # 🚀 Special Features
    # =========================
    def unban_account(self) -> bool:
        server_handler = core.ServerHandler(self._require_save())
        return server_handler.create_new_account()

    def unlock_enemy_guide(self):
        save = self._require_save()
        for i in range(len(save.enemy_guide)): core.Enemy(i).unlock_enemy_guide(save)

    def unlock_aku_realm(self):
        save = self._require_save()
        for stage_id in [255, 256, 257, 258, 265, 266, 268]: save.event_stages.clear_map(1, stage_id, 0, False)

    def clear_storage(self):
        for item in self._require_save().cats.storage_items:
            item.item_id = 0
            item.item_type = 0

    def fix_time_errors(self):
        save = self._require_save()
        now = datetime.datetime.now()
        save.date_3 = now
        save.timestamp = now.timestamp()
        save.energy_penalty_timestamp = now.timestamp()

    def fix_crashes(self):
        save = self._require_save()
        save.gamatoto.skin = 2
        save.ototo.cannons = core.game.gamoto.ototo.Cannons.init(save.game_version)

    def max_catamins_and_chests(self):
        save = self._require_save()
        max_catamins = core.core_data.max_value_manager.catamins
        for i in range(len(save.catamins)): save.catamins[i] = max_catamins
        max_chests = core.core_data.max_value_manager.treasure_chests
        for i in range(len(save.treasure_chests)): save.treasure_chests[i] = max_chests

    def activate_gold_pass(self):
        try: self._require_save().officer_pass.is_active = True
        except: pass

    def activate_restart_pack(self):
        self._require_save().restart_pack = 1

    def max_ototo_materials(self):
        try:
            save = self._require_save()
            if hasattr(save.ototo, 'base_materials') and hasattr(save.ototo.base_materials, 'materials'):
                for mat in save.ototo.base_materials.materials: mat.amount = 9999
        except Exception: pass

    def load_file(self, file_path: str) -> bool:
        try:
            path = core.Path(file_path)
            data = path.read()
            self.save = core.SaveFile(data)
            self.handler = core.ServerHandler(self.save)
            return True
        except Exception as e:
            print(f"File Load Error: {e}")
            return False

    def save_to_file(self, path: str):
        self._require_save().to_file(core.Path(path))