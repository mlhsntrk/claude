"""
Result reporting and notifications.

Formats the per-country check results as a readable console summary
and highlights any countries where appointments are available.
"""
from datetime import datetime
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
