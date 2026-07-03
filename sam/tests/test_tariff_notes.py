import unittest

from sam.tariff_notes import build_chapter_notes_index, build_chapter_titles_index


class _Chunk:
    def __init__(self, content: str) -> None:
        self.page_content = content


class TestTariffNotes(unittest.TestCase):
    def test_build_chapter_notes_from_chunks(self) -> None:
        chunks = [
            _Chunk(
                "Chapitre 42\nNotes.\n"
                "1.- Au sens du present Chapitre, le cuir naturel comprend egalement les cuirs chamoides.\n"
                "2.- Le present Chapitre ne comprend pas les vetements du n° 42.03."
            )
        ]
        index = build_chapter_notes_index(chunks)
        self.assertIn(42, index)
        self.assertGreaterEqual(len(index[42]), 1)

    def test_chapter_title_skips_tariff_position_lines(self) -> None:
        chunks = [
            _Chunk(
                "Chapitre 42\n"
                "Ouvrages en cuir; articles de voyage, sacs a main et contenants similaires\n"
                "4202.31.00.00 -- A surface exterieure en cuir naturel ou en cuir reconsti-"
            )
        ]
        index = build_chapter_titles_index(chunks)
        self.assertIn(42, index)
        self.assertIn("ouvrages en cuir", index[42].lower())
        self.assertNotIn("surface exterieure", index[42].lower())

    def test_chapter_title_skips_table_header_and_prefers_real_title(self) -> None:
        chunks = [
            _Chunk(
                "Chapitre 84\n"
                "Reacteurs nucleaires, chaudieres, machines, appareils et engins mecaniques\n"
            ),
            _Chunk(
                "Section XVI\nChapitre 84\n84.862/87\n395 F\nN° de\n"
                "position N.T.S. Designation des marchandises U.S. D.D. R.S.\n"
                "8404.90.00.00 - Parties kg 5 1"
            ),
        ]
        index = build_chapter_titles_index(chunks)
        self.assertIn(84, index)
        self.assertIn("reacteurs", index[84].lower())
        self.assertNotIn("n.t.s", index[84].lower())


if __name__ == "__main__":
    unittest.main()
