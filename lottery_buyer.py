import os
import sys
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

LOGIN_URL = "https://dhlottery.co.kr/user.do?method=login"
LOTTO_URL = "https://ol.dhlottery.co.kr/olotto/game_mobile/game645.do"
BALANCE_URL = "https://dhlottery.co.kr/userSsl.do?method=myPage"


class LotteryBuyer:
    def __init__(self):
        self.lottery_id = os.environ["LOTTERY_ID"]
        self.lottery_pw = os.environ["LOTTERY_PW"]
        self.purchase_count = int(os.environ.get("PURCHASE_COUNT", "1"))
        self.notifier = TelegramNotifier()

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            try:
                logger.info("=== 로또 자동 구매 시작 ===")
                self._login(page)
                balance = self._get_balance(page)
                logger.info(f"현재 예치금: {balance}")
                tickets = self._purchase(page)
                self._notify_success(balance, tickets)
            except Exception as e:
                logger.error(f"오류 발생: {e}")
                try:
                    page.screenshot(path="error_screenshot.png")
                    logger.info("에러 스크린샷 저장: error_screenshot.png")
                except Exception:
                    pass
                self._notify_failure(str(e))
                sys.exit(1)
            finally:
                browser.close()

    def _login(self, page):
        logger.info("로그인 시도 중...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_selector("#userId", timeout=15000)

        page.fill("#userId", self.lottery_id)
        page.fill("input[name='password']", self.lottery_pw)
        page.click(".btn_common.lrg.blu")

        # 로그인 성공 여부 확인 (실패 시 에러 메시지 표시됨)
        page.wait_for_timeout(3000)
        if "로그인" in page.url or page.locator(".msg_fail").count() > 0:
            raise RuntimeError("로그인 실패: ID/PW를 확인하세요")

        logger.info("로그인 성공")

    def _get_balance(self, page) -> str:
        try:
            page.goto(BALANCE_URL, wait_until="domcontentloaded")
            page.wait_for_selector(".box_my_detail", timeout=10000)
            balance_el = page.locator(".money em").first
            return balance_el.inner_text() + "원"
        except Exception:
            return "확인 불가"

    def _purchase(self, page) -> list[str]:
        logger.info(f"로또 6/45 구매 시작 (수량: {self.purchase_count}장)")
        page.goto(LOTTO_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        tickets = []
        for i in range(self.purchase_count):
            logger.info(f"  {i + 1}번째 티켓 구매 중...")
            ticket_numbers = self._buy_one_ticket(page)
            tickets.append(ticket_numbers)
            logger.info(f"  구매 완료: {ticket_numbers}")

        return tickets

    def _buy_one_ticket(self, page) -> str:
        # 자동번호 선택 버튼
        page.locator("button.btn_auto, a.btn_auto, input[value='자동']").first.click()
        page.wait_for_timeout(1000)

        # 장바구니 추가
        page.locator("button.btn_add, a.btn_add, .btn_basket").first.click()
        page.wait_for_timeout(1000)

        # 구매하기 버튼
        page.locator("button.btn_buy, a.btn_buy, .btn_purchase").first.click()
        page.wait_for_timeout(2000)

        # 구매 확인 팝업 처리
        if page.locator(".popup_confirm").count() > 0:
            page.locator(".popup_confirm .btn_confirm, .popup_confirm .btn_ok").first.click()
            page.wait_for_timeout(2000)

        # 구매된 번호 추출 (결과 화면에서)
        try:
            result = page.locator(".num_result, .result_num, .selected_num").first.inner_text(timeout=5000)
            return result.strip()
        except Exception:
            return "번호 확인 불가"

    def _notify_success(self, balance: str, tickets: list[str]):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        ticket_lines = "\n".join(f"  {i + 1}. {t}" for i, t in enumerate(tickets))
        msg = (
            f"✅ <b>로또 6/45 자동 구매 완료</b>\n"
            f"📅 {now}\n"
            f"🎫 구매 수량: {len(tickets)}장\n"
            f"🔢 번호:\n{ticket_lines}\n"
            f"💰 구매 전 예치금: {balance}"
        )
        self.notifier.send(msg)
        logger.info("=== 구매 완료 ===")

    def _notify_failure(self, error: str):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = (
            f"❌ <b>로또 6/45 자동 구매 실패</b>\n"
            f"📅 {now}\n"
            f"🚨 오류: {error}"
        )
        self.notifier.send(msg)


if __name__ == "__main__":
    buyer = LotteryBuyer()
    buyer.run()
