"""
로그인 테스트 스크립트
: 로그인 성공 여부 + 예치금 확인 후 텔레그램 알림
"""
import os
import sys
import logging
from playwright.sync_api import sync_playwright

from notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

LOGIN_URL = "https://dhlottery.co.kr/user.do?method=login"
MYPAGE_URL = "https://dhlottery.co.kr/userSsl.do?method=myPage"


def test_login():
    lottery_id = os.environ["LOTTERY_ID"]
    lottery_pw = os.environ["LOTTERY_PW"]
    notifier = TelegramNotifier()

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
            logger.info("로그인 페이지 접속 중...")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_selector("#userId", timeout=15000)

            page.fill("#userId", lottery_id)
            page.fill("input[name='password']", lottery_pw)
            page.screenshot(path="before_login.png")

            page.click(".btn_common.lrg.blu")
            page.wait_for_timeout(3000)

            # 로그인 실패 감지
            if page.locator(".msg_fail").count() > 0:
                raise RuntimeError("로그인 실패: ID/PW를 확인하세요")
            if "login" in page.url.lower():
                raise RuntimeError(f"로그인 후에도 로그인 페이지에 머물러 있음: {page.url}")

            logger.info(f"로그인 성공, 현재 URL: {page.url}")

            # 마이페이지에서 예치금 확인
            page.goto(MYPAGE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path="mypage.png")

            # 예치금 추출 시도
            balance = "확인 불가"
            try:
                el = page.locator(".box_my_detail .money em").first
                balance = el.inner_text(timeout=5000) + "원"
            except Exception:
                pass

            # 사용자 이름 추출 시도
            username = "확인 불가"
            try:
                el = page.locator(".user_name, .lnb_user strong").first
                username = el.inner_text(timeout=3000)
            except Exception:
                pass

            logger.info(f"사용자: {username}, 예치금: {balance}")

            notifier.send(
                f"✅ <b>로그인 테스트 성공</b>\n"
                f"👤 사용자: {username}\n"
                f"💰 예치금: {balance}"
            )

        except Exception as e:
            logger.error(f"오류: {e}")
            try:
                page.screenshot(path="error_screenshot.png")
            except Exception:
                pass
            notifier.send(f"❌ <b>로그인 테스트 실패</b>\n🚨 오류: {e}")
            browser.close()
            sys.exit(1)

        browser.close()
        logger.info("테스트 완료")


if __name__ == "__main__":
    test_login()
