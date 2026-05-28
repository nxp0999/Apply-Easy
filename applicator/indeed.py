"""
applicator/indeed.py
Automates Indeed Easy Apply using Playwright.

Indeed's apply flow uses a multi-step modal (IndeedApply widget) embedded in the
job page. The steps vary by job, but the common pattern is:
  1. Resume upload / confirm existing resume
  2. Contact info confirmation
  3. Screening questions
  4. Review & Submit
"""

import logging

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from .base import BaseApplicator
from credentials import cred_store

logger = logging.getLogger(__name__)

_SESSION_KEY = "indeed_session"
_LOGIN_URL   = "https://secure.indeed.com/account/login"
_HOME_URL    = "https://www.indeed.com"
_STEP_DELAY  = 1.0


class IndeedApplicator(BaseApplicator):
    PLATFORM = "indeed"

    def apply(self, job: dict, pdf_path: str, dry_run: bool = False) -> dict:
        with sync_playwright() as p:
            browser = self._launch_browser(p)
            context = self._load_session(browser)
            page    = context.new_page()

            try:
                if not self._ensure_logged_in(page, context):
                    return {"success": False, "notes": "Indeed login failed"}

                self._update_for_job(job)
                url = job.get("apply_url_direct") or job.get("apply_url") or ""
                if not url:
                    return {"success": False, "notes": "No apply URL found"}

                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)

                if dry_run:
                    return {"success": True, "notes": "DRY RUN — navigated to job page, not clicking Apply"}

                # Click Apply / Apply Now button
                try:
                    apply_btn = page.locator(
                        'button:has-text("Apply now"), '
                        'a:has-text("Apply now"), '
                        'button[id="indeedApplyButton"], '
                        'span:has-text("Apply now")'
                    ).first
                    apply_btn.wait_for(state="visible", timeout=6000)
                    apply_btn.click()
                    page.wait_for_timeout(2000)
                except PWTimeout:
                    return {"success": False, "notes": "Apply Now button not found"}

                # Walk through multi-step form
                return self._walk_form(page, job, pdf_path)

            except Exception as e:
                logger.exception("Indeed apply error")
                return {"success": False, "notes": str(e)}
            finally:
                self._save_session(context)
                browser.close()

    # ── Login / session ───────────────────────────────────────────────────────

    def _load_session(self, browser):
        session = cred_store.get(_SESSION_KEY)
        if session:
            try:
                return browser.new_context(storage_state=session)
            except Exception:
                pass
        return browser.new_context()

    def _save_session(self, context):
        try:
            state = context.storage_state()  # returns dict
            cred_store.set(_SESSION_KEY, state)
        except Exception:
            pass

    def _ensure_logged_in(self, page, context) -> bool:
        # Navigate to a page that requires auth — Indeed redirects to login if not logged in
        page.goto("https://www.indeed.com/myjobs", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2500)  # allow any auth redirects to settle
        if "indeed.com/myjobs" in page.url or "indeed.com/myresumes" in page.url:
            return True  # stayed on protected page → we're logged in

        # Session missing or expired — need manual login (supports Google OAuth)
        if self.headless:
            logger.error(
                "Indeed session not found. Set HEADLESS=False in config.py, "
                "then run once to complete login manually."
            )
            return False

        print("\n[Indeed] Not logged in — opening login page.")
        print("Sign in using Google or any method, then return here and press Enter.\n")
        page.goto(_LOGIN_URL)
        input("Press Enter after you are signed in to Indeed → ")
        self._save_session(context)
        logger.info("Indeed session saved — future runs will skip login.")
        return True

    # ── Form walking ──────────────────────────────────────────────────────────

    def _walk_form(self, page, job: dict, pdf_path: str) -> dict:
        uploaded = False

        for step in range(15):
            page.wait_for_timeout(int(_STEP_DELAY * 1000))

            # -- Upload resume ------------------------------------------------
            if not uploaded:
                try:
                    fi = page.locator(
                        'input[type="file"], '
                        'input[accept*="pdf"]'
                    ).first
                    if fi.is_visible(timeout=500):
                        fi.set_input_files(pdf_path)
                        page.wait_for_timeout(1200)
                        uploaded = True
                    else:
                        # Click "Upload new resume" if present
                        upload_lnk = page.locator(
                            'button:has-text("Upload new resume"), '
                            'a:has-text("Upload new resume")'
                        ).first
                        if upload_lnk.is_visible(timeout=400):
                            upload_lnk.click()
                            page.wait_for_timeout(800)
                            page.locator('input[type="file"]').first.set_input_files(pdf_path)
                            page.wait_for_timeout(1200)
                            uploaded = True
                except Exception:
                    pass

            # -- Fill text fields ---------------------------------------------
            self._fill_text_fields(page)
            self._fill_selects(page)
            self._handle_radios(page)

            # -- Navigation ---------------------------------------------------
            continue_btn = page.locator(
                'button:has-text("Continue"), '
                'button[type="submit"]:has-text("Continue")'
            ).first
            submit_btn = page.locator(
                'button:has-text("Submit your application"), '
                'button:has-text("Submit application"), '
                'button[type="submit"]:has-text("Submit")'
            ).first

            if submit_btn.is_visible(timeout=500):
                submit_btn.click()
                page.wait_for_timeout(3000)
                confirm = page.locator(
                    'h1:has-text("Your application has been submitted"), '
                    'div:has-text("application submitted"), '
                    'h2:has-text("Your application was sent")'
                ).first
                if confirm.is_visible(timeout=5000):
                    return {"success": True, "notes": "Submitted via Indeed Apply"}
                return {"success": True, "notes": "Submit clicked — confirm manually"}

            elif continue_btn.is_visible(timeout=400):
                continue_btn.click()
            else:
                generic = page.locator('button[type="submit"]:visible').last
                if generic.count() and generic.is_visible(timeout=400):
                    generic.click()
                else:
                    return {"success": False, "notes": f"Stuck at step {step}"}

        return {"success": False, "notes": "Exceeded max Indeed Apply steps (15)"}

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fill_text_fields(self, page):
        selectors = (
            'input[type="text"]:visible, input[type="number"]:visible, '
            'input[type="tel"]:visible, input[type="email"]:visible'
        )
        for field in page.locator(selectors).all():
            try:
                if field.input_value():
                    continue
                label = self._get_label_text(field, page)
                value = self._infer_value(label)
                if value is not None:
                    field.fill(value)
                elif field.get_attribute("type") == "number":
                    field.fill("1")
            except Exception:
                pass

    def _fill_selects(self, page):
        for sel in page.locator("select:visible").all():
            try:
                if sel.input_value():
                    continue
                label   = self._get_label_text(sel, page)
                profile_val = self._infer_value(label)
                options = sel.locator("option").all()
                non_empty = [
                    o for o in options
                    if (o.get_attribute("value") or "").strip()
                    not in ("", "Select", "Please select")
                ]
                if not non_empty:
                    continue
                if profile_val:
                    matched = [
                        o for o in non_empty
                        if profile_val.lower() in (o.inner_text() or "").lower()
                    ]
                    if matched:
                        sel.select_option(value=matched[0].get_attribute("value"))
                        continue
                sel.select_option(value=non_empty[0].get_attribute("value"))
            except Exception:
                pass

    def _handle_radios(self, page):
        handled: set = set()
        for radio in page.locator('input[type="radio"]:visible').all():
            try:
                name  = radio.get_attribute("name") or ""
                if name in handled:
                    continue
                value = (radio.get_attribute("value") or "").lower()
                if value in ("yes", "true", "1", "y"):
                    radio.check()
                    handled.add(name)
                elif name not in handled:
                    radio.check()
                    handled.add(name)
            except Exception:
                pass
