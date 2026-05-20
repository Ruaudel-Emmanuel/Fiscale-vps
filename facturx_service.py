import logging
import tempfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from facturx import generate_from_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)


MINIMUM_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <rsm:ExchangedDocumentContext>
    <ram:BusinessProcessSpecifiedDocumentContextParameter>
      <ram:ID>A1</ram:ID>
    </ram:BusinessProcessSpecifiedDocumentContextParameter>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:factur-x.eu:1p0:minimum</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{invoice_number}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">{invoice_date}</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:BuyerReference>{buyer_reference}</ram:BuyerReference>
      <ram:SellerTradeParty>
        <ram:Name>{seller_name}</ram:Name>
        <ram:SpecifiedLegalOrganization>
          <ram:ID schemeID="0002">{seller_legal_id}</ram:ID>
        </ram:SpecifiedLegalOrganization>
        <ram:PostalTradeAddress>
          <ram:CountryID>{seller_country}</ram:CountryID>
        </ram:PostalTradeAddress>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="VA">{seller_vat_id}</ram:ID>
        </ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>{buyer_name}</ram:Name>
        <ram:SpecifiedLegalOrganization>
          <ram:ID schemeID="0002">{buyer_legal_id}</ram:ID>
        </ram:SpecifiedLegalOrganization>
      </ram:BuyerTradeParty>
      <ram:BuyerOrderReferencedDocument>
        <ram:IssuerAssignedID>{buyer_order_reference}</ram:IssuerAssignedID>
      </ram:BuyerOrderReferencedDocument>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>{currency}</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount currencyID="{currency}">{tax_basis_total}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="{currency}">{tax_total}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount currencyID="{currency}">{grand_total}</ram:GrandTotalAmount>
        <ram:DuePayableAmount currencyID="{currency}">{due_payable}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""


def q(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fmt_dec(value):
    return format(q(value), "f")


def parse_date_yyyymmdd(date_str):
    return str(date_str or "").replace("-", "")


def xml_escape(value):
    value = "" if value is None else str(value)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def normalize_payload(data):
    seller = data.get("seller", {}) or {}
    buyer = data.get("buyer", {}) or {}

    total = q(data.get("totalAmount", 0))
    tax_total = q(data.get("taxTotalAmount", 0))

    return {
        "invoice_number": xml_escape(data.get("invoiceNumber", "FAC-0001")),
        "invoice_date": xml_escape(parse_date_yyyymmdd(data.get("invoiceDate", "20260520"))),
        "currency": xml_escape(data.get("currency", "EUR") or "EUR"),
        "buyer_reference": xml_escape(data.get("buyerReference", "SOLO")),
        "buyer_order_reference": xml_escape(data.get("buyerOrderReference", "SOLO")),
        "seller_name": xml_escape(seller.get("name", "Rennesdev")),
        "seller_country": xml_escape(seller.get("countryCode", "FR") or "FR"),
        "seller_legal_id": xml_escape(seller.get("legalId", seller.get("siren", "12345678900000"))),
        "seller_vat_id": xml_escape(seller.get("vatId", "FR00123456789")),
        "buyer_name": xml_escape(buyer.get("name", "Client")),
        "buyer_legal_id": xml_escape(buyer.get("legalId", buyer.get("siren", "99999999900000"))),
        "tax_basis_total": fmt_dec(total),
        "tax_total": fmt_dec(tax_total),
        "grand_total": fmt_dec(total + tax_total),
        "due_payable": fmt_dec(total + tax_total),
        "notes": data.get("notes", ""),
        "display_total": fmt_dec(total + tax_total),
    }


def build_minimum_cii_xml(payload):
    data = normalize_payload(payload)
    xml_string = MINIMUM_XML_TEMPLATE.format(**data)
    logger.info("MINIMUM XML preview: %r", xml_string[:1200])
    return xml_string


def build_visual_pdf(payload, pdf_path):
    data = normalize_payload(payload)

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    _, height = A4
    y = height - 50

    c.setTitle(data["invoice_number"])

    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, y, "FACTURE")

    c.setFont("Helvetica", 10)
    c.drawString(40, y - 18, "Version minimale Factur-X pour usage interne")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(380, y, f"Facture : {data['invoice_number']}")

    c.setFont("Helvetica", 10)
    c.drawString(380, y - 16, f"Date : {data['invoice_date']}")
    c.drawString(380, y - 30, f"Devise : {data['currency']}")

    y -= 90

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Vendeur")
    c.drawString(300, y, "Client")

    c.setFont("Helvetica", 10)
    c.drawString(40, y - 18, seller_name := data["seller_name"])
    c.drawString(40, y - 32, f"Pays : {data['seller_country']}")
    c.drawString(40, y - 46, f"SIREN/SIRET : {data['seller_legal_id']}")
    c.drawString(40, y - 60, f"TVA : {data['seller_vat_id']}")

    c.drawString(300, y - 18, buyer_name := data["buyer_name"])
    c.drawString(300, y - 32, f"ID : {data['buyer_legal_id']}")

    y -= 110
    c.line(40, y, 560, y)

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Montant total à payer")
    c.drawRightString(550, y, f"{data['display_total']} {data['currency']}")

    if data.get("notes"):
        y -= 35
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Notes : {str(data['notes'])}"[:95])

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