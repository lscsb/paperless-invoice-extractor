"""ZUGFeRD/Factur-X (CII) and UBL invoice parser."""

from dataclasses import dataclass
from typing import Optional

import defusedxml.ElementTree as ET


# CII namespaces
NS_RSM = 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100'
NS_RAM = 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100'
NS_UDT = 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100'

# UBL namespaces
NS_UBL_INV = 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'
NS_UBL_CN = 'urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2'
NS_CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
NS_CAC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'


@dataclass
class InvoiceData:
    invoice_number: Optional[str]
    invoice_date: Optional[str]    # YYYY-MM-DD
    due_date: Optional[str]        # YYYY-MM-DD
    amount: Optional[str]          # original string from XML
    currency: Optional[str]
    seller_name: Optional[str]
    iban: Optional[str]
    bic: Optional[str]
    payment_reference: Optional[str]
    is_credit_note: bool
    source_format: str             # 'CII' or 'UBL'


def _cii_text(root, path_parts: list[str], ns: dict) -> Optional[str]:
    """Navigate a CII path and return .text, or None."""
    node = root
    for part in path_parts:
        node = node.find(part, ns)
        if node is None:
            return None
    return node.text.strip() if node.text else None


def _parse_cii_date(raw: Optional[str]) -> Optional[str]:
    """Convert YYYYMMDD to YYYY-MM-DD."""
    if raw and len(raw) == 8:
        return f'{raw[:4]}-{raw[4:6]}-{raw[6:]}'
    return None


def _parse_cii(root) -> Optional[InvoiceData]:
    """Parse CII (CrossIndustryInvoice) root element."""
    cii_tag = f'{{{NS_RSM}}}CrossIndustryInvoice'
    if root.tag != cii_tag:
        return None

    ns = {'rsm': NS_RSM, 'ram': NS_RAM, 'udt': NS_UDT}

    def find(path):
        return root.find(path, ns)

    def text(path):
        node = find(path)
        return node.text.strip() if node is not None and node.text else None

    invoice_number = text('rsm:ExchangedDocument/ram:ID')

    # Date with format='102' attribute
    date_node = root.find(
        'rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString[@format="102"]', ns
    )
    if date_node is None:
        date_node = root.find(
            'rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString', ns
        )
    invoice_date = _parse_cii_date(date_node.text.strip() if date_node is not None and date_node.text else None)

    due_date_node = root.find(
        'rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement'
        '/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime'
        '/udt:DateTimeString[@format="102"]', ns
    )
    if due_date_node is None:
        due_date_node = root.find(
            'rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement'
            '/ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime'
            '/udt:DateTimeString', ns
        )
    due_date = _parse_cii_date(due_date_node.text.strip() if due_date_node is not None and due_date_node.text else None)

    settlement = 'rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement'

    amount = text(f'{settlement}/ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:DuePayableAmount')
    currency = text(f'{settlement}/ram:InvoiceCurrencyCode')

    seller_name = text(
        'rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeAgreement'
        '/ram:SellerTradeParty/ram:Name'
    )

    payment_means = f'{settlement}/ram:SpecifiedTradeSettlementPaymentMeans'
    iban = text(f'{payment_means}/ram:PayeePartyCreditorFinancialAccount/ram:IBANID')
    bic = text(f'{payment_means}/ram:PayeeSpecifiedCreditorFinancialInstitution/ram:BICID')
    payment_reference = text(f'{settlement}/ram:PaymentReference')

    type_code = text('rsm:ExchangedDocument/ram:TypeCode')
    is_credit_note = type_code == '381'

    return InvoiceData(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        amount=amount,
        currency=currency,
        seller_name=seller_name,
        iban=iban,
        bic=bic,
        payment_reference=payment_reference,
        is_credit_note=is_credit_note,
        source_format='CII',
    )


def _parse_ubl(root) -> Optional[InvoiceData]:
    """Parse UBL Invoice or CreditNote root element."""
    is_credit_note = root.tag == f'{{{NS_UBL_CN}}}CreditNote'
    if root.tag not in (f'{{{NS_UBL_INV}}}Invoice', f'{{{NS_UBL_CN}}}CreditNote'):
        return None

    ns = {'cbc': NS_CBC, 'cac': NS_CAC}

    def text(path):
        node = root.find(path, ns)
        return node.text.strip() if node is not None and node.text else None

    invoice_number = text('cbc:ID')
    invoice_date = text('cbc:IssueDate')
    due_date = text('cbc:DueDate')
    amount = text('cac:LegalMonetaryTotal/cbc:PayableAmount')
    currency = text('cbc:DocumentCurrencyCode')

    seller_name = text(
        'cac:AccountingSupplierParty/cac:Party/cac:PartyLegalEntity/cbc:RegistrationName'
    ) or text(
        'cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name'
    )

    iban = text('cac:PaymentMeans/cac:PayeeFinancialAccount/cbc:ID')
    bic = text(
        'cac:PaymentMeans/cac:PayeeFinancialAccount'
        '/cac:FinancialInstitutionBranch/cbc:ID'
    )
    payment_reference = text('cac:PaymentMeans/cbc:PaymentID')

    return InvoiceData(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        due_date=due_date,
        amount=amount,
        currency=currency,
        seller_name=seller_name,
        iban=iban,
        bic=bic,
        payment_reference=payment_reference,
        is_credit_note=is_credit_note,
        source_format='UBL',
    )


def parse_xml(xml_bytes: bytes) -> Optional[InvoiceData]:
    """Try CII then UBL. Return None if neither matches."""
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except Exception:
        return None

    result = _parse_cii(root)
    if result is not None:
        return result

    return _parse_ubl(root)
