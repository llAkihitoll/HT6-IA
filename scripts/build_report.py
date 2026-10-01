"""Genera el informe desde docs/RESPUESTAS.md, usando reportlab."""
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Flowable

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'output/pdf/respuestas_lab5.pdf'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
INK = colors.HexColor('#18354a')
GREEN = colors.HexColor('#147d64')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle('ReportTitle', fontName='Helvetica-Bold', fontSize=23, leading=28,
                          textColor=INK, spaceAfter=16))
styles.add(ParagraphStyle('Question', fontName='Helvetica-Bold', fontSize=13, leading=17,
                          textColor=GREEN, spaceBefore=10, spaceAfter=12))
styles.add(ParagraphStyle('ReportBody', fontName='Helvetica', fontSize=10.5, leading=15,
                          textColor=INK, spaceAfter=10))
styles.add(ParagraphStyle('Small', parent=styles['ReportBody'], fontSize=8.5, leading=12))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GREEN)
    canvas.line(48, 40, A4[0]-48, 40)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(INK)
    canvas.drawString(48, 27, 'PARACHUTE S.A.  /  HT5 - ORQUESTACIÓN')
    canvas.drawRightString(A4[0]-48, 27, str(doc.page))
    canvas.restoreState()


class Architecture(Flowable):
    def __init__(self):
        super().__init__()
        self.width = 490
        self.height = 490

    def draw(self):
        c = self.canv
        def box(x, y, w, h, text, fill='#eef5f3'):
            c.setFillColor(colors.HexColor(fill)); c.setStrokeColor(GREEN)
            c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
            p = Paragraph(text, ParagraphStyle('box', fontName='Helvetica', fontSize=10,
                leading=14, alignment=TA_CENTER, textColor=INK))
            _, ph = p.wrap(w-16, h-10)
            p.drawOn(c, x+8, y+(h-ph)/2)
        def arrow(x1,y1,x2,y2, both=False, dash=False):
            import math
            c.setStrokeColor(GREEN); c.setFillColor(GREEN); c.setLineWidth(1.3)
            c.setDash(4,3) if dash else c.setDash()
            c.line(x1,y1,x2,y2); c.setDash()
            def tip(x,y,angle):
                p=c.beginPath();p.moveTo(x,y)
                p.lineTo(x-7*math.cos(angle-.45),y-7*math.sin(angle-.45))
                p.lineTo(x-7*math.cos(angle+.45),y-7*math.sin(angle+.45));p.close()
                c.drawPath(p,fill=1,stroke=0)
            angle=math.atan2(y2-y1,x2-x1);tip(x2,y2,angle)
            if both:tip(x1,y1,angle+math.pi)
        box(145,425,200,48,'<b>Usuario / CLI</b><br/>Historial + agente activo')
        box(5,310,130,55,'<b>Agente FAQs</b><br/>Entrada de la sesión')
        box(180,310,130,55,'<b>Agente Clima</b>')
        box(355,310,130,55,'<b>Agente Reservas</b>')
        arrow(180,425,80,365)
        arrow(135,338,180,338,both=True)
        arrow(310,338,355,338,both=True)
        # Reservas -> FAQs, por encima de los agentes.
        c.setStrokeColor(GREEN);c.line(420,365,420,391);c.line(420,391,70,391)
        arrow(70,391,70,365)
        c.setFont('Helvetica',8);c.setFillColor(INK)
        c.drawCentredString(250,397,'handoff: Reservas → FAQs'.replace('→','a'))
        c.drawCentredString(157,349,'handoff');c.drawCentredString(332,349,'handoff')
        box(5,210,130,58,'<b>shared.faqs</b><br/>Búsqueda semántica')
        box(180,210,130,58,'<b>weather_service</b><br/>Consulta + evaluación')
        box(355,210,130,58,'<b>shared.bookings</b><br/>Revalida + persiste')
        for x in [70,245,420]:arrow(x,310,x,268,dash=True)
        box(5,95,130,58,'<b>PostgreSQL</b><br/>pgvector / 120 FAQs')
        box(180,95,130,58,'<b>Open-Meteo daily</b><br/>weather_evaluator')
        box(355,95,130,58,'<b>SQLite</b><br/>Citas con ID único')
        arrow(70,210,70,153);arrow(245,210,245,153);arrow(420,210,420,153)
        arrow(380,210,300,153)
        box(15,0,460,60,
            '<b>La regla se aplica antes de escribir</b><br/>'
            'Ideal: confirmada · Marginal: pendiente de revisión<br/>'
            'Prohibido o error: no se registra la cita', '#e2f1eb')


def main():
    content = (ROOT/'docs/RESPUESTAS.md').read_text(encoding='utf-8')
    story = [Paragraph('Hoja de trabajo 5', styles['ReportTitle']),
             Paragraph('Orquestación de agentes para Parachute S.A.', styles['Question'])]
    paragraphs = content.split('\n\n')
    for text in paragraphs[1:]:
        text = text.strip()
        if text.startswith('## 2.'):
            story.append(PageBreak())
        if text.startswith('## '):
            story.append(Paragraph(escape(text[3:]), styles['Question']))
        else:
            style = styles['Small'] if text.startswith('- ') else styles['ReportBody']
            story.append(Paragraph(escape(text).replace('\n- ', '<br/>- ').replace('\n',' '), style))
    story += [PageBreak(), Paragraph('Arquitectura descentralizada', styles['ReportTitle']),
              Paragraph('Parte 3: especialistas pares y servicios compartidos', styles['Question']),
              Architecture(), Spacer(1,20), Paragraph(
              'Las flechas entre agentes son handoffs. Las flechas punteadas son llamadas '
              'a herramientas. La CLI continúa con el último agente y el historial; no '
              'hay un manager que reciba todos los resultados. El Runner limita cada '
              'solicitud a 12 turnos para acotar ciclos.', styles['ReportBody'])]
    doc=SimpleDocTemplate(str(OUTPUT),pagesize=A4,rightMargin=48,leftMargin=48,
                          topMargin=42,bottomMargin=55,title='HT5 - Orquestación',
                          author='Equipo Parachute S.A.')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(OUTPUT)


if __name__ == '__main__':
    main()
