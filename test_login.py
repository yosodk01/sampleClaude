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

# 동행복권 로그인 폼 셀렉터 후보 (변경될 수 있으므로 복수 지정)
ID_SELECTORS = ["#userId", "input[name='userId']", "input[name='user_id']", "input[type='text']"]
PW_SELECTORS = ["input[name='password']", "input[type='password']", "#userPw"]


def find_and_fill(page, selectors: list[str], value: str, label: str) -> str:
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                page.fill(sel, value)
                logger.info(f"{label} 셀렉터 사용: {sel}")
                return sel
        except Exception:
            continue
    raise RuntimeError(f"{label} 입력 필드를 찾지 못함. 시도한 셀렉터: {selectors}")


def test_login():
    lottery_id = os.environ.get("LOTTERY_ID", "").strip()
    lottery_pw = os.environ.get("LOTTERY_PW", "").strip()
    notifier = TelegramNotifier()

    if not lottery_id or not lottery_pw:
        logger.error("LOTTERY_ID 또는 LOTTERY_PW 환경변수가 비어 있습니다. GitHub Secrets를 확인하세요.")
        sys.exit(1)

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
            page.goto(LOGIN_URL, wait_until="load", timeout=30000)
            page.wait_for_timeout(2000)
            page.screenshot(path="login_page.png")
            logger.info(f"페이지 로드 완료: {page.url}")
            logger.info(f"페이지 타이틀: {page.title()}")

            find_and_fill(page, ID_SELECTORS, lottery_id, "아이디")
            find_and_fill(page, PW_SELECTORS, lottery_pw, "비밀번호")
            page.screenshot(path="before_login.png")

            # 로그인 버튼 클릭 (여러 셀렉터 시도)
            for btn_sel in [".btn_common.lrg.blu", "input[value='로그인']", "button[type='submit']", ".btn_login"]:
                if page.locator(btn_sel).count() > 0:
                    logger.info(f"로그인 버튼 클릭: {btn_sel}")
                    page.locator(btn_sel).first.click()
                    break

            page.wait_for_timeout(4000)
            page.screenshot(path="after_login.png")
            logger.info(f"로그인 후 URL: {page.url}")

            # 로그인 실패 감지
            if page.locator(".msg_fail, .login_fail, #loginErrMsg").count() > 0:
                raise RuntimeError("로그인 실패: ID/PW를 확인하세요")
            if "login" in page.url.lower() and "method=login" in page.url:
                raise RuntimeError(f"로그인 후에도 로그인 페이지에 머물러 있음: {page.url}")

            logger.info("로그인 성공")

            # 마이페이지에서 예치금 확인
            page.goto(MYPAGE_URL, wait_until="load", timeout=20000)
            page.wait_for_timeout(2000)
            page.screenshot(path="mypage.png")

            balance = "확인 불가"
            for sel in [".box_my_detail .money em", ".money em", ".balance"]:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0:
                        balance = el.inner_text(timeout=3000) + "원"
                        break
                except Exception:
                    continue

            username = "확인 불가"
            for sel in [".user_name", ".lnb_user strong", ".nickname", ".my_name"]:
                try:
                    el = page.locator(sel).first
                    if el.count() > 0:
                        username = el.inner_text(timeout=3000).strip()
                        break
                except Exception:
                    continue

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
