# -*- coding: utf-8 -*-
"""
PDF report generator for PLU analysis.

Version: 0.2.0
Date: 2025-11-16
Author: Grey Panda (optimized by Boat)
"""

import html
import json
import re
import warnings
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.flowables import Flowable
from reportlab.platypus.tableofcontents import TableOfContents
from svglib.svglib import svg2rlg

from mawa.config import CONFIG_DIR, DOCS_DIR, IMAGES_DIR

FONTS_DIR = DOCS_DIR / "fonts"

# ============================================================================
# Font Registration
# ============================================================================


def _register_fonts() -> bool:
    """Register Lato fonts, fallback to Helvetica if unavailable."""
    font_files = {
        "Lato-Regular": FONTS_DIR / "Lato-Regular.ttf",
        "Lato-Bold": FONTS_DIR / "Lato-Bold.ttf",
        "Lato-Italic": FONTS_DIR / "Lato-Italic.ttf",
    }

    missing = []
    for font_name, path in font_files.items():
        if not path.exists():
            missing.append(font_name)
            continue
        try:
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
        except Exception:
            missing.append(font_name)

    if missing:
        warnings.warn(
            f"Lato fonts missing ({', '.join(missing)}). Using Helvetica.",
            RuntimeWarning,
        )
        return False

    pdfmetrics.registerFontFamily(
        "Lato",
        normal="Lato-Regular",
        bold="Lato-Bold",
        italic="Lato-Italic",
        boldItalic="Lato-Bold",
    )
    return True


_LATO_AVAILABLE = _register_fonts()
FONT_REGULAR = "Lato-Regular" if _LATO_AVAILABLE else "Helvetica"
FONT_BOLD = "Lato-Bold" if _LATO_AVAILABLE else "Helvetica-Bold"
FONT_ITALIC = "Lato-Italic" if _LATO_AVAILABLE else "Helvetica-Oblique"

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class Regle:
    """A single rule with content and optional source reference."""

    contenu: str
    source_ref: str = ""


@dataclass
class Subsection:
    """A subsection with rules."""

    code: str
    number: str
    title: str
    heading: str
    bookmark: str
    regles: List[Regle] = field(default_factory=list)


@dataclass
class Section:
    """A top-level section with subsections."""

    code: str
    number: str
    title: str
    heading: str
    bookmark: str
    subsections: List[Subsection] = field(default_factory=list)


# ============================================================================
# Style Factory
# ============================================================================


class StyleFactory:
    """Factory for creating consistent paragraph styles."""

    @staticmethod
    def create(
        name: str, font: str = FONT_REGULAR, size: int = 11, leading: int = 14, **kwargs
    ) -> ParagraphStyle:
        """Create a paragraph style with common defaults."""
        defaults = {
            "fontName": font,
            "fontSize": size,
            "leading": leading,
            "textColor": black,
            "spaceBefore": 0,
            "spaceAfter": 0,
        }
        defaults.update(kwargs)
        return ParagraphStyle(name=name, **defaults)

    @classmethod
    def heading(cls, level: int) -> ParagraphStyle:
        """Create heading styles."""
        configs = {
            1: {
                "font": FONT_BOLD,
                "size": 18,
                "leading": 22,
                "spaceBefore": 18,
                "spaceAfter": 8,
            },
            2: {
                "font": FONT_BOLD,
                "size": 14,
                "leading": 18,
                "spaceBefore": 14,
                "spaceAfter": 6,
            },
            3: {
                "font": FONT_BOLD,
                "size": 12,
                "leading": 16,
                "spaceBefore": 10,
                "spaceAfter": 4,
                "leftIndent": 0.5 * cm,
            },
            4: {
                "font": FONT_ITALIC,
                "size": 11,
                "leading": 14,
                "spaceBefore": 8,
                "spaceAfter": 2,
            },
        }
        config = configs.get(level, configs[4])
        return cls.create(f"H{level}", **config)


# ============================================================================
# Utility Functions
# ============================================================================


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", slug) or "section"


def _extract_number(pattern: str, text: str) -> Optional[str]:
    """Extract number from text using regex pattern."""
    match = re.search(pattern, text or "")
    return match.group(1) if match else None


def _chapter_number(key: str) -> Optional[str]:
    """Extract chapter number from key like 'chapitre_1'."""
    return _extract_number(r"(\d+)", key)


def _section_number(key: str) -> Optional[str]:
    """Extract section number from key like 'section_1_2'."""
    match = re.match(r"section_(\d+)_(\d+)", key or "")
    return f"{match.group(1)}.{match.group(2)}" if match else None


def _format_title(raw_title: str) -> str:
    """Clean and format schema title."""
    if not raw_title:
        return ""

    # Remove leading numbers and separators
    cleaned = re.sub(
        r"^\s*\d+(?:[.\-]\d+)*(?:\s*[-–—:])?\s*",
        "",
        raw_title.strip(),
        flags=re.UNICODE,
    ).strip()

    # Remove any remaining leading punctuation (like ". " or "- ")
    cleaned = re.sub(r"^[.\-–—:\s]+", "", cleaned).strip()

    if not cleaned:
        cleaned = raw_title.strip()

    # Convert all-caps to title case
    return cleaned.title() if cleaned.isupper() else cleaned


def _compose_heading(number: Optional[str], title: str) -> str:
    """Compose heading from number and title."""
    title = title.strip() if title else ""
    if number and title:
        return f"{number} – {title}"
    return number or title or "Sans titre"


@lru_cache(maxsize=1)
def _load_schema_titles() -> Dict[str, Dict[str, str]]:
    """Load chapter and section titles from schema."""
    schema_path = CONFIG_DIR / "schemas" / "response_schema_synthese.json"
    if not schema_path.exists():
        return {"chapters": {}, "sections": {}}

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    chapters, sections = {}, {}
    for chap_key, chap_meta in schema.get("properties", {}).items():
        chapters[chap_key] = chap_meta.get("description", "").strip()
        for sec_key, sec_meta in chap_meta.get("properties", {}).items():
            sections[sec_key] = sec_meta.get("description", "").strip()

    return {"chapters": chapters, "sections": sections}


# ============================================================================
# SVG Drawing
# ============================================================================


def _scale_and_draw_svg(
    canvas, svg_path: str, x: float, y: float, target_width_cm: float
) -> Optional[float]:
    """Scale and draw SVG at specified position. Returns bottom y-coordinate."""
    drawing = svg2rlg(svg_path)
    if not drawing or (drawing.width == 0 and drawing.height == 0):
        return None

    target_width = target_width_cm * cm

    # Calculate scale factor
    if drawing.width == 0:
        scale = target_width / (drawing.height * 0.1) if drawing.height != 0 else 1
    elif drawing.height == 0:
        scale = target_width / drawing.width
    else:
        scale = target_width / drawing.width

    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)

    canvas.saveState()
    try:
        renderPDF.draw(drawing, canvas, x, y)
    finally:
        canvas.restoreState()

    return y - drawing.height


def _draw_centered_logo(
    canvas, logo_path: str, width_cm: float = 6.9
) -> Optional[float]:
    """Draw centered logo at top of page."""
    y_top = A4[1] - 10 * cm
    x_center = (A4[0] - width_cm * cm) / 2
    y_bottom = _scale_and_draw_svg(canvas, logo_path, x_center, y_top, width_cm)
    return y_bottom - 2 * cm if y_bottom else None


def _draw_corner_logo(canvas, logo_path: str, width_cm: float = 2.0):
    """Draw logo at bottom-left corner."""
    if logo_path:
        _scale_and_draw_svg(canvas, logo_path, 1.6 * cm, 0.2 * cm, width_cm)


# ============================================================================
# Data Normalization
# ============================================================================


def _normalize_regles(raw_regles: Any) -> List[Regle]:
    """Normalize rules from various formats."""
    if not isinstance(raw_regles, list):
        return []

    regles = []
    for item in raw_regles:
        if isinstance(item, dict):
            contenu = str(item.get("contenu", "")).strip()
            source_ref = str(
                item.get("source_ref") or item.get("page_source", "")
            ).strip()
        else:
            contenu = str(item).strip()
            source_ref = ""

        if contenu:
            regles.append(Regle(contenu, source_ref))

    return regles


def _extract_parsed_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract parsed data from various JSON structures."""
    if not isinstance(raw_data, dict):
        return {}

    # Try direct parsed field
    if "parsed" in raw_data and isinstance(raw_data["parsed"], dict):
        return raw_data["parsed"]

    # Try response.parsed
    response = raw_data.get("response", {})
    if isinstance(response, dict) and "parsed" in response:
        if isinstance(response["parsed"], dict):
            return response["parsed"]

    # Try candidates (Gemini-style)
    for candidate in raw_data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            text = part.get("text")
            if text:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        return (
                            parsed.get("parsed", parsed)
                            if "parsed" in parsed
                            else parsed
                        )
                except json.JSONDecodeError:
                    continue

    return {}


def _build_sections(data: Dict[str, Any]) -> List[Section]:
    """Build normalized sections from JSON data."""
    titles = _load_schema_titles()
    chapters_titles = titles["chapters"]
    sections_titles = titles["sections"]

    # Try parsed format first
    parsed = _extract_parsed_data(data)
    if parsed:
        return _build_from_parsed(parsed, chapters_titles, sections_titles)

    # Fallback to legacy format
    response = data.get("response", {})
    if isinstance(response, dict):
        return _build_from_legacy(response, chapters_titles, sections_titles)

    return []


def _build_from_parsed(
    parsed: Dict, chapter_titles: Dict, section_titles: Dict
) -> List[Section]:
    """Build sections from parsed format."""
    sections = []

    for chap_key in sorted(
        parsed.keys(),
        key=lambda k: int(
            re.search(r"(\d+)", k or "").group(1) if re.search(r"(\d+)", k or "") else 0
        ),
    ):
        chap_data = parsed.get(chap_key, {})
        if not isinstance(chap_data, dict):
            continue

        subsections = []
        for sec_key in sorted(
            chap_data.keys(),
            key=lambda k: tuple(
                map(int, re.findall(r"\d+", k or "")) or [float("inf")]
            ),
        ):
            regles = _normalize_regles(chap_data.get(sec_key))
            if regles:
                subsections.append(_make_subsection(sec_key, regles, section_titles))

        if subsections:
            sections.append(_make_section(chap_key, subsections, chapter_titles))

    return sections


def _build_from_legacy(
    response: Dict, chapter_titles: Dict, section_titles: Dict
) -> List[Section]:
    """Build sections from legacy format."""
    sections = []

    for sec_key in sorted(response.keys()):
        sous_sections = response.get(sec_key, [])
        if not isinstance(sous_sections, list):
            continue

        subsections = []
        for idx, ss in enumerate(sous_sections, 1):
            if not isinstance(ss, dict):
                continue
            regles = _normalize_regles(ss.get("regles"))
            if not regles:
                continue

            raw_num = ss.get("sous_section")
            derived_key = (
                f"section_{raw_num.replace('.', '_')}"
                if isinstance(raw_num, str) and "." in raw_num
                else f"{sec_key}_{idx}"
            )
            subsections.append(
                _make_subsection(
                    derived_key,
                    regles,
                    section_titles,
                    override_title=ss.get("titre"),
                    override_number=raw_num,
                )
            )

        if subsections:
            chap_key = sec_key.replace("section_", "chapitre_")
            sections.append(_make_section(chap_key, subsections, chapter_titles))

    return sections


def _make_subsection(
    key: str,
    regles: List[Regle],
    titles: Dict,
    override_title: Optional[str] = None,
    override_number: Optional[str] = None,
) -> Subsection:
    """Create a subsection from components."""
    number = override_number or _section_number(key) or key.replace("_", " ").title()

    if override_title and override_title.strip():
        title = override_title.strip()
    elif key in titles and titles[key]:
        title = _format_title(titles[key])
    else:
        title = key.replace("_", " ").title()

    heading = _compose_heading(number, title)

    return Subsection(
        code=key,
        number=number,
        title=title,
        heading=heading,
        bookmark=_slugify(heading),
        regles=regles,
    )


def _make_section(key: str, subsections: List[Subsection], titles: Dict) -> Section:
    """Create a section from components."""
    number = _chapter_number(key) or key.replace("_", " ").title()
    raw_title = titles.get(key, "")
    title = _format_title(raw_title) if raw_title else key.replace("_", " ").title()
    heading = _compose_heading(number, title)

    return Section(
        code=key,
        number=number,
        title=title,
        heading=heading,
        bookmark=_slugify(heading),
        subsections=subsections,
    )


def _ensure_unique_bookmarks(sections: List[Section]) -> List[Section]:
    """Ensure all bookmarks are unique."""
    seen = {}

    def make_unique(base: str) -> str:
        count = seen.get(base, 0)
        seen[base] = count + 1
        return base if count == 0 else f"{base}-{count + 1}"

    for section in sections:
        section.bookmark = make_unique(section.bookmark)
        for subsection in section.subsections:
            subsection.bookmark = make_unique(subsection.bookmark)

    return sections


# ============================================================================
# PDF Building
# ============================================================================


class BookmarkFlowable(Flowable):
    """Adds bookmark and outline entry."""

    def __init__(self, name: str, label: str, level: int = 0):
        super().__init__()
        self.bookmark_name = name
        self.bookmark_label = label
        self.level = max(0, level)
        self.width = self.height = 0

    def wrap(self, availWidth, availHeight):
        return (0, 0)

    def draw(self):
        # Create bookmark at current position
        self.canv.bookmarkPage(self.bookmark_name)
        # Add to outline/navigation tree
        self.canv.addOutlineEntry(
            self.bookmark_label, self.bookmark_name, self.level, closed=0
        )


def _add_section_to_story(
    story: List,
    title: str,
    content: Optional[str] = None,
    level: int = 1,
    bookmark: Optional[str] = None,
    toc_level: Optional[int] = None,
):
    """Add a section with optional bookmark to story."""
    para = Paragraph(title, StyleFactory.heading(level))

    # Set TOC attributes if this should appear in TOC
    if toc_level is not None:
        para._headingLevel = toc_level
        para._headingText = title

    # IMPORTANT: Set bookmark name on the paragraph itself
    # This ensures the bookmark is created when the paragraph is drawn
    if bookmark:
        para._bookmarkName = bookmark
        # Also manually add the outline entry via a flowable for navigation
        story.append(BookmarkFlowable(bookmark, title, level - 1))

    story.append(para)

    if content:
        body_style = StyleFactory.create(
            "Body", size=11, leading=16, spaceAfter=8, textColor=HexColor("#222222")
        )
        story.append(Paragraph(content, body_style))


def _add_regles_to_story(story: List, regles: List[Regle]):
    """Add rules to story."""
    for regle in regles:
        text = html.escape(regle.contenu)
        if regle.source_ref:
            text += f' <font size="9" color="#888888">({html.escape(regle.source_ref)})</font>'
        _add_section_to_story(story, "", text, level=4)


def _build_content(story: List, sections: List[Section]):
    """Build main content sections."""
    if not sections:
        _add_section_to_story(story, "Aucune section disponible", None, level=2)
        return

    for section in sections:
        _add_section_to_story(
            story,
            section.heading,
            None,
            level=1,
            bookmark=section.bookmark,
            toc_level=0,
        )

        if not section.subsections:
            _add_section_to_story(story, "Aucune sous-section", None, level=2)
            continue

        for subsection in section.subsections:
            _add_section_to_story(
                story,
                subsection.heading,
                None,
                level=2,
                bookmark=subsection.bookmark,
                toc_level=1,
            )
            _add_regles_to_story(story, subsection.regles)
            story.append(Spacer(1, 0.3 * cm))


def _build_cover_page(
    metadata: Dict, custom_title: Optional[List[Dict[str, str]]] = None
) -> List:
    """
    Build cover page story elements.

    Args:
        metadata: Document metadata (used for fallback)
        custom_title: Optional custom title. List of dicts with 'text' and 'style' keys.
                     Example: [
                         {'text': 'PARIS 15ème', 'style': 'city'},
                         {'text': 'Plan Local d\'Urbanisme', 'style': 'zoning'},
                         {'text': 'Zone UG', 'style': 'zone'}
                     ]
    """
    story = [Spacer(1, 12 * cm)]

    styles = {
        "city": StyleFactory.create(
            "City", FONT_BOLD, 22, alignment=TA_CENTER, spaceAfter=20
        ),
        "zoning": StyleFactory.create(
            "Zoning", size=18, leading=22, alignment=TA_CENTER, spaceAfter=16
        ),
        "zone": StyleFactory.create(
            "Zone",
            size=16,
            leading=20,
            alignment=TA_CENTER,
            spaceAfter=32,
            textColor=HexColor("#222222"),
        ),
        "link": StyleFactory.create(
            "Link",
            size=11,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=6,
            textColor=HexColor("#444444"),
        ),
    }

    # Use custom title if provided, otherwise fallback to metadata
    if custom_title:
        for line in custom_title:
            text = line.get("text", "")
            style_name = line.get("style", "zoning")
            style = styles.get(style_name, styles["zoning"])
            story.append(Paragraph(text, style))
    else:
        # Default automatic title
        story.extend(
            [
                Paragraph(metadata.get("name_city", "").upper(), styles["city"]),
                Paragraph(metadata.get("name_zoning", ""), styles["zoning"]),
                Paragraph(f"Zone {metadata.get('name_zone', '-')}", styles["zone"]),
            ]
        )

    story.extend(
        [
            Spacer(1, 4 * cm),
            Paragraph('<a href="https://mwplu.com">mwplu.com</a>', styles["link"]),
            Paragraph(
                '<a href="mailto:contact@mwplu.com">contact@mwplu.com</a>',
                styles["link"],
            ),
            Spacer(1, 2 * cm),
            PageBreak(),
        ]
    )

    return story


def _build_toc_page(has_sections: bool) -> tuple[List, str]:
    """Build table of contents page."""
    story = []
    toc_title = "Sommaire"
    toc_bookmark = _slugify(toc_title)

    # Add bookmark
    story.append(BookmarkFlowable(toc_bookmark, toc_title, 0))

    # Styles
    title_style = StyleFactory.create("TOCTitle", FONT_BOLD, 18, 22, spaceAfter=8)
    subtitle_style = StyleFactory.create(
        "TOCSubtitle", size=11, leading=15, spaceAfter=18, textColor=HexColor("#555555")
    )

    story.append(Paragraph(toc_title, title_style))

    if has_sections:
        toc = TableOfContents()
        toc.levelStyles = [
            StyleFactory.create("TOCSection", FONT_BOLD, 12, 18, spaceBefore=2),
            StyleFactory.create(
                "TOCSubsection",
                size=10.5,
                leading=15,
                leftIndent=0.8 * cm,
                textColor=HexColor("#444444"),
            ),
        ]
        toc.dotsMinLevel = 0
        story.append(toc)
    else:
        story.append(
            Paragraph("Aucune section disponible pour ce document.", subtitle_style)
        )

    # Add reference link
    ref_style = StyleFactory.create("RefLink", FONT_BOLD, 11.5, 16, spaceBefore=18)
    story.append(
        Paragraph(
            '<a href="#références-et-mentions-légales">Références et Mentions Légales</a>',
            ref_style,
        )
    )
    story.append(PageBreak())

    return story, toc_bookmark


def _build_references_page(references: Optional[Dict[str, str]] = None) -> List:
    """Build references and legal mentions page."""
    story = []
    ref_bookmark = "références-et-mentions-légales"
    story.append(BookmarkFlowable(ref_bookmark, "Références et Mentions Légales", 0))

    styles = {
        "title": StyleFactory.create(
            "RefTitle", FONT_BOLD, 16, 20, spaceBefore=24, spaceAfter=12
        ),
        "section": StyleFactory.create(
            "RefSection", FONT_BOLD, 12, 16, spaceBefore=16, spaceAfter=8
        ),
        "content": StyleFactory.create(
            "RefContent",
            size=10,
            leading=14,
            spaceBefore=4,
            spaceAfter=4,
            textColor=HexColor("#222222"),
        ),
        "company": StyleFactory.create(
            "CompanyInfo",
            size=10,
            leading=14,
            spaceBefore=4,
            spaceAfter=4,
            textColor=HexColor("#444444"),
        ),
    }

    refs = references or {}

    story.append(Paragraph("Références et Mentions Légales", styles["title"]))
    story.append(Spacer(1, 0.5 * cm))

    # Urbanisme references
    story.append(Paragraph("Références d'urbanisme", styles["section"]))
    for key, label in [
        ("source_plu_url", "Lien vers les documents PLU complets"),
        ("vocabulaire", "Vocabulaire de l'urbanisme"),
    ]:
        link = refs.get(key, "-")
        text = f'<a href="{link}">{label}</a>' if link != "-" else f"{label} : -"
        story.append(Paragraph(text, styles["content"]))
    story.append(Spacer(1, 0.5 * cm))

    # Legal mentions
    story.append(
        Paragraph("Mentions légales et politique de confidentialité", styles["section"])
    )
    for key, label in [
        ("politiques_vente", "Politiques de vente"),
        ("politique_confidentialite", "Politique de confidentialité"),
        ("cgu", "Conditions générales d'utilisation"),
    ]:
        link = refs.get(key, "-")
        text = (
            f'<a href="{link}">Accéder à {label.lower()}</a>'
            if link != "-"
            else f"{label} : -"
        )
        story.append(Paragraph(text, styles["content"]))
    story.append(Spacer(1, 0.5 * cm))

    # Company info
    story.append(Paragraph("Informations Société", styles["section"]))
    for text in [
        "Société : MEWE PARTNERS SAS (MWP)",
        "SIRET : 94134170300010",
        "Dirigeants : Zakaria TOUATI, Rim ENNACIRI",
    ]:
        story.append(Paragraph(text, styles["company"]))

    return story


# ============================================================================
# Main Generator
# ============================================================================


def generate_pdf_report(
    json_path: str,
    output_path: str,
    logo_path: str = str(IMAGES_DIR / "svg" / "BLACK-MATRIX.svg"),
    page_logo_path: Optional[str] = str(IMAGES_DIR / "svg" / "BLANK-MEWE.svg"),
    references: Optional[Dict[str, str]] = None,
    custom_title: Optional[List[Dict[str, str]]] = None,
) -> None:
    """
    Generate PDF report from JSON file.

    Args:
        json_path: Path to input JSON file
        output_path: Path to output PDF file
        logo_path: Path to main SVG logo for cover
        page_logo_path: Path to corner logo for all pages
        references: Dictionary of reference links
        custom_title: Optional custom title. List of dicts with 'text' and 'style' keys.
                     Example: [
                         {'text': 'PARIS 15ème', 'style': 'city'},
                         {'text': 'Plan Local d\'Urbanisme', 'style': 'zoning'},
                         {'text': 'Zone UG', 'style': 'zone'}
                     ]
    """
    # Load and normalize data
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    sections = _ensure_unique_bookmarks(_build_sections(data))
    metadata = data.get("metadata", {})

    # Build story
    story = []
    story.extend(_build_cover_page(metadata, custom_title))
    toc_story, toc_bookmark = _build_toc_page(bool(sections))
    story.extend(toc_story)
    _build_content(story, sections)
    story.append(PageBreak())
    story.extend(_build_references_page(references))

    # Create document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.9 * cm,
        bottomMargin=1.6 * cm,
        title=metadata.get("name_zone", "Synthèse PLU"),
        author="SIFT - MEWE",
    )

    # TOC notification handler
    def after_flowable(flowable):
        if hasattr(flowable, "_headingLevel") and hasattr(flowable, "_headingText"):
            doc.notify(
                "TOCEntry",
                (
                    flowable._headingLevel,
                    flowable._headingText,
                    doc.page,
                    getattr(flowable, "_bookmarkName", None),
                ),
            )

    doc.afterFlowable = after_flowable

    # Page handlers
    def on_first_page(canvas, doc_obj):
        if logo_path:
            _draw_centered_logo(canvas, logo_path)
        canvas.setTitle(metadata.get("name_zone", "Synthèse PLU"))
        canvas.setAuthor("SIFT - MEWE")

    def on_later_pages(canvas, doc_obj):
        if page_logo_path:
            _draw_corner_logo(canvas, page_logo_path)

        # Display TOC link starting from page 4 onwards
        # Pages 1-3 are cover page (1) and TOC pages (2-3)
        if doc_obj.page >= 4:
            # TOC link in footer
            canvas.setFont(FONT_REGULAR, 8)
            canvas.setFillColor(HexColor("#666666"))
            text = "Sommaire ↑"
            text_width = canvas.stringWidth(text, FONT_REGULAR, 8)
            x_pos = A4[0] - doc_obj.rightMargin - text_width - 0.2 * cm
            y_pos = 0.8 * cm
            canvas.drawString(x_pos, y_pos, text)
            canvas.linkRect(
                "",
                toc_bookmark,
                (x_pos, y_pos, x_pos + text_width, y_pos + 8),
                relative=0,
            )

    # Build PDF
    doc.multiBuild(story, onFirstPage=on_first_page, onLaterPages=on_later_pages)
