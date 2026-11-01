"""
Playwright-based PDF generator for executive reports.
Renders standalone HTML documents into print-ready vector PDF packets.
Licensed under GNU AGPLv3.
"""

import os
from rich.console import Console

console = Console()


def _launch_print_browser(playwright_instance):
    """
    Launch headless Chromium, Microsoft Edge, or Google Chrome for PDF printing.
    Discovers installed system browsers gracefully.
    """
    from ..auth.portal_auth import load_config

    cfg = load_config()
    browser_id = cfg.get("browser_id", "msedge")
    preferred = "msedge" if browser_id == "msedge" else ("chrome" if browser_id == "chrome" else None)

    for ch in [preferred, "msedge", "chrome", None]:
        try:
            if ch:
                return playwright_instance.chromium.launch(channel=ch, headless=True)
            return playwright_instance.chromium.launch(headless=True)
        except Exception:
            continue

    raise RuntimeError(
        "No compatible browser found for PDF generation. "
        "Install Microsoft Edge, Google Chrome, or run 'playwright install chromium'."
    )


def is_pdf_generation_available() -> bool:
    """Check if Playwright and a compatible browser are available for PDF generation."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = _launch_print_browser(p)
            browser.close()
            return True
    except Exception:
        return False


def render_html_to_pdf(
    html_path: str,
    output_pdf_path: str,
    header_title: str = "Microsoft Intune Security Posture Assessment",
) -> str:
    """
    Render a local HTML document to a vector PDF using Playwright headless Chromium.
    Applies print CSS margins, background graphics, and dynamic page numbering.
    """
    if not os.path.exists(html_path):
        raise FileNotFoundError(f"HTML source file not found: {html_path}")

    from playwright.sync_api import sync_playwright

    out_dir = os.path.dirname(os.path.abspath(output_pdf_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    abs_html = os.path.abspath(html_path)
    file_url = f"file://{abs_html}"

    header_html = (
        f'<div style="font-size: 8px; font-family: sans-serif; color: #64748b; '
        f'width: 100%; text-align: right; padding-right: 12mm;">'
        f'{header_title} | Confidential</div>'
    )
    footer_html = (
        '<div style="font-size: 8px; font-family: sans-serif; color: #64748b; '
        'width: 100%; text-align: center;">'
        'Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>'
    )

    with sync_playwright() as p:
        browser = _launch_print_browser(p)
        page = browser.new_page()
        page.goto(file_url, wait_until="networkidle")
        page.pdf(
            path=output_pdf_path,
            format="Letter",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "12mm", "right": "12mm"},
            display_header_footer=True,
            header_template=header_html,
            footer_template=footer_html,
        )
        browser.close()

    return os.path.abspath(output_pdf_path)
