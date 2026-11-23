"""Build the separate Word comparison report.

Inputs:
    versions/safe_cycle_ai/results.json   (historical CYCLE)
    benchmarks/current_results.json       (FAST + danger)

Output:
    Docs/Сравнение алгоритмов змейки.docx
    Docs/algorithm_speedup_10.png
"""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OLD_PATH = ROOT / "versions" / "safe_cycle_ai" / "results.json"
NEW_PATH = ROOT / "benchmarks" / "current_results.json"
DOC_PATH = ROOT / "Docs" / "Сравнение алгоритмов змейки.docx"
CHART_PATH = ROOT / "Docs" / "algorithm_speedup_10.png"


def ru(value, digits=1, signed=False):
    fmt = f"{{:+.{digits}f}}" if signed else f"{{:.{digits}f}}"
    return fmt.format(value).replace(".", ",")


def aggregate(configs, predicate):
    games = sum(c["games"] for c in configs if predicate(c))
    moves = sum(
        c["avg_moves"] * c["games"]
        for c in configs
        if predicate(c)
    )
    return games, moves


def make_chart(old_cfg, new_cfg):
    fields = [(5, 5), (6, 6), (7, 7), (10, 10), (15, 15), (20, 20), (30, 30)]
    data = []
    for width, height in fields:
        old_moves = old_cfg[(width, height, 10)]["avg_moves"]
        new_moves = new_cfg[(width, height, 10)]["avg_moves"]
        data.append(
            (
                f"{width}×{height}",
                (old_moves - new_moves) / old_moves * 100.0,
            )
        )

    width, height = 1500, 820
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    def font(size, bold=False):
        path = (
            r"C:\Windows\Fonts\arialbd.ttf"
            if bold
            else r"C:\Windows\Fonts\arial.ttf"
        )
        return ImageFont.truetype(path, size)

    left, right, top, bottom = 110, 80, 120, 120
    plot_width = width - left - right
    plot_height = height - top - bottom
    y_min, y_max = -20, 20

    def y(value):
        return top + (y_max - value) / (y_max - y_min) * plot_height

    for value in range(y_min, y_max + 1, 5):
        yy = y(value)
        draw.line(
            (left, yy, left + plot_width, yy),
            fill=(225, 229, 225),
            width=1,
        )
        draw.text(
            (left - 45, yy - 14),
            f"{value:+d}" if value else "0",
            font=font(22),
            fill=(80, 85, 80),
        )

    draw.line(
        (left, y(0), left + plot_width, y(0)),
        fill=(90, 95, 90),
        width=2,
    )
    draw.text(
        (left, 30),
        "10 яблок: изменение числа ходов, %",
        font=font(40, True),
        fill=(30, 40, 30),
    )
    draw.text(
        (left, 82),
        "Положительное значение — адаптивный алгоритм быстрее",
        font=font(24),
        fill=(90, 95, 90),
    )

    count = len(data)
    slot = plot_width / count
    bar_width = min(105, slot * 0.55)

    for index, (label, value) in enumerate(data):
        cx = left + slot * (index + 0.5)
        x0, x1 = cx - bar_width / 2, cx + bar_width / 2
        y0, y1 = y(0), y(value)
        color = (70, 170, 95) if value >= 0 else (215, 85, 80)

        if y1 < y0:
            draw.rounded_rectangle((x0, y1, x1, y0), radius=8, fill=color)
        else:
            draw.rounded_rectangle((x0, y0, x1, y1), radius=8, fill=color)

        label_y = (min(y0, y1) - 36) if value >= 0 else (max(y0, y1) + 8)
        text = f"{value:+.1f}%".replace(".", ",")
        text_width = draw.textlength(text, font=font(24, True))
        draw.text(
            (cx - text_width / 2, label_y),
            text,
            font=font(24, True),
            fill=(40, 45, 40),
        )

        label_width = draw.textlength(label, font=font(24))
        draw.text(
            (cx - label_width / 2, height - bottom + 35),
            label,
            font=font(24),
            fill=(35, 40, 35),
        )

    draw.line(
        (left, height - bottom + 20, left + plot_width, height - bottom + 20),
        fill=(160, 165, 160),
        width=1,
    )
    image.save(CHART_PATH)


def set_cell_shading(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("— ")
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)

    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    paragraph._p.append(field)


def style_document(document):
    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for name, size in (("Heading 1", 16), ("Heading 2", 14)):
        style = document.styles[name]
        style.font.name = "Times New Roman"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(24, 65, 38)
        style.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.paragraph_format.space_before = Pt(12)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True


def body_paragraph(document, text, first_indent=True):
    paragraph = document.add_paragraph(text)
    if first_indent:
        paragraph.paragraph_format.first_line_indent = Cm(1.25)
    paragraph.paragraph_format.space_after = Pt(6)
    return paragraph


def add_caption(document, text):
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    run.italic = True
    return paragraph


def add_table(document, headers, rows, widths, font_size=8.5):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.allow_autofit = False

    tbl_pr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)

    for index, width in enumerate(widths):
        table.columns[index].width = Cm(width)

    header_cells = table.rows[0].cells
    for index, (header, width) in enumerate(zip(headers, widths)):
        cell = header_cells[index]
        cell.width = Cm(width)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(header)
        run.bold = True
        run.font.name = "Times New Roman"
        run.font.size = Pt(font_size)
        set_cell_shading(cell, "D9EAD3")
    set_repeat_table_header(table.rows[0])

    for row_data in rows:
        cells = table.add_row().cells
        for index, (value, width) in enumerate(zip(row_data, widths)):
            cell = cells[index]
            cell.width = Cm(width)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
                if index == 0
                else WD_ALIGN_PARAGRAPH.CENTER
            )
            paragraph.paragraph_format.line_spacing = 1.0
            paragraph.paragraph_format.space_before = Pt(0)
            paragraph.paragraph_format.space_after = Pt(0)
            run = paragraph.add_run(str(value))
            run.font.name = "Times New Roman"
            run.font.size = Pt(font_size)

    return table


def main():
    old = json.loads(OLD_PATH.read_text(encoding="utf-8"))
    new = json.loads(NEW_PATH.read_text(encoding="utf-8"))

    old_cfg = {
        (c["width"], c["height"], c["apples"]): c
        for c in old["configurations"]
    }
    new_cfg = {
        (c["width"], c["height"], c["apples"]): c
        for c in new["configurations"]
    }

    keys = sorted(old_cfg, key=lambda k: (k[0], k[2]))
    old_wins = sum(d["won"] for d in old["details"])
    new_wins = sum(d["won"] for d in new["details"])
    total_games = len(old["details"])

    total_old = sum(c["avg_moves"] * c["games"] for c in old_cfg.values())
    total_new = sum(c["avg_moves"] * c["games"] for c in new_cfg.values())
    total_delta = (total_old - total_new) / total_old * 100.0
    minutes_old = total_old / 8.0 / 60.0
    minutes_new = total_new / 8.0 / 60.0
    minutes_saved = minutes_old - minutes_new

    unweighted_delta = sum(
        (old_cfg[k]["avg_moves"] - new_cfg[k]["avg_moves"])
        / old_cfg[k]["avg_moves"]
        * 100.0
        for k in keys
    ) / len(keys)

    small_games, small_old = aggregate(
        old_cfg.values(), lambda c: c["width"] <= 10
    )
    _, small_new = aggregate(new_cfg.values(), lambda c: c["width"] <= 10)
    _, mid_old = aggregate(old_cfg.values(), lambda c: c["width"] == 15)
    _, mid_new = aggregate(new_cfg.values(), lambda c: c["width"] == 15)
    _, large_old = aggregate(old_cfg.values(), lambda c: c["width"] >= 20)
    _, large_new = aggregate(new_cfg.values(), lambda c: c["width"] >= 20)

    make_chart(old_cfg, new_cfg)

    document = Document()
    style_document(document)
    document.core_properties.title = "Сравнение алгоритмов змейки"
    document.core_properties.subject = (
        "CYCLE против FAST + коэффициент опасности"
    )
    document.core_properties.author = "Rafael"

    add_page_number(document.sections[0].footer.paragraphs[0])

    # ------------------------------------------------------------------
    # Титульная страница
    # ------------------------------------------------------------------
    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(110)
    run = title.add_run("Сравнение алгоритмов\nавтопилота змейки")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(26)
    run.font.color.rgb = RGBColor(24, 65, 38)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_before = Pt(18)
    run = subtitle.add_run(
        "Гарантированный цикл против адаптивного FAST\n"
        "с коэффициентом опасности"
    )
    run.font.name = "Times New Roman"
    run.font.size = Pt(16)

    intro = document.add_paragraph()
    intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
    intro.paragraph_format.space_before = Pt(46)
    run = intro.add_run("Отчёт по результатам тестирования")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)

    date = document.add_paragraph()
    date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date.paragraph_format.space_before = Pt(10)
    run = date.add_run("23 ноября 2026 г.")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)

    document.add_page_break()

    # ------------------------------------------------------------------
    # 1. Методика
    # ------------------------------------------------------------------
    document.add_heading("1. Цель и методика", level=1)

    body_paragraph(
        document,
        "Цель работы — сравнить историческую версию автопилота, которая "
        "всегда использует только гарантированный обход кольца, и текущую "
        "адаптивную версию, которая в начале партии собирает яблоки "
        "безопасным BFS-маршрутом, а затем переходит на кольцо.",
    )
    body_paragraph(
        document,
        "Историческая версия: «versions/safe_cycle_ai». В ней "
        "SnakeAI.fast_enabled = False, FAST-вызов удалён, решение "
        "принимается только режимами CYCLE и RECOVERY.",
    )
    body_paragraph(
        document,
        "Текущая версия: FAST + коэффициент опасности. На каждом ходу "
        "строится BFS-путь до ближайшего яблока, проверяется достижимость "
        "хвоста и запас свободных клеток. Пока коэффициент опасности ниже "
        "0,68, выбирается самый короткий безопасный путь. При росте "
        "опасности или отсутствии безопасного пути автопилот возвращается "
        "к кольцу.",
    )
    body_paragraph(
        document,
        "Условия одинаковые: поля 5×5, 6×6, 7×7, 10×10, 15×15, 20×20 и "
        "30×30; по 1, 3 и 10 яблок; одинаковые seeds. Всего 21 конфигурация "
        "и 51 партия на каждую версию.",
    )
    body_paragraph(
        document,
        "Партия считается пройденной, когда тело заполняет всё поле. "
        "Игровое время пересчитано для FPS = 8 по формуле "
        "«минуты = ходы / 8 / 60». Время работы процессора не измерялось "
        "и в таблицы не включено: сравнение идёт по ходам и игровому "
        "времени.",
    )
    body_paragraph(
        document,
        f"Обе версии выиграли все партии: CYCLE — {old_wins}/{total_games}, "
        f"FAST — {new_wins}/{total_games}. Аварийных столкновений нет.",
    )

    # ------------------------------------------------------------------
    # 2. Результаты
    # ------------------------------------------------------------------
    document.add_heading("2. Результаты", level=1)

    body_paragraph(
        document,
        f"Суммарно на 51 партию историческая версия сделала "
        f"{total_old:,.0f} ходов, текущая — {total_new:,.0f}. "
        f"Экономия составляет {ru(total_delta)} % (в среднем по конфигурациям "
        f"{ru(unweighted_delta)} %). В игровом времени это "
        f"{ru(minutes_old)} минуты против {ru(minutes_new)}; "
        f"сэкономлено {ru(minutes_saved)} минуты.",
    ).runs[0].font.name = "Times New Roman"

    body_paragraph(
        document,
        "На крупных полях эффект устойчивее: для поля 20×20 и больше "
        f"экономия {ru((large_old - large_new) / large_old * 100)} %, "
        "на малых полях до 10×10 — "
        f"{ru((small_old - small_new) / small_old * 100)} %.",
    )

    add_caption(document, "Таблица 1 — 10 яблок: ходы и игровое время")
    summary_rows = []
    for width, height in [(5, 5), (6, 6), (7, 7), (10, 10), (15, 15), (20, 20), (30, 30)]:
        old_row = old_cfg[(width, height, 10)]
        new_row = new_cfg[(width, height, 10)]
        delta = (
            old_row["avg_moves"] - new_row["avg_moves"]
        ) / old_row["avg_moves"] * 100.0
        summary_rows.append(
            [
                f"{width}×{height}",
                ru(old_row["avg_moves"]),
                f"{ru(new_row['avg_moves'])} ({ru(delta, signed=True)} %)",
                ru(old_row["game_minutes"]),
                ru(new_row["game_minutes"]),
            ]
        )

    add_table(
        document,
        [
            "Поле",
            "CYCLE,\nходы",
            "FAST, ходы\n(Δ за счёт FAST)",
            "CYCLE,\nмин",
            "FAST,\nмин",
        ],
        summary_rows,
        [2.3, 2.8, 5.0, 2.8, 2.8],
        font_size=9,
    )

    chart_paragraph = document.add_paragraph()
    chart_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    chart_paragraph.paragraph_format.space_before = Pt(8)
    chart_paragraph.add_run().add_picture(str(CHART_PATH), width=Cm(16.3))
    add_caption(
        document,
        "Рисунок 1 — экономия ходов на 10 яблоках; "
        "зелёные столбцы — FAST быстрее, красные — медленнее",
    )

    body_paragraph(
        document,
        "Лучшие результаты текущей версии: 7×7 с 3 яблоками (–14,7 % ходов), "
        "20×20 с 1 и 10 яблоками (–10,3 %), 30×30 с 10 яблоками (–6,8 %). "
        "Худшие: 6×6 с 3 яблоками (+15,5 % к числу ходов), 5×5 с 10 яблоками "
        "(+12,0 %), 15×15 с 10 яблоками (+11,5 %), 7×7 с 10 яблоками "
        "(+10,4 %).",
    )

    document.add_page_break()
    add_caption(
        document,
        "Таблица 2 — полная матрица экспериментов (51 партия на версию)",
    )
    full_rows = []
    for key in keys:
        width, height, apples = key
        old_row = old_cfg[key]
        new_row = new_cfg[key]
        delta = (
            old_row["avg_moves"] - new_row["avg_moves"]
        ) / old_row["avg_moves"] * 100.0
        full_rows.append(
            [
                f"{width}×{height}",
                apples,
                old_row["games"],
                ru(old_row["avg_moves"]),
                f"{ru(new_row['avg_moves'])} ({ru(delta, signed=True)} %)",
                ru(old_row["game_minutes"]),
                ru(new_row["game_minutes"]),
            ]
        )

    add_table(
        document,
        [
            "Поле",
            "Яблок",
            "Партий",
            "CYCLE,\nходы",
            "FAST, ходы\n(Δ за счёт FAST)",
            "CYCLE,\nмин",
            "FAST,\nмин",
        ],
        full_rows,
        [2.1, 1.2, 1.4, 2.5, 4.7, 2.7, 2.7],
        font_size=8.3,
    )

    # ------------------------------------------------------------------
    # 3. Анализ
    # ------------------------------------------------------------------
    document.add_heading("3. Анализ", level=1)

    document.add_heading("3.1. Крупные поля", level=2)
    body_paragraph(
        document,
        "Главный выигрыш дают поля 20×20 и 30×30. На 20×20 с одним яблоком "
        "число ходов снижается с 38 268 до 34 329 (–10,3 %), с десятью "
        "яблоками — с 4 280 до 3 840 (–10,3 %). На 30×30 с одним яблоком "
        "экономия 5,4 %, с десятью — 6,8 %.",
    )
    body_paragraph(
        document,
        "Причина в том, что чистому кольцу приходится ждать, пока яблоко "
        "окажется рядом с маршрутом. Чем больше поле и чем меньше яблок, тем "
        "дольше это ожидание. FAST-режим строит короткий безопасный путь "
        "непосредственно к яблоку и сокращает «холостой» проход по кольцу.",
    )

    document.add_heading("3.2. Малые и средние поля", level=2)
    body_paragraph(
        document,
        "На малых полях выигрыш почти исчезает. Для полей до 10×10 "
        f"средняя экономия {ru((small_old - small_new) / small_old * 100)} %, "
        "а на 15×15 — "
        f"{ru((mid_old - mid_new) / mid_old * 100)} %. Более того, часть "
        "конфигураций становится медленнее: 6×6 с 3 яблоками — 103,3 → "
        "119,3 хода, 5×5 с 10 яблоками — 33,3 → 37,3, 15×15 с 10 яблоками — "
        "1 329 → 1 482 хода.",
    )
    body_paragraph(
        document,
        "Это не ошибка безопасности, а свойство эвристики. На плотном поле "
        "коэффициент опасности быстро превышает порог 0,68, поэтому FAST "
        "успевает сделать лишь несколько ходов. Один ранний обход меняет "
        "фазу кольца, и дальше змейка собирает яблоки в другом порядке. "
        "Фиксированный обход в старой версии иногда оказывается выгоднее "
        "по суммарному числу ходов, хотя формально никакой гарантии "
        "оптимальности у него тоже нет.",
    )

    document.add_heading("3.3. Что именно улучшилось в алгоритме", level=2)
    body_paragraph(
        document,
        "В старой версии решение всегда принималось по кольцу: положение "
        "головы и яблока переводились в слоты, и выбиралось направление "
        "вдоль заранее построенного гамильтонова цикла. Это даёт "
        "гарантированное заполнение поля, но не учитывает, насколько долго "
        "яблоко будет ждать на маршруте.",
    )
    body_paragraph(
        document,
        "В новой версии появились три элемента. Первый — BFS до ближайшего "
        "яблока с проверкой безопасности пути. Второй — проверка "
        "достижимости хвоста и запаса свободных клеток после роста. Третий — "
        "коэффициент опасности, который объединяет заполнение поля, тесноту "
        "малого поля и запас свободных клеток; при значении выше 0,68 "
        "автопилот возвращается к кольцу.",
    )
    body_paragraph(
        document,
        "Именно сочетание «быстрый безопасный путь + возврат к кольцу» даёт "
        "выигрыш на больших полях, не отменяя гарантию завершения партии. "
        "Фиксированного ограничения «первые N яблок» больше нет: момент "
        "перехода зависит от опасности.",
    )

    document.add_heading("3.4. Безопасность и режимы", level=2)
    body_paragraph(
        document,
        "Все 51 партия текущей версии завершились победой. В 37 партиях "
        "использовались FAST, CYCLE и RECOVERY; в 14 — только FAST и CYCLE. "
        "RECOVERY — страховочный режим на случай, когда после быстрого "
        "участка нужно восстановить корректное положение на кольце. "
        "Появление RECOVERY не означает ошибку: это штатный механизм "
        "восстановления.",
    )

    document.add_heading("3.5. Ограничения", level=2)
    body_paragraph(
        document,
        "FAST — эвристика, а не глобально оптимальный алгоритм. Он сокращает "
        "ожидание яблока, но может выбрать порядок, который на конкретном "
        "поле увеличит общее число ходов. Поэтому текущая версия быстрее "
        "в среднем и на крупных полях, но не обязана быть быстрее в каждой "
        "отдельной конфигурации.",
    )
    body_paragraph(
        document,
        "Для дальнейшего улучшения можно отдельно настраивать порог "
        "опасности для малых полей, сравнивать несколько безопасных "
        "маршрутов по вероятному числу будущих ходов и учитывать фазу "
        "кольца при выборе яблока. Это уже задача оптимизации эвристики, "
        "а не сохранения гарантии.",
    )

    # ------------------------------------------------------------------
    # 4. Выводы
    # ------------------------------------------------------------------
    document.add_heading("4. Выводы", level=1)
    body_paragraph(
        document,
        f"1. Текущая версия сократила суммарное число ходов на "
        f"{ru(total_delta)} % и сэкономила {ru(minutes_saved)} минуты "
        f"игрового времени на 51 партии.",
    )
    body_paragraph(
        document,
        "2. Наибольший эффект достигнут на полях 20×20 и 30×30: экономия "
        "до 10,3 %; это основной сценарий, ради которого вводился FAST.",
    )
    body_paragraph(
        document,
        "3. На малых и средних полях выигрыш нестабилен: до 10×10 он "
        "составляет около 1 %, а отдельные конфигурации становятся "
        "медленнее. Для них разумно оставить кольцо или отдельно "
        "настроить порог опасности.",
    )
    body_paragraph(
        document,
        "4. Обе версии проходят все 51 партию без столкновений; новая "
        "версия сохраняет гарантию завершения и добавляет адаптивный "
        "быстрый участок.",
    )
    body_paragraph(
        document,
        "5. Время работы процессора в отчёте не используется: сравнение "
        "проведено по ходам и игровому времени при FPS = 8.",
    )

    document.add_heading("Источники данных", level=1)
    for text in (
        "results.json исторической версии: "
        "versions/safe_cycle_ai/results.json",
        "результаты текущей версии: benchmarks/current_results.json",
        "скрипты: versions/safe_cycle_ai/benchmark.py, "
        "benchmark_current.py",
    ):
        paragraph = document.add_paragraph(text, style="List Bullet")
        paragraph.paragraph_format.line_spacing = 1.15
        paragraph.paragraph_format.space_after = Pt(2)

    document.save(DOC_PATH)
    print(f"written {DOC_PATH}")


if __name__ == "__main__":
    main()
