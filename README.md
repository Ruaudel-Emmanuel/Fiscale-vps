# Factur-X Generator V3

This package provides a practical V3 architecture for generating a **real Factur-X invoice**: a human-readable PDF combined with an embedded XML file inside a **PDF/A-3** container.[web:227][web:166]

## What is included

- `facturx-generator-v3.html`: frontend page that captures invoice data and exports a JSON payload.
- `facturx_builder.py`: Python backend script that turns the payload into:
  - a readable invoice PDF,
  - an XML invoice file,
  - and a final Factur-X PDF with embedded XML.[web:216][web:415]

## Why a backend is required

A true Factur-X invoice is not just a PDF plus a downloadable XML file. It must be a **PDF/A-3 file** with an XML invoice embedded inside the PDF and appropriate metadata.[web:227][web:414][web:166]

That level of compliance is better handled on the server side with dedicated libraries and validation tools than with browser-only JavaScript.[web:216][web:220]

## Python dependencies

Install the required packages:

```bash
pip install factur-x reportlab
```

The `factur-x` library is designed to generate Factur-X invoices from a regular PDF and a compliant XML invoice file.[web:216]

## Usage

1. Open the HTML page.
2. Fill in the invoice fields.
3. Export the payload as `payload.json`.
4. Run the backend command:

```bash
python facturx_builder.py payload.json output.pdf
```

The script creates a visual PDF, builds the XML file, then embeds the XML in the final PDF/A-3 Factur-X output.[web:415][web:216]

## Important limitation

This package demonstrates the correct **technical direction**, but the sample XML generated here is still simplified. For production use, the XML must fully match the selected Factur-X profile and the applicable EN 16931 business rules.[web:227][web:166]

## Validation before production

Before using generated invoices in production, validate:

- the PDF/A-3 compliance with **veraPDF**,[web:418][web:216]
- the embedded XML and business rules with a **Factur-X / EN 16931 validator**.[web:204][web:227]

## Practical note

The `factur-x` library can generate a compliant Factur-X file when the source PDF is PDF/A compatible and the XML is compliant with the expected profile.[web:216]
