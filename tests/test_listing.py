"""Store-description/package checks; stdlib only, no network or HA changes."""
import json
from pathlib import Path
import re
import struct
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/philipp-builder/ha-garten-bewaesserung-integration"
RAW = "https://raw.githubusercontent.com/philipp-builder/ha-garten-bewaesserung-integration"


class ListingTests(unittest.TestCase):
    def test_newcomer_first_structure(self):
        readme = (ROOT / "README.md").read_text()
        headings = re.findall(r"^## (.+)$", readme, re.M)
        self.assertEqual(headings[:3], [
            "Passt das zu deinem Garten?", "Was du brauchst",
            "Installation und erster Kreis",
        ])
        self.assertNotIn("v1.10", readme.split("## Installation")[0])
        self.assertIn("Release Notes", readme)
        self.assertTrue(json.loads((ROOT / "hacs.json").read_text())["render_readme"])

    def test_public_description_links_resolve_in_checkout(self):
        readme = (ROOT / "README.md").read_text()
        links = re.findall(r"\]\(([^)]+)\)", readme)
        links += re.findall(r'src="([^"]+)"', readme)
        self.assertTrue(links)
        for url in links:
            with self.subTest(url=url):
                self.assertEqual(urlsplit(url).scheme, "https")
                for prefix in (REPO + "/blob/main/", RAW + "/main/"):
                    if url.startswith(prefix):
                        self.assertTrue((ROOT / url[len(prefix):]).is_file())
        self.assertIn(RAW + "/main/assets/icon.png", links)

    def test_packaged_icons_are_original_correct_size(self):
        for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
            with self.subTest(name=name):
                image = (ROOT / "custom_components/garten_bewaesserung/brand" / name).read_bytes()
                self.assertEqual(image, (ROOT / "assets" / name).read_bytes())
                self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(struct.unpack(">II", image[16:24]), (size, size))

    def test_preserved_pause_guide_links(self):
        guide = ROOT / "docs/PAUSES.md"
        content = guide.read_text()
        self.assertIn("## Bodensensoren im Winter", content)
        self.assertIn("## Urlaub und Winterpause", content)
        for link in re.findall(r"\]\(([^)]+)\)", content):
            self.assertTrue((guide.parent / link).is_file(), link)


if __name__ == "__main__":
    unittest.main()
