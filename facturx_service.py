import logging
import tempfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from facturx import generate_from_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


def q(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt_dec(value):
    return format(q(value), "f")


def parse_date_yyyymmdd(date_str):
    return str(date_str or "").replace("-", "")


def add_text(parent, tag, text, attrib=None):
    node = SubElement(parent, tag, attrib or {})
    node.text = "" if text is None else str(text)
    return node


def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        if not elem.tail or not elem.tail.strip():
            elem.tail = i


def compute_totals(lines):
    subtotal = q(sum(q(line.get("quantity", 0)) * q(line.get("unitPrice", 0)) for line in lines))
    vat_total = q(
        sum(
            q(line.get("quantity", 0))
            * q(line.get("unitPrice", 0))
            * q(line.get("vatRate", 20))
            / Decimal("100")
            for line in lines
        )
    )
    total = q(subtotal + vat_total)
    return subtotal, vat_total, total


def payment_method_label(code):
    mapping = {
        "BANK_TRANSFER": "Virement bancaire",
        "CASH": "Espèces",
        "CARD": "Carte bancaire",
        "DIRECT_DEBIT": "Prélèvement",
        "CHECK": "Chèque",
    }
    return mapping.get(code, code or "Virement bancaire")


def payment_terms_label(code):
    mapping = {
        "PAYMENT_ON_RECEIPT": "Paiement à réception",
        "NET_30": "Paiement à 30 jours",
        "NET_45": "Paiement à 45 jours",
        "NET_60": "Paiement à 60 jours",
    }
    return mapping.get(code, code or "Paiement à réception")


def get_nested(data, *keys, default=None):
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def normalize_payload(data):
    seller = data.get("seller", {}) or {}
    buyer = data.get("buyer", {}) or {}
    profile = data.get("invoiceProfile", {}) or {}

    normalized_lines = []
    for line in data.get("lines", []) or []:
        normalized_lines.append(
            {
                "description": line.get("description", "Prestation"),
                "quantity": line.get("quantity", 1),
                "unitPrice": line.get("unitPrice", 0),
                "unitCode": line.get("unitCode", "H87"),
                "vatRate": line.get("vatRate", 20),
            }
        )

    return {
        "invoiceNumber": data.get("invoiceNumber", "INV-0001"),
        "invoiceDate": data.get("invoiceDate", ""),
        "serviceDate": data.get("serviceDate", ""),
        "currency": data.get("currency", "EUR") or "EUR",
        "notes": data.get("notes", ""),
        "paymentMethod": payment_method_label(profile.get("paymentMethodCode")),
        "paymentTerms": payment_terms_label(profile.get("paymentTermsCode")),
        "seller": {
            "name": seller.get("name", "Vendeur"),
            "addressLine1": seller.get("addressLine1", ""),
            "addressLine2": seller.get("addressLine2", ""),
            "addressLine3": seller.get("addressLine3", ""),
            "postalCode": seller.get("postalCode", ""),
            "city": seller.get("city", ""),
            "countryCode": seller.get("countryCode", "FR"),
            "siren": seller.get("siren", ""),
            "vatId": seller.get("vatId", ""),
        },
        "buyer": {
            "name": buyer.get("name", "Client"),
            "addressLine1": buyer.get("addressLine1", ""),
            "addressLine2": buyer.get("addressLine2", ""),
            "addressLine3": buyer.get("addressLine3", ""),
            "postalCode": buyer.get("postalCode", ""),
            "city": buyer.get("city", ""),
            "countryCode": buyer.get("countryCode", "FR"),
            "siren": buyer.get("siren", ""),
            "vatId": buyer.get("vatId", ""),
            "electronicAddress": buyer.get("electronicAddress", ""),
            "electronicAddressScheme": buyer.get("electronicAddressScheme", "EM"),
        },
        "lines": normalized_lines,
    }


def is_micro_vat_exempt(data):
    notes = (data.get("notes") or "").lower()
    lines = data.get("lines", [])
    if not lines:
        return False
    return all(q(line.get("vatRate", 0)) == Decimal("0.00") for line in lines) and (
        "293 b" in notes or "tva non applicable" in notes
    )


def tax_category_and_reason(data):
    if is_micro_vat_exempt(data):
        return {
            "category_code": "E",
            "exemption_reason": "TVA non applicable, article 293 B du CGI",
        }
    return {
        "category_code": "S",
        "exemption_reason": None,
    }


def add_postal_address(parent, ns_ram, party_data):
    postal = SubElement(parent, f"{{{ns_ram}}}PostalTradeAddress")
    add_text(postal, f"{{{ns_ram}}}LineOne", party_data.get("addressLine1", "-"))
    add_text(postal, f"{{{ns_ram}}}CityName", party_data.get("city", ""))
    add_text(postal, f"{{{ns_ram}}}CountryID", party_data.get("countryCode", "FR"))


def build_cii_xml(payload):
    data = normalize_payload(payload)

    ns_rsm = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    ns_ram = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    ns_udt = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

    register_namespace("rsm", ns_rsm)
    register_namespace("ram", ns_ram)
    register_namespace("udt", ns_udt)

    root = Element(f"{{{ns_rsm}}}CrossIndustryInvoice")

    subtotal, vat_total, total = compute_totals(data["lines"])
    currency = data["currency"]
    invoice_date = parse_date_yyyymmdd(data["invoiceDate"])
    service_date = parse_date_yyyymmdd(data["serviceDate"])
    tax_meta = tax_category_and_reason(data)
    category_code = tax_meta["category_code"]
    exemption_reason = tax_meta["exemption_reason"]

    context = SubElement(root, f"{{{ns_rsm}}}ExchangedDocumentContext")
    guideline = SubElement(context, f"{{{ns_ram}}}GuidelineSpecifiedDocumentContextParameter")
    add_text(
        guideline,
        f"{{{ns_ram}}}ID",
        "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic",
    )

    exchanged_doc = SubElement(root, f"{{{ns_rsm}}}ExchangedDocument")
    add_text(exchanged_doc, f"{{{ns_ram}}}ID", data["invoiceNumber"])
    add_text(exchanged_doc, f"{{{ns_ram}}}TypeCode", "380")

    issue_dt = SubElement(exchanged_doc, f"{{{ns_ram}}}IssueDateTime")
    add_text(issue_dt, f"{{{ns_udt}}}DateTimeString", invoice_date, {"format": "102"})

    if data.get("notes"):
        note = SubElement(exchanged_doc, f"{{{ns_ram}}}IncludedNote")
        add_text(note, f"{{{ns_ram}}}Content", data["notes"])

    sctt = SubElement(root, f"{{{ns_rsm}}}SupplyChainTradeTransaction")

    for idx, line in enumerate(data["lines"], start=1):
        qty = q(line["quantity"])
        unit_price = q(line["unitPrice"])
        line_total = q(qty * unit_price)
        vat_rate = q(line.get("vatRate", 20))
        unit_code = line.get("unitCode", "H87") or "H87"

        line_item = SubElement(sctt, f"{{{ns_ram}}}IncludedSupplyChainTradeLineItem")

        line_doc = SubElement(line_item, f"{{{ns_ram}}}AssociatedDocumentLineDocument")
        add_text(line_doc, f"{{{ns_ram}}}LineID", idx)

        product = SubElement(line_item, f"{{{ns_ram}}}SpecifiedTradeProduct")
        add_text(product, f"{{{ns_ram}}}Name", line.get("description", f"Ligne {idx}"))

        agreement = SubElement(line_item, f"{{{ns_ram}}}SpecifiedLineTradeAgreement")
        gross = SubElement(agreement, f"{{{ns_ram}}}GrossPriceProductTradePrice")
        add_text(gross, f"{{{ns_ram}}}ChargeAmount", fmt_dec(unit_price))
        net = SubElement(agreement, f"{{{ns_ram}}}NetPriceProductTradePrice")
        add_text(net, f"{{{ns_ram}}}ChargeAmount", fmt_dec(unit_price))

        delivery = SubElement(line_item, f"{{{ns_ram}}}SpecifiedLineTradeDelivery")
        billed_qty = SubElement(delivery, f"{{{ns_ram}}}BilledQuantity", {"unitCode": unit_code})
        billed_qty.text = fmt_dec(qty)

        settlement = SubElement(line_item, f"{{{ns_ram}}}SpecifiedLineTradeSettlement")
        tax = SubElement(settlement, f"{{{ns_ram}}}ApplicableTradeTax")
        add_text(tax, f"{{{ns_ram}}}TypeCode", "VAT")
        add_text(tax, f"{{{ns_ram}}}CategoryCode", category_code)
        add_text(tax, f"{{{ns_ram}}}RateApplicablePercent", fmt_dec(vat_rate))
        if exemption_reason:
            add_text(tax, f"{{{ns_ram}}}ExemptionReason", exemption_reason)

        summation = SubElement(
            settlement,
            f"{{{ns_ram}}}SpecifiedTradeSettlementLineMonetarySummation",
        )
        add_text(summation, f"{{{ns_ram}}}LineTotalAmount", fmt_dec(line_total))

    header_agreement = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeAgreement")

    seller = SubElement(header_agreement, f"{{{ns_ram}}}SellerTradeParty")
    add_text(seller, f"{{{ns_ram}}}Name", data["seller"]["name"])
    add_postal_address(seller, ns_ram, data["seller"])
    if data["seller"].get("vatId"):
    seller_tax = SubElement(seller, f"{{{ns_ram}}}SpecifiedTaxRegistration")
    add_text(seller_tax, f"{{{ns_ram}}}ID", data["seller"]["vatId"], {"schemeID": "VA"})

    buyer = SubElement(header_agreement, f"{{{ns_ram}}}BuyerTradeParty")
    add_text(buyer, f"{{{ns_ram}}}Name", data["buyer"]["name"])
    add_postal_address(buyer, ns_ram, data["buyer"])
    if data["buyer"].get("electronicAddress"):
        buyer_comm = SubElement(buyer, f"{{{ns_ram}}}URIUniversalCommunication")
        add_text(
            buyer_comm,
            f"{{{ns_ram}}}URIID",
            data["buyer"]["electronicAddress"],
        {"schemeID": data["buyer"].get("electronicAddressScheme", "EM")},
    )
    if data["buyer"].get("vatId"):
    buyer_tax = SubElement(buyer, f"{{{ns_ram}}}SpecifiedTaxRegistration")
    add_text(buyer_tax, f"{{{ns_ram}}}ID", data["buyer"]["vatId"], {"schemeID": "VA"})

    header_delivery = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeDelivery")
    if service_date:
        event = SubElement(header_delivery, f"{{{ns_ram}}}ActualDeliverySupplyChainEvent")
        occurrence = SubElement(event, f"{{{ns_ram}}}OccurrenceDateTime")
        add_text(occurrence, f"{{{ns_udt}}}DateTimeString", service_date, {"format": "102"})

    header_settlement = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeSettlement")
    add_text(header_settlement, f"{{{ns_ram}}}InvoiceCurrencyCode", currency)

    tax = SubElement(header_settlement, f"{{{ns_ram}}}ApplicableTradeTax")
    add_text(tax, f"{{{ns_ram}}}CalculatedAmount", fmt_dec(vat_total))
    add_text(tax, f"{{{ns_ram}}}TypeCode", "VAT")
    add_text(tax, f"{{{ns_ram}}}BasisAmount", fmt_dec(subtotal))
    add_text(tax, f"{{{ns_ram}}}CategoryCode", category_code)
    add_text(
        tax,
        f"{{{ns_ram}}}RateApplicablePercent",
        fmt_dec(data["lines"][0].get("vatRate", 20) if data["lines"] else 20),
    )
    if exemption_reason:
        add_text(tax, f"{{{ns_ram}}}ExemptionReason", exemption_reason)

    payment_terms = SubElement(header_settlement, f"{{{ns_ram}}}SpecifiedTradePaymentTerms")
    add_text(payment_terms, f"{{{ns_ram}}}Description", data.get("paymentTerms", "Paiement à réception"))

    monetary = SubElement(
        header_settlement,
        f"{{{ns_ram}}}SpecifiedTradeSettlementHeaderMonetarySummation",
    )
    add_text(monetary, f"{{{ns_ram}}}LineTotalAmount", fmt_dec(subtotal))
    add_text(monetary, f"{{{ns_ram}}}TaxBasisTotalAmount", fmt_dec(subtotal))
    add_text(monetary, f"{{{ns_ram}}}TaxTotalAmount", fmt_dec(vat_total), {"currencyID": currency})
    add_text(monetary, f"{{{ns_ram}}}GrandTotalAmount", fmt_dec(total))
    add_text(monetary, f"{{{ns_ram}}}DuePayableAmount", fmt_dec(total))

    indent(root)
    xml_string = tostring(root, encoding="unicode")
    logger.info("XML preview: %r", xml_string[:500])
    return xml_string


def build_visual_pdf(payload, pdf_path):
    data = normalize_payload(payload)
    width, height = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    y = height - 50

    subtotal, vat_total, total = compute_totals(data["lines"])

    c.setTitle(data["invoiceNumber"])
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, y, "FACTURE")
    c.setFont("Helvetica", 10)
    c.drawString(40, y - 18, "Couche lisible du document Factur-X")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(380, y, f"Facture : {data['invoiceNumber']}")
    c.setFont("Helvetica", 10)
    c.drawString(380, y - 16, f"Date : {data['invoiceDate']}")
    c.drawString(380, y - 30, f"Prestation : {data['serviceDate']}")

    y -= 80
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Vendeur")
    c.drawString(300, y, "Client")
    c.setFont("Helvetica", 10)

    seller_vat = data["seller"].get("vatId", "")
    vat_label = f"TVA : {seller_vat}" if seller_vat else "TVA non applicable, art. 293 B du CGI"

    issuer_lines = [
        data["seller"].get("name", ""),
        data["seller"].get("addressLine1", ""),
        f"{data['seller'].get('postalCode', '')} {data['seller'].get('city', '')}".strip(),
        vat_label,
        f"SIREN : {data['seller'].get('siren', '')}" if data["seller"].get("siren") else "",
    ]

    buyer_lines = [
        data["buyer"].get("name", ""),
        data["buyer"].get("addressLine1", ""),
        f"{data['buyer'].get('postalCode', '')} {data['buyer'].get('city', '')}".strip(),
        f"SIREN : {data['buyer'].get('siren', '')}" if data["buyer"].get("siren") else "",
        f"TVA : {data['buyer'].get('vatId', '')}" if data["buyer"].get("vatId") else "",
    ]

    yy = y - 18
    for line in issuer_lines:
        if line:
            c.drawString(40, yy, line[:38])
            yy -= 14

    yy = y - 18
    for line in buyer_lines:
        if line:
            c.drawString(300, yy, line[:38])
            yy -= 14

    y -= 100
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Description")
    c.drawString(360, y, "Qté")
    c.drawString(420, y, "PU HT")
    c.drawString(500, y, "Total HT")

    y -= 10
    c.line(40, y, 560, y)
    y -= 18
    c.setFont("Helvetica", 10)

    for line in data["lines"]:
        qty = q(line["quantity"])
        unit_price = q(line["unitPrice"])
        line_total = q(qty * unit_price)

        c.drawString(40, y, str(line.get("description", ""))[:48])
        c.drawRightString(390, y, fmt_dec(qty))
        c.drawRightString(470, y, fmt_dec(unit_price))
        c.drawRightString(550, y, fmt_dec(line_total))
        y -= 16

    y -= 8
    c.line(360, y, 560, y)
    y -= 18
    c.setFont("Helvetica", 10)
    c.drawString(390, y, "Sous-total HT")
    c.drawString(490, y, fmt_dec(subtotal))
    y -= 18
    c.drawString(390, y, "TVA")
    c.drawString(490, y, fmt_dec(vat_total))
    y -= 18
    c.setFont("Helvetica-Bold", 12)
    c.drawString(390, y, "Total TTC")
    c.drawString(490, y, fmt_dec(total))

    y -= 26
    c.setFont("Helvetica", 9)
    c.drawString(
        40,
        y,
        f"Paiement : {data.get('paymentMethod', '')} | Conditions : {data.get('paymentTerms', '')}"[:95],
    )

    if data.get("notes"):
        y -= 20
        c.drawString(40, y, f"Notes : {data['notes']}"[:95])

    c.save()


def generate_facturx_pdf(payload_dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        visual_pdf = tmp_path / "invoice.pdf"
        output_pdf = tmp_path / "invoice-facturx.pdf"

        build_visual_pdf(payload_dict, visual_pdf)
        xml_content = build_cii_xml(payload_dict)

        generate_from_file(
            str(visual_pdf),
            xml_content.encode("utf-8"),
            output_pdf_file=str(output_pdf),
        )

        return output_pdf.read_bytes(), output_pdf.name