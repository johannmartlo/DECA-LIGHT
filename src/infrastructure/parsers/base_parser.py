from __future__ import annotations

import re
from datetime import date, datetime

from src.domain.value_objects import ExtractedField


class BaseDocumentParser:
    """Utilidades y métodos base deterministas para extracción textual sin IA."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Normaliza saltos de línea y espacios en blanco continuos."""
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def extract_regex_string(
        text: str, patterns: list[str], flags: int = re.IGNORECASE
    ) -> ExtractedField[str]:
        """Busca patrones en orden y devuelve un ExtractedField tipado."""
        for pattern in patterns:
            match = re.search(pattern, text, flags)
            if match:
                raw_val = match.group(1).lstrip(" /:-").rstrip(" :\t-").strip()
                if raw_val:
                    return ExtractedField.extracted(value=raw_val, raw_text=match.group(0))
        return ExtractedField.not_present()

    @staticmethod
    def extract_date(text: str, patterns: list[str]) -> ExtractedField[date]:
        """Extrae fechas deterministamente y las convierte a datetime.date."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_str = match.group(1).strip()
                # Probar formatos habituales DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y"):
                    try:
                        parsed_date = datetime.strptime(raw_str, fmt).date()
                        return ExtractedField.extracted(value=parsed_date, raw_text=raw_str)
                    except ValueError:
                        continue
                return ExtractedField.not_recognized(raw_text=raw_str)
        return ExtractedField.not_present()

    @staticmethod
    def extract_weight(text: str, patterns: list[str]) -> ExtractedField[float]:
        """Extrae magnitudes de peso y las estandariza en kilogramos flotantes."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_str = match.group(1).strip()
                clean_num = raw_str.lower().replace("kg", "").replace("kilos", "").strip()
                is_tons = "t" in clean_num or "toneladas" in clean_num
                clean_num = clean_num.replace("toneladas", "").replace("t", "").strip()

                try:
                    clean_num = clean_num.replace(" ", "")
                    if "," in clean_num and "." in clean_num:
                        if clean_num.rfind(",") > clean_num.rfind("."):
                            clean_num = clean_num.replace(".", "").replace(",", ".")
                        else:
                            clean_num = clean_num.replace(",", "")
                    elif "." in clean_num:
                        if re.match(r"^\d{1,3}(?:\.\d{3})+$", clean_num):
                            clean_num = clean_num.replace(".", "")
                    elif "," in clean_num:
                        if re.match(r"^\d{1,3}(?:,\d{3})+$", clean_num):
                            clean_num = clean_num.replace(",", "")
                        else:
                            clean_num = clean_num.replace(",", ".")

                    val = float(re.findall(r"[-+]?\d*\.\d+|\d+", clean_num)[0])
                    if is_tons:
                        val = val * 1000.0

                    if val > 0:
                        return ExtractedField.extracted(value=round(val, 2), raw_text=raw_str)
                except (ValueError, IndexError):
                    return ExtractedField.not_recognized(raw_text=raw_str)

        return ExtractedField.not_present()

    @staticmethod
    def extract_integer(text: str, patterns: list[str]) -> ExtractedField[int]:
        """Extrae cantidades enteras (ej. bultos, cajas, pallets)."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                raw_str = match.group(1).strip()
                clean_num = raw_str.replace(".", "").replace(" ", "").replace(",", "")
                digits = re.findall(r"\d+", clean_num)
                if digits:
                    try:
                        val = int(digits[0])
                        if val > 0:
                            return ExtractedField.extracted(value=val, raw_text=match.group(0))
                    except ValueError:
                        return ExtractedField.not_recognized(raw_text=raw_str)
        return ExtractedField.not_present()
