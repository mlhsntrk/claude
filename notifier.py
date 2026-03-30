"""
Result reporting and notifications.

Formats the per-country check results as a readable console summary
and highlights any countries where appointments are available.
Also sends the summary by email after each job cycle.
"""
import logging
import smtplib
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED  = "FAILED"
STATUS_ERROR   = "ERROR"

_ICON = {
    STATUS_SUCCESS: "[RANDEVU VAR]",
    STATUS_FAILED:  "[YOK]        ",
    STATUS_ERROR:   "[HATA]       ",
}

_LINE_WIDTH = 72


def print_results(results: List[dict]) -> None:
    """
    Print a formatted summary table to stdout.

    Example output:
    ════════════════════════════════════════════════════════════════════════
      VFS Randevu Kontrol — 2026-03-30 14:35:00
    ════════════════════════════════════════════════════════════════════════
      [YOK]         İsviçre (Switzerland)   | Randevu bulunamadı
      [YOK]         Fransa (France)         | Randevu bulunamadı
      [RANDEVU VAR] Avusturya (Austria)     | Randevu mevcut! Devam Et aktif.
      [HATA]        Hollanda (Netherlands)  | Timeout: element not found
    ════════════════════════════════════════════════════════════════════════

      *** RANDEVU MEVCUT: Avusturya (Austria) ***

    """
    separator = "═" * _LINE_WIDTH
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{separator}")
    print(f"  VFS Randevu Kontrol — {now}")
    print(separator)

    for r in results:
        icon   = _ICON.get(r["status"], "[?]          ")
        country = r.get("country", r.get("code", "?"))
        detail  = r.get("detail", "")
        # Truncate detail for table width
        detail_short = detail[:45] + "…" if len(detail) > 45 else detail
        print(f"  {icon}  {country:<28} | {detail_short}")

    print(separator)

    successes = [r for r in results if r["status"] == STATUS_SUCCESS]
    if successes:
        names = ", ".join(r.get("country", r.get("code")) for r in successes)
        print(f"\n  {'*' * 3} RANDEVU MEVCUT: {names} {'*' * 3}\n")
    else:
        failed  = sum(1 for r in results if r["status"] == STATUS_FAILED)
        errors  = sum(1 for r in results if r["status"] == STATUS_ERROR)
        print(f"\n  Tüm {len(results)} ülke kontrol edildi — {failed} randevu yok, {errors} hata.\n")


def build_notification_message(results: List[dict]) -> str:
    """
    Build a concise notification string suitable for messaging integrations.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"VFS Randevu Kontrol [{now}]"]
    for r in results:
        icon = "✅" if r["status"] == STATUS_SUCCESS else "❌" if r["status"] == STATUS_FAILED else "⚠️"
        country = r.get("country", r.get("code", "?"))
        lines.append(f"{icon} {country}: {r.get('detail', '')[:60]}")
    return "\n".join(lines)


def send_email_report(results: List[dict]) -> None:
    """
    Send the results summary by email via Gmail SMTP.
    Reads GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFICATION_EMAIL from config.
    Silently skips if any of these are not configured.
    """
    from config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFICATION_EMAIL

    if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, NOTIFICATION_EMAIL]):
        logging.warning(
            "Email report skipped — GMAIL_ADDRESS, GMAIL_APP_PASSWORD or "
            "NOTIFICATION_EMAIL is not set in .env"
        )
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    successes = [r for r in results if r["status"] == STATUS_SUCCESS]

    subject = (
        f"✅ VFS RANDEVU MEVCUT — {', '.join(r['country'] for r in successes)}"
        if successes
        else f"❌ VFS Randevu Yok — {now}"
    )

    # --- Plain-text body ---
    plain_lines = [f"VFS Global Randevu Kontrol Raporu\n{now}\n", "─" * 50]
    for r in results:
        icon = "✅" if r["status"] == STATUS_SUCCESS else "❌" if r["status"] == STATUS_FAILED else "⚠️"
        country = r.get("country", r.get("code", "?"))
        plain_lines.append(f"{icon}  {country:<30} {r.get('detail', '')}")
    plain_lines.append("─" * 50)
    if successes:
        plain_lines.append(f"\n*** RANDEVU MEVCUT: {', '.join(r['country'] for r in successes)} ***")
    else:
        plain_lines.append("\nHiçbir konsoloslukta uygun randevu bulunamadı.")
    plain_body = "\n".join(plain_lines)

    # --- HTML body ---
    rows_html = ""
    for r in results:
        color = "#2e7d32" if r["status"] == STATUS_SUCCESS else "#c62828" if r["status"] == STATUS_FAILED else "#e65100"
        icon  = "✅" if r["status"] == STATUS_SUCCESS else "❌" if r["status"] == STATUS_FAILED else "⚠️"
        country = r.get("country", r.get("code", "?"))
        detail  = r.get("detail", "")
        rows_html += (
            f"<tr>"
            f"<td style='padding:8px 12px'>{icon}</td>"
            f"<td style='padding:8px 12px'><b>{country}</b></td>"
            f"<td style='padding:8px 12px;color:{color}'>{detail}</td>"
            f"</tr>"
        )

    banner = ""
    if successes:
        names = ", ".join(r["country"] for r in successes)
        banner = (
            f"<div style='background:#2e7d32;color:white;padding:14px 20px;"
            f"border-radius:6px;font-size:16px;margin-bottom:20px'>"
            f"🎉 <b>RANDEVU MEVCUT:</b> {names}</div>"
        )

    html_body = f"""
    <html><body style='font-family:Arial,sans-serif;max-width:640px;margin:0 auto'>
      <h2 style='color:#1a237e'>VFS Global Randevu Kontrol</h2>
      <p style='color:#555'>{now}</p>
      {banner}
      <table border='0' cellspacing='0' cellpadding='0'
             style='border-collapse:collapse;width:100%;border:1px solid #ddd;border-radius:6px'>
        <thead>
          <tr style='background:#e8eaf6'>
            <th style='padding:10px 12px;text-align:left'></th>
            <th style='padding:10px 12px;text-align:left'>Ülke</th>
            <th style='padding:10px 12px;text-align:left'>Sonuç</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style='color:#999;font-size:12px;margin-top:20px'>
        Bu e-posta VFS randevu kontrol botu tarafından otomatik gönderilmiştir.
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = NOTIFICATION_EMAIL
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        logging.info(f"Email report sent to {NOTIFICATION_EMAIL}")
    except smtplib.SMTPAuthenticationError:
        logging.error("Email report failed: Gmail authentication error. Check GMAIL_APP_PASSWORD in .env")
    except Exception as exc:
        logging.error(f"Email report failed: {exc}")
