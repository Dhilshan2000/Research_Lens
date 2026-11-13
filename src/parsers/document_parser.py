import os
import re
import importlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedDocumentItem:
    text: str
    filename: str
    file_type: str
    page: Optional[int] = None
    section: Optional[str] = None
    sheet: Optional[str] = None
    total_pages: Optional[int] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """Multi-format parser for research papers and supplementary data.
    Supports PDF, DOCX, TXT, CSV, and XLSX formats with detailed metadata preservation.
    """

    @classmethod
    def parse_file(cls, file_path: str, original_filename: Optional[str] = None) -> List[ParsedDocumentItem]:
        path = Path(file_path)
        filename = original_filename or path.name
        ext = path.suffix.lower()

        if ext == ".pdf":
            return cls.parse_pdf(file_path, filename)
        elif ext in [".docx", ".doc"]:
            return cls.parse_docx(file_path, filename)
        elif ext == ".txt":
            return cls.parse_txt(file_path, filename)
        elif ext == ".csv":
            return cls.parse_csv(file_path, filename)
        elif ext in [".xlsx", ".xls"]:
            return cls.parse_xlsx(file_path, filename)
        else:
            raise ValueError(f"Unsupported file format: {ext}. Supported formats: PDF, DOCX, TXT, CSV, XLSX.")

    @classmethod
    def _detect_pdf_section(cls, text: str, current_section: str) -> str:
        section_pattern = re.compile(r"^(?:\d+\.|\b[IVXLCDM]+\.|\bSection\b|[A-Z\s]{4,}\b)", re.IGNORECASE)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:5]:
            if len(line) < 60 and (line.isupper() or section_pattern.match(line)) and not line.isdigit():
                return line.title()
        return current_section

    @classmethod
    def _parse_pdf_fitz(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        fitz = importlib.import_module("fitz")
        doc = fitz.open(file_path)
        items: List[ParsedDocumentItem] = []
        try:
            total_pages = len(doc)
            current_section = "Introduction"
            for page_idx in range(total_pages):
                page = doc[page_idx]
                text = page.get_text("text").strip()
                if not text:
                    continue

                current_section = cls._detect_pdf_section(text, current_section)
                items.append(ParsedDocumentItem(
                    text=text,
                    filename=filename,
                    file_type="pdf",
                    page=page_idx + 1,
                    total_pages=total_pages,
                    section=current_section,
                    extra_metadata={"page_char_count": len(text)}
                ))
            return items
        finally:
            doc.close()

    @classmethod
    def _parse_pdf_pypdf(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        pypdf = importlib.import_module("pypdf")
        reader = pypdf.PdfReader(file_path)
        items: List[ParsedDocumentItem] = []
        total_pages = len(reader.pages)
        for page_idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                items.append(ParsedDocumentItem(
                    text=text,
                    filename=filename,
                    file_type="pdf",
                    page=page_idx + 1,
                    total_pages=total_pages,
                    section=f"Page {page_idx + 1}",
                    extra_metadata={"page_char_count": len(text)}
                ))
        return items

    @classmethod
    def parse_pdf(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        try:
            return cls._parse_pdf_fitz(file_path, filename)
        except (ImportError, ModuleNotFoundError):
            try:
                return cls._parse_pdf_pypdf(file_path, filename)
            except Exception as e:
                raise RuntimeError(f"Error parsing PDF '{filename}': {str(e)}") from e
        except Exception as e:
            raise RuntimeError(f"Error parsing PDF '{filename}': {str(e)}") from e

    @classmethod
    def _extract_docx_paragraphs(cls, doc: Any, filename: str) -> List[ParsedDocumentItem]:
        items: List[ParsedDocumentItem] = []
        current_section = "Main Content"
        current_paragraphs: List[str] = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue

            if p.style and p.style.name.startswith("Heading"):
                if current_paragraphs:
                    items.append(ParsedDocumentItem(
                        text="\n\n".join(current_paragraphs),
                        filename=filename,
                        file_type="docx",
                        section=current_section,
                        extra_metadata={"paragraph_count": len(current_paragraphs)}
                    ))
                    current_paragraphs = []
                current_section = text
            else:
                current_paragraphs.append(text)

        if current_paragraphs:
            items.append(ParsedDocumentItem(
                text="\n\n".join(current_paragraphs),
                filename=filename,
                file_type="docx",
                section=current_section,
                extra_metadata={"paragraph_count": len(current_paragraphs)}
            ))
        return items

    @classmethod
    def _extract_docx_tables(cls, doc: Any, filename: str) -> List[ParsedDocumentItem]:
        items: List[ParsedDocumentItem] = []
        for table_idx, table in enumerate(doc.tables):
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                if any(row_data):
                    table_data.append(" | ".join(row_data))
            if table_data:
                items.append(ParsedDocumentItem(
                    text="\n".join(table_data),
                    filename=filename,
                    file_type="docx",
                    section=f"Table {table_idx + 1}",
                    extra_metadata={"is_table": True, "rows": len(table_data)}
                ))
        return items

    @classmethod
    def parse_docx(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        try:
            docx = importlib.import_module("docx")
            doc = docx.Document(file_path)
            items = cls._extract_docx_paragraphs(doc, filename)
            items.extend(cls._extract_docx_tables(doc, filename))
            return items
        except Exception as e:
            raise RuntimeError(f"Error parsing DOCX '{filename}': {str(e)}") from e

    @classmethod
    def parse_txt(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        try:
            for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                with open(file_path, "r", errors="ignore") as f:
                    content = f.read()

            content = content.strip()
            if not content:
                return []

            # Split into sections if markdown or capitalized headings exist
            sections = re.split(r"\n(?=#{1,3}\s+|[A-Z0-9\s]{4,}:|\bSECTION\b)", content)
            items: List[ParsedDocumentItem] = []

            for idx, sec in enumerate(sections):
                sec = sec.strip()
                if not sec:
                    continue
                first_line = sec.split("\n")[0][:60]
                section_title = first_line.strip("# ").strip() if first_line else f"Section {idx + 1}"
                items.append(ParsedDocumentItem(
                    text=sec,
                    filename=filename,
                    file_type="txt",
                    section=section_title,
                    extra_metadata={"char_count": len(sec)}
                ))

            return items
        except Exception as e:
            raise RuntimeError(f"Error parsing TXT '{filename}': {str(e)}")

    @classmethod
    def parse_csv(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        try:
            import pandas as pd
            df = pd.read_csv(file_path)
            items: List[ParsedDocumentItem] = []

            # Metadata overview
            overview_text = (
                f"Dataset File: {filename}\n"
                f"Columns: {', '.join(df.columns.astype(str))}\n"
                f"Total Rows: {len(df)}\n"
                f"Summary Statistics:\n{df.describe(include='all').to_string()}"
            )
            items.append(ParsedDocumentItem(
                text=overview_text,
                filename=filename,
                file_type="csv",
                section="Data Summary",
                extra_metadata={"rows": len(df), "columns": list(df.columns)}
            ))

            # Batch rows into chunks of 15 rows with header
            chunk_size = 15
            for start_idx in range(0, min(len(df), 150), chunk_size):
                sub_df = df.iloc[start_idx:start_idx + chunk_size]
                table_str = sub_df.to_markdown(index=False) if hasattr(sub_df, "to_markdown") else sub_df.to_string(index=False)
                items.append(ParsedDocumentItem(
                    text=f"Table Segment (Rows {start_idx+1} to {start_idx+len(sub_df)}):\n{table_str}",
                    filename=filename,
                    file_type="csv",
                    section=f"Rows {start_idx+1}-{start_idx+len(sub_df)}",
                    extra_metadata={"row_start": start_idx, "row_end": start_idx + len(sub_df)}
                ))

            return items
        except Exception as e:
            raise RuntimeError(f"Error parsing CSV '{filename}': {str(e)}")

    @classmethod
    def parse_xlsx(cls, file_path: str, filename: str) -> List[ParsedDocumentItem]:
        try:
            import pandas as pd
            excel_file = pd.ExcelFile(file_path)
            items: List[ParsedDocumentItem] = []

            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                overview_text = (
                    f"Workbook: {filename} | Sheet: {sheet_name}\n"
                    f"Columns: {', '.join(df.columns.astype(str))}\n"
                    f"Total Rows: {len(df)}"
                )
                items.append(ParsedDocumentItem(
                    text=overview_text,
                    filename=filename,
                    file_type="xlsx",
                    sheet=sheet_name,
                    section=f"Sheet '{sheet_name}' Overview",
                    extra_metadata={"sheet": sheet_name, "rows": len(df)}
                ))

                chunk_size = 15
                for start_idx in range(0, min(len(df), 120), chunk_size):
                    sub_df = df.iloc[start_idx:start_idx + chunk_size]
                    table_str = sub_df.to_markdown(index=False) if hasattr(sub_df, "to_markdown") else sub_df.to_string(index=False)
                    items.append(ParsedDocumentItem(
                        text=f"Sheet '{sheet_name}' Rows {start_idx+1}-{start_idx+len(sub_df)}:\n{table_str}",
                        filename=filename,
                        file_type="xlsx",
                        sheet=sheet_name,
                        section=f"{sheet_name} Rows {start_idx+1}-{start_idx+len(sub_df)}"
                    ))

            return items
        except Exception as e:
            raise RuntimeError(f"Error parsing XLSX '{filename}': {str(e)}")

