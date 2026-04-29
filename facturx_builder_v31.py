#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring


def q(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def fmt_dec(value):
    return format(q(value), 'f')


def parse_date_yyyymmdd(date_str):
    return str(date_str or '').replace('-', '')


def compute_totals(lines):
    subtotal = q(sum(q(line['quantity']) * q(line['unitPrice']) for line in lines))
    vat_total = q(sum((q(line['quantity']) * q(line['unitPrice']) * q(line['vatRate']) / Decimal('100')) for line in lines))
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

    context = SubElement(root, f'{{{NS_RSM}}}ExchangedDocumentContext')
    guideline = SubElement(context, f'{{{NS_RAM}}}GuidelineSpecifiedDocumentContextParameter')
    add_text(guideline, f'{{{NS_RAM}}}ID', 'urn:factur-x.eu:1p0:basic')

    exchanged_doc = SubElement(root, f'{{{NS_RSM}}}ExchangedDocument')
    add_text(exchanged_doc, f'{{{NS_RAM}}}ID', data.get('invoiceNumber', 'INV-0001'))
    add_text(exchanged_doc, f'{{{NS_RAM}}}TypeCode', '380')
    issue_dt = SubElement(exchanged_doc, f'{{{NS_RAM}}}IssueDateTime')
    add_text(issue_dt, f'{{{NS_UDT}}}DateTimeString', invoice_date, {'format': '102'})
    if data.get('notes'):
        note = SubElement(exchanged_doc, f'{{{NS_RAM}}}IncludedNote')
        add_text(note, f'{{{NS_RAM}}}Content', data['notes'])

    sctt = SubElement(root, f'{{{NS_RSM}}}SupplyChainTradeTransaction')

    for idx, line in enumerate(data['lines'], start=1):
        qty = q(line['quantity'])
        unit_price = q(line['unitPrice'])
        line_total = q(qty * unit_price)
        vat_rate = q(line.get('vatRate', 20))

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
        add_text(tax, f'{{{NS_RAM}}}CategoryCode', 'S')
        add_text(tax, f'{{{NS_RAM}}}RateApplicablePercent', fmt_dec(vat_rate))
        summation = SubElement(settlement, f'{{{NS_RAM}}}SpecifiedTradeSettlementLineMonetarySummation')
        add_text(summation, f'{{{NS_RAM}}}LineTotalAmount', fmt_dec(line_total))

    header_agreement = SubElement(sctt, f'{{{NS_RAM}}}ApplicableHeaderTradeAgreement')
    seller = SubElement(header_agreement, f'{{{NS_RAM}}}SellerTradeParty')
    add_text(seller, f'{{{NS_RAM}}}Name', data.get('sellerName', 'Vendeur'))
    seller_postal = SubElement(seller, f'{{{NS_RAM}}}PostalTradeAddress')
    add_text(seller_postal, f'{{{NS_RAM}}}LineOne', data.get('sellerAddress', 'Adresse vendeur'))
    add_text(seller_postal, f'{{{NS_RAM}}}CountryID', 'FR')
    seller_tax = SubElement(seller, f'{{{NS_RAM}}}SpecifiedTaxRegistration')
    add_text(seller_tax, f'{{{NS_RAM}}}ID', data.get('sellerVat', 'FR00000000000'), {'schemeID': 'VA'})

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
    add_text(tax, f'{{{NS_RAM}}}CategoryCode', 'S')
    add_text(tax, f'{{{NS_RAM}}}RateApplicablePercent', fmt_dec(data['lines'][0].get('vatRate', 20) if data['lines'] else 20))

    payment_terms = SubElement(header_settlement, f'{{{NS_RAM}}}SpecifiedTradePaymentTerms')
    add_text(payment_terms, f'{{{NS_RAM}}}Description', data.get('paymentTerms', '30 jours'))

    monetary = SubElement(header_settlement, f'{{{NS_RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation')
    add_text(monetary, f'{{{NS_RAM}}}LineTotalAmount', fmt_dec(subtotal))
    add_text(monetary, f'{{{NS_RAM}}}TaxBasisTotalAmount', fmt_dec(subtotal))
    add_text(monetary, f'{{{NS_RAM}}}TaxTotalAmount', fmt_dec(vat_total), {'currencyID': currency})
    add_text(monetary, f'{{{NS_RAM}}}GrandTotalAmount', fmt_dec(total))
    add_text(monetary, f'{{{NS_RAM}}}DuePayableAmount', fmt_dec(total))

    indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding='unicode')


def build_visual_pdf(data, pdf_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

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
    issuer = [data.get('sellerName', ''), data.get('sellerAddress', ''), f"TVA: {data.get('sellerVat', '')}"]
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
        c.drawString(430, y, f"{q(line['vatRate'])}%")
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


def generate_facturx(payload_path, output_pdf):
    from facturx import generate_from_file

    data = json.loads(Path(payload_path).read_text(encoding='utf-8'))
    workdir = Path(output_pdf).resolve().parent
    workdir.mkdir(parents=True, exist_ok=True)

    visual_pdf = workdir / f"{Path(output_pdf).stem}.visual.pdf"
    xml_file = workdir / 'factur-x.xml'

    build_visual_pdf(data, visual_pdf)
    xml_file.write_text(build_cii_xml(data), encoding='utf-8')

    generate_from_file(
        str(visual_pdf),
        str(xml_file),
        flavor='factur-x',
        level='basic',
        output_pdf_file=str(output_pdf),
        check_xsd=True,
        check_schematron=True,
    )

    return visual_pdf, xml_file


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage : python facturx_builder_v31.py payload.json output/facture-facturx.pdf')
        sys.exit(1)
    payload_path = sys.argv[1]
    output_pdf = sys.argv[2]
    try:
        visual_pdf, xml_file = generate_facturx(payload_path, output_pdf)
        print(f'PDF Factur-X généré : {output_pdf}')
        print(f'PDF lisible source : {visual_pdf}')
        print(f'XML source : {xml_file}')
        print('Valide ensuite le PDF avec veraPDF et un validateur Factur-X / EN16931.')
    except ModuleNotFoundError:
        print('Dépendance manquante : pip install factur-x reportlab lxml')
        sys.exit(2)