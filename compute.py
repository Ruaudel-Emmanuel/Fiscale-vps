from __future__ import annotations

from typing import List

from app.models import InvoicePayload, InvoiceTotals, ComputedLine


def round2(value: float) -> float:
    """
    Arrondi à 2 décimales avec un petit epsilon
    pour éviter les artefacts.
    """
    return round(value + 1e-9, 2)


def compute_invoice(payload: InvoicePayload) \
        -> tuple[InvoiceTotals, List[ComputedLine]]:
    """
    Calcule les montants par ligne et les totaux de facture à partir du brut.

    - applique la remise par ligne
    - calcule net HT, TVA, TTC par ligne
    - agrège HT, remises, TVA, TTC
    """
    computed_lines: List[ComputedLine] = []
    total_ht = 0.0
    total_discount = 0.0
    total_tva = 0.0

    for line in payload.lines:
        gross = line.quantity * line.unit_price_ht
        discount = gross * (line.discount_rate / 100.0)
        net = gross - discount
        tva_amount = net * (line.tva_rate / 100.0)
        ttc = net + tva_amount

        computed_line = ComputedLine(
            line_number=line.line_number,
            description=line.description,
            quantity=line.quantity,
            unit=line.unit,
            unit_price_ht=round2(line.unit_price_ht),
            discount_rate=round2(line.discount_rate),
            tva_rate=round2(line.tva_rate),
            line_gross_ht=round2(gross),
            line_discount=round2(discount),
            line_net_ht=round2(net),
            line_tva=round2(tva_amount),
            line_ttc=round2(ttc),
        )
        computed_lines.append(computed_line)

        total_ht += net
        total_discount += discount
        total_tva += tva_amount

    totals = InvoiceTotals(
        total_ht=round2(total_ht),
        total_discount=round2(total_discount),
        total_tva=round2(total_tva),
        total_ttc=round2(total_ht + total_tva),
    )

    return totals, computed_lines