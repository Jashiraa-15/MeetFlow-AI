import io
import csv
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.database import get_db
from app.models import User, Meeting, ActionItem
from app.auth import get_current_user

router = APIRouter(prefix="/export", tags=["Exports"])

@router.get("/{meeting_id}")
def export_meeting_csv(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports action items of the specified meeting as a CSV file.
    Only accessible by the meeting's owner.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.user_id == current_user.id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting #{meeting_id} not found or access denied"
        )

    output = io.StringIO()
    writer = csv.writer(output)

    # Write headers exactly as specified
    headers = [
        "id",
        "task",
        "owner",
        "deadline",
        "priority",
        "category",
        "confidence",
        "needs_clarification",
        "is_confirmed",
        "status",
        "mention_count",
        "source_sentence",
        "created_at",
        "updated_at"
    ]
    writer.writerow(headers)

    # Write rows
    for item in meeting.action_items:
        writer.writerow([
            item.id,
            item.task,
            item.owner if item.owner else "",
            item.deadline.isoformat() if item.deadline else "",
            item.priority,
            item.category,
            item.confidence,
            "true" if item.needs_clarification else "false",
            "true" if item.is_confirmed else "false",
            item.status,
            item.mention_count,
            item.source_sentence if item.source_sentence else "",
            item.created_at.isoformat() if item.created_at else "",
            item.updated_at.isoformat() if item.updated_at else ""
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"meeting_{meeting_id}_action_items.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{meeting_id}/pdf")
def export_meeting_pdf(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports meeting details, action items, and decisions as a landscape PDF document.
    Only accessible by the meeting's owner.
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.user_id == current_user.id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting #{meeting_id} not found or access denied"
        )

    buffer = io.BytesIO()
    # Use landscape letter orientation for optimal table width
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A")
    )
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569")
    )
    h2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#1E293B")
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )
    cell_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0F172A")
    )

    elements = []

    # Title & Metadata
    title_text = meeting.title or f"Meeting #{meeting.id}"
    elements.append(Paragraph(f"<b>{title_text}</b>", title_style))
    elements.append(Spacer(1, 6))
    
    action_item_count = len(meeting.action_items)
    meta_line = (
        f"<b>Meeting Date:</b> {meeting.meeting_date} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Action-Item Count:</b> {action_item_count} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Sentiment:</b> {meeting.sentiment or 'N/A'}"
    )
    elements.append(Paragraph(meta_line, meta_style))
    elements.append(Spacer(1, 14))

    # Action Items Table
    elements.append(Paragraph("<b>Action Items</b>", h2_style))
    elements.append(Spacer(1, 6))

    table_data = [[
        Paragraph("<b>#</b>", cell_header),
        Paragraph("<b>Task</b>", cell_header),
        Paragraph("<b>Owner</b>", cell_header),
        Paragraph("<b>Deadline</b>", cell_header),
        Paragraph("<b>Priority</b>", cell_header),
        Paragraph("<b>Category</b>", cell_header),
        Paragraph("<b>Status</b>", cell_header),
        Paragraph("<b>Clarify?</b>", cell_header),
        Paragraph("<b>Confirmed?</b>", cell_header)
    ]]

    for idx, item in enumerate(meeting.action_items, 1):
        table_data.append([
            Paragraph(str(idx), cell_style),
            Paragraph(item.task, cell_style),
            Paragraph(item.owner if item.owner else "—", cell_style),
            Paragraph(item.deadline.isoformat() if item.deadline else "—", cell_style),
            Paragraph(item.priority, cell_style),
            Paragraph(item.category, cell_style),
            Paragraph(item.status, cell_style),
            Paragraph("Yes" if item.needs_clarification else "No", cell_style),
            Paragraph("Yes" if item.is_confirmed else "No", cell_style)
        ])

    if action_item_count > 0:
        # Total printable width on landscape letter: ~736pt
        col_widths = [24, 250, 75, 75, 55, 75, 65, 55, 62]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("<i>No action items recorded for this meeting.</i>", meta_style))

    elements.append(Spacer(1, 14))

    # Decisions Section
    if meeting.decisions:
        elements.append(Paragraph("<b>Decisions Made</b>", h2_style))
        elements.append(Spacer(1, 6))
        for idx, dec in enumerate(meeting.decisions, 1):
            dec_text = f"<b>{idx}. {dec.decision_text}</b>"
            if dec.context:
                dec_text += f"<br/><font color='#64748B'><i>Context: {dec.context}</i></font>"
            elements.append(Paragraph(dec_text, cell_style))
            elements.append(Spacer(1, 4))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"meeting_{meeting_id}_action_items.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

