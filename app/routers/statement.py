import csv
import io
import re
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.models.wallet import Wallet
from app.models.account import Account
from app.models.ledger_entry import LedgerEntry
from app.models.transaction import Transaction


router = APIRouter(tags=["Statements"])

CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(CENT)


def build_statement(db, user, month):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
        raise HTTPException(
            status_code=422,
            detail="Month must use YYYY-MM format"
        )

    year, month_number = map(int, month.split("-"))
    start = datetime(year, month_number, 1)

    if month_number == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month_number + 1, 1)

    wallet = db.query(Wallet).filter(
        Wallet.owner_id == user.id
    ).first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    account = db.query(Account).filter(
        Account.wallet_id == wallet.id
    ).first()

    if not account:
        raise HTTPException(404, "Wallet ledger account not found")

    # Read all wallet ledger entries in chronological order.
    entries = (
        db.query(LedgerEntry, Transaction)
        .join(
            Transaction,
            LedgerEntry.transaction_id == Transaction.id
        )
        .filter(
            LedgerEntry.account_id == account.id,
            LedgerEntry.created_at < end
        )
        .order_by(
            LedgerEntry.created_at.asc(),
            LedgerEntry.id.asc()
        )
        .all()
    )

    opening = Decimal("0.00")
    rows = []
    total_credits = Decimal("0.00")
    total_debits = Decimal("0.00")

    for entry, transaction in entries:
        amount = money(entry.amount)

        if entry.created_at < start:
            if entry.entry_type == "Credit":
                opening += amount
            else:
                opening -= amount
            continue

        if entry.entry_type == "Credit":
            total_credits += amount
        else:
            total_debits += amount

        rows.append({
            "date": entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "reference": transaction.transaction_ref,
            "type": transaction.type,
            "description": transaction.description or "",
            "entry_type": entry.entry_type,
            "credit": amount if entry.entry_type == "Credit" else Decimal("0.00"),
            "debit": amount if entry.entry_type == "Debit" else Decimal("0.00"),
            "balance": money(entry.balance_after)
        })

    closing = money(opening + total_credits - total_debits)

    return {
        "name": user.full_name,
        "wallet_number": wallet.wallet_number,
        "month": month,
        "opening": money(opening),
        "credits": money(total_credits),
        "debits": money(total_debits),
        "closing": closing,
        "rows": rows
    }


@router.get("/statements")
def download_statement(
    month: str = Query(..., description="YYYY-MM"),
    format: str = Query(..., pattern="^(pdf|csv)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    data = build_statement(db, current_user, month)

    filename = (
        f"statement_{data['wallet_number']}_{month}.{format}"
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Digital Wallet Statement"])
        writer.writerow(["Name", data["name"]])
        writer.writerow(["Wallet Number", data["wallet_number"]])
        writer.writerow(["Period", month])
        writer.writerow(["Opening Balance", data["opening"]])
        writer.writerow([])

        writer.writerow([
            "Date", "Transaction Reference", "Type",
            "Description", "Entry", "Credit", "Debit",
            "Balance After"
        ])

        for row in data["rows"]:
            writer.writerow([
                row["date"],
                row["reference"],
                row["type"],
                row["description"],
                row["entry_type"],
                row["credit"],
                row["debit"],
                row["balance"]
            ])

        writer.writerow([])
        writer.writerow(["Total Credits", data["credits"]])
        writer.writerow(["Total Debits", data["debits"]])
        writer.writerow(["Closing Balance", data["closing"]])

        output.seek(0)

        return StreamingResponse(
            iter([output.getvalue().encode("utf-8-sig")]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=30,
        rightMargin=30
    )

    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Digital Wallet Statement", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Name: {data['name']}", styles["Normal"]),
        Paragraph(
            f"Wallet Number: {data['wallet_number']}",
            styles["Normal"]
        ),
        Paragraph(f"Period: {month}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            f"Opening Balance: INR {data['opening']}",
            styles["Normal"]
        ),
        Spacer(1, 12)
    ]

    table_data = [[
        "Date", "Reference", "Type", "Credit", "Debit", "Balance"
    ]]

    for row in data["rows"]:
        table_data.append([
            row["date"][:10],
            row["reference"],
            row["type"],
            str(row["credit"]),
            str(row["debit"]),
            str(row["balance"])
        ])

    table = Table(
        table_data,
        repeatRows=1,
        colWidths=[65, 145, 105, 60, 60, 60]
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15))

    elements.extend([
        Paragraph(
            f"Total Credits: INR {data['credits']}",
            styles["Normal"]
        ),
        Paragraph(
            f"Total Debits: INR {data['debits']}",
            styles["Normal"]
        ),
        Paragraph(
            f"Closing Balance: INR {data['closing']}",
            styles["Normal"]
        )
    ])

    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


    