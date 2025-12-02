"""
Utility functions for detecting and replacing markdown tables with PDF page images.

This module provides functions to:
1. Detect markdown tables in text content
2. Render PDF pages to base64-encoded images
3. Replace table paragraphs with image references

Usage:
    from mawa.etl.table_utils import replace_tables_with_images

    # In your transform step:
    document = replace_tables_with_images(document, pdf_path)

Dependencies:
    - pymupdf (add to pyproject.toml: "pymupdf>=1.24.0")
"""

import base64
import re
from io import BytesIO
from pathlib import Path

import fitz  # pymupdf
from PIL import Image as PILImage

from mawa.schemas.document_schema import Document, Paragraph
from mawa.schemas.ocr_schema import Image


def is_markdown_table(content: str) -> bool:
    """
    Detect if a paragraph content contains a markdown table.

    A markdown table is identified by:
    - Lines containing pipe characters with content between them (|...|...|)
    - A separator line with dashes (|---|---|) or (| --- | --- |)

    Args:
        content: The paragraph content to check

    Returns:
        True if the content appears to be a markdown table, False otherwise

    Examples:
        >>> is_markdown_table("| Header 1 | Header 2 |\\n| --- | --- |\\n| Cell 1 | Cell 2 |")
        True
        >>> is_markdown_table("This is regular text")
        False
    """
    if not content or not content.strip():
        return False

    lines = content.strip().split("\n")

    # Need at least 2 lines for a valid table (header + separator or header + row)
    if len(lines) < 2:
        return False

    # Pattern for table row: starts and ends with |, has content between pipes
    row_pattern = re.compile(r"^\|.*\|.*\|$")

    # Pattern for separator line: |---|---| or | --- | --- | with optional spaces
    separator_pattern = re.compile(r"^\|\s*[-:]+\s*\|")

    has_rows = False
    has_separator = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if row_pattern.match(line):
            has_rows = True
        if separator_pattern.match(line):
            has_separator = True

    # A valid markdown table should have both data rows and a separator
    return has_rows and has_separator


def pdf_page_to_base64(
    pdf_path: Path, page_num: int, dpi: int = 200, quality: int = 85
) -> tuple[str, int, int]:
    """
    Render a PDF page to a base64-encoded JPEG image.

    Args:
        pdf_path: Path to the PDF file
        page_num: Page number (0-indexed)
        dpi: Resolution for rendering (default: 200, matching OCR dimensions)
        quality: JPEG quality (1-100, default: 85)

    Returns:
        Tuple of (base64_string, width, height) where width and height are in pixels

    Raises:
        FileNotFoundError: If the PDF file doesn't exist
        IndexError: If the page number is out of range
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # Open PDF and get the page
    doc = fitz.open(pdf_path)

    if page_num < 0 or page_num >= len(doc):
        doc.close()
        raise IndexError(f"Page {page_num} out of range (0-{len(doc) - 1})")

    page = doc[page_num]

    # Calculate zoom factor for desired DPI (default PDF is 72 DPI)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    # Render page to pixmap
    pixmap = page.get_pixmap(matrix=matrix)

    # Convert to PIL Image
    img = PILImage.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

    # Save to bytes buffer as JPEG
    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)

    # Encode to base64
    base64_str = base64.b64encode(buffer.read()).decode("utf-8")

    width, height = pixmap.width, pixmap.height

    doc.close()

    return base64_str, width, height


def replace_tables_with_images(
    document: Document, pdf_path: Path, dpi: int = 200, tag_name: str = "table_image"
) -> Document:
    """
    Replace markdown table paragraphs with image references from the original PDF.

    For each paragraph detected as a markdown table:
    1. Renders the corresponding PDF page as an image
    2. Adds the image to the page's images list
    3. Replaces the paragraph content with a markdown image reference
    4. Sets the paragraph tag to identify it as a table image

    Args:
        document: The Document object to process
        pdf_path: Path to the original PDF file
        dpi: Resolution for rendering PDF pages (default: 200)
        tag_name: Tag to apply to table paragraphs (default: "table_image")

    Returns:
        The modified Document with tables replaced by image references

    Note:
        This function modifies the document in-place and also returns it.
        The PDF page numbers are assumed to match the document page indices.
    """
    # Track which pages we've already rendered to avoid duplicates
    rendered_pages: dict[int, tuple[str, int, int]] = {}
    table_count = 0

    for page in document.pages:
        page_idx = page.index  # 1-indexed in the document
        pdf_page_idx = page_idx - 1  # 0-indexed for pymupdf

        new_paragraphs: list[Paragraph] = []
        new_images: list[Image] = list(page.images)  # Copy existing images

        for para in page.paragraphs:
            if is_markdown_table(para.content):
                table_count += 1

                # Generate unique image name for this table
                img_name = f"table_{table_count}.jpg"

                # Render page if not already done
                if pdf_page_idx not in rendered_pages:
                    try:
                        base64_str, width, height = pdf_page_to_base64(
                            pdf_path, pdf_page_idx, dpi
                        )
                        rendered_pages[pdf_page_idx] = (base64_str, width, height)
                    except (FileNotFoundError, IndexError) as e:
                        # If we can't render, keep the original paragraph
                        print(f"Warning: Could not render page {page_idx}: {e}")
                        new_paragraphs.append(para)
                        continue

                base64_str, width, height = rendered_pages[pdf_page_idx]

                # Create the Image object for this table
                # Coordinates cover the full page since we don't have table bounds
                table_image = Image(
                    name_img=img_name,
                    top_left_x=0,
                    top_left_y=0,
                    bottom_right_x=width,
                    bottom_right_y=height,
                    image_base64=base64_str,
                )
                new_images.append(table_image)

                # Create the replacement paragraph with tag
                new_para = Paragraph(
                    index=para.index,
                    content=f"![{img_name}]({img_name})",
                    tag=tag_name,
                    source_ref=para.source_ref,
                )
                new_paragraphs.append(new_para)
            else:
                # Keep non-table paragraphs as-is
                new_paragraphs.append(para)

        # Update the page with new paragraphs and images
        page.paragraphs = new_paragraphs
        page.images = new_images

    return document


def get_table_paragraphs(document: Document) -> list[tuple[int, int, str]]:
    """
    Find all paragraphs containing markdown tables in a document.

    Useful for debugging or previewing which tables will be replaced.

    Args:
        document: The Document object to scan

    Returns:
        List of tuples (page_index, paragraph_index, content_preview)
        where content_preview is the first 100 characters of the table
    """
    tables = []
    for page in document.pages:
        for para in page.paragraphs:
            if is_markdown_table(para.content):
                preview = (
                    para.content[:100] + "..."
                    if len(para.content) > 100
                    else para.content
                )
                tables.append((page.index, para.index, preview))
    return tables


# Example usage and integration hints
if __name__ == "__main__":
    # Example: Test table detection
    test_table = """| Header 1 | Header 2 |
| --- | --- |
| Cell 1 | Cell 2 |"""

    test_not_table = "This is regular text with | a pipe character"

    print(f"Is table (should be True): {is_markdown_table(test_table)}")
    print(f"Is table (should be False): {is_markdown_table(test_not_table)}")

    # Integration example (commented out):
    # from mawa.utils import read_json, save_json
    # from mawa.schemas.document_schema import Document
    #
    # # Load document
    # doc_data = read_json(raw_path)
    # document = Document(**doc_data)
    #
    # # Replace tables
    # document = replace_tables_with_images(document, pdf_path)
    #
    # # Save updated document
    # save_json(document.model_dump(), raw_path)
