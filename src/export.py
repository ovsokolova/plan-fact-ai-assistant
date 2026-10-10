"""Экспорт аналитической записки и графиков.

Соответствует openspec/specs/export.md (Epic 7).
- report_to_docx: ReportJSON -> .docx
- export_charts_html: dict[name, Figure] -> отдельные .html
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt
from plotly.graph_objects import Figure

from src.llm_agent import ReportJSON


def report_to_docx(report: ReportJSON) -> bytes:
    """Рендерит ReportJSON в DOCX, возвращает bytes."""
    doc = Document()

    # Заголовок
    title = doc.add_heading("Аналитическая записка по отклонениям план/факт", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Мета
    meta_p = doc.add_paragraph()
    meta_run = meta_p.add_run(
        f"Сгенерировано: {report.meta.generated_at}\nМодель: {report.meta.model}"
    )
    meta_run.italic = True
    meta_run.font.size = Pt(9)

    if report.meta.masked:
        masked_p = doc.add_paragraph()
        mr = masked_p.add_run("Данные маскированы перед отправкой в LLM")
        mr.italic = True
        mr.font.size = Pt(9)

    # Резюме
    doc.add_heading("Резюме", level=1)
    doc.add_paragraph(report.summary)

    # Items
    for i, item in enumerate(report.items, 1):
        rel_str = f"{item.rel_variance:+.2%}" if item.rel_variance is not None else "н/д"
        doc.add_heading(f"{i}. {item.account} ({item.period})", level=2)

        var_p = doc.add_paragraph()
        var_run = var_p.add_run("Отклонение: ")
        var_run.bold = True
        var_p.add_run(f"{item.abs_variance:+,.0f} ({rel_str})")

        if item.hypotheses:
            doc.add_paragraph("Гипотезы причин:", style="Heading 3")
            for h in item.hypotheses:
                doc.add_paragraph(h, style="List Bullet")

        if item.references:
            doc.add_paragraph("Ссылки на документы:", style="Heading 3")
            for r in item.references:
                clause = f", п. {r.clause}" if r.clause else ""
                page = f", стр. {r.page}" if r.page else ""
                doc.add_paragraph(f"{r.source}{clause}{page}: «{r.quote}»", style="List Bullet")

        if item.questions:
            doc.add_paragraph("Вопросы ответственным:", style="Heading 3")
            for q in item.questions:
                doc.add_paragraph(q, style="List Bullet")

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_charts_html(
    charts: dict[str, Figure],
    output_dir: str | Path = "exports/charts",
) -> list[Path]:
    """Сохраняет каждую Figure в отдельный .html.

    Returns:
        Список путей к созданным файлам.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for name, fig in charts.items():
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        path = out_dir / f"{safe_name}.html"
        fig.write_html(str(path), include_plotlyjs="cdn")
        created.append(path)
    return created


def report_to_markdown_bytes(markdown: str) -> bytes:
    """Обёртка для скачивания .md с корректным BOM-less UTF-8."""
    return markdown.encode("utf-8")