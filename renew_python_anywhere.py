import os
import sys
import json
import requests
from bs4 import BeautifulSoup
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("renewal.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.pythonanywhere.com/login/"


def load_accounts() -> list:
    """
    يقرأ الحسابات من متغيرات البيئة بالشكل:
      PA_USERNAME_1 / PA_PASSWORD_1
      PA_USERNAME_2 / PA_PASSWORD_2
      ...
    يكمل يعد لحد ما يلاقيش رقم جديد.
    كمان يدعم PA_LABEL_N اختياري كاسم ودود في اللوج.
    """
    accounts = []
    i = 1
    while True:
        username = os.environ.get(f"PA_USERNAME_{i}", "").strip()
        password = os.environ.get(f"PA_PASSWORD_{i}", "").strip()

        if not username and not password:
            break  # مفيش حسابات تانية

        if username and password:
            label = os.environ.get(f"PA_LABEL_{i}", f"Account {i}").strip()
            accounts.append({
                "username": username,
                "password": password,
                "label":    label,
                "index":    i,
            })
            logger.info(f"🔑 Found account #{i}: {username} ({label})")
        else:
            logger.warning(f"⚠️  Account #{i} is incomplete — skipping (need both USERNAME and PASSWORD)")

        i += 1

    if not accounts:
        logger.error(
            "❌ No accounts found!\n"
            "   Add secrets like: PA_USERNAME_1, PA_PASSWORD_1, PA_USERNAME_2, PA_PASSWORD_2 ..."
        )
        sys.exit(1)

    logger.info(f"✅ Total accounts loaded: {len(accounts)}\n")
    return accounts


def renew_account(account: dict) -> dict:
    username = account["username"]
    password = account["password"]
    label    = account["label"]
    index    = account["index"]

    result = {
        "index":     index,
        "username":  username,
        "label":     label,
        "status":    "FAILED",
        "message":   "",
        "extended":  False,
        "timestamp": datetime.utcnow().isoformat() + " UTC",
    }

    dashboard_url = f"https://www.pythonanywhere.com/user/{username}/webapps/"
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    try:
        # ── 1. صفحة تسجيل الدخول ─────────────────────────────────────────────
        logger.info(f"[{label}] 🔐 Logging in as {username}...")
        login_page = session.get(LOGIN_URL, timeout=15)
        login_page.raise_for_status()

        soup = BeautifulSoup(login_page.content, "html.parser")
        csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if not csrf_input:
            result["message"] = "CSRF token not found on login page"
            logger.error(f"[{label}] ❌ {result['message']}")
            return result

        # ── 2. إرسال بيانات الدخول ───────────────────────────────────────────
        payload = {
            "csrfmiddlewaretoken":    csrf_input["value"],
            "auth-username":          username,
            "auth-password":          password,
            "login_view-current_step": "auth",
        }
        response = session.post(
            LOGIN_URL,
            data=payload,
            headers={"Referer": LOGIN_URL},
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()

        if "Log out" not in response.text and "logout" not in response.text.lower():
            result["message"] = "Login failed — credentials may be wrong"
            logger.error(f"[{label}] ❌ {result['message']} (URL: {response.url})")
            return result

        if "login" in response.url.lower():
            result["message"] = "Login failed — still on login page"
            logger.error(f"[{label}] ❌ {result['message']}")
            return result

        logger.info(f"[{label}] ✅ Login successful")

        # ── 3. داشبورد الويب أبس ─────────────────────────────────────────────
        logger.info(f"[{label}] 📊 Checking web apps dashboard...")
        time.sleep(1)
        dashboard = session.get(dashboard_url, timeout=15)
        dashboard.raise_for_status()
        soup = BeautifulSoup(dashboard.content, "html.parser")

        # ── 4. البحث عن زرار Extend ──────────────────────────────────────────
        extend_action = None
        for form in soup.find_all("form", action=True):
            if "/extend" in form.get("action", "").lower():
                extend_action = form["action"]
                logger.info(f"[{label}] 🔍 Found extend form: {extend_action}")
                break

        if not extend_action:
            result["status"]   = "SUCCESS"
            result["message"]  = "No extend button — app doesn't need renewal yet"
            result["extended"] = False
            logger.info(f"[{label}] ℹ️  {result['message']}")
            return result

        # ── 5. CSRF من الداشبورد ──────────────────────────────────────────────
        dashboard_csrf = soup.find("input", {"name": "csrfmiddlewaretoken"})
        if not dashboard_csrf:
            result["message"] = "CSRF token not found on dashboard"
            logger.error(f"[{label}] ❌ {result['message']}")
            return result

        # ── 6. إرسال طلب التمديد ─────────────────────────────────────────────
        extend_url = f"https://www.pythonanywhere.com{extend_action}"
        logger.info(f"[{label}] ⏰ Sending extend request...")
        ext_resp = session.post(
            extend_url,
            data={"csrfmiddlewaretoken": dashboard_csrf["value"]},
            headers={"Referer": dashboard_url},
            timeout=15,
        )
        ext_resp.raise_for_status()

        if ext_resp.status_code == 200 and "webapps" in ext_resp.url.lower():
            result["status"]   = "SUCCESS"
            result["message"]  = "Web app extended successfully"
            result["extended"] = True
            logger.info(f"[{label}] ✅ {result['message']}")
        else:
            result["message"] = f"Unexpected response (HTTP {ext_resp.status_code}, URL: {ext_resp.url})"
            logger.warning(f"[{label}] ⚠️  {result['message']}")

    except requests.Timeout:
        result["message"] = "Request timed out"
        logger.error(f"[{label}] ❌ {result['message']}")
    except requests.RequestException as e:
        result["message"] = f"Network error: {e}"
        logger.error(f"[{label}] ❌ {result['message']}")
    except Exception as e:
        result["message"] = f"Unexpected error: {e}"
        logger.exception(f"[{label}] ❌ {result['message']}")

    return result


def run_all(accounts: list, max_workers: int = 4) -> list:
    results = []
    logger.info(f"{'='*60}")
    logger.info(f"🚀 Starting renewal for {len(accounts)} account(s)")
    logger.info(f"{'='*60}\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(renew_account, acc): acc for acc in accounts}
        for future in as_completed(futures):
            results.append(future.result())

    # رتب النتايج حسب رقم الحساب
    results.sort(key=lambda r: r["index"])
    return results


def print_summary(results: list) -> bool:
    total    = len(results)
    success  = sum(1 for r in results if r["status"] == "SUCCESS")
    failed   = total - success
    extended = sum(1 for r in results if r["extended"])

    logger.info(f"\n{'='*60}")
    logger.info("📋 RENEWAL SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"  Total accounts : {total}")
    logger.info(f"  ✅ Succeeded   : {success}")
    logger.info(f"  ❌ Failed      : {failed}")
    logger.info(f"  🔄 Extended    : {extended}")
    logger.info(f"{'='*60}")

    for r in results:
        icon = "✅" if r["status"] == "SUCCESS" else "❌"
        ext  = " 🔄 EXTENDED" if r["extended"] else ""
        logger.info(f"  {icon} #{r['index']} {r['label']:<20} — {r['message']}{ext}")

    logger.info(f"{'='*60}\n")

    with open("renewal_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total":    total,
                "success":  success,
                "failed":   failed,
                "extended": extended,
                "run_at":   datetime.utcnow().isoformat() + " UTC",
            },
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    logger.info("📄 Report saved → renewal_report.json")
    return failed == 0


if __name__ == "__main__":
    accounts    = load_accounts()
    max_workers = int(os.environ.get("MAX_WORKERS", min(4, len(accounts))))
    results     = run_all(accounts, max_workers=max_workers)
    all_ok      = print_summary(results)
    sys.exit(0 if all_ok else 1)
