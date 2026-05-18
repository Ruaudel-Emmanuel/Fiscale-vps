import logging
import tempfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring, register_namespace

from facturx import generate_from_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

ALLOWED_UNIT_CODES = {"H87", "DAY", "HUR"}
PAYMENT_METHOD_LABELS = {
    "BANK_TRANSFER": "Virement bancaire",
    "CARD": "Carte bancaire",
    "DIRECT_DEBIT": "Prélèvement automatique",
}
PAYMENT_TERMS_LABELS = {
    "PAYMENT_ON_RECEIPT": "Paiement à réception",
    "NET_30": "Paiement à 30 jours",
}
LATE_PENALTY_LABELS = {
    "ECB_PLUS_10": "Pénalités de retard : taux directeur de la BCE majoré de 10 points.",
    "LEGAL_RATE": "Pénalités de retard : taux légal en vigueur.",
}
COLLECTION_FEE_LABELS = {
    "FIXED_40_EUR": "Indemnité forfaitaire pour frais de recouvrement : 40 euros.",
    "NOT_APPLICABLE": "Indemnité forfaitaire pour frais de recouvrement : non applicable.",
}
DISCOUNT_LABELS = {
    "NO_DISCOUNT": "Escompte pour paiement anticipé : néant.",
    "DISCOUNT_2_PERCENT": "Escompte pour paiement anticipé : 2 %.",
}
VAT_PROFILES = {
    "FR_STANDARD_20": {
        "vat_rate": Decimal("20.00"),
        "category_code": "S",
        "exemption_reason": None,
        "requires_seller_vat_id": True,
    },
    "FR_INTERMEDIATE_10": {
        "vat_rate": Decimal("10.00"),
        "category_code": "S",
        "exemption_reason": None,
        "requires_seller_vat_id": True,
    },
    "FR_REDUCED_55": {
        "vat_rate": Decimal("5.50"),
        "category_code": "S",
        "exemption_reason": None,
        "requires_seller_vat_id": True,
    },
    "FR_293B": {
        "vat_rate": Decimal("0.00"),
        "category_code": "E",
        "exemption_reason": "TVA non applicable, article 293 B du CGI",
        "requires_seller_vat_id": False,
    },
}


def q(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)



def fmt_dec(value: Any) -> str:
    return format(q(value), "f")



def parse_date_yyyymmdd(date_str: str | None) -> str:
    return str(date_str or "").replace("-", "")



def only_digits(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())



def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)



def resolve_vat_profile(invoice_profile: dict[str, Any]) -> dict[str, Any]:
    vat_regime = invoice_profile.get("vatRegime")
    require(vat_regime in VAT_PROFILES, f"Régime TVA non supporté : {vat_regime}")
    return VAT_PROFILES[vat_regime]



def build_legal_notes(invoice_profile: dict[str, Any], vat_profile: dict[str, Any]) -> str:
    late_penalty = LATE_PENALTY_LABELS[invoice_profile["latePenaltyProfile"]]
    collection_fee = COLLECTION_FEE_LABELS[invoice_profile["collectionFeeProfile"]]
    discount = DISCOUNT_LABELS[invoice_profile["discountProfile"]]
    notes = [late_penalty, collection_fee, discount]
    if vat_profile.get("exemption_reason"):
        notes.append(vat_profile["exemption_reason"])
    return " ".join(notes)



def payment_method_label(code: str) -> str:
    require(code in PAYMENT_METHOD_LABELS, f"Mode de paiement non supporté : {code}")
    return PAYMENT_METHOD_LABELS[code]



def payment_terms_label(code: str) -> str:
    require(code in PAYMENT_TERMS_LABELS, f"Conditions de paiement non supportées : {code}")
    return PAYMENT_TERMS_LABELS[code]



def validate_party(party: dict[str, Any], role: str, vat_required: bool = False) -> None:
    require(bool((party.get("name") or "").strip()), f"{role}.name est obligatoire")
    require(bool((party.get("addressLine1") or "").strip()), f"{role}.addressLine1 est obligatoire")
    require(bool((party.get("postalCode") or "").strip()), f"{role}.postalCode est obligatoire")
    require(bool((party.get("city") or "").strip()), f"{role}.city est obligatoire")
    require((party.get("countryCode") or "") == "FR", f"{role}.countryCode doit être FR")
    siren = only_digits(party.get("siren"))
    require(len(siren) == 9, f"{role}.siren doit contenir exactement 9 chiffres")
    vat_id = (party.get("vatId") or "").strip()
    if vat_required:
        require(vat_id.startswith("FR"), f"{role}.vatId doit commencer par FR")
        require(len(vat_id) >= 4, f"{role}.vatId semble incomplet")



def validate_lines(lines: list[dict[str, Any]]) -> None:
    require(bool(lines), "Au moins une ligne est obligatoire")
    for idx, line in enumerate(lines, start=1):
        require(bool((line.get("description") or "").strip()), f"lines[{idx}].description est obligatoire")
        require(q(line.get("quantity", 0)) > Decimal("0.00"), f"lines[{idx}].quantity doit être > 0")
        require(q(line.get("unitPrice", 0)) >= Decimal("0.00"), f"lines[{idx}].unitPrice doit être >= 0")
        require((line.get("unitCode") or "") in ALLOWED_UNIT_CODES, f"lines[{idx}].unitCode non supporté")



def validate_payload(data: dict[str, Any]) -> dict[str, Any]:
    require(bool((data.get("invoiceNumber") or "").strip()), "invoiceNumber est obligatoire")
    require(bool((data.get("invoiceDate") or "").strip()), "invoiceDate est obligatoire")
    require(bool((data.get("serviceDate") or "").strip()), "serviceDate est obligatoire")
    require((data.get("currency") or "EUR") == "EUR", "Seule la devise EUR est supportée")

    invoice_profile = data.get("invoiceProfile") or {}
    vat_profile = resolve_vat_profile(invoice_profile)

    validate_party(data.get("seller") or {}, "seller", vat_required=vat_profile["requires_seller_vat_id"])
    validate_party(data.get("buyer") or {}, "buyer", vat_required=False)
    validate_lines(data.get("lines") or [])

    payment_method_label(invoice_profile.get("paymentMethodCode"))
    payment_terms_label(invoice_profile.get("paymentTermsCode"))
    require(invoice_profile.get("latePenaltyProfile") in LATE_PENALTY_LABELS, "latePenaltyProfile non supporté")
    require(invoice_profile.get("collectionFeeProfile") in COLLECTION_FEE_LABELS, "collectionFeeProfile non supporté")
    require(invoice_profile.get("discountProfile") in DISCOUNT_LABELS, "discountProfile non supporté")

    if not vat_profile["requires_seller_vat_id"]:
        seller_vat = (data.get("seller") or {}).get("vatId")
        require(not seller_vat, "seller.vatId doit être vide pour le régime FR_293B")

    return vat_profile



def compute_totals(lines: list[dict[str, Any]], vat_rate: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = q(sum(q(line["quantity"]) * q(line["unitPrice"]) for line in lines))
    vat_total = q(sum(q(line["quantity"]) * q(line["unitPrice"]) * vat_rate / Decimal("100") for line in lines))
    total = q(subtotal + vat_total)
    return subtotal, vat_total, total



def indent(elem: Element, level: int = 0) -> None:
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



def add_text(parent: Element, tag: str, text: Any, attrib: dict[str, str] | None = None) -> Element:
    node = SubElement(parent, tag, attrib or {})
    node.text = "" if text is None else str(text)
    return node



def add_postal_address(parent: Element, ns_ram: str, party: dict[str, Any]) -> None:
    address = SubElement(parent, f"{{{ns_ram}}}PostalTradeAddress")
    add_text(address, f"{{{ns_ram}}}LineOne", party.get("addressLine1"))
    add_text(address, f"{{{ns_ram}}}PostcodeCode", party.get("postalCode"))
    add_text(address, f"{{{ns_ram}}}CityName", party.get("city"))
    add_text(address, f"{{{ns_ram}}}CountryID", party.get("countryCode", "FR"))



def add_siren(parent: Element, ns_ram: str, siren: str) -> None:
    legal_org = SubElement(parent, f"{{{ns_ram}}}SpecifiedLegalOrganization")
    add_text(legal_org, f"{{{ns_ram}}}ID", only_digits(siren), {"schemeID": "0002"})



def add_vat_registration(parent: Element, ns_ram: str, vat_id: str | None) -> None:
    if not vat_id:
        return
    tax_reg = SubElement(parent, f"{{{ns_ram}}}SpecifiedTaxRegistration")
    add_text(tax_reg, f"{{{ns_ram}}}ID", vat_id, {"schemeID": "VA"})



def build_cii_xml(data: dict[str, Any]) -> str:
    ns_rsm = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    ns_ram = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    ns_udt = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"

    register_namespace("rsm", ns_rsm)
    register_namespace("ram", ns_ram)
    register_namespace("udt", ns_udt)

    vat_profile = validate_payload(data)
    seller = data["seller"]
    buyer = data["buyer"]
    invoice_profile = data["invoiceProfile"]
    legal_notes = build_legal_notes(invoice_profile, vat_profile)
    subtotal, vat_total, total = compute_totals(data["lines"], vat_profile["vat_rate"])

    root = Element(f"{{{ns_rsm}}}CrossIndustryInvoice")

    context = SubElement(root, f"{{{ns_rsm}}}ExchangedDocumentContext")
    guideline = SubElement(context, f"{{{ns_ram}}}GuidelineSpecifiedDocumentContextParameter")
    add_text(guideline, f"{{{ns_ram}}}ID", "urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic")

    exchanged_doc = SubElement(root, f"{{{ns_rsm}}}ExchangedDocument")
    add_text(exchanged_doc, f"{{{ns_ram}}}ID", data["invoiceNumber"])
    add_text(exchanged_doc, f"{{{ns_ram}}}TypeCode", "380")
    issue_dt = SubElement(exchanged_doc, f"{{{ns_ram}}}IssueDateTime")
    add_text(issue_dt, f"{{{ns_udt}}}DateTimeString", parse_date_yyyymmdd(data["invoiceDate"]), {"format": "102"})
    note = SubElement(exchanged_doc, f"{{{ns_ram}}}IncludedNote")
    add_text(note, f"{{{ns_ram}}}Content", legal_notes)

    sctt = SubElement(root, f"{{{ns_rsm}}}SupplyChainTradeTransaction")

    for idx, line in enumerate(data["lines"], start=1):
        qty = q(line["quantity"])
        unit_price = q(line["unitPrice"])
        line_total = q(qty * unit_price)

        line_item = SubElement(sctt, f"{{{ns_ram}}}IncludedSupplyChainTradeLineItem")
        line_doc = SubElement(line_item, f"{{{ns_ram}}}AssociatedDocumentLineDocument")
        add_text(line_doc, f"{{{ns_ram}}}LineID", idx)

        product = SubElement(line_item, f"{{{ns_ram}}}SpecifiedTradeProduct")
        add_text(product, f"{{{ns_ram}}}Name", line["description"])

        agreement = SubElement(line_item, f"{{{ns_ram}}}SpecifiedLineTradeAgreement")
        gross = SubElement(agreement, f"{{{ns_ram}}}GrossPriceProductTradePrice")
        add_text(gross, f"{{{ns_ram}}}ChargeAmount", fmt_dec(unit_price))
        net = SubElement(agreement, f"{{{ns_ram}}}NetPriceProductTradePrice")
        add_text(net, f"{{{ns_ram}}}ChargeAmount", fmt_dec(unit_price))

        delivery = SubElement(line_item, f"{{{ns_ram}}}SpecifiedLineTradeDelivery")
        billed_qty = SubElement(delivery, f"{{{ns_ram}}}BilledQuantity", {"unitCode": line["unitCode"]})
        billed_qty.text = fmt_dec(qty)

        settlement = SubElement(line_item, f"{{{ns_ram}}}SpecifiedLineTradeSettlement")
        tax = SubElement(settlement, f"{{{ns_ram}}}ApplicableTradeTax")
        add_text(tax, f"{{{ns_ram}}}TypeCode", "VAT")
        add_text(tax, f"{{{ns_ram}}}CategoryCode", vat_profile["category_code"])
        add_text(tax, f"{{{ns_ram}}}RateApplicablePercent", fmt_dec(vat_profile["vat_rate"]))
        if vat_profile["exemption_reason"]:
            add_text(tax, f"{{{ns_ram}}}ExemptionReason", vat_profile["exemption_reason"])

        summation = SubElement(settlement, f"{{{ns_ram}}}SpecifiedTradeSettlementLineMonetarySummation")
        add_text(summation, f"{{{ns_ram}}}LineTotalAmount", fmt_dec(line_total))

    header_agreement = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeAgreement")
    seller_node = SubElement(header_agreement, f"{{{ns_ram}}}SellerTradeParty")
    add_text(seller_node, f"{{{ns_ram}}}Name", seller["name"])
    add_postal_address(seller_node, ns_ram, seller)
    add_siren(seller_node, ns_ram, seller["siren"])
    add_vat_registration(seller_node, ns_ram, seller.get("vatId"))

    buyer_node = SubElement(header_agreement, f"{{{ns_ram}}}BuyerTradeParty")
    add_text(buyer_node, f"{{{ns_ram}}}Name", buyer["name"])
    add_postal_address(buyer_node, ns_ram, buyer)
    add_siren(buyer_node, ns_ram, buyer["siren"])
    add_vat_registration(buyer_node, ns_ram, buyer.get("vatId"))

    header_delivery = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeDelivery")
    event = SubElement(header_delivery, f"{{{ns_ram}}}ActualDeliverySupplyChainEvent")
    occurrence = SubElement(event, f"{{{ns_ram}}}OccurrenceDateTime")
    add_text(occurrence, f"{{{ns_udt}}}DateTimeString", parse_date_yyyymmdd(data["serviceDate"]), {"format": "102"})

    header_settlement = SubElement(sctt, f"{{{ns_ram}}}ApplicableHeaderTradeSettlement")
    add_text(header_settlement, f"{{{ns_ram}}}InvoiceCurrencyCode", data.get("currency", "EUR"))
    tax = SubElement(header_settlement, f"{{{ns_ram}}}ApplicableTradeTax")
    add_text(tax, f"{{{ns_ram}}}CalculatedAmount", fmt_dec(vat_total))
    add_text(tax, f"{{{ns_ram}}}TypeCode", "VAT")
    add_text(tax, f"{{{ns_ram}}}BasisAmount", fmt_dec(subtotal))
    add_text(tax, f"{{{ns_ram}}}CategoryCode", vat_profile["category_code"])
    add_text(tax, f"{{{ns_ram}}}RateApplicablePercent", fmt_dec(vat_profile["vat_rate"]))
    if vat_profile["exemption_reason"]:
        add_text(tax, f"{{{ns_ram}}}ExemptionReason", vat_profile["exemption_reason"])

    payment_terms = SubElement(header_settlement, f"{{{ns_ram}}}SpecifiedTradePaymentTerms")
    add_text(payment_terms, f"{{{ns_ram}}}Description", payment_terms_label(invoice_profile["paymentTermsCode"]))

    monetary = SubElement(header_settlement, f"{{{ns_ram}}}SpecifiedTradeSettlementHeaderMonetarySummation")
    add_text(monetary, f"{{{ns_ram}}}LineTotalAmount", fmt_dec(subtotal))
    add_text(monetary, f"{{{ns_ram}}}TaxBasisTotalAmount", fmt_dec(subtotal))
    add_text(monetary, f"{{{ns_ram}}}TaxTotalAmount", fmt_dec(vat_total), {"currencyID": data.get("currency", "EUR")})
    add_text(monetary, f"{{{ns_ram}}}GrandTotalAmount", fmt_dec(total))
    add_text(monetary, f"{{{ns_ram}}}DuePayableAmount", fmt_dec(total))

    indent(root)
    return tostring(root, encoding="unicode")



def build_visual_pdf(data: dict[str, Any], pdf_path: Path) -> None:
    vat_profile = validate_payload(data)
    seller = data["seller"]
    buyer = data["buyer"]
    invoice_profile = data["invoiceProfile"]
    legal_notes = build_legal_notes(invoice_profile, vat_profile)
    payment_method = payment_method_label(invoice_profile["paymentMethodCode"])
    payment_terms = payment_terms_label(invoice_profile["paymentTermsCode"])
    subtotal, vat_total, total = compute_totals(data["lines"], vat_profile["vat_rate"])

    width, height = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    y = height - 50

    c.setTitle(data.get("invoiceNumber", "Facture"))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, y, "FACTURE")
    c.setFont("Helvetica", 10)
    c.drawString(40, y - 18, "Couche lisible du document Factur-X")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(360, y, f"Facture : {data['invoiceNumber']}")
    c.setFont("Helvetica", 10)
    c.drawString(360, y - 16, f"Date : {data['invoiceDate']}")
    c.drawString(360, y - 30, f"Prestation : {data['serviceDate']}")

    y -= 80
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Vendeur")
    c.drawString(300, y, "Client")
    c.setFont("Helvetica", 10)

    seller_vat_label = f"TVA : {seller['vatId']}" if seller.get("vatId") else "TVA non applicable, article 293 B du CGI"
    seller_lines = [
        seller["name"],
        seller["addressLine1"],
        f"{seller['postalCode']} {seller['city']}",
        f"SIREN : {seller['siren']}",
        seller_vat_label,
    ]
    buyer_lines = [
        buyer["name"],
        buyer["addressLine1"],
        f"{buyer['postalCode']} {buyer['city']}",
        f"SIREN : {buyer['siren']}",
    ]
    if buyer.get("vatId"):
        buyer_lines.append(f"TVA : {buyer['vatId']}")

    yy = y - 18
    for line in seller_lines:
        c.drawString(40, yy, line)
        yy -= 14

    yy = y - 18
    for line in buyer_lines:
        c.drawString(300, yy, line)
        yy -= 14

    y -= 110
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Description")
    c.drawString(355, y, "Qté")
    c.drawString(415, y, "PU HT")
    c.drawString(500, y, "Total HT")

    y -= 10
    c.line(40, y, 560, y)
    y -= 18
    c.setFont("Helvetica", 10)

    for line in data["lines"]:
        qty = q(line["quantity"])
        unit_price = q(line["unitPrice"])
        line_total = q(qty * unit_price)
        c.drawString(40, y, str(line["description"])[:48])
        c.drawRightString(390, y, fmt_dec(qty))
        c.drawRightString(470, y, fmt_dec(unit_price))
        c.drawRightString(550, y, fmt_dec(line_total))
        y -= 16

    y -= 8
    c.line(360, y, 560, y)
    y -= 18
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
    c.drawString(40, y, f"Paiement : {payment_method} | Conditions : {payment_terms}")
    y -= 18
    c.drawString(40, y, legal_notes[:110])

    c.save()



def generate_facturx_pdf(payload_dict: dict[str, Any]) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        visual_pdf = tmp_path / "invoice.pdf"
        output_pdf = tmp_path / "invoice-facturx.pdf"

        build_visual_pdf(payload_dict, visual_pdf)
        xml_content = build_cii_xml(payload_dict)
        logger.info("XML preview: %r", xml_content[:300])

        generate_from_file(
            str(visual_pdf),
            xml_content.encode("utf-8"),
            output_pdf_file=str(output_pdf),
        )

        return output_pdf.read_bytes(), output_pdf.name