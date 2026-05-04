from __future__ import annotations

from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from app.models import Address, InvoicePayload, ComputationResult

NS = "https://rennesdev.fr/schema/invoice/v2"


def _add_address(parent: Element, tag_name: str, address: Address) -> None:
    node = SubElement(parent, tag_name)
    SubElement(node, "Line1").text = address.line1
    SubElement(node, "Line2").text = address.line2 or ""
    SubElement(node, "PostalCode").text = address.postal_code
    SubElement(node, "City").text = address.city
    SubElement(node, "CountryCode").text = address.country_code


def build_xml(payload: InvoicePayload, computed: ComputationResult) -> bytes:
    """
    Construit un XML simple de la facture.
    Schéma maison, pensé pour être mappable plus tard vers Factur-X / EN16931.
    """
    language = payload.meta.language if payload.meta else "fr"
    profile = payload.meta.profile.value if payload.meta else "BASIC"

    root = Element(
        "Invoice",
        attrib={
            "xmlns": NS,
            "profile": profile,
            "currency": payload.invoice.currency,
            "language": language,
        },
    )

    # Header
    header = SubElement(root, "InvoiceHeader")
    SubElement(header, "Number").text = payload.invoice.number
    
    issue_date = payload.invoice.issue_date.isoformat()
    SubElement(header, "IssueDate").text = issue_date
    
    if payload.invoice.supply_date:
        supply_date = payload.invoice.supply_date.isoformat()
        SubElement(header, "SupplyDate").text = supply_date
        
    op_nature = payload.invoice.operation_nature.value
    SubElement(header, "OperationNature").text = op_nature
    
    tva_option = "true" if payload.invoice.tva_on_debits_option else "false"
    SubElement(header, "TVAOnDebitsOption").text = tva_option
    
    if payload.invoice.payment_terms:
        SubElement(header, "PaymentTerms").text = payload.invoice.payment_terms
    if payload.invoice.due_date:
        due_date = payload.invoice.due_date.isoformat()
        SubElement(header, "DueDate").text = due_date

    # Seller
    seller = SubElement(root, "Seller")
    SubElement(seller, "Name").text = payload.seller.name
    SubElement(seller, "SIREN").text = payload.seller.siren
    if payload.seller.siret:
        SubElement(seller, "SIRET").text = payload.seller.siret
    if payload.seller.vat_number:
        SubElement(seller, "VATNumber").text = payload.seller.vat_number
    if payload.seller.naf_code:
        SubElement(seller, "NAFCode").text = payload.seller.naf_code
    if payload.seller.legal_form:
        SubElement(seller, "LegalForm").text = payload.seller.legal_form
    if payload.seller.share_capital is not None:
        cap = payload.seller.share_capital
        SubElement(seller, "ShareCapital").text = f"{cap:.2f}"
    if payload.seller.rcs_city:
        SubElement(seller, "RCSCity").text = payload.seller.rcs_city

    _add_address(seller, "Address", payload.seller.address)

    if payload.seller.email:
        SubElement(seller, "Email").text = str(payload.seller.email)
    if payload.seller.phone:
        SubElement(seller, "Phone").text = payload.seller.phone
    if payload.seller.website:
        SubElement(seller, "Website").text = str(payload.seller.website)

    # Buyer
    buyer = SubElement(root, "Buyer")
    SubElement(buyer, "Name").text = payload.buyer.name
    SubElement(buyer, "SIREN").text = payload.buyer.siren
    if payload.buyer.siret:
        SubElement(buyer, "SIRET").text = payload.buyer.siret
    if payload.buyer.vat_number:
        SubElement(buyer, "VATNumber").text = payload.buyer.vat_number

    _add_address(buyer, "BillingAddress", payload.buyer.address_billing)
    if payload.buyer.address_shipping:
        _add_address(buyer, "ShippingAddress", payload.buyer.address_shipping)
    if payload.buyer.email:
        SubElement(buyer, "Email").text = str(payload.buyer.email)

    # Lines
    lines_node = SubElement(root, "Lines")
    for line in computed.lines:
        line_el = SubElement(lines_node, "Line")
        SubElement(line_el, "LineNumber").text = str(line.line_number)
        SubElement(line_el, "Description").text = line.description
        quantity = SubElement(line_el, "Quantity")
        quantity.text = str(line.quantity)
        if line.unit:
            quantity.set("unit", line.unit)
        SubElement(line_el, "UnitPriceHT").text = f"{line.unit_price_ht:.2f}"
        SubElement(line_el, "DiscountRate").text = f"{line.discount_rate:.2f}"
        SubElement(line_el, "TVARate").text = f"{line.tva_rate:.2f}"
        SubElement(line_el, "LineGrossHT").text = f"{line.line_gross_ht:.2f}"
        SubElement(line_el, "LineDiscount").text = f"{line.line_discount:.2f}"
        SubElement(line_el, "LineTotalHT").text = f"{line.line_net_ht:.2f}"
        SubElement(line_el, "LineTotalTVA").text = f"{line.line_tva:.2f}"
        SubElement(line_el, "LineTotalTTC").text = f"{line.line_ttc:.2f}"

    # Totals
    totals_el = SubElement(root, "Totals")
    SubElement(totals_el, "TotalHT").text = f"{computed.totals.total_ht:.2f}"
    SubElement(totals_el, "TotalDiscount").text = (
        f"{computed.totals.total_discount:.2f}"
    )
    SubElement(totals_el, "TotalTVA").text = f"{computed.totals.total_tva:.2f}"
    SubElement(totals_el, "TotalTTC").text = f"{computed.totals.total_ttc:.2f}"

    # Meta
    meta_el = SubElement(root, "Meta")
    created_at = (
        payload.meta.created_at
        if payload.meta and payload.meta.created_at
        else datetime.now(timezone.utc)
    )
    generation_tool = (
        payload.meta.generation_tool
        if payload.meta and payload.meta.generation_tool
        else "rennesdev-invoice-v2"
    )
    SubElement(meta_el, "CreatedAt").text = created_at.isoformat()
    SubElement(meta_el, "GenerationTool").text = generation_tool

    return tostring(root, encoding="utf-8", xml_declaration=True)

