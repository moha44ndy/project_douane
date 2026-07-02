import unittest

from sam.tariff_metadata import (
    get_full_chapter_name,
    get_full_section_name,
    get_position_heading,
)


class TestTariffMetadata(unittest.TestCase):
    def test_section_viii_full_title(self) -> None:
        title = get_full_section_name("VIII")
        self.assertIn("pelleteries", title.lower())
        self.assertIn("sacs a main", title.lower())
        self.assertIn("boyaux", title.lower())

    def test_chapter_42_full_title(self) -> None:
        from sam.tariff_notes import set_chapter_titles_index

        set_chapter_titles_index(
            {
                42: (
                    "Ouvrages en cuir; articles de bourrellerie ou de sellerie; "
                    "articles de voyage, sacs a main et contenants similaires; ouvrages en boyaux"
                )
            }
        )
        title = get_full_chapter_name(42)
        self.assertIn("ouvrages en cuir", title.lower())
        self.assertIn("sacs a main", title.lower())

    def test_position_heading_from_tec_index(self) -> None:
        from sam.tariff_labels import build_tariff_label_index, set_tariff_label_index

        sample = type(
            "Doc",
            (),
            {"page_content": "4202.31.00.00 -- Sacs a main en cuir kg 20 1"},
        )()
        set_tariff_label_index(build_tariff_label_index([sample]))
        title = get_position_heading("4202.31.00.00")
        self.assertIn("cuir", title.lower())


if __name__ == "__main__":
    unittest.main()
