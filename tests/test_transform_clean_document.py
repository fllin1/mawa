"""Test for the clean_document method to verify paragraph modifications work correctly."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mawa.config import City
from mawa.etl.transform import Transform
from mawa.schemas.document_schema import Document, Page, Paragraph, Image, Dimensions


class TestCleanDocument(unittest.TestCase):
    """Test that clean_document correctly modifies paragraphs in place."""

    def setUp(self):
        """Create a temporary document with duplicate images for testing."""
        # Create a temporary directory for test files
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create test document data
        duplicate_image_b64 = "duplicate_base64_string"
        unique_image_b64 = "unique_base64_string"

        # Create images
        duplicate_image_1 = Image(
            name_img="img1.png",
            top_left_x=0,
            top_left_y=0,
            bottom_right_x=100,
            bottom_right_y=100,
            image_base64=duplicate_image_b64,
        )
        duplicate_image_2 = Image(
            name_img="img1.png",  # Same name
            top_left_x=0,
            top_left_y=0,
            bottom_right_x=100,
            bottom_right_y=100,
            image_base64=duplicate_image_b64,  # Same base64 (duplicate)
        )
        unique_image = Image(
            name_img="img2.png",
            top_left_x=0,
            top_left_y=0,
            bottom_right_x=100,
            bottom_right_y=100,
            image_base64=unique_image_b64,
        )

        # Create paragraphs with image references
        paragraph_with_image = Paragraph(
            index=1,
            content="This paragraph contains img1.png reference",
        )
        paragraph_with_image_only = Paragraph(
            index=2,
            content="img1.png",  # Only the image reference
        )
        paragraph_without_image = Paragraph(
            index=3,
            content="This paragraph has no image reference",
        )
        paragraph_with_multiple_refs = Paragraph(
            index=4,
            content="img1.png and some other text img1.png",
        )

        # Create pages
        page1 = Page(
            index=1,
            paragraphs=[
                paragraph_with_image,
                paragraph_with_image_only,
                paragraph_without_image,
            ],
            images=[duplicate_image_1, unique_image],
            dimensions=Dimensions(dpi=300, width=1000, height=1000),
        )

        page2 = Page(
            index=2,
            paragraphs=[paragraph_with_multiple_refs],
            images=[duplicate_image_2],
            dimensions=Dimensions(dpi=300, width=1000, height=1000),
        )

        # Create document
        self.test_doc = Document(
            pages=[page1, page2],
            name_of_document="test_document",
            date_of_document="2024-01-01",
            document_type="PLU",
            city=City.GRENOBLE.value,
            model_metadata={},
        )

        # Save to temporary file
        self.test_file = self.temp_dir / "test_document.json"
        with open(self.test_file, "w") as f:
            json.dump(self.test_doc.model_dump(), f, indent=2)

        # Store references for later verification
        self.paragraph_with_image = paragraph_with_image
        self.paragraph_with_image_only = paragraph_with_image_only
        self.paragraph_without_image = paragraph_without_image
        self.paragraph_with_multiple_refs = paragraph_with_multiple_refs

    def tearDown(self):
        """Clean up temporary directory."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_paragraphs_modified_in_place(self):
        """Test that paragraph.content modifications affect the original objects."""
        # Create Transform instance
        transform = Transform(City.GRENOBLE, Path("test_document"))
        # Override the file path to use our test file
        transform.file_path = self.test_file

        # Save our test document
        with open(self.test_file, "w") as f:
            json.dump(self.test_doc.model_dump(), f, indent=2)

        # Run clean_document
        result_path = transform.clean_document()

        # Reload the document
        with open(result_path, "r") as f:
            cleaned_doc_data = json.load(f)
        cleaned_doc = Document(**cleaned_doc_data)

        # Verify that paragraphs were modified correctly
        # Paragraph with image reference should have the reference removed
        page1_paragraphs = cleaned_doc.pages[0].paragraphs
        self.assertEqual(
            len(page1_paragraphs), 2
        )  # One empty paragraph should be removed

        # Find the paragraph that originally had the image
        # Pydantic converts dictionaries back to Paragraph objects
        remaining_paragraph = next(
            (p for p in page1_paragraphs if "This paragraph contains" in p.content),
            None,
        )
        self.assertIsNotNone(remaining_paragraph)
        self.assertNotIn("img1.png", remaining_paragraph.content)
        self.assertIn("This paragraph contains", remaining_paragraph.content)

        # Verify paragraph without image is still there
        paragraph_without = next(
            (p for p in page1_paragraphs if "no image reference" in p.content),
            None,
        )
        self.assertIsNotNone(paragraph_without)
        self.assertEqual(
            paragraph_without.content, "This paragraph has no image reference"
        )

        # Verify page2 paragraph with multiple references
        page2_paragraphs = cleaned_doc.pages[1].paragraphs
        self.assertEqual(len(page2_paragraphs), 1)
        self.assertNotIn("img1.png", page2_paragraphs[0].content)

    def test_duplicate_images_removed(self):
        """Test that duplicate images are removed from all pages."""
        transform = Transform(City.GRENOBLE, Path("test_document"))
        transform.file_path = self.test_file

        # Save our test document
        with open(self.test_file, "w") as f:
            json.dump(self.test_doc.model_dump(), f, indent=2)

        # Run clean_document
        result_path = transform.clean_document()

        # Reload the document
        with open(result_path, "r") as f:
            cleaned_doc_data = json.load(f)
        cleaned_doc = Document(**cleaned_doc_data)

        # Verify duplicate images are removed
        page1_images = cleaned_doc.pages[0].images
        page2_images = cleaned_doc.pages[1].images

        # Count images with duplicate base64
        # Pydantic converts dictionaries back to Image objects
        duplicate_b64 = "duplicate_base64_string"
        page1_duplicate_count = sum(
            1 for img in page1_images if img.image_base64 == duplicate_b64
        )
        page2_duplicate_count = sum(
            1 for img in page2_images if img.image_base64 == duplicate_b64
        )

        # Both duplicate images should be removed
        self.assertEqual(
            page1_duplicate_count, 0, "Page 1 should have no duplicate images"
        )
        self.assertEqual(
            page2_duplicate_count, 0, "Page 2 should have no duplicate images"
        )

        # Unique image should still be present
        unique_b64 = "unique_base64_string"
        page1_unique_count = sum(
            1 for img in page1_images if img.image_base64 == unique_b64
        )
        self.assertEqual(
            page1_unique_count, 1, "Page 1 should still have the unique image"
        )

    def test_empty_paragraphs_removed(self):
        """Test that paragraphs that become empty after image removal are deleted."""
        transform = Transform(City.GRENOBLE, Path("test_document"))
        transform.file_path = self.test_file

        # Save our test document
        with open(self.test_file, "w") as f:
            json.dump(self.test_doc.model_dump(), f, indent=2)

        # Run clean_document
        result_path = transform.clean_document()

        # Reload the document
        with open(result_path, "r") as f:
            cleaned_doc_data = json.load(f)
        cleaned_doc = Document(**cleaned_doc_data)

        # Verify that the paragraph containing only the image reference is removed
        page1_paragraphs = cleaned_doc.pages[0].paragraphs

        # Should have 2 paragraphs left (one with image removed, one without image)
        self.assertEqual(len(page1_paragraphs), 2)

        # None of the remaining paragraphs should be empty
        for paragraph in page1_paragraphs:
            self.assertTrue(paragraph.content.strip(), "No paragraph should be empty")


if __name__ == "__main__":
    unittest.main()
