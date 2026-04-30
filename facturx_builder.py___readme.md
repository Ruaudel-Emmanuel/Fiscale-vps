<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Très bien, fais-moi une version en anglais s'il te plaît.

Here is the same document in **English (Markdown)**, focused on *why* and *how* each version evolved, and which libraries were used.[^1][^2]

***

# History and Technical Choices of `facturx_builder`

This document explains the evolution of the scripts:

- `facturx_builder.py`
- `facturx_builder_v31.py`
- `facturx_builder_v32.py`
- `facturx_builder_v33.py`

and details **which Python libraries are used, why they were chosen, and what changed** between the different versions, from the first attempt up to a fully valid Factur‑X PDF.[^3][^1]

***

## 1. Global goal of the project

The goal is to start from an HTML form that exports a `payload.json`, and on the Python backend:

1. Build a **human‑readable PDF invoice**.
2. Generate a **Factur‑X XML** that matches the chosen profile (here BASIC, based on EN16931 + CII).[^4][^3]
3. Package everything into a **PDF/A‑3 with embedded XML**, validated both by XSD and Schematron according to the Factur‑X standard.[^5][^1]

Key libraries:

- **`reportlab`**: generates the human‑readable PDF (visual layer).[^6][^7]
- **`factur-x`** (Akretion’s library, PyPI): creates a Factur‑X PDF from a visual PDF and a compliant CII XML, including official XSD and Schematron validation.[^2][^8][^1]
- **`decimal`**: handles monetary values (cent‑level rounding), which is critical in invoicing.[^2]
- **`xml.etree.ElementTree`** (from V3.1 onward): constructs a structured CII XML instead of a home‑made, non‑standard XML.[^9][^3]

***

## 2. Initial version: `facturx_builder.py` (V3.0)

### 2.1 Purpose of V3.0

This first version aimed to:

- Load `payload.json`.
- Generate a **visual PDF**.
- Generate a **simplified XML** invoice (not CII).
- Call the `factur-x` library to produce a Factur‑X PDF.[^8][^1]


### 2.2 Libraries used

- `json` and `pathlib.Path`: load/store `payload.json` and manage file paths for PDFs and XML.[^2]
- `decimal.Decimal`: compute monetary amounts (net, VAT, gross) with correct rounding.[^2]
- `reportlab`: build the visual PDF in `build_visual_pdf()`.[^7][^6]
- `facturx.generate_from_file`: attempt to generate a Factur‑X PDF from the PDF and XML.[^1][^8]


### 2.3 Limitations of V3.0

```
- The XML structure was custom, with a root `<Invoice>...</Invoice>` and generic tags (`<Header>`, `<Seller>`, etc.).  
```

- The `factur-x` validator expects a **CII XML** with root `rsm:CrossIndustryInvoice` and official namespaces (`rsm`, `ram`, `udt`).[^3][^9]
- Result: XSD validation failed, and no valid Factur‑X PDF could be created.

***

## 3. V3.1: `facturx_builder_v31.py` — switching to CII XML

### 3.1 Goal

Fix the core problem by producing a **CII (CrossIndustryInvoice)** XML as expected by the Factur‑X standard instead of a custom `<Invoice>` format.[^9][^3]

### 3.2 Libraries used

In addition to V3.0:

- `xml.etree.ElementTree`: build a structured CII XML with elements, attributes, and namespaces.[^3][^9]

Still used:

- `decimal`: for monetary values (`q()`, `compute_totals()`).
- `reportlab`: for the human‑readable PDF.
- `factur-x`: for Factur‑X generation and XSD/Schematron validation.[^8][^1]


### 3.3 Concrete changes

1. **CII root element**:

```xml
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
```

This aligns the XML with UN/CEFACT and Factur‑X expectations.[^9][^3]
2. **Main sections**:
    - `ExchangedDocumentContext` (with `GuidelineSpecifiedDocumentContextParameter`).[^9]
    - `ExchangedDocument` (invoice number, type code `380`, issue date).[^3]
    - `SupplyChainTradeTransaction`, including:
        - `IncludedSupplyChainTradeLineItem` for each invoice line.
        - `ApplicableHeaderTradeAgreement` (seller/buyer).
        - `ApplicableHeaderTradeDelivery` (service/delivery date).
        - `ApplicableHeaderTradeSettlement` (tax, monetary totals, payment terms).[^3][^9]
3. **Profile level**:
    - First attempt with `ram:ID = "urn:factur-x.eu:1p0:basic"` in `GuidelineSpecifiedDocumentContextParameter`.[^9]

### 3.4 Result

- **XSD**: passes (XML structure is syntactically valid).
- **Schematron**: still fails, mainly because:
    - the profile URN (`ram:ID`) is incomplete for BASIC,
    - some header settlement elements are missing or appear in the wrong order.[^10][^5]

***

## 4. V3.2: `facturx_builder_v32.py` — XSD‑compliant settlement section

### 4.1 Goal

Fix remaining XSD errors, especially in the `ApplicableHeaderTradeSettlement` section.[^11][^3]

### 4.2 Libraries

No new libraries, but the order/structure of some elements is adjusted:

- Still using `decimal`, `reportlab`, `xml.etree.ElementTree`, `factur-x`.[^1][^3][^9]


### 4.3 Key changes

1. **Remove/reorder `SpecifiedTradeSettlementPaymentMeans`**:
    - The XSD error pointed out that `ram:SpecifiedTradeSettlementPaymentMeans` appeared at a position where it was not allowed and that at this point the schema expected one of:
        - `ApplicableTradeTax`,
        - `BillingSpecifiedPeriod`,
        - `SpecifiedTradeAllowanceCharge`,
        - `SpecifiedTradePaymentTerms`,
        - `SpecifiedTradeSettlementHeaderMonetarySummation`.[^11][^3]
    - The implementation was simplified to keep:
        - `ApplicableTradeTax`,
        - `SpecifiedTradePaymentTerms`,
        - `SpecifiedTradeSettlementHeaderMonetarySummation`.
2. **Order adapted to the schema**:
    - `ApplicableTradeTax`
    - `SpecifiedTradePaymentTerms`
    - `SpecifiedTradeSettlementHeaderMonetarySummation`[^3][^9]

### 4.4 Result

- **XSD**: OK.
- **Schematron**: still one error on `GuidelineSpecifiedDocumentContextParameter/ram:ID` (profile URN not allowed).[^5][^10]

***

## 5. V3.3: `facturx_builder_v33.py` — correct BASIC URN, fully valid Factur‑X

### 5.1 Goal

Fix the Schematron error on the profile ID in `GuidelineSpecifiedDocumentContextParameter/ram:ID` by using the **official BASIC URN**.[^12][^10]

### 5.2 Libraries

Same as V3.2:

- `decimal`: monetary computations.
- `reportlab`: visual PDF layer.
- `xml.etree.ElementTree`: structured CII XML.
- `factur-x`: Factur‑X generation + XSD + Schematron validation.[^5][^8][^1]


### 5.3 Key change

In `build_cii_xml(data)`, the line:

```python
add_text(guideline, f'{NS_RAM}ID', 'urn:factur-x.eu:1p0:basic')
```

is replaced by:

```python
add_text(
    guideline,
    f'{NS_RAM}ID',
    'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic'
)
```

This URN is the official identifier for the **BASIC** profile in Factur‑X, combining EN16931 compliance and the Factur‑X version.[^10][^12]

### 5.4 Result

- **XSD validation**: OK.
- **Schematron validation**: OK.
- `factur-x` successfully:
    - validates the XML against XSD and Schematron,
    - embeds `factur-x.xml` into the PDF,
    - generates `output/facture-facturx.pdf` as a valid Factur‑X PDF/A‑3.[^1][^5]

***

## 6. Version and library summary

| Version | File | Key libraries used | Main role |
| :-- | :-- | :-- | :-- |
| V3.0 | `facturx_builder.py` | `decimal`, `reportlab`, `factur-x`, `json`, `pathlib` | Generate a visual PDF + a home‑made XML, attempt Factur‑X generation (fails XSD). |
| V3.1 | `facturx_builder_v31.py` | `decimal`, `reportlab`, `factur-x`, `xml.etree`, `json` | Switch to CII XML (`CrossIndustryInvoice`), XSD OK, Schematron still failing. |
| V3.2 | `facturx_builder_v32.py` | same as V3.1 | Fix header settlement structure/order to satisfy XSD expectations. |
| V3.3 | `facturx_builder_v33.py` | same as V3.2 | Use official BASIC profile URN; Schematron OK; fully valid Factur‑X PDF generated. |


***

## 7. Why these libraries (and not others)?

- **`reportlab`**
    - Generates PDFs directly from Python without external tools.[^6][^7]
    - Widely used for invoices, reports, and structured documents.
- **`factur-x` (Akretion)**
    - Dedicated library for Factur‑X in France, built on EN16931/ZUGFeRD/CII.[^13][^1]
    - Handles PDF/A‑3 container generation, XML embedding, and official XSD and Schematron validation.[^5][^1]
- **`decimal`**
    - Avoids floating‑point rounding issues that are unacceptable in invoicing.[^2]
    - Ensures cent‑level accuracy for net, VAT and gross amounts.
- **`xml.etree.ElementTree`**
    - Simple and standard way to build CII XML programmatically.[^9][^3]
    - Lets the `factur-x` library validate this XML against the official Factur‑X schema.

***

If you want, I can now turn this into a **README.md** tailored specifically to your `Fiscale‑vps` GitHub repo (with sections like Installation, Usage, Architecture, and Limitations), so you can drop it in the root of the project as‑is.

<div align="center">⁂</div>

[^1]: https://github.com/akretion/factur-x

[^2]: https://github.com/akretion/factur-x/blob/master/README.rst

[^3]: https://facturxapi.com/blog/python-facturx-generer-valider-xml-en16931

[^4]: https://fnfe-mpe.org/factur-x/factur-x_en/

[^5]: https://facturxapi.com/blog/valider-en16931-facturx-schematron-br

[^6]: https://docs.reportlab.com/install/ReportLab_Plus_version_installation/

[^7]: https://docs.reportlab.com/install/open_source_installation/

[^8]: https://pypi.org/project/factur-x/

[^9]: https://4gl.fr/HELP/xml-file.htm

[^10]: https://facturxapi.com/blog/erreur-profil-facturx-guideline-id-incorrect

[^11]: https://github.com/akretion/factur-x/blob/master/facturx/facturx.py

[^12]: https://www.facturwise.com/en/blog/facturx-zugferd-compliant-invoice-guide

[^13]: https://www.akretion.com/fr/blog/akretion-publishes-an-opensource-factur-x-python-library

