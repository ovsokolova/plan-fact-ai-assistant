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

def report_to_pdf(report: ReportJSON, *, markdown_text: str | None = None) -> bytes | None:
    """Экспорт отчёта в PDF.

    Стратегия: markdown -> HTML -> WeasyPrint -> PDF.
    Если WeasyPrint не установлен или системные библиотеки недоступны —
    возвращает None (UI покажет «PDF недоступен»).

    Установка (опционально):
        pip install weasyprint
        # Linux: sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b
    """
    try:
        from weasyprint import HTML  # type: ignore
    except Exception:  # noqa: BLE001
        return None

    # Локальный импорт, чтобы избежать циклической зависимости
    from src.llm_agent import report_to_markdown as _md

    md = markdown_text if markdown_text is not None else _md(report)
    html = _markdown_to_simple_html(md)

    try:
        return HTML(string=html).write_pdf()
    except Exception:  # noqa: BLE001
        return None


def _markdown_to_simple_html(md: str) -> str:
    """Минимальный конвертер markdown -> HTML для PDF.

    Поддерживает: заголовки #..###, жирный **, курсив *, списки -, абзацы.
    Не тянет внешние зависимости.
    """
    import html as _html
    import re as _re

    lines = md.splitlines()
    out: list[str] = ['<html><head><meta charset="utf-8">',
                      '<style>body{font-family:sans-serif;line-height:1.5;max-width:800px;margin:2em auto;padding:0 1em;}',
                      'h1{font-size:22px;} h2{font-size:18px;margin-top:1.5em;} h3{font-size:15px;color:#333;}',
                      'ul{margin:.4em 0;} li{margin:.2em 0;}</style></head><body>']

    for raw in lines:
        line = raw.rstrip()
        if not line:
            out.append("<p></p>")
            continue
        m = _re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            continue
        if line.startswith("- "):
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        out.append(f"<p>{_inline(line)}</p>")

    out.append("</body></html>")
    return "\n".join(out)


def _inline(text: str) -> str:
    import html as _html
    import re as _re

    text = _html.escape(text)
    text = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = _re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    return text
