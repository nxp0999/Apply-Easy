"""
applicator/linkedin.py
Automates LinkedIn Easy Apply using Playwright.

Session is persisted to output/.linkedin_session.json so login only happens once.
If the session expires or 2FA is required, the applicator will pause and print
instructions for the user to complete login manually (only when headless=False).
"""

import logging

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from .base import BaseApplicator
from credentials import cred_store
from config import LINKEDIN_EMAIL as LOGIN_EMAIL, LINKEDIN_PASSWORD as LOGIN_PASSWORD

logger = logging.getLogger(__name__)

_SESSION_KEY = "linkedin_session"
_LOGIN_URL   = "https://www.linkedin.com/login"
_FEED_URL    = "https://www.linkedin.com/feed"

# Seconds to pause between Easy Apply steps (avoids bot detection)
_STEP_DELAY = 1.2


class LinkedInApplicator(BaseApplicator):
    PLATFORM = "linkedin"

    def apply(self, job: dict, pdf_path: str, dry_run: bool = False) -> dict:
        with sync_playwright() as p:
            browser = self._launch_browser(p)
            context = self._load_session(browser)
            page    = context.new_page()

            try:
                if not self._ensure_logged_in(page, context):
                    return {"success": False, "notes": "LinkedIn login failed or requires manual 2FA"}

                self._update_for_job(job)
                url = job.get("apply_url") or job.get("apply_url_direct") or ""
                if not url:
                    return {"success": False, "notes": "No apply URL found"}

                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)

                # Locate and click Easy Apply button
                try:
                    ea_btn = page.locator(
                        'button:has-text("Easy Apply"), '
                        'a:has-text("Easy Apply")'
                    ).first
                    ea_btn.wait_for(state="visible", timeout=8000)
                    if dry_run:
                        return {"success": True, "notes": "DRY RUN — Easy Apply button found, not clicked"}
                    ea_btn.click()
                    page.wait_for_timeout(1500)
                except PWTimeout:
                    return {"success": False, "notes": "Easy Apply button not found on page"}

                # Walk through the multi-step modal
                return self._walk_form(page, job, pdf_path)

            except Exception as e:
                logger.exception("LinkedIn apply error")
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
        page.goto(_FEED_URL, wait_until="domcontentloaded", timeout=15000)
        if "/feed" in page.url:
            return True

        # Session missing or expired — auto-login with stored credentials
        if not LOGIN_EMAIL or not LOGIN_PASSWORD:
            logger.error("No login credentials found. Add EMAIL/PASSWORD to _local.py")
            return False

        logger.info("[LinkedIn] Session expired — auto-logging in with stored credentials")
        page.goto(_LOGIN_URL, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(1000)
        try:
            page.fill('input[name="session_key"]',      LOGIN_EMAIL)
            page.fill('input[name="session_password"]', LOGIN_PASSWORD)
            page.click('button[type="submit"]')
            page.wait_for_url("**/feed**", timeout=15000)
            self._save_session(context)
            logger.info("LinkedIn auto-login successful — session saved.")
            return True
        except Exception as e:
            logger.error(f"LinkedIn auto-login failed: {e}")
            return False

    # ── Form walking ──────────────────────────────────────────────────────────

    def _walk_form(self, page, job: dict, pdf_path: str) -> dict:
        """
        Iterates through Easy Apply modal steps: fills fields, uploads resume,
        clicks Next/Review/Submit.
        """
        uploaded = False

        for step in range(20):
            page.wait_for_timeout(int(_STEP_DELAY * 1000))

            # -- Upload resume (only once) ------------------------------------
            if not uploaded:
                try:
                    file_inputs = page.locator('input[type="file"]').all()
                    for fi in file_inputs:
                        if fi.is_visible(timeout=300):
                            fi.set_input_files(pdf_path)
                            page.wait_for_timeout(1200)
                            uploaded = True
                            break
                    if not uploaded:
                        # Some LinkedIn forms hide the input; click the upload button first
                        upload_btn = page.locator(
                            'button:has-text("Upload resume"), '
                            'label:has-text("Upload"), '
                            'button:has-text("Change resume")'
                        ).first
                        if upload_btn.is_visible(timeout=500):
                            upload_btn.click()
                            page.wait_for_timeout(800)
                            fi = page.locator('input[type="file"]').first
                            fi.set_input_files(pdf_path)
                            page.wait_for_timeout(1200)
                            uploaded = True
                except Exception as e:
                    logger.debug(f"Resume upload attempt failed: {e}")

            # -- Fill text / number / tel fields ------------------------------
            self._fill_text_fields(page)

            # -- Fill selects -------------------------------------------------
            self._fill_selects(page)

            # -- Handle radio buttons -----------------------------------------
            self._handle_radios(page)

            # -- Handle checkboxes (e.g., "I agree to terms") -----------------
            self._handle_checkboxes(page)

            # -- Determine navigation button ----------------------------------
            submit_btn = page.locator(
                'button[aria-label="Submit application"], '
                'button:has-text("Submit application")'
            )
            review_btn = page.locator(
                'button[aria-label="Review your application"], '
                'button:has-text("Review")'
            )
            next_btn = page.locator(
                'button[aria-label="Continue to next step"], '
                'button:has-text("Next")'
            )
            if submit_btn.first.is_visible(timeout=600):
                submit_btn.first.click()
                page.wait_for_timeout(2500)
                # Check for success confirmation
                success = page.locator(
                    'h2:has-text("Your application was sent"), '
                    'div:has-text("application was sent"), '
                    'h3:has-text("Application submitted")'
                ).first
                if success.is_visible(timeout=4000):
                    return {"success": True, "notes": "Submitted via LinkedIn Easy Apply"}
                return {"success": True, "notes": "Submit clicked — confirm manually"}

            elif review_btn.first.is_visible(timeout=400):
                review_btn.first.click()

            elif next_btn.first.is_visible(timeout=400):
                next_btn.first.click()

            else:
                # Last resort — look for any visible primary button
                any_btn = page.locator(
                    '.artdeco-button--primary:visible'
                ).last
                if any_btn.count() and any_btn.is_visible(timeout=400):
                    label = any_btn.inner_text().strip()
                    any_btn.click()
                    if "Submit" in label:
                        page.wait_for_timeout(2500)
                        return {"success": True, "notes": "Submitted via Easy Apply (generic button)"}
                else:
                    return {"success": False, "notes": f"Stuck at step {step} — no navigation button found"}

        return {"success": False, "notes": "Exceeded max Easy Apply steps (20)"}

    # ── Field filling helpers ─────────────────────────────────────────────────

    def _fill_text_fields(self, page):
        selectors = (
            'input[type="text"]:visible, '
            'input[type="number"]:visible, '
            'input[type="tel"]:visible, '
            'input[type="email"]:visible'
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
                label = self._get_label_text(sel, page)
                # Try profile value first
                profile_val = self._infer_value(label)
                options = sel.locator("option").all()
                non_empty = [
                    o for o in options
                    if (o.get_attribute("value") or "").strip()
                    not in ("", "Select an option", "Select", "Please select")
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
                name = radio.get_attribute("name") or ""
                if name in handled:
                    continue
                value = (radio.get_attribute("value") or "").lower()
                # Pick "Yes" / "True" when available; otherwise first option
                if value in ("yes", "true", "1", "y"):
                    radio.check()
                    handled.add(name)
                elif name not in handled:
                    radio.check()
                    handled.add(name)
            except Exception:
                pass

    def _handle_checkboxes(self, page):
        for cb in page.locator('input[type="checkbox"]:visible').all():
            try:
                label = self._get_label_text(cb, page)
                # Auto-check consent/terms boxes; leave preference checkboxes alone
                if any(kw in label for kw in ["agree", "consent", "terms", "policy", "acknowledge"]):
                    if not cb.is_checked():
                        cb.check()
            except Exception:
                pass
