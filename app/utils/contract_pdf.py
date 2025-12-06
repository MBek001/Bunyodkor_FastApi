"""
Contract PDF Generator using ReportLab with Uzbek language support
"""
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
import json
import os
from reportlab.pdfbase.pdfmetrics import registerFontFamily


# Try to register DejaVu fonts (for Cyrillic support)
FONT_NORMAL = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
FONT_FALLBACK = True

# Common font paths to try
FONT_PATHS = [
    # Linux paths
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    # Windows paths (if running on Windows)
    r"C:\Windows\Fonts\DejaVuSans.ttf",
    r"C:\Users\Home\Downloads\dejavu-fonts-ttf-2.37\dejavu-fonts-ttf-2.37\ttf\DejaVuSans.ttf",
]

BOLD_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
    r"C:\Users\Home\Downloads\dejavu-fonts-ttf-2.37\dejavu-fonts-ttf-2.37\ttf\DejaVuSans-Bold.ttf",
]

# Try to find and register fonts
for font_path, bold_path in zip(FONT_PATHS, BOLD_FONT_PATHS):
    if os.path.exists(font_path) and os.path.exists(bold_path):
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", font_path))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold_path))
            registerFontFamily(
                'DejaVu',
                normal='DejaVu',
                bold='DejaVu-Bold',
                italic='DejaVu',
                boldItalic='DejaVu-Bold'
            )
            FONT_NORMAL = 'DejaVu'
            FONT_BOLD = 'DejaVu-Bold'
            FONT_FALLBACK = False
            break
        except Exception as e:
            continue

if FONT_FALLBACK:
    print("Warning: DejaVu fonts not found. Cyrillic text may not display correctly.")


# --- STYLES ---
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(name='TitleUz', fontName=FONT_BOLD, fontSize=15, alignment=TA_CENTER, spaceAfter=5, leading=18))
styles.add(ParagraphStyle(name='SubtitleUz', fontName=FONT_NORMAL, fontSize=10, alignment=TA_CENTER, spaceAfter=15, leading=12))
styles.add(ParagraphStyle(name='SectionHeaderUz', fontName=FONT_BOLD, fontSize=12, alignment=TA_CENTER, spaceAfter=10, spaceBefore=15, leading=16))
styles.add(ParagraphStyle(name='NormalUz', fontName=FONT_NORMAL, fontSize=11, leading=16, alignment=TA_JUSTIFY, firstLineIndent=15, spaceAfter=3))
styles.add(ParagraphStyle(name='ListItemUz', fontName=FONT_NORMAL, fontSize=11, leading=16, alignment=TA_JUSTIFY, leftIndent=15, firstLineIndent=-15, spaceAfter=5))
styles.add(ParagraphStyle(name='AddressHeader', fontName=FONT_BOLD, fontSize=10, alignment=TA_LEFT, spaceAfter=10))
styles.add(ParagraphStyle(name='AddressDetail', fontName=FONT_NORMAL, fontSize=11, leading=14, spaceAfter=3))
styles.add(ParagraphStyle(name='SectionHeaderUzSpaced', parent=styles['SectionHeaderUz'], spaceBefore=65))
styles.add(ParagraphStyle(name='UnderlineField', parent=styles['NormalUz'], fontName=FONT_BOLD, fontSize=11, leading=11, spaceAfter=0, firstLineIndent=0))
styles.add(ParagraphStyle(name='SmallCenter', fontName=FONT_NORMAL, fontSize=9, alignment=TA_CENTER, leading=10, spaceAfter=5))
styles.add(ParagraphStyle(name='SmallText', parent=styles['Normal'], fontName=FONT_NORMAL, fontSize=8, leading=10, alignment=TA_CENTER, spaceAfter=15))
styles.add(ParagraphStyle(name='NormalUzNoIndent', parent=styles['NormalUz'], firstLineIndent=0, alignment=TA_JUSTIFY, spaceAfter=15))


class ContractPDFGenerator:
    """Generate contract PDF with Uzbek language support"""

    def __init__(self, data_dict):
        """Initialize with contract data dict"""
        self.data = data_dict
        self.story = []
        self.doc = None
        self.logo_filename = "Bunyodkor-new.png"

    def _add_underlined_multiline_text(self, text, style, line_width=0.5):
        """Add multi-line text with underlines"""
        from reportlab.pdfbase.pdfmetrics import stringWidth

        max_width = self.doc.width
        words = text.split()
        lines = []
        current = ""

        for word in words:
            test = (current + " " + word).strip()
            if stringWidth(test, style.fontName, style.fontSize) <= max_width:
                current = test
            else:
                lines.append(current)
                current = word

        if current:
            lines.append(current)

        flowables = []
        for line in lines:
            p = Paragraph(line, style)
            flowables.append(p)

            table = Table([[""]],  colWidths=[max_width])
            table.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (0, 0), line_width, black),
                ('TOPPADDING', (0, 0), (0, 0), -4),
                ('BOTTOMPADDING', (0, 0), (0, 0), 0),
                ('LEFTPADDING', (0, 0), (0, 0), 0),
                ('RIGHTPADDING', (0, 0), (0, 0), 0),
            ]))
            flowables.append(table)

        return flowables

    def _add_spacer(self, height=5):
        self.story.append(Spacer(1, height * mm))

    def _add_spacer_return(self, height=5):
        return Spacer(1, height * mm)

    def _add_logo(self):
        if os.path.exists(self.logo_filename):
            logo = Image(self.logo_filename, width=15 * mm, height=15 * mm)
            logo.hAlign = 'CENTER'
            self.story.append(logo)
            self._add_spacer(1)
            self.story.append(Table([['']], colWidths=[self.doc.width], style=TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, black),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0)
            ])))
            self._add_spacer(3)

    def _add_header(self):
        data = self.data
        self._add_logo()

        self.story.append(Paragraph(
            f"Шартнома №{data.get('shartnoma_raqami', '______')}",
            styles['TitleUz']
        ))
        self.story.append(Paragraph(
            "(Пуллик жисмоний тарбия ва спорт хизматларини кўрсатиш бўйича)",
            styles['SubtitleUz']
        ))

        sana = data.get('sana', {})
        sana_text = f'«{sana.get("kun", "___")}» {sana.get("oy", "___________")} {sana.get("yil", "___")} й.'

        col_widths = [self.doc.width - 50 * mm, 50 * mm]
        header_table_data = [
            [
                Paragraph("Тошкент ш.", ParagraphStyle(name='HLeft', fontName=FONT_NORMAL, fontSize=11, alignment=TA_LEFT)),
                Paragraph(sana_text, ParagraphStyle(name='HRight', fontName=FONT_NORMAL, fontSize=11, alignment=TA_RIGHT))
            ]
        ]

        header_table = Table(header_table_data, colWidths=col_widths)
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        self.story.append(header_table)
        self._add_spacer(10)

    def _add_parties_info(self):
        data = self.data
        buyurtmachi = data.get('buyurtmachi', {})
        tarbiya = data.get('tarbiyalanuvchi', {})

        text1 = """<b>«FK BUNYODKOR» МЧЖ Тошкент шаҳар филиали</b> бундан буён «Ижрочи» деб юритиладиган, ишончнома асосида фаолият юритаётган Директор Ш.Н.Саидов, бир томондан ва бундан буён «Буюртмачи» деб юритиладиган """
        self.story.append(Paragraph(text1, styles['NormalUz']))

        fio_buyurtmachi = buyurtmachi.get('fio', '<b>________________________________</b>')
        elements = self._add_underlined_multiline_text(fio_buyurtmachi, styles['UnderlineField'])
        self.story.extend(elements)

        self.story.append(Paragraph(
            "(фуқаронинг Ф.И.Ш, паспорт серияси, ким томонидан ва қачон берилган)",
            styles['SmallText']
        ))

        text2 = "бошқа томондан, ушбу шартномани қўйидагилар тўғрисида туздилар:"
        self.story.append(Paragraph(text2, styles['NormalUzNoIndent']))

        text3 = "Тарбияланувчининг туғилганлик тўғрисидаги гувоҳномаси:"
        self.story.append(Paragraph(text3, styles['NormalUzNoIndent']))

        fio_tarbiya = tarbiya.get('fio', '________________________________')
        elements = self._add_underlined_multiline_text(fio_tarbiya, styles['UnderlineField'])
        self.story.extend(elements)

        self.story.append(Paragraph(
            "(Ф.И.Ш, серияси, ким томонидан ва қачон берилган)",
            styles['SmallText']
        ))

    def _add_section(self, num, title, paragraphs, is_list=False, header_style='SectionHeaderUz'):
        self.story.append(Paragraph(f"{num}. {title}", styles[header_style]))
        for p in paragraphs:
            if is_list:
                self.story.append(Paragraph(p, styles['ListItemUz']))
            else:
                self.story.append(Paragraph(p, styles['NormalUz']))

    def _add_signature_block(self):
        self.story.append(Paragraph(
            "11. ЮРИДИК МАНЗИЛЛАР ВА БАНК РЕКВИЗИТЛАРИ",
            styles['SectionHeaderUz']
        ))
        self._add_spacer(5)

        buyurtmachi = self.data.get('buyurtmachi', {})

        ijrochi_text = """
        <b>« Ижрочи »</b><br/>
        <b>« FK BUNYODKOR » МЧЖ</b><br/>
        Тошкент шаҳар филиали<br/><br/>
        Тошкент шаҳар, Чилонзор тумани,<br/>
        Бунёдкор шох кўчаси, 47-уй.<br/><br/>
        ҳ/р 2020 8000 9044 2411 1005<br/>
        ЎзСҚБ АТБ Тошкент шаҳар Бош офиси<br/>
        МФО: 00440, СТИР: 205 737 924, ОКЭД: 93110<br/>
        Тел/факс: 71-230-40-01<br/><br/><br/>
        <b>Директор</b>       Ш.Н.Саидов<br/><br/>
        _______________________<br/>
        М.Ў.
        """
        P_ijrochi = Paragraph(ijrochi_text, styles['AddressDetail'])

        def underline_row(text):
            t = Table([[Paragraph(text, styles['AddressDetail'])]], colWidths=[self.doc.width / 2 - 20])
            t.setStyle(TableStyle([
                ('LINEBELOW', (0, 0), (-1, -1), 0.8, black),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
            ]))
            return t

        fio = buyurtmachi.get("fio", "")
        pasport = buyurtmachi.get("pasport_seriya", "")
        kim_bergan = buyurtmachi.get("pasport_kim_bergan", "")
        qachon_bergan = buyurtmachi.get("pasport_qachon_bergan", "")
        manzil = buyurtmachi.get("manzil", "")
        telefon = buyurtmachi.get("telefon", "")

        right_block = [
            Paragraph("<b>«Буюртмачи»</b>", styles['AddressDetail']),
            Paragraph("«Ота ёки Она»", styles['AddressDetail']),
            self._add_spacer_return(6),
            underline_row(fio),
            Paragraph("(фамилия, исм, отасининг исми)", styles['SmallCenter']),
            self._add_spacer_return(4),
            underline_row("Паспорт № " + pasport),
            underline_row("Берилган: " + kim_bergan),
            underline_row(qachon_bergan),
            underline_row("Манзил: " + manzil),
            underline_row("Телефон: " + telefon),
            self._add_spacer_return(8),
            underline_row("Имзо")
        ]

        right_flow = [item for item in right_block if item is not None]

        signature_table = Table([[P_ijrochi, right_flow]], colWidths=[self.doc.width / 2, self.doc.width / 2])
        signature_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), "TOP"),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 15),
            ('LEFTPADDING', (1, 0), (1, 0), 15),
            ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ]))

        self.story.append(KeepTogether(signature_table))

    def get_flowables(self):
        """Build all contract sections"""
        self._add_header()
        self._add_parties_info()

        # Section 1
        section1 = [
            "Мазкур шартноманинг предмети <b>Ижрочи</b> томонидан <b>Буюртмачига</b> пуллик жисмоний тарбия ва спорт хизматларини (футбол курси) кўрсатиш ҳисобланади.",
            "«FK BUNYODKOR» МЧЖ Тошкент шаҳар филиали ички тартиб қоидаларига мувофиқ пуллик жисмоний тарбия ва спорт хизматларини (футбол курси) кўрсатиш бўйича шартномалар ҳар ойнинг 25-санасидан бошлаб ой охирига қадар имзоланиши ва мазкур шартноманинг 6.1-бандига мувофиқ тўлов тўлангандан сўнг ўқув-машғулотлар бошлашга рухсат берилиши маълумот учун қабул қилинади."
        ]
        self._add_section("1", "Шартнома предмети", section1)

        # Section 2 (Ijrochi)
        section2_1 = [
            "<b>2.1. Ижрочи қуйидаги мажбуриятларни ўз зиммасига олади:</b>",
            "<b>2.1.1.</b> Машғулотларни тасдиқланган график асосида олиб бориш;",
            "<b>2.1.2.</b> Буюртмачини машғулотларни олиб бориш бўйича зарурий ахборот билан таъминлаш;",
            "<b>2.1.3.</b> Машғулотларни олиб бориш бўйича зарур шароитни яратиб бериш;",
            "<b>2.1.4.</b> <b>«Бунёдкор ФК»</b> БЎФАсида жисмоний тарбия ва спорт тадбирларини ўтказишда техника хавфсизлиги бўйича кириш ва жорий инструктаж олиб бориш;",
            "<b>2.1.5.</b> Тарбияланувчининг максимал спорт натижаларига эришиш учун унинг имкониятларини кенгайтиришга шароитлар яратиш, унинг спорт маҳоратини оширишда замонавий техника воситаларидан фойдаланиш;",
            "<b>2.1.6.</b> Ўз вақтида хизматларни кўрсатишнинг ўзгариши тўғрисида Буюртмачини хабардор қилиш;",
            "<b>2.1.7.</b> Ўтказиладиган спорт машғулотлари дастури ва жадвалига мувофиқ мураббий (лар) бошчилигида машғулотларни ўтказишни сифатли ва тўлиқ таъминлаш. Ижрочи жамоага мураббий (лар)ни мустақил равишда алмаштириш, тайинлаш ҳуқуқини ўзида сақлаб қолади."
        ]
        section2_2 = [
            "<b>2.2. Ижрочи қуйидагиларга ҳақли:</b>",
            "<b>2.2.1.</b> Шартнома муддати тугаши билан янги муддатга шартнома тузишдан бош тортиш, агар Буюртмачи амалдаги шартнома муддати давомида ушбу шартномада (тўлов муддати, соғлиғи ва ички тартиб қоидаларни бузиш ҳоллари) ва фуқаролик қонунчилигида белгиланган қоидабузарликларни содир қилса;",
            "<b>2.2.2.</b> Агар <b>Буюртмачи</b> ўз хоҳишига кўра спорт-машғулотларга қатнашишни тўхтатса, шунингдек, Ички тартиб қоидаларни мунтазам равишда бузиб келган бўлса, келиб тушган тўловларни қайтармайди. Бунда, Буюртмачи томонидан шартномнинг 6.1-бандига мувофиқ келиб тушган маблағлар ҳам қайтарилмаслиги инобатга олинади;",
            "<b>2.2.3.</b> <b>Ижрочи</b> бир томонлама шартнома шартларига ўзгартириш киритиш ҳуқуқига эга, хусусан, хизматлар нархини ўзгартириш масаласида (коммунал тўловлар нархининг ўсиши ва х.к.). Шартнома шартларининг ўзгариши тўғрисида Буюртмачи ўн кун олдин оғзаки ёки ёзма тарзда огоҳлантирилади;",
            """2.2.4. Агар <b>Буюртмачи</b> шартноманинг амал қилиш мудати давомида ўз хоҳишига кўра узрли сабабларсиз спорт-машғулотларга қатнашишни 15 кундан ортиқ тўхтатиб, кейинги ойдан бошлаб спорт-машғулотларга қатнашиш истагини <b>Ижрочига</b> қайта билдирса, <b>Ижрочи</b> спорт-машғулотларга келинмаган кунлар учун ҳам тегишли тўловни талаб қилишга ҳақли.""",
            "<b>2.2.5.</b> Ижрочи ўз тарбияланувчилари (ОАВ, Интернетда) ҳақидаги маълумотларни тарқатишда ва буюртмачи билан профессионал футболда янада ривожлантириш масаласини ҳал қилишда имтиёзли ҳуқуққа эга;",
            "<b>2.2.6.</b> Ижрочи ота-она (қонуний вакил)лар билан келишилган ҳолда спорт тадбирларини қисман молиялаштириш учун тарбияланувчининг ота-она маблағларини, шунингдек қонуний вакиллар маблағларини жалб қилиш ва фойдаланишга ҳақли."
        ]
        self._add_section("2", "Ижрочининг ҳуқуқ ва мажбуриятлари", section2_1 + section2_2, is_list=True)

        # Section 3 (Buyurtmachi)
        section3_1 = [
            "<b>3.1. Буюртмачи қуйидагиларга ҳақли:</b>",
            "<b>3.1.1.</b> Мазкур шартнома бўйича кўрсатиладиган хизматларнинг амалга оширилиши бўйича маълумотлар берилишини талаб қилиш;",
            "<b>3.1.2.</b> Жисмоний тарбия ва спорт хизматларини кўрсатиш учун зарур бўлган Ижрочининг мулкидан фойдаланиш;",
            "<b>3.1.3.</b> Ижрочи фаолиятини тартибга солувчи ҳужжатлар (Низом, спорт машғулотлари жадвали ва бошқалар) билан танишиш;",
            "<b>3.1.4.</b> Мазкур шартномада белгиланган муддатларда Ижрочига ёзма хабар юбориш орқали хизматлардан фойдаланишдан бош тортиш."
        ]
        section3_2 = [
            "<b>3.2. Буюртмачи қуйидаги мажбуриятларни ўз зиммасига олади:</b>",
            "<b>3.2.1.</b> Тиббий маълумотномани ўз вақтида тақдим этиш;",
            "<b>3.2.2.</b> Машғулотларни тўхтатиш бўйича оқилона муддат давомида Ижрочини хабардор қилиш;",
            "<b>3.2.3.</b> Машғулотларга белгиланган спорт экипировкасида келиш;",
            "<b>3.2.4.</b> Ўзбекистон Республикасининг амалдаги қонунчилик ҳужжатларига мувофиқ Ижрочига тегишли мол-мулкка етказилган зарарни қоплаб бериш;",
            "<b>3.2.5.</b> Футбол клуби раҳбарияти ҳамда БЎФА тренерлари ваколат доирасига кирувчи масалаларга аралашмаслик, жумладан, спорт-машғулот жараёнини ташкил этиш ва ўтказиш ишларига, футбол ўйинининг тактик режаси, шунингдек сафарлар, учрашувлар ва ҳакозоларнинг умумий режасига таъллуқли кўрсатмаларга ҳамда Клуб (БЎФА) обрўсига путур етказишга ҳаракатлар тўғрисида хабар бериб туриш."
        ]
        section3_3 = [
            "<b>3.3. Буюртмачи, тарбияланувчининг мажбуриятлари:</b>",
            "<b>3.3.1.</b> Мазкур шартноманинг амал қилиш муддати тугагунга қадар бошқа спорт мактаби (секция, академия), спорт мактаб-интернати, профессионал ёки ҳаваскор футбол клуби (шу жумладан селекционерлар) билан ушбу шартномага ўхшаш шартнома (контракт) тузмаслик;",
            "<b>3.3.2.</b> Тарбияланувчини машғулотлар жараёнида бошқа спорт мактаби (секция, академия), спорт мактаб-интернати, профессионал ёки ҳаваскор футбол клуб юбормайди."
        ]
        self._add_section("3", "Буюртмачи, тарбияланувчининг ҳуқуқ ва мажбуриятлари", section3_1 + section3_2 + section3_3, is_list=True, header_style='SectionHeaderUzSpaced')

        # Section 4 (Muddat)
        muddat = self.data.get('shartnoma_muddati', {})
        section4 = [
            f"Мазкур шартнома «{muddat.get('boshlanish', '___')}» {muddat.get('yil', '2025')} йилдан {muddat.get('yil', '2025')} йил «{muddat.get('tugash', '31')}» декабрга қадар амал қилади."
        ]
        self._add_section("4", "Шартноманинг амал қилиш муддати", section4, is_list=False)

        # Section 5 (Huquqlar)
        section5 = [
            "<b>5.1. </b>Мазкур шартнома бўйича кўрсатиладиган хизматларнинг амалга оширилиши бўйича маълумотлар берилишини талаб қилиш;",
            "<b>5.2. </b>Жисмоний тарбия ва спорт хизматларини кўрсатиш учун зарур бўлган Ижрочининг мулкидан фойдаланиш."
        ]
        self._add_section("5", "Буюртмачи ва ижрочининг ҳуқуқлари", section5, is_list=True)

        # Section 6 (To'lov)
        tolov = self.data.get('tolov', {})
        narx = tolov.get('oylik_narx', '600 000')
        narx_sozlar = tolov.get('oylik_narx_sozlar', 'олти юз минг')
        narx_html = f"<u><b>{narx}</b></u>"
        narx_sozlar_html = f"<u><b>{narx_sozlar}</b></u>"

        section6 = [
            f"<b>6.1.</b> Абонементнинг ойлик тўлов нархи ҚҚСсиз {narx_html} ({narx_sozlar_html}) сўмни ташкил қилади.",
            """<b>6.2.</b> Ушбу шартнома бўйича тўлов спорт-машғулот бошланишига қадар 100% миқдорида ҳар ойнинг 1 (биринчи) санасидан 10 (ўнинчи) санасига қадар пул кўчириш ёки пластик карта орқали клубга хизмат кўрсатадиган банкдаги ҳисоб рақамига ўтказган ҳолда амалга оширилади.""",
            f"""<b>6.3.</b> Ота-оналар бир марталик {narx_html} ({narx_sozlar_html}) сўмни олдиндан тўловини амалга оширадилар, ушбу тўлов тарбияланувчининг ўқишга келишини ва ота-оналарнинг тўловларни мунтазам (ўз вақтида) амалга ошириш ниятларининг кафолатидир."""
        ]
        self._add_section("6", "Тўлов қилиш тартиби", section6, is_list=True)

        # Sections 7-10
        section7 = ["<b>7.1.</b>Шартнома доирасида ўз мажбуриятларини бажариш қисми сифатида, томонлар амалдаги қонун талабларига мувофиқликни таъминлаш, шу жумладан, коррупцияга қарши кураш бўйича қабул қилинган қонунга риоя этиш..."]
        self._add_section("7", "Коррупцияга қарши қоидалар", section7, is_list=False)

        section8 = ["<b>8.1.</b>Мазкур шартнома шартларини бузганлик фактлари аниқланса, айбдор томон амалдаги Ўзбекистон Республикаси қонунчилик ҳужжатларида белгиланган тартибда жавобгар бўлади."]
        self._add_section("8", "Тарафларнинг жавобгарлиги", section8, is_list=False)

        section9 = ["<b>9.1.</b>Ушбу шартномани ижро қилиш билан боғлиқ барча низолар тарафлар ўртасида музокаралар ўтказиш йўли билан ҳал этилади."]
        self._add_section("9", "Низоларни ҳал этиш тартиби", section9, is_list=False, header_style='SectionHeaderUzSpaced')

        section10 = [
            "<b>10.1.</b> <b>Буюртмачи</b> футболнинг тўқнашувларга бой спорт туриш эканлиги хақида огоҳлантирилган...",
            "<b>10.2.</b> <b>Ижрочи</b> спорт-машғулотидан ташқаридаги ҳар қандай тарбияланувчи билан боғлиқ оқибатларга жавоб бермайди.",
            "<b>10.3.</b> Тарафлардан бирининг ташаббуси билан ушбу шартнома ҳар қандай вақтда бир томонлама бекор қилиниши мумкин...",
            "<b>10.4.</b> Шартнома имзоланган кундан бошлаб кучга киради ва шартнома бўйича мажбуриятлар тўлиқ бажарилгунга қадар амал қилади.",
            "<b>10.5.</b> Ҳеч қайси тараф ушбу шартнома бўйича ўз ҳуқуқ ва мажбуриятларини бошқа учинчи шахсга бошқа тарафнинг ёзма розилигисиз беришга ҳақли эмас.",
            "<b>10.6.</b> Ушбу Шартномада кўзда тутилмаган ўзаро муносабатлар Ўзбекистон Республикаси қонун Ҳужжатлари билан тартибга солинади.",
            "<b>10.7.</b> Шартномага киритилиши лозим бўлган барча ўзгартириш ва кўшимчалар фақат ёзма тартибда амалга оширилади...",
            "<b>10.8.</b> Мазкур шартнома иккита бир хил юридик кучга эга бўлган асл нусхаларда тузилади ва тарафлар томонидан имзолангандан бошлаб кучга киради."
        ]
        self._add_section("10", "Шартноманинг бошқа қоидалари", section10, is_list=True)

        self._add_spacer(15)
        self._add_signature_block()

        return self.story

    def generate(self, output_file):
        """Generate PDF contract"""
        try:
            self.doc = SimpleDocTemplate(
                output_file,
                pagesize=A4,
                leftMargin=15 * mm,
                rightMargin=15 * mm,
                topMargin=10 * mm,
                bottomMargin=25 * mm
            )
            self.doc.width = A4[0] - self.doc.leftMargin - self.doc.rightMargin

            self.doc.build(self.get_flowables())
            return output_file
        except Exception as e:
            print(f"PDF generation error: {e}")
            raise
