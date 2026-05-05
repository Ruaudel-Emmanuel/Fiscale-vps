import tempfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from facturx import generate_from_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from fastapi.logger import logger 

def q(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def fmt_dec(value):
    return format(q(value), 'f')


def parse_date_yyyymmdd(date_str):
    return str(date_str or '').replace('-', '')


def is_micro_vat_exempt(data):
    notes = (data.get('notes') or '').lower()
    lines = data.get('lines', [])
    if not lines:
        return False
    return all(q(line.get('vatRate', 0)) == Decimal('0.00') for line in lines) and (
        '293 b' in notes or 'tva non applicable' in notes
    )


def tax_category_and_reason(data):
    if is_micro_vat_exempt(data):
        return {
            'category_code': 'E',
            'exemption_reason': 'TVA non applicable, article 293 B du CGI'
        }
    return {
        'category_code': 'S',
        'exemption_reason': None
    }


def compute_totals(lines):
    subtotal = q(sum(q(line['quantity']) * q(line['unitPrice']) for line in lines))
    vat_total = q(sum(
        (q(line['quantity']) * q(line['unitPrice']) * q(line.get('vatRate', 0)) / Decimal('100'))
        for line in lines
    ))
    total = q(subtotal + vat_total)
    return subtotal, vat_total, total


def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    if level and (not elem.tail or not elem.tail.strip()):
        elem.tail = i


def add_text(parent, tag, text, attrib=None):
    node = SubElement(parent, tag, attrib or {})
    node.text = '' if text is None else str(text)
    return node


def build_cii_xml(data):
    NS_RSM = 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100'
    NS_RAM = 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100'
    NS_UDT = 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100'

    root = Element(f'{{{NS_RSM}}}CrossIndustryInvoice', {
        'xmlns:rsm': NS_RSM,
        'xmlns:ram': NS_RAM,
        'xmlns:udt': NS_UDT,
    })

    subtotal, vat_total, total = compute_totals(data['lines'])
    currency = data.get('currency', 'EUR') or 'EUR'
    invoice_date = parse_date_yyyymmdd(data.get('invoiceDate'))
    tax_meta = tax_category_and_reason(data)
    category_code = tax_meta['category_code']
    exemption_reason = tax_meta['exemption_reason']

    context = SubElement(root, f'{{{NS_RSM}}}ExchangedDocumentContext')
    guideline = SubElement(context, f'{{{NS_RAM}}}GuidelineSpecifiedDocumentContextParameter')
    add_text(guideline, f'{{{NS_RAM}}}ID', 'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic')

    exchanged_doc = SubElement(root, f'{{{NS_RSM}}}ExchangedDocument')
    add_text(exchanged_doc, f'{{{NS_RAM}}}ID', data.get('invoiceNumber', 'INV-0001'))
    add_text(exchanged_doc, f'{{{NS_RAM}}}TypeCode', '380')
    issue_dt = SubElement(exchanged_doc, f'{{{NS_RAM}}}IssueDateTime')
    add_text(issue_dt, f'{{{NS_UDT}}}DateTimeString', invoice_date, {'format': '102'})

    notes_value = data.get('notes')
    if notes_value:
        note = SubElement(exchanged_doc, f'{{{NS_RAM}}}IncludedNote')
        add_text(note, f'{{{NS_RAM}}}Content', notes_value)

    sctt = SubElement(root, f'{{{NS_RSM}}}SupplyChainTradeTransaction')

    for idx, line in enumerate(data['lines'], start=1):
        qty = q(line['quantity'])
        unit_price = q(line['unitPrice'])
        line_total = q(qty * unit_price)
        vat_rate = q(line.get('vatRate', 0))

        line_item = SubElement(sctt, f'{{{NS_RAM}}}IncludedSupplyChainTradeLineItem')
        line_doc = SubElement(line_item, f'{{{NS_RAM}}}AssociatedDocumentLineDocument')
        add_text(line_doc, f'{{{NS_RAM}}}LineID', idx)

        product = SubElement(line_item, f'{{{NS_RAM}}}SpecifiedTradeProduct')
        add_text(product, f'{{{NS_RAM}}}Name', line.get('description', f'Ligne {idx}'))

        agreement = SubElement(line_item, f'{{{NS_RAM}}}SpecifiedLineTradeAgreement')
        gross = SubElement(agreement, f'{{{NS_RAM}}}GrossPriceProductTradePrice')
        add_text(gross, f'{{{NS_RAM}}}ChargeAmount', fmt_dec(unit_price))
        net = SubElement(agreement, f'{{{NS_RAM}}}NetPriceProductTradePrice')
        add_text(net, f'{{{NS_RAM}}}ChargeAmount', fmt_dec(unit_price))

        delivery = SubElement(line_item, f'{{{NS_RAM}}}SpecifiedLineTradeDelivery')
        billed_qty = SubElement(delivery, f'{{{NS_RAM}}}BilledQuantity', {'unitCode': 'H87'})
        billed_qty.text = fmt_dec(qty)

        settlement = SubElement(line_item, f'{{{NS_RAM}}}SpecifiedLineTradeSettlement')
        tax = SubElement(settlement, f'{{{NS_RAM}}}ApplicableTradeTax')
        add_text(tax, f'{{{NS_RAM}}}TypeCode', 'VAT')
        add_text(tax, f'{{{NS_RAM}}}CategoryCode', category_code)
        add_text(tax, f'{{{NS_RAM}}}RateApplicablePercent', fmt_dec(vat_rate))
        if exemption_reason:
            add_text(tax, f'{{{NS_RAM}}}ExemptionReason', exemption_reason)

        summation = SubElement(settlement, f'{{{NS_RAM}}}SpecifiedTradeSettlementLineMonetarySummation')
        add_text(summation, f'{{{NS_RAM}}}LineTotalAmount', fmt_dec(line_total))

    header_agreement = SubElement(sctt, f'{{{NS_RAM}}}ApplicableHeaderTradeAgreement')
    seller = SubElement(header_agreement, f'{{{NS_RAM}}}SellerTradeParty')
    add_text(seller, f'{{{NS_RAM}}}Name', data.get('sellerName', 'Vendeur'))

    seller_postal = SubElement(seller, f'{{{NS_RAM}}}PostalTradeAddress')
    add_text(seller_postal, f'{{{NS_RAM}}}LineOne', data.get('sellerAddress', 'Adresse vendeur'))
    add_text(seller_postal, f'{{{NS_RAM}}}CountryID', 'FR')

    seller_vat = data.get('sellerVat')
    if seller_vat:
        seller_tax = SubElement(seller, f'{{{NS_RAM}}}SpecifiedTaxRegistration')
        add_text(seller_tax, f'{{{NS_RAM}}}ID', seller_vat, {'schemeID': 'VA'})

    buyer = SubElement(header_agreement, f'{{{NS_RAM}}}BuyerTradeParty')
    add_text(buyer, f'{{{NS_RAM}}}Name', data.get('buyerName', 'Client'))
    buyer_postal = SubElement(buyer, f'{{{NS_RAM}}}PostalTradeAddress')
    add_text(buyer_postal, f'{{{NS_RAM}}}LineOne', data.get('buyerAddress', 'Adresse client'))
    add_text(buyer_postal, f'{{{NS_RAM}}}CountryID', 'FR')

    header_delivery = SubElement(sctt, f'{{{NS_RAM}}}ApplicableHeaderTradeDelivery')
    if data.get('serviceDate'):
        event = SubElement(header_delivery, f'{{{NS_RAM}}}ActualDeliverySupplyChainEvent')
        occurrence = SubElement(event, f'{{{NS_RAM}}}OccurrenceDateTime')
        add_text(occurrence, f'{{{NS_UDT}}}DateTimeString', parse_date_yyyymmdd(data['serviceDate']), {'format': '102'})

    header_settlement = SubElement(sctt, f'{{{NS_RAM}}}ApplicableHeaderTradeSettlement')
    add_text(header_settlement, f'{{{NS_RAM}}}InvoiceCurrencyCode', currency)

    tax = SubElement(header_settlement, f'{{{NS_RAM}}}ApplicableTradeTax')
    add_text(tax, f'{{{NS_RAM}}}CalculatedAmount', fmt_dec(vat_total))
    add_text(tax, f'{{{NS_RAM}}}TypeCode', 'VAT')
    add_text(tax, f'{{{NS_RAM}}}BasisAmount', fmt_dec(subtotal))
    add_text(tax, f'{{{NS_RAM}}}CategoryCode', category_code)
    add_text(tax, f'{{{NS_RAM}}}RateApplicablePercent', fmt_dec(data['lines'][0].get('vatRate', 0) if data['lines'] else 0))
    if exemption_reason:
        add_text(tax, f'{{{NS_RAM}}}ExemptionReason', exemption_reason)

    payment_terms = SubElement(header_settlement, f'{{{NS_RAM}}}SpecifiedTradePaymentTerms')
    add_text(payment_terms, f'{{{NS_RAM}}}Description', data.get('paymentTerms', '30 jours'))

    monetary = SubElement(header_settlement, f'{{{NS_RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation')
    add_text(monetary, f'{{{NS_RAM}}}LineTotalAmount', fmt_dec(subtotal))
    add_text(monetary, f'{{{NS_RAM}}}TaxBasisTotalAmount', fmt_dec(subtotal))
    add_text(monetary, f'{{{NS_RAM}}}TaxTotalAmount', fmt_dec(vat_total), {'currencyID': currency})
    add_text(monetary, f'{{{NS_RAM}}}GrandTotalAmount', fmt_dec(total))
    add_text(monetary, f'{{{NS_RAM}}}DuePayableAmount', fmt_dec(total))

    indent(root)
    return tostring(root, encoding="unicode")


def build_visual_pdf(data, pdf_path):
    width, height = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    y = height - 50

    c.setTitle(data.get('invoiceNumber', 'Facture'))
    c.setFont('Helvetica-Bold', 22)
    c.drawString(40, y, 'FACTURE')
    c.setFont('Helvetica', 10)
    c.drawString(40, y - 18, 'Couche lisible du document Factur-X')
    c.setFont('Helvetica-Bold', 11)
    c.drawString(380, y, f"Facture : {data.get('invoiceNumber', 'INV-0001')}")
    c.setFont('Helvetica', 10)
    c.drawString(380, y - 16, f"Date : {data.get('invoiceDate', '')}")
    c.drawString(380, y - 30, f"Prestation : {data.get('serviceDate', '')}")

    y -= 80
    c.setFont('Helvetica-Bold', 11)
    c.drawString(40, y, 'Vendeur')
    c.drawString(300, y, 'Client')
    c.setFont('Helvetica', 10)

    seller_vat = data.get('sellerVat', '')
    vat_label = f"TVA: {seller_vat}" if seller_vat else "TVA non applicable, art. 293 B du CGI"
    issuer = [data.get('sellerName', ''), data.get('sellerAddress', ''), vat_label]
    buyer = [data.get('buyerName', ''), data.get('buyerAddress', ''), f"SIREN: {data.get('buyerSiren', '')}"]

    for i, line in enumerate(issuer):
        c.drawString(40, y - 18 - i * 14, str(line))
    for i, line in enumerate(buyer):
        c.drawString(300, y - 18 - i * 14, str(line))

    y -= 92
    c.setFont('Helvetica-Bold', 10)
    c.drawString(40, y, 'Description')
    c.drawString(300, y, 'Qté')
    c.drawString(350, y, 'PU HT')
    c.drawString(430, y, 'TVA')
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
        c.drawString(430, y, f"{q(line.get('vatRate', 0))}%")
        c.drawString(490, y, str(total_ht))
        y -= 16

    subtotal, vat_total, total = compute_totals(data['lines'])
    y -= 10
    c.line(350, y, 555, y)
    y -= 20
    c.setFont('Helvetica-Bold', 10)
    c.drawString(390, y, 'Sous-total HT')
    c.drawString(490, y, str(subtotal))
    y -= 16
    c.drawString(390, y, 'TVA')
    c.drawString(490, y, str(vat_total))
    y -= 18
    c.setFont('Helvetica-Bold', 12)
    c.drawString(390, y, 'Total TTC')
    c.drawString(490, y, str(total))
    y -= 26
    c.setFont('Helvetica', 9)
    c.drawString(40, y, f"Paiement : {data.get('paymentMethod', '')} | Conditions : {data.get('paymentTerms', '')}")
    c.save()

import logging
logger = logging.getLogger(__name__)

def generate_facturx_pdf(payload_dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        visual_pdf = tmp_path / "invoice.pdf"
        xml_file = tmp_path / "factur-x.xml"
        output_pdf = tmp_path / "invoice-facturx.pdf"

        # 1) PDF lisible
        build_visual_pdf(payload_dict, visual_pdf)

        # 2) XML CII
        xml_content = build_cii_xml(payload_dict)
        logger.info("XML preview: %r", xml_content[:200])

        # Optionnel: dossier tmp persistant dans l'image si tu veux garder une trace
        persist_tmp = Path("/app/tmp")
        try:
            persist_tmp.mkdir(parents=True, exist_ok=True)
            (persist_tmp / "debug-facturx.xml").write_text(xml_content, encoding="utf-8")
        except Exception as e:
            logger.warning("Impossible d'écrire /app/tmp/debug-facturx.xml : %s", e)

        xml_file.write_text(xml_content, encoding="utf-8")

        # 3) Génération Factur-X
        generate_from_file(
            str(visual_pdf),
            str(xml_file),
            output_pdf_file=str(output_pdf),
        )

        # 4) Retour du PDF généré
        return output_pdf.read_bytes(), output_pdf.name