"""PDF report (reports layer), built with ReportLab."""

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from data.models import format_money as _format_money


def format_money(minor, currency="INR"):
    """Like the normal formatter, but PDF-safe: the built-in PDF font has no ₹."""
    return _format_money(minor, currency).replace("₹", "Rs. ")


def _table(rows, widths=None):
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f3e5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def build_pdf(group, members, expenses, balances, settlements, names):
    """Return the PDF report as bytes."""
    cur = group.base_currency
    styles = getSampleStyleSheet()
    cell = styles["BodyText"]
    cell.fontSize = 8

    def p(text):  # wrapping cell; escape() stops user text breaking the markup
        return Paragraph(escape(str(text)), cell)

    story = [
        Paragraph("FairShare Report", styles["Title"]),
        Paragraph(escape(f"Group: {group.name} ({cur})"), styles["Heading2"]),
        Paragraph(f"Members: {len(members)} | Expenses: {len(expenses)} | "
                  f"Total spending: {format_money(sum(e.base_amount for e in expenses), cur)}",
                  styles["Normal"]),
        Spacer(1, 12),
    ]

    story.append(Paragraph("Members", styles["Heading3"]))
    story.append(_table([["Name", "Status"]] + [
        [p(m.name), "Active" if m.is_active else "Inactive"] for m in members]))

    story.append(Paragraph("Expenses", styles["Heading3"]))
    rows = [["Date", "Expense", "Category", "Split", "Amount", "Paid by", "Shares"]]
    for e in expenses:
        rows.append([
            e.expense_date, p(e.title), e.category, e.split_method,
            format_money(e.base_amount, cur),
            p(", ".join(f"{names[x.member_id]} {format_money(x.amount_paid, cur)}"
                        for x in e.payers)),
            p(", ".join(f"{names[s.member_id]} {format_money(s.share_amount, cur)}"
                        for s in e.splits)),
        ])
    story.append(_table(rows, [50, 70, 55, 45, 55, 100, 120]))

    story.append(Paragraph("Net balances", styles["Heading3"]))
    story.append(_table([["Member", "Paid", "Owed (share)", "Net"]] + [
        [p(names[m]), format_money(b["paid"], cur), format_money(b["owed"], cur),
         format_money(b["net"], cur)] for m, b in balances.items()
        if b["paid"] or b["owed"]]))

    story.append(Paragraph("Settlements", styles["Heading3"]))
    if settlements:
        story.append(_table([["From", "To", "Amount", "Status"]] + [
            [p(names[s.from_member_id]), p(names[s.to_member_id]),
             format_money(s.amount, cur), s.status] for s in settlements]))
    else:
        story.append(Paragraph("No settlements generated yet.", styles["Normal"]))

    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=30, rightMargin=30,
                      topMargin=30, bottomMargin=30).build(story)
    return buffer.getvalue()