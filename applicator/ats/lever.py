"""
applicator/ats/lever.py
Automates Lever.co job applications.

Lever apply pages are single-page forms with a consistent layout:
  URL pattern : jobs.lever.co/{company}/{id}/apply
  Fields      : name, email, phone, org (current company), resume upload,
                cover letter (textarea), optional custom questions
  Submit      : button[type="submit"] with text "Submit application"
"""

import logging

from playwright.sync_api import sync_playwright

from applicator.base import BaseApplicator, get_cover_letter

logger = logging.getLogger(__name__)


class LeverApplicator(BaseApplicator):
    PLATFORM = "lever"

    def apply(self, job: dict, pdf_path: str, dry_run: bool = False) -> dict:
        url = job.get("apply_url_direct") or job.get("apply_url") or ""
        if not url:
            return {"success": False, "notes": "No apply URL"}
        # Ensure we land on the /apply page
        if not url.endswith("/apply"):
            url = url.rstrip("/") + "/apply"

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            page    = browser.new_page()
            try:
                self._update_for_job(job)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1500)

                if dry_run:
                    return {"success": True, "notes": f"DRY RUN — would apply at {url}"}

                # -- Standard Lever fields ------------------------------------
                self._safe_fill(page, 'input[name="name"]',  self.profile["full_name"])
                self._safe_fill(page, 'input[name="email"]', self.profile["email"])
                self._safe_fill(page, 'input[name="phone"]', self.profile["phone"])
                # "org" = current company / most recent employer
                self._safe_fill(page, 'input[name="org"]',   self.profile.get("current_company", ""))
                self._safe_fill(page, 'input[name*="linkedin"]', self.profile["linkedin_url"])
                self._safe_fill(page, 'input[name*="github"]',   self.profile["github_url"])
                self._safe_fill(page, 'input[name*="website"]',  self.profile["linkedin_url"])

                # -- Resume upload --------------------------------------------
                try:
                    fi = page.locator(
                        'input[type="file"], input[name="resume"]'
                    ).first
                    fi.set_input_files(pdf_path)
                    page.wait_for_timeout(1000)
                except Exception as e:
                    logger.warning(f"Lever resume upload failed: {e}")

                # -- Cover letter (textarea) ----------------------------------
                cover = get_cover_letter(job["job_id"])
                if cover:
                    self._safe_fill(page, 'textarea[name="comments"]', cover)
                    self._safe_fill(page, 'textarea[class*="cover"]',  cover)

                # -- Custom questions (best-effort) ---------------------------
                self._fill_custom_questions(page)

                # -- Submit ---------------------------------------------------
                submit = page.locator(
                    'button[type="submit"]:has-text("Submit"), '
                    'button:has-text("Submit application")'
                ).first
                submit.wait_for(state="visible", timeout=5000)
                submit.click()
                page.wait_for_timeout(3000)

                confirm = page.locator(
                    'h2:has-text("Thanks for applying"), '
                    'div:has-text("application has been submitted"), '
                    'p:has-text("Thank you")'
                ).first
                if confirm.is_visible(timeout=5000):
                    return {"success": True, "notes": "Submitted via Lever"}
                return {"success": True, "notes": "Submit clicked — confirm manually"}

            except Exception as e:
                logger.exception("Lever apply error")
                return {"success": False, "notes": str(e)}
            finally:
                browser.close()

    def _safe_fill(self, page, selector: str, value: str):
        if not value:
            return
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=400):
                el.fill(value)
        except Exception:
            pass

    def _fill_custom_questions(self, page):
        for field in page.locator(
            '.application-question input[type="text"]:visible, '
            '.application-question textarea:visible'
        ).all():
            try:
                if field.input_value():
                    continue
                label = self._get_label_text(field, page)
                value = self._infer_value(label)
                if value is not None:
                    field.fill(value)
            except Exception:
                pass

        for sel in page.locator('.application-question select:visible').all():
            try:
                if sel.input_value():
                    continue
                label   = self._get_label_text(sel, page)
                options = sel.locator("option").all()
                non_empty = [
                    o for o in options
                    if (o.get_attribute("value") or "").strip() not in ("", "--", "Select")
                ]
                if not non_empty:
                    continue
                pval = self._infer_value(label)
                if pval:
                    matched = [o for o in non_empty
                               if pval.lower() in (o.inner_text() or "").lower()]
                    if matched:
                        sel.select_option(value=matched[0].get_attribute("value"))
                        continue
                sel.select_option(value=non_empty[0].get_attribute("value"))
            except Exception:
                pass
