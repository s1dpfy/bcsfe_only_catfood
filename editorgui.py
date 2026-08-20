from __future__ import annotations
import sys
import traceback
from bcsfe import core

class BCSFEService:
    def __init__(self):
        core.core_data.init_data()
        self.handler: core.ServerHandler | None = None
        self.save: core.SaveFile | None = None

    def _require_save(self) -> core.SaveFile:
        if self.save is None: 
            raise RuntimeError("먼저 서버에서 계정을 불러오세요.")
        return self.save

    def _require_handler(self) -> core.ServerHandler:
        if self.handler is None: 
            raise RuntimeError("먼저 서버에서 계정을 불러오세요.")
        return self.handler

    def download(self, transfer_code: str, confirmation_code: str, country: str = "kr", game_version: str = "15.5.0") -> bool:
        try:
            # 국가 코드 및 버전 객체 안전 변환
            country_code = core.CountryCode.from_code(country)
            version = core.GameVersion.from_string(game_version)

            handler, result = core.ServerHandler.from_codes(
                transfer_code, 
                confirmation_code, 
                cc=country_code, 
                gv=version
            )
            
            if handler is None or handler.save_file is None: 
                print(f"⚠️ 서버 응답 결과: {result}")
                return False

            self.handler = handler
            self.save = handler.save_file
            return True
        except Exception as e:
            print(f"❌ 다운로드 상세 에러: {e}")
            traceback.print_exc()
            return False

    def upload(self) -> tuple[str, str]:
        return self._require_handler().get_codes()

    # 재화 Getter/Setter
    def get_catfood(self): return self._require_save().catfood
    def set_catfood(self, value: int): self._require_save().catfood = value

    def get_xp(self): return self._require_save().xp
    def set_xp(self, value: int): self._require_save().xp = min(value, core.core_data.max_value_manager.xp)

    def get_np(self): return self._require_save().np
    def set_np(self, value: int): self._require_save().np = min(value, core.core_data.max_value_manager.np)

    def get_rare_tickets(self): return self._require_save().rare_tickets
    def set_rare_tickets(self, value: int): self._require_save().rare_tickets = min(value, core.core_data.max_value_manager.rare_tickets)

    def get_leadership(self): return self._require_save().leadership
    def set_leadership(self, value: int): self._require_save().leadership = min(value, core.core_data.max_value_manager.leadership)


def get_int_input(prompt: str, current_value: int) -> int:
    user_input = input(f"{prompt} (현재: {current_value}) [엔터 시 유지]: ").strip()
    if not user_input:
        return current_value
    try:
        return int(user_input)
    except ValueError:
        print("❌ 잘못된 입력입니다. 기존 값을 유지합니다.")
        return current_value


def main():
    print("=" * 45)
    print("   냥코 대전쟁 심플 CLI 에디터 (서버 연동)")
    print("=" * 45)

    service = BCSFEService()

    transfer_code = input("이어하기 코드를 입력하세요: ").strip()
    confirm_code = input("인증 번호를 입력하세요: ").strip()

    if not transfer_code or not confirm_code:
        print("❌ 이어하기 코드와 인증 번호를 모두 입력해야 합니다.")
        return

    print("\n⏳ 서버에서 데이터를 다운로드하는 중...")
    if not service.download(transfer_code, confirm_code):
        print("❌ 계정을 불러오는데 실패했습니다. 코드를 확인해주세요.")
        return

    print("✅ 성공적으로 데이터를 불러왔습니다!\n")

    print("-" * 45)
    print("수정할 값을 입력하세요. 변경하지 않으려면 [Enter]를 누르세요.")
    print("-" * 45)

    new_catfood = get_int_input("통조림 (제한 없음)", service.get_catfood())
    new_xp = get_int_input("XP", service.get_xp())
    new_np = get_int_input("NP", service.get_np())
    new_tickets = get_int_input("레어 티켓", service.get_rare_tickets())
    new_leadership = get_int_input("리더십", service.get_leadership())

    service.set_catfood(new_catfood)
    service.set_xp(new_xp)
    service.set_np(new_np)
    service.set_rare_tickets(new_tickets)
    service.set_leadership(new_leadership)

    print("\n⏳ 수정된 데이터를 서버에 저장하는 중...")
    try:
        new_transfer, new_confirm = service.upload()
        print("\n" + "=" * 45)
        print("🎉 서버 업로드 성공!")
        print(f"새 이어하기 코드 : {new_transfer}")
        print(f"새 인증 번호     : {new_confirm}")
        print("=" * 45)
        print("게임 내에서 위 코드로 이어하기를 진행하세요.")
    except Exception as e:
        print(f"\n❌ 서버 업로드 중 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()