"""
applicator/ats/ashby.py
Automates Ashby HQ job applications.

Ashby forms are React-based but consistent in structure:
  URL pattern : jobs.ashbyhq.com/{company}/{id}/application
  Fields      : name, email, phone, resume upload, cover letter,
                social links, optional custom questions
  Submit      : button with text "Submit Application"
"""

import logging

from playwright.sync_api import sync_playwright

from applicator.base import BaseApplicator, get_cover_letter

logger = logging.getLogger(__name__)


class AshbyApplicator(BaseApplicator):
    PLATFORM = "ashby"

    def apply(self, job: dict, pdf_path: str, dry_run: bool = False) -> dict:
        url = job.get("apply_url_direct") or job.get("apply_url") or ""
        if not url:
            return {"success": False, "notes": "No apply URL"}
        # Ensure we land on the /application page
        if "/application" not in url:
            url = url.rstrip("/") + "/application"

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            page    = browser.new_page()
            try:
                self._update_for_job(job)
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2000)

                if dry_run:
                    return {"success": True, "notes": f"DRY RUN — would apply at {url}"}

                # Ashby renders fields lazily; wait for the form
                page.wait_for_selector('form', timeout=8000)

                # -- Resume upload (must come first — Ashby validates it) ----
                try:
                    fi = page.locator('input[type="file"]').first
                    if fi.is_visible(timeout=1000):
                        fi.set_input_files(pdf_path)
                        page.wait_for_timeout(1500)
                    else:
                        # Ashby sometimes hides the input behind a button
                        upload_btn = page.locator(
                            'button:has-text("Upload"), label:has-text("Upload")'
                        ).first
                        if upload_btn.is_visible(timeout=600):
                            upload_btn.click()
                            page.wait_for_timeout(500)
                            page.locator('input[type="file"]').first.set_input_files(pdf_path)
                            page.wait_for_timeout(1500)
                except Exception as e:
                    logger.warning(f"Ashby resume upload failed: {e}")

                # -- Standard fields (Ashby uses placeholder / aria-label) ---
                self._fill_all_text_fields(page)

                # -- Cover letter textarea ------------------------------------
                cover = get_cover_letter(job["job_id"])
                if cover:
                    for ta in page.locator('textarea:visible').all():
                        try:
                            if not ta.input_value():
                                ta.fill(cover)
                                break
                        except Exception:
                            pass

                # -- Selects / radios -----------------------------------------
                self._fill_selects(page)
                self._handle_radios(page)

                # -- Submit ---------------------------------------------------
                submit = page.locator(
                    'button:has-text("Submit Application"), '
                    'button[type="submit"]:has-text("Submit")'
                ).first
                submit.wait_for(state="visible", timeout=6000)
                submit.click()
                page.wait_for_timeout(3000)

                confirm = page.locator(
                    'h1:has-text("Application submitted"), '
                    'div:has-text("Thank you for applying"), '
                    'p:has-text("application received")'
                ).first
                if confirm.is_visible(timeout=5000):
                    return {"success": True, "notes": "Submitted via Ashby"}
                return {"success": True, "notes": "Submit clicked — confirm manually"}

            except Exception as e:
                logger.exception("Ashby apply error")
                return {"success": False, "notes": str(e)}
            finally:
                browser.close()

    def _fill_all_text_fields(self, page):
        selectors = (
            'input[type="text"]:visible, input[type="email"]:visible, '
            'input[type="tel"]:visible, input[type="number"]:visible'
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
                options = sel.locator("option").all()
                non_empty = [
                    o for o in options
                    if (o.get_attribute("value") or "").strip() not in ("", "Select", "--")
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
