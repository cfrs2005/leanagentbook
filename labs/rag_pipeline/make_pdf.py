"""Generate an original, synthetic text PDF; no downloaded source material."""
from pathlib import Path
from reportlab.pdfgen import canvas


def make_pdf(path: Path):
    pdf = canvas.Canvas(str(path), pagesize=(420, 300), invariant=1)
    pdf.setTitle('Synthetic calibration guide')
    pdf.setAuthor('Lean Agent Book')
    pdf.setFont('Helvetica-Bold', 17)
    pdf.drawString(30, 255, 'SYNTHETIC CALIBRATION GUIDE')
    pdf.setFont('Helvetica', 12)
    pdf.drawString(30, 215, 'Calibration interval: 14 days.')
    pdf.drawString(30, 190, 'Use the blue reference plate for calibration.')
    pdf.drawString(30, 150, 'Training fixture only. Not a real device manual.')
    pdf.showPage()
    pdf.save()


if __name__ == '__main__':
    make_pdf(Path(__file__).parent / 'fixtures' / 'calibration.pdf')
