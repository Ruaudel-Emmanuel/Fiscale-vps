#!/usr/bin/env python3
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def q(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def xml_escape(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')


def compute_totals(lines):
    subtotal = q(sum(q(line['quantity']) * q(line['unitPrice']) for line in lines))
    vat_total = q(sum((q(line['quantity']) * q(line['unitPrice']) * q(line['vatRate']) / Decimal('100')) for line in lines))
    total = q(subtotal + vat_total)
    return subtotal, vat_total, total


def build_xml(data):
    lines_xml = []
    for idx, line in enumerate(data['lines'], start=1):
        line_total = q(q(line['quantity']) * q(line['unitPrice']))
        lines_xml.append(f"""    <Line index=\"{idx}\">\n      <Description>{xml_escape(line['description'])}</Description>\n      <Quantity>{q(line['quantity'])}</Quantity>\n      <UnitPriceHT>{q(line['unitPrice'])}</UnitPriceHT>\n      <VatRate>{q(line['vatRate'])}</VatRate>\n      <LineTotalHT>{line_total}</LineTotalHT>\n    </Line>""")
    subtotal, vat_total, total = compute_totals(data['lines'])
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Invoice>
  <Header>
    <InvoiceNumber>{xml_escape(data['invoiceNumber'])}</InvoiceNumber>
    <InvoiceDate>{xml_escape(data['invoiceDate'])}</InvoiceDate>
    <ServiceDate>{xml_escape(data['serviceDate'])}</ServiceDate>
    <Currency>{xml_escape(data['currency'])}</Currency>
    <OperationNature>{xml_escape(data['operationNature'])}</OperationNature>
    <VatOnDebits>{xml_escape(data['vatOnDebits'])}</VatOnDebits>
  </Header>
  <Seller>
    <Name>{xml_escape(data['sellerName'])}</Name>
    <SIREN>{xml_escape(data['sellerSiren'])}</SIREN>
    <Address>{xml_escape(data['sellerAddress'])}</Address>
  </Seller>
  <Buyer>
    <Name>{xml_escape(data['buyerName'])}</Name>
    <SIREN>{xml_escape(data['buyerSiren'])}</SIREN>
    <BillingAddress>{xml_escape(data['buyerAddress'])}</BillingAddress>
    <DeliveryAddress>{xml_escape(data['deliveryAddress'])}</DeliveryAddress>
  </Buyer>
  <Payment>
    <Terms>{xml_escape(data['paymentTerms'])}</Terms>
    <Method>{xml_escape(data['paymentMethod'])}</Method>
  </Payment>
  <Lines>
{chr(10).join(lines_xml)}
  </Lines>
  <Totals>
    <SubtotalHT>{subtotal}</SubtotalHT>
    <TotalVAT>{vat_total}</TotalVAT>
    <TotalTTC>{total}</TotalTTC>
  </Totals>
  <Notes>{xml_escape(data['notes'])}</Notes>
</Invoice>
"""


def build_visual_pdf(data, pdf_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    width, height = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    y = height - 50
    c.setTitle(data['invoiceNumber'])
    c.setFont('Helvetica-Bold', 22)
    c.drawString(40, y, 'INVOICE')
    c.setFont('Helvetica', 10)
    c.drawString(40, y - 18, 'Visual invoice used as the human-readable layer of the Factur-X file')
    c.setFont('Helvetica-Bold', 11)
    c.drawString(380, y, f"Invoice No: {data['invoiceNumber']}")
    c.setFont('Helvetica', 10)
    c.drawString(380, y - 16, f"Invoice date: {data['invoiceDate']}")
    c.drawString(380, y - 30, f"Service date: {data['serviceDate']}")
    y -= 80
    c.setFont('Helvetica-Bold', 11)
    c.drawString(40, y, 'Issuer')
    c.drawString(300, y, 'Buyer')
    c.setFont('Helvetica', 10)
    issuer = [data['sellerName'], f"SIREN: {data['sellerSiren']}", data['sellerAddress']]
    buyer = [data['buyerName'], f"SIREN: {data['buyerSiren']}", data['buyerAddress'], f"Delivery: {data['deliveryAddress']}"]
    for i, line in enumerate(issuer):
        c.drawString(40, y - 18 - (i*14), str(line))
    for i, line in enumerate(buyer):
        c.drawString(300, y - 18 - (i*14), str(line))
    y -= 92
    c.setFont('Helvetica-Bold', 10)
    c.drawString(40, y, f"Nature of operation: {data['operationNature']}")
    c.drawString(300, y, f"VAT on debits: {data['vatOnDebits']}")
    y -= 28
    c.drawString(40, y, 'Description')
    c.drawString(300, y, 'Qty')
    c.drawString(350, y, 'Unit HT')
    c.drawString(430, y, 'VAT')
    c.drawString(490, y, 'Total HT')
    y -= 8
    c.line(40, y, 555, y)
    y -= 18
    c.setFont('Helvetica', 10)
    for line in data['lines']:
        total_ht = q(q(line['quantity']) * q(line['unitPrice']))
        if y < 100:
            c.showPage()
            y = height - 50
        c.drawString(40, y, str(line['description'])[:42])
        c.drawString(300, y, str(q(line['quantity'])))
        c.drawString(350, y, str(q(line['unitPrice'])))
        c.drawString(430, y, f"{q(line['vatRate'])}%")
        c.drawString(490, y, str(total_ht))
        y -= 16
    subtotal, vat_total, total = compute_totals(data['lines'])
    y -= 10
    c.line(350, y, 555, y)
    y -= 20
    c.setFont('Helvetica-Bold', 10)
    c.drawString(390, y, 'Subtotal HT')
    c.drawString(490, y, str(subtotal))
    y -= 16
    c.drawString(390, y, 'Total VAT')
    c.drawString(490, y, str(vat_total))
    y -= 18
    c.setFont('Helvetica-Bold', 12)
    c.drawString(390, y, 'Total TTC')
    c.drawString(490, y, str(total))
    y -= 26
    c.setFont('Helvetica', 9)
    c.drawString(40, y, f"Payment terms: {data['paymentTerms']} | Payment method: {data['paymentMethod']}")
    y -= 14
    c.drawString(40, y, f"Notes: {data['notes']}")
    c.save()


def generate_facturx(payload_path, output_pdf):
    from facturx import generate_from_file
    data = json.loads(Path(payload_path).read_text(encoding='utf-8'))

    workdir = Path(output_pdf).resolve().parent
    workdir.mkdir(parents=True, exist_ok=True)

    visual_pdf = workdir / f"{Path(output_pdf).stem}.visual.pdf"
    xml_file = workdir / 'factur-x.xml'

    # PDF lisible
    build_visual_pdf(data, visual_pdf)
    # XML de facture
    xml_file.write_text(build_xml(data), encoding='utf-8')

    # Factur-X final : on utilise la signature de TA version
    generate_from_file(
        str(visual_pdf),
        str(xml_file),
        flavor='factur-x',
        level='basic',
        output_pdf_file=str(output_pdf),
        check_xsd=True,
        check_schematron=True
    )

    return visual_pdf, xml_file


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python facturx_builder.py payload.json output.pdf')
        sys.exit(1)
    payload_path = sys.argv[1]
    output_pdf = sys.argv[2]
    try:
        visual_pdf, xml_file = generate_facturx(payload_path, output_pdf)
        print(f'Generated Factur-X PDF: {output_pdf}')
        print(f'Visual PDF source: {visual_pdf}')
        print(f'Embedded XML source: {xml_file}')
        print('Validate the output with veraPDF and a Factur-X validator before production use.')
    except ModuleNotFoundError:
        print('Missing dependency: install with `pip install factur-x reportlab`')
        sys.exit(2)
