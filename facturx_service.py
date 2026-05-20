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


def normalize_payload(data):
    seller = data.get("seller", {}) or {}
    buyer = data.get("buyer", {}) or {}

    return {
        "invoiceNumber": data.get("invoiceNumber", "FAC-0001"),
        "invoiceDate": data.get("invoiceDate", ""),
        "currency": data.get("currency", "EUR") or "EUR",
        "seller": {
            "name": seller.get("name", "Vendeur"),
            "countryCode": seller.get("countryCode", "FR") or "FR",
        },
        "buyer": {
            "name": buyer.get("name", "Client"),
            "countryCode": buyer.get("countryCode", "FR") or "FR",
        },
        "totalAmount": q(data.get("totalAmount", 0)),
        "notes": data.get("notes", ""),
    }


def build_minimum_cii_xml(payload):
    data = normalize_payload(payload)

    ns_rsm = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    ns_ram = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    ns_udt = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

    register_namespace("rsm", ns_rsm)
    register_namespace("ram", ns_ram)
    register_namespace("udt", ns_udt)

    root = Element(f"{{{ns_rsm}}}CrossIndustryInvoice")

    context = SubElement(root, f"{{{ns_rsm}}}ExchangedDocumentContext")
    guideline = SubElement(context, f"{{{ns_ram}}}GuidelineSpecifiedDocumentContextParameter")
    add_text(guideline, f"{{{ns_ram}}}ID", "urn:factur-x.eu:1p0:minimum")

    exchanged_doc = SubElement(root, f"{{{ns_rsm}}}ExchangedDocument")
    add_text(exchanged_doc, f"{{{ns_ram}}}ID", data["invoiceNumber"])
    add_text(exchanged_doc, f"{{{ns_ram}}}TypeCode", "380")

    issue_dt = SubElement(exchanged_doc, f"{{{ns_ram}}}IssueDateTime")
    add_text(
        issue_dt,
        f"{{{ns_udt}}}DateTimeString",
        parse_date_yyyymmdd(data["invoiceDate"]),
        {"format": "102"},
    )

    if data.get("notes"):
        note = SubElement(exchanged_doc, f"{{{ns_ram}}}IncludedNote")
        add_text(note, f"{{{ns_ram}}}Content", data["notes"])

    sctt = SubElement(root, f"{{{ns_rsm}}}SupplyChainTradeTransaction")

    header_agreement = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeAgreement")

    seller = SubElement(header_agreement, f"{{{ns_ram}}}SellerTradeParty")
    add_text(seller, f"{{{ns_ram}}}Name", data["seller"]["name"])
    seller_postal = SubElement(seller, f"{{{ns_ram}}}PostalTradeAddress")
    add_text(seller_postal, f"{{{ns_ram}}}CountryID", data["seller"]["countryCode"])

    buyer = SubElement(header_agreement, f"{{{ns_ram}}}BuyerTradeParty")
    add_text(buyer, f"{{{ns_ram}}}Name", data["buyer"]["name"])
    buyer_postal = SubElement(buyer, f"{{{ns_ram}}}PostalTradeAddress")
    add_text(buyer_postal, f"{{{ns_ram}}}CountryID", data["buyer"]["countryCode"])

    SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeDelivery")

    header_settlement = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeSettlement")
    add_text(header_settlement, f"{{{ns_ram}}}InvoiceCurrencyCode", data["currency"])

    monetary = SubElement(
        header_settlement,
        f"{{{ns_ram}}}SpecifiedTradeSettlementHeaderMonetarySummation",
    )
    add_text(monetary, f"{{{ns_ram}}}GrandTotalAmount", fmt_dec(data["totalAmount"]))
    add_text(monetary, f"{{{ns_ram}}}DuePayableAmount", fmt_dec(data["totalAmount"]))

    indent(root)
    xml_string = tostring(root, encoding="unicode")
    logger.info("MINIMUM XML preview: %r", xml_string[:1000])
    return xml_string


def build_visual_pdf(payload, pdf_path):
    data = normalize_payload(payload)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    y = height - 50

    c.setTitle(data["invoiceNumber"])

    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, y, "FACTURE")

    c.setFont("Helvetica", 10)
    c.drawString(40, y - 18, "Version minimale Factur-X pour usage interne")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(380, y, f"Facture : {data['invoiceNumber']}")

    c.setFont("Helvetica", 10)
    c.drawString(380, y - 16, f"Date : {data['invoiceDate']}")
    c.drawString(380, y - 30, f"Devise : {data['currency']}")

    y -= 90

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Vendeur")
    c.drawString(300, y, "Client")

    c.setFont("Helvetica", 10)
    c.drawString(40, y - 18, data["seller"]["name"])
    c.drawString(40, y - 32, f"Pays : {data['seller']['countryCode']}")

    c.drawString(300, y - 18, data["buyer"]["name"])
    c.drawString(300, y - 32, f"Pays : {data['buyer']['countryCode']}")

    y -= 90
    c.line(40, y, 560, y)

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Montant total à payer")
    c.drawRightString(550, y, f"{fmt_dec(data['totalAmount'])} {data['currency']}")

    if data.get("notes"):
        y -= 35
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Notes : {data['notes']}"[:95])

    c.save()


def generate_facturx_pdf(payload_dict):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        visual_pdf = tmp_path / "invoice.pdf"
        output_pdf = tmp_path / "invoice-facturx.pdf"

        build_visual_pdf(payload_dict, visual_pdf)
        xml_content = build_minimum_cii_xml(payload_dict)

        generate_from_file(
            str(visual_pdf),
            xml_content.encode("utf-8"),
            output_pdf_file=str(output_pdf),
        )

        return output_pdf.read_bytes(), output_pdf.name