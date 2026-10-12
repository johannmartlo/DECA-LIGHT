from __future__ import annotations

from src.application.dtos.document_dto import RawDocumentDTO
from src.domain.enums import DocumentFormatType, FieldExtractionStatus
from src.infrastructure.parsers.carta_de_porte_parser import CartaDePorteParser
from src.infrastructure.parsers.cmr_parser import CMRParser
from src.infrastructure.parsers.composite_parser import CompositeDocumentParser


def test_carta_de_porte_parser_success() -> None:
    sample_text = """
    TOMATES DE AUTOR S.L.
    ALBARÁN DE CARGA / CARTA DE PORTE NACIONAL
    Albarán Nº: EXP-2026-00452
    Fecha Transporte: 03/10/2026
    Cargador Contractual: Tomates de Autor S.L.
    NIF Cargador: B04123456
    Domicilio Cargador: Pol. Ind. La Redonda, Calle 5, El Ejido (Almería)
    Transportista Efectivo: Transportes Frigoríficos García S.L.
    NIF Transportista: B18998877
    Origen: El Ejido (Almería)
    Destino: Mercamadrid, Nave 4 (Madrid)
    Mercancía: Tomate Rama Calibre M
    Peso Total: 18.450,50 kg
    Observaciones: Mantener a 10 grados centígrados
    """

    raw_doc = RawDocumentDTO(
        content_bytes=b"%PDF-sample",
        filename="carta_porte_452.pdf",
        sha256_hash="hash-1",
        extracted_text=sample_text,
    )

    parser = CartaDePorteParser()
    can_handle, confidence = parser.can_parse(raw_doc)
    assert can_handle is True
    assert confidence >= 0.7

    norm = parser.parse(raw_doc)
    assert norm.format_type == DocumentFormatType.CARTA_DE_PORTE
    assert norm.reference.status == FieldExtractionStatus.EXTRAIDO
    assert norm.reference.value == "EXP-2026-00452"
    assert norm.transport_date.status == FieldExtractionStatus.EXTRAIDO
    assert str(norm.transport_date.value) == "2026-10-03"
    assert norm.shipper_name.status == FieldExtractionStatus.EXTRAIDO
    assert "Tomates de Autor" in str(norm.shipper_name.value)
    assert norm.carrier_name.status == FieldExtractionStatus.EXTRAIDO
    assert "García" in str(norm.carrier_name.value)
    assert norm.weight_kg.status == FieldExtractionStatus.EXTRAIDO
    assert norm.weight_kg.value == 18450.50
    assert norm.origin.status == FieldExtractionStatus.EXTRAIDO
    assert norm.destination.status == FieldExtractionStatus.EXTRAIDO
    assert norm.tractor_plate.status == FieldExtractionStatus.NO_PRESENTE
    assert norm.is_complete_and_confident() is True


def test_cmr_parser_success() -> None:
    sample_text = """
    CMR - INTERNATIONAL CONSIGNMENT NOTE
    CONTRAT DE TRANSPORT INTERNATIONAL DE MARCHANDISES PAR ROUTE
    CMR Nº: CMR-EU-88912
    Date: 03/10/2026
    1 Expéditeur / Sender: Tomates de Autor S.L.
    VAT: ESB04123456
    Address: El Ejido, Almeria, Spain
    2 Destinataire / Consignee: Rungis Primeurs SAS
    Place of delivery: Paris, France
    4 Place of taking over: El Ejido, Almeria
    16 Transporteur / Carrier: Trans-Europe Express BV
    VAT: NL123456789B01
    6 Nature of the goods: Fresh Tomatoes on the vine
    11 Gross weight: 21.300 kg
    18 Observations: Temperature controlled +12C
    """

    raw_doc = RawDocumentDTO(
        content_bytes=b"%PDF-cmr",
        filename="cmr_88912.pdf",
        sha256_hash="hash-2",
        extracted_text=sample_text,
    )

    parser = CMRParser()
    can_handle, confidence = parser.can_parse(raw_doc)
    assert can_handle is True
    assert confidence >= 0.7

    norm = parser.parse(raw_doc)
    assert norm.format_type == DocumentFormatType.CMR
    assert norm.reference.value == "CMR-EU-88912"
    assert norm.carrier_name.value == "Trans-Europe Express BV"
    assert norm.consignee.value == "Rungis Primeurs SAS"
    assert norm.destination.value == "Paris, France"
    assert norm.is_complete_and_confident() is True


def test_composite_parser_auto_detection() -> None:
    composite = CompositeDocumentParser()

    # Documento 1: Carta de Porte
    raw_cp = RawDocumentDTO(
        content_bytes=b"1",
        filename="albaran.pdf",
        sha256_hash="h1",
        extracted_text=(
            "CARTA DE PORTE NACIONAL HISPATEC Albarán Nº: 1234 Cargador: Autor Peso: 1000 kg"
        ),
    )
    norm_cp = composite.parse(raw_cp)
    assert norm_cp.format_type == DocumentFormatType.CARTA_DE_PORTE

    # Documento 2: CMR
    raw_cmr = RawDocumentDTO(
        content_bytes=b"2",
        filename="cmr.pdf",
        sha256_hash="h2",
        extracted_text=(
            "CONVENTION CMR INTERNATIONAL CONSIGNMENT NOTE "
            "16 Transporteur: ABC Gross weight: 5000 kg"
        ),
    )
    norm_cmr = composite.parse(raw_cmr)
    assert norm_cmr.format_type == DocumentFormatType.CMR

    # Documento 3: Desconocido
    raw_unk = RawDocumentDTO(
        content_bytes=b"3",
        filename="factura.pdf",
        sha256_hash="h3",
        extracted_text="FACTURA DE SUMINISTRO ELÉCTRICO ENDESA TOTAL 240 EUROS",
    )
    norm_unk = composite.parse(raw_unk)
    assert norm_unk.format_type == DocumentFormatType.DESCONOCIDO
    assert norm_unk.reference.status == FieldExtractionStatus.REQUIERE_REVISION
    assert norm_unk.is_complete_and_confident() is False


def test_audit_real_carta_de_porte_operational_scenario() -> None:
    """Auditoría de Carta de Porte real de Tomates de Autor (Hispatec).

    Verifica que:
    - No hay albarán fiable -> external_reference = null, status = NO_PRESENTE.
    - Transportista y matrículas están vacíos -> NO_PRESENTE.
    - Datos de carga, origen, destino, bultos y pesos se extraen fielmente.
    - is_valid_for_import() es True (válido para PENDIENTE_MATRICULA).
    - is_ready_for_deca() es False (requiere asignación de matrícula posterior).
    """
    real_hispatec_text = """
    TOMATES DE AUTOR S.L.
    CARTA DE PORTE NACIONAL
    Documento Nº: CP-2026/00189
    Fecha Transporte: 03/10/2026
    Cargador: Tomates de Autor S.L.
    CIF Cargador: B04123456
    Domicilio Cargador: Paraje El Treinta s/n, El Ejido (Almería)
    Lugar de Carga: El Ejido (Almería)
    Lugar de Descarga: Mercamadrid, Nave 4 (Madrid)
    Consignatario: Frutas Hermanos Sánchez S.A.
    Mercancía: Tomate Rama Extra Calibre M
    Total Bultos: 1200 cajas
    Peso Bruto: 18.450,50 kg
    Peso Neto: 17.200,00 kg
    Instrucciones: Transporte refrigerado +10ºC
    """
    raw_doc = RawDocumentDTO(
        content_bytes=b"%PDF-real-cp",
        filename="carta_porte_hispatec_00189.pdf",
        sha256_hash="hash-cp-real",
        extracted_text=real_hispatec_text,
    )

    parser = CartaDePorteParser()
    norm = parser.parse(raw_doc)

    assert norm.format_type == DocumentFormatType.CARTA_DE_PORTE
    assert norm.document_number.value == "CP-2026/00189"
    assert norm.document_number.status == FieldExtractionStatus.EXTRAIDO

    assert norm.external_reference.value is None
    assert norm.external_reference.status == FieldExtractionStatus.NO_PRESENTE

    assert norm.fiscal_year.value == "2026"
    assert norm.fiscal_year.status == FieldExtractionStatus.EXTRAIDO
    assert str(norm.loading_date.value) == "2026-10-03"
    assert norm.loading_date.status == FieldExtractionStatus.EXTRAIDO

    assert "Tomates de Autor" in str(norm.shipper.value)
    assert norm.shipper.status == FieldExtractionStatus.EXTRAIDO
    assert norm.consignee.value == "Frutas Hermanos Sánchez S.A."
    assert norm.consignee.status == FieldExtractionStatus.EXTRAIDO

    assert norm.carrier.value is None
    assert norm.carrier.status == FieldExtractionStatus.NO_PRESENTE
    assert norm.tractor_plate.value is None
    assert norm.tractor_plate.status == FieldExtractionStatus.NO_PRESENTE
    assert norm.trailer_plate.value is None
    assert norm.trailer_plate.status == FieldExtractionStatus.NO_PRESENTE

    assert norm.origin.value == "El Ejido (Almería)"
    assert norm.destination.value == "Mercamadrid, Nave 4 (Madrid)"
    assert norm.goods.value == "Tomate Rama Extra Calibre M"
    assert norm.total_packages.value == 1200
    assert norm.total_gross_weight_kg.value == 18450.50
    assert norm.total_net_weight_kg.value == 17200.00

    assert norm.is_valid_for_import() is True
    assert norm.is_ready_for_deca() is False


def test_audit_real_cmr_operational_scenario() -> None:
    """Auditoría de CMR internacional real.

    Verifica que:
    - CMR contiene número de documento y referencia de albarán (ambos EXTRAIDO).
    - Transportista efectivo y matrículas están identificados.
    - Mercancía, pesos y consignatario internacional extraídos.
    - is_valid_for_import() es True y is_ready_for_deca() es True si tiene matrículas.
    """
    real_cmr_text = """
    CMR - INTERNATIONAL CONSIGNMENT NOTE
    CONTRAT DE TRANSPORT INTERNATIONAL DE MARCHANDISES PAR ROUTE
    CMR Nº: CMR-FR-2026-99120
    Albarán Origen: ALB-2026-0881
    Date: 03/10/2026
    1 Expéditeur / Sender: Tomates de Autor S.L.
    VAT: ESB04123456
    Address: El Ejido, Almeria, Spain
    2 Destinataire / Consignee: Rungis Primeurs SAS
    Place of delivery: Paris, France
    4 Place of taking over: El Ejido, Almeria
    16 Transporteur / Carrier: Trans-Europe Express BV
    VAT: NL123456789B01
    6 Nature of the goods: Fresh Tomatoes on the vine
    7 Number of packages: 1450 packages
    11 Gross weight: 21.300 kg
    11a Net weight: 20.100 kg
    Vehicle: 1234-BBB
    Trailer: R-5678-BBB
    18 Observations: Temperature controlled +12C
    """
    raw_doc = RawDocumentDTO(
        content_bytes=b"%PDF-real-cmr",
        filename="cmr_international_99120.pdf",
        sha256_hash="hash-cmr-real",
        extracted_text=real_cmr_text,
    )

    parser = CMRParser()
    norm = parser.parse(raw_doc)

    assert norm.format_type == DocumentFormatType.CMR
    assert norm.document_number.value == "CMR-FR-2026-99120"
    assert norm.external_reference.value == "ALB-2026-0881"
    assert norm.external_reference.status == FieldExtractionStatus.EXTRAIDO
    assert norm.fiscal_year.value == "2026"
    assert str(norm.loading_date.value) == "2026-10-03"
    assert "Tomates de Autor" in str(norm.shipper.value)
    assert norm.consignee.value == "Rungis Primeurs SAS"
    assert norm.carrier.value == "Trans-Europe Express BV"
    assert norm.origin.value == "El Ejido, Almeria"
    assert norm.destination.value == "Paris, France"
    assert norm.goods.value == "Fresh Tomatoes on the vine"
    assert norm.total_packages.value == 1450
    assert norm.total_gross_weight_kg.value == 21300.00
    assert norm.total_net_weight_kg.value == 20100.00
    assert norm.tractor_plate.value == "1234-BBB"
    assert norm.trailer_plate.value == "R-5678-BBB"

    assert norm.is_valid_for_import() is True
    assert norm.is_ready_for_deca() is True
