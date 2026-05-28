"""
applicator/ats/greenhouse.py
Automates Greenhouse.io job applications.

Greenhouse forms are standardized across all companies:
  URL pattern : boards.greenhouse.io/{company}/jobs/{id}
  Form fields : first_name, last_name, email, phone, resume upload,
                cover_letter, optional custom questions
  Submit      : input[type="submit"] or button[type="submit"]
"""

import logging

from playwright.sync_api import sync_playwright

from applicator.base import BaseApplicator, get_cover_letter

logger = logging.getLogger(__name__)


class GreenhouseApplicator(BaseApplicator):
    PLATFORM = "greenhouse"

    def apply(self, job: dict, pdf_path: str, dry_run: bool = False) -> dict:
        url = job.get("apply_url_direct") or job.get("apply_url") or ""
        # Greenhouse apply page is usually /jobs/{id}/apply — append if missing
        if "/apply" not in url:
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

                # -- Standard identity fields ---------------------------------
                self._safe_fill(page, "#first_name",  self.profile["first_name"])
                self._safe_fill(page, "#last_name",   self.profile["last_name"])
                self._safe_fill(page, "#email",       self.profile["email"])
                self._safe_fill(page, "#phone",       self.profile["phone"])

                # -- Resume upload --------------------------------------------
                self._upload_resume(page, pdf_path)

                # -- Cover letter ---------------------------------------------
                cover = get_cover_letter(job["job_id"])
                if cover:
                    self._safe_fill(page, "#cover_letter_text", cover)
                    # Some Greenhouse forms use a file upload for CL
                    cl_file = page.locator(
                        'input[name="cover_letter"], input[id*="cover_letter_file"]'
                    ).first
                    if cl_file.is_visible(timeout=400):
                        # Skip file upload for cover letter — text field is sufficient
                        pass

                # -- LinkedIn / website fields --------------------------------
                self._safe_fill(page, 'input[name*="linkedin"], input[id*="linkedin"]',
                                self.profile["linkedin_url"])
                self._safe_fill(page, 'input[name*="website"], input[id*="website"]',
                                self.profile["linkedin_url"])
                self._safe_fill(page, 'input[name*="github"], input[id*="github"]',
                                self.profile["github_url"])

                # -- Custom questions (best-effort) ---------------------------
                self._fill_custom_questions(page)

                # -- Submit ---------------------------------------------------
                submit = page.locator(
                    'input[type="submit"], button[type="submit"]:has-text("Submit")'
                ).first
                submit.wait_for(state="visible", timeout=5000)
                submit.click()
                page.wait_for_timeout(3000)

                # Greenhouse shows "Your application has been submitted" on success
                confirm = page.locator(
                    'h1:has-text("submitted"), '
                    'div:has-text("Thank you for applying"), '
                    'p:has-text("application has been submitted")'
                ).first
                if confirm.is_visible(timeout=5000):
                    return {"success": True, "notes": "Submitted via Greenhouse"}
                return {"success": True, "notes": "Submit clicked — confirm manually"}

            except Exception as e:
                logger.exception("Greenhouse apply error")
                return {"success": False, "notes": str(e)}
            finally:
                browser.close()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _safe_fill(self, page, selector: str, value: str):
        if not value:
            return
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=400):
                el.fill(value)
        except Exception:
            pass

    def _upload_resume(self, page, pdf_path: str):
        selectors = [
            'input#resume',
            'input[name="resume"]',
            'input[accept*="pdf"]',
            'input[type="file"]',
        ]
        for sel in selectors:
            try:
                fi = page.locator(sel).first
                if fi.is_visible(timeout=400):
                    fi.set_input_files(pdf_path)
                    page.wait_for_timeout(1000)
                    return
                # Hidden input triggered by a button
                btn = page.locator(
                    'a:has-text("Attach"), button:has-text("Attach"), '
                    'a:has-text("Upload"), button:has-text("Upload resume")'
                ).first
                if btn.is_visible(timeout=400):
                    btn.click()
                    page.wait_for_timeout(500)
                    fi.set_input_files(pdf_path)
                    page.wait_for_timeout(1000)
                    return
            except Exception:
                continue

    def _fill_custom_questions(self, page):
        """Best-effort fill for Greenhouse custom questions."""
        for field in page.locator(
            '.field input[type="text"]:visible, '
            '.field input[type="number"]:visible, '
            '.field textarea:visible'
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

        for sel in page.locator('.field select:visible').all():
            try:
                if sel.input_value():
                    continue
                label   = self._get_label_text(sel, page)
                options = sel.locator("option").all()
                non_empty = [
                    o for o in options
                    if (o.get_attribute("value") or "").strip()
                    not in ("", "Select", "--")
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
