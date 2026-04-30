<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# [facturx_builder.py](https://github.com/Ruaudel-Emmanuel/Fiscale-vps/blob/main/facturx_builder.py)

[facturx_builder_v31.py](https://github.com/Ruaudel-Emmanuel/Fiscale-vps/blob/main/facturx_builder_v31.py)
[facturx_builder_v32.py](https://github.com/Ruaudel-Emmanuel/Fiscale-vps/blob/main/facturx_builder_v31.py)
[facturx_builder_v33.py](https://github.com/Ruaudel-Emmanuel/Fiscale-vps/blob/main/facturx_builder_v31.py)

Fais-moi un document markdown. Qui explique pourquoi À quelle en montrant bien quelle bibliothèque ont été utilisées, pourquoi elles ont été utilisées dans toutes les versions de Factories builder ? En passant par la 31, la 32 et la 33.

Voici un document **Markdown** qui raconte l’évolution de ton `facturx_builder` et les bibliothèques utilisées à chaque étape. Je m’appuie sur la structure des versions que nous avons construites ensemble (V3.0/V3.1/V3.2/V3.3) et sur le fonctionnement documenté de la librairie `factur-x`.[^1][^2]

***

# Historique et choix techniques de `facturx_builder`

Ce document décrit l’évolution des scripts :

- `facturx_builder.py`
- `facturx_builder_v31.py`
- `facturx_builder_v32.py`
- `facturx_builder_v33.py`

pour générer un **PDF Factur‑X** à partir d’un `payload.json` (issu de ton front HTML) et explique quelles bibliothèques Python sont utilisées, **pourquoi** elles sont là, et **ce qui change** d’une version à l’autre.[^3][^1]

***

## 1. Objectif global du projet

L’objectif est de partir d’un formulaire HTML qui génère un `payload.json`, puis côté backend Python :

1. Construire un **PDF lisible** (couche humaine).
2. Générer un **XML Factur‑X** conforme au profil visé (ici BASIC, basé sur EN16931 et CII).[^4][^3]
3. Emballer le tout dans un **PDF/A‑3 avec XML embarqué**, validé XSD + Schematron (Factur‑X officiel).[^5][^1]

Les bibliothèques clés :

- **`reportlab`** : pour générer le PDF « lisible » (mise en page texte).[^6][^7]
- **`factur-x`** (librairie Akretion, PyPI) : pour créer un PDF Factur‑X à partir d’un PDF existant et d’un XML CII conforme, avec validation XSD/Schematron.[^2][^8][^1]
- **`decimal`** : pour gérer les montants (arrondis au centime), indispensable en facturation.[^2]
- **`xml.etree.ElementTree`** (V3.1+) : pour construire un XML CII structuré, au lieu d’un simple XML « maison ».[^9][^3]

***

## 2. Version initiale : `facturx_builder.py` (V3.0)

### 2.1. But de la V3.0

Première version « fonctionnelle » : générer un PDF lisible et un XML **simplifié** à partir du `payload.json`, puis appeler la librairie `factur-x` pour fabriquer un PDF Factur‑X.[^8][^1]

### 2.2. Bibliothèques utilisées

- `json` et `pathlib.Path` : chargement de `payload.json` et gestion des chemins de fichiers (PDF/ XML).[^2]
- `decimal.Decimal` : calculs de montants (HT, TVA, TTC) avec arrondi correct.[^2]
- `reportlab` : création du PDF lisible (`build_visual_pdf`).[^7][^6]
- `facturx.generate_from_file` : tentative de génération du Factur‑X à partir du PDF et du XML.[^1][^8]


### 2.3. Limites de la V3.0

```
- Le XML était un format libre avec une racine `<Invoice>...</Invoice>` et des balises génériques (`<Header>`, `<Seller>`, etc.).  
```

- Le validateur XSD de `factur-x` attend un XML **CII** avec racine `rsm:CrossIndustryInvoice` et les namespaces officiels (`rsm`, `ram`, `udt`).[^3][^9]
- Résultat : échec de validation XSD et impossibilité de générer un Factur‑X conforme.

***

## 3. V3.1 : `facturx_builder_v31.py` — passage au XML CII

### 3.1. Objectif

Corriger le cœur du problème : produire un XML **CII (CrossIndustryInvoice)** conforme aux attentes de Factur‑X, au lieu d’un XML « maison ».[^9][^3]

### 3.2. Bibliothèques utilisées

En plus de celles de V3.0 :

- `xml.etree.ElementTree` : construction structurée du XML CII (balises, namespaces).[^3][^9]

Toujours présentes :

- `decimal` : pour les montants (`q()`, `compute_totals()`).
- `reportlab` : pour le PDF lisible.
- `factur-x` : pour la génération Factur‑X + validation XSD/Schematron.[^8][^1]


### 3.3. Ce qui change concrètement

1. **Racine CII** :

```xml
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
```

Ceci aligne la structure sur les normes UN/CEFACT utilisées par Factur‑X.[^9][^3]
2. **Sections principales** :
    - `ExchangedDocumentContext` (avec `GuidelineSpecifiedDocumentContextParameter`).[^9]
    - `ExchangedDocument` (numéro de facture, date, type 380).[^3]
    - `SupplyChainTradeTransaction` avec :
        - `IncludedSupplyChainTradeLineItem` pour chaque ligne,
        - `ApplicableHeaderTradeAgreement` (Vendeur/Client),
        - `ApplicableHeaderTradeDelivery` (date de prestation),
        - `ApplicableHeaderTradeSettlement` (TVA, monétaire, etc.).[^3][^9]
3. **Niveau de profil** :
    - Première tentative avec `ram:ID = "urn:factur-x.eu:1p0:basic"` dans `GuidelineSpecifiedDocumentContextParameter`.[^9]

### 3.4. Résultat

- **XSD** : OK (structure XML valide).
- **Schematron** : erreurs, notamment sur la valeur de `ram:ID` et l’ordre/présence de certaines balises dans `ApplicableHeaderTradeSettlement`.[^10][^5]

***

## 4. V3.2 : `facturx_builder_v32.py` — ajustement au schéma XSD

### 4.1. Objectif

Corriger les erreurs XSD résiduelles, en particulier l’ordre et la présence des éléments dans `ApplicableHeaderTradeSettlement`.[^11][^3]

### 4.2. Bibliothèques

Aucune nouvelle bibliothèque, mais un **ajustement de l’ordre des balises** :

- Toujours `decimal`, `reportlab`, `xml.etree.ElementTree`, `factur-x`.[^1][^3][^9]


### 4.3. Modifications majeures

1. **Suppression / déplacement de `SpecifiedTradeSettlementPaymentMeans`** :
    - Le XSD signalait que `ram:SpecifiedTradeSettlementPaymentMeans` n’était pas attendu à l’endroit où il apparaissait, et qu’il attendait plutôt :
        - `ApplicableTradeTax`,
        - `BillingSpecifiedPeriod`,
        - `SpecifiedTradeAllowanceCharge`,
        - `SpecifiedTradePaymentTerms`,
        - `SpecifiedTradeSettlementHeaderMonetarySummation`.[^11][^3]
    - Solution : simplifier et conserver seulement :
        - `ApplicableTradeTax`,
        - `SpecifiedTradePaymentTerms`,
        - `SpecifiedTradeSettlementHeaderMonetarySummation`.
2. **Ordre conforme** :
    - `ApplicableTradeTax`,
    - `SpecifiedTradePaymentTerms`,
    - `SpecifiedTradeSettlementHeaderMonetarySummation`.[^3][^9]

### 4.4. Résultat

- **XSD** : OK.
- **Schematron** : toujours une erreur sur la valeur de `GuidelineSpecifiedDocumentContextParameter/ram:ID` (profil BASIC mal déclaré).[^5][^10]

***

## 5. V3.3 : `facturx_builder_v33.py` — URN BASIC correcte, validation complète

### 5.1. Objectif

Résoudre l’erreur Schematron sur `ram:ID` en mettant l’URN officielle du profil BASIC.[^12][^10]

### 5.2. Bibliothèques

Toujours les mêmes :

- `decimal` : montants, arrondis au centime.
- `reportlab` : PDF lisible (couche humaine).
- `xml.etree.ElementTree` : XML CII structuré.
- `factur-x` : génération du PDF Factur‑X + validation XSD et Schematron.[^5][^8][^1]


### 5.3. Changement clé

Dans `build_cii_xml(data)`, on passe de :

```python
add_text(guideline, f'{NS_RAM}ID', 'urn:factur-x.eu:1p0:basic')
```

à :

```python
add_text(
    guideline,
    f'{NS_RAM}ID',
    'urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic'
)
```

Cette URN complète est celle attendue pour un profil **BASIC** conforme EN16931, d’après la documentation et les retours de validateurs Factur‑X.[^10][^12]

### 5.4. Résultat

- **Validation XSD** : OK.
- **Validation Schematron** : OK.
- **Génération PDF Factur‑X** par `factur-x` :
    - ajout de `factur-x.xml` dans le PDF,
    - sortie `output/facture-facturx.pdf`,
    - messages de log confirmant la génération.[^1][^5]

***

## 6. Récapitulatif par version et bibliothèques

| Version | Fichier | Bibliothèques clés | Rôle principal |
| :-- | :-- | :-- | :-- |
| V3.0 | `facturx_builder.py` | `decimal`, `reportlab`, `factur-x`, `json`, `pathlib` | Générer PDF lisible + XML simplifié “maison”, tentative Factur‑X mais XML non CII. |
| V3.1 | `facturx_builder_v31.py` | `decimal`, `reportlab`, `factur-x`, `xml.etree`, `json` | Passage au XML CII (`CrossIndustryInvoice`) avec namespaces, XSD OK, Schematron encore KO. |
| V3.2 | `facturx_builder_v32.py` | idem V3.1 | Réorganisation / simplification de `ApplicableHeaderTradeSettlement` pour respecter le XSD. |
| V3.3 | `facturx_builder_v33.py` | idem V3.2 | URN BASIC correcte dans `ram:ID`, Schematron OK, Factur‑X PDF généré et conforme. |


***

## 7. Pourquoi ces bibliothèques (et pas d’autres) ?

- **`reportlab`** :
    - permet de générer un PDF lisible en pure Python, sans dépendre d’un moteur externe ;[^6][^7]
    - largement utilisé pour la génération de PDF professionnels (factures, rapports).
- **`factur-x` (Akretion)** :
    - bibliothèque spécialisée dans Factur‑X pour la France, basée sur EN16931, ZUGFeRD, CII ;[^13][^1]
    - encapsule la logique PDF/A‑3 + XML embarqué + validations XSD \& Schematron officielles.[^5][^1]
- **`decimal`** :
    - la facturation ne supporte pas les erreurs de flottant ; `Decimal` garantit les arrondis au centime.[^2]
- **`xml.etree.ElementTree`** :
    - suffisante pour construire un XML CII propre sans dépendance externe ;[^9][^3]
    - la lib `factur-x` se charge ensuite de vérifier que ce XML respecte le schéma officiel.

***

Si tu veux, je peux maintenant t’écrire un **README.md “projet complet”** pour ton repo `Fiscale-vps`, en reprenant ce contenu mais orienté “utilisateur final” / “autres devs” (avec sections Installation, Usage, Architecture, Limitations).
<span style="display:none">[^14]</span>

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

[^14]: https://www.linkedin.com/in/emmanuel-ruaudel-bb5059362

