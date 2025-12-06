"""
PDF Contract Generator using ReportLab
"""
import os
from datetime import date, datetime
from typing import Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm


def convert_dates(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert date objects to strings for JSON serialization"""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = convert_dates(value)
        elif isinstance(value, (date, datetime)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


class ContractGenerator:
    """Generate PDF contract from data"""

    def __init__(self, data_or_path: str | Dict[str, Any]):
        """
        Initialize generator with contract data

        Args:
            data_or_path: Either path to JSON file or dict with contract data
        """
        if isinstance(data_or_path, str):
            import json
            with open(data_or_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            self.data = data_or_path

    def generate(self, output_path: str) -> str:
        """
        Generate PDF contract

        Args:
            output_path: Path where to save PDF

        Returns:
            Path to generated PDF
        """
        # Create canvas
        c = canvas.Canvas(output_path, pagesize=A4)
        width, height = A4

        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, height - 50, "SHARTNOMA")

        # Add contract number
        c.setFont("Helvetica", 12)
        y = height - 80
        c.drawString(50, y, f"Shartnoma raqami: {self.data.get('shartnoma_raqami', 'N/A')}")

        # Add date
        y -= 30
        sana = self.data.get('sana', {})
        c.drawString(50, y, f"Sana: {sana.get('kun', '')} {sana.get('oy', '')} {sana.get('yil', '')} yil")

        # Add customer info
        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "BUYURTMACHI:")
        c.setFont("Helvetica", 11)

        buyurtmachi = self.data.get('buyurtmachi', {})
        y -= 20
        c.drawString(70, y, f"F.I.O: {buyurtmachi.get('fio', '')}")
        y -= 20
        c.drawString(70, y, f"Pasport: {buyurtmachi.get('pasport_seriya', '')}")
        y -= 20
        c.drawString(70, y, f"Kim bergan: {buyurtmachi.get('pasport_kim_bergan', '')}")
        y -= 20
        c.drawString(70, y, f"Berilgan sana: {buyurtmachi.get('pasport_qachon_bergan', '')}")
        y -= 20
        c.drawString(70, y, f"Manzil: {buyurtmachi.get('manzil', '')}")
        y -= 20
        c.drawString(70, y, f"Telefon: {buyurtmachi.get('telefon', '')}")

        # Add student info
        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "TARBIYALANUVCHI:")
        c.setFont("Helvetica", 11)

        tarbiyalanuvchi = self.data.get('tarbiyalanuvchi', {})
        y -= 20
        c.drawString(70, y, f"F.I.O: {tarbiyalanuvchi.get('fio', '')}")
        y -= 20
        c.drawString(70, y, f"Tug'ilganlik guvohnomasi: {tarbiyalanuvchi.get('tugilganlik_guvohnoma', '')}")
        y -= 20
        c.drawString(70, y, f"Kim bergan: {tarbiyalanuvchi.get('guvohnoma_kim_bergan', '')}")

        # Add contract terms
        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "SHARTNOMA SHARTLARI:")
        c.setFont("Helvetica", 11)

        muddat = self.data.get('shartnoma_muddati', {})
        y -= 20
        c.drawString(70, y, f"Amal qilish muddati: {muddat.get('boshlanish', '')} dan {muddat.get('tugash', '')} gacha")

        tolov = self.data.get('tolov', {})
        y -= 20
        c.drawString(70, y, f"Oylik to'lov: {tolov.get('oylik_narx', '')} so'm")

        # Save PDF
        c.save()

        return output_path
