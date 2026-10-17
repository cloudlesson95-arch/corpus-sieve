"""Add deterministic synthetic problem documents to data/raw/.

Each document has one problem, and data/raw/_expected.json names the check
that should catch it. The texts are written for this project (no network);
the two duplicates copy articles from the Wikipedia snapshot, whose ids sort
before "synthetic-" so the corpus checks keep the originals.

Usage: uv run python -m pipeline.make_messy   (after pipeline.fetch)
"""

import re

import ftfy.bad_codecs  # noqa: F401  registers the sloppy-windows-1252 codec

from pipeline.files import EXPECTED_PATH, RAW_DIR, read_json, write_json

SYNTHETIC_LICENSE = "CC0 1.0 (synthetic test document)"

MOLTEN_SALT = (
    "Molten-salt storage lets a solar tower keep working after sunset. The plant’s two tanks "
    "hold a nitrate mixture: the “cold” tank sits at about 290 °C, while the “hot” tank reaches "
    "565 °C. During the day, mirrors focus sunlight on the receiver – a dark, heat-absorbing tube "
    "bundle – and the salt flows through it. At night, the hot salt passes a heat exchanger, makes "
    "steam, and drives a turbine. Operators in Andalucía and Chile report storage of 7–15 hours, "
    "which smooths the evening peak. Engineers still worry about freezing: below roughly 220 °C "
    "the salt solidifies, so pipes need trace heating… and a careful start-up procedure."
)

CABLE_REPAIR = (
    "Repairing an export cable at sea is slow and expensive. When a fault appears, the operator’s "
    "first job is to locate it – usually with time-domain reflectometry from the onshore end – "
    "before a cable-repair vessel can be booked. The crew lifts the damaged section, cuts it out, "
    "and splices in a new length with two “universal” joints; each joint can take 3–4 days in good "
    "weather. Because the repaired cable is now longer, it is laid in an “omega” loop on the "
    "seabed. Insurers in Denmark, Germany and the Netherlands report that cable faults cause "
    "around 80 % of offshore wind insurance claims – far more than turbine failures."
)

BOILERPLATE_PAGE = """Skip to main content
Home | Products | Solutions | About us | Contact
Menu
Search
Sign in
We use cookies to improve your experience. By continuing to browse you agree to our use of cookies.
Accept all cookies
Manage cookie preferences
Reject non-essential cookies
Heat pumps explained
An air-source heat pump moves heat from outdoor air into a building instead of burning fuel to make it. \
A refrigerant absorbs heat in the outdoor coil, a compressor raises its temperature, and an indoor coil \
releases that heat into radiators or air ducts. For every unit of electricity, a well-installed unit \
delivers three to four units of heat, which is why heat pumps are central to decarbonising homes.
Share on Facebook | Share on X | Share on LinkedIn
Subscribe to our newsletter
Follow us
Privacy policy | Terms of use | Cookie policy
© 2026 Example Energy Ltd. All rights reserved.
Home | Products | Solutions | About us | Contact
Back to top"""

GERMAN = (
    "Windenergie ist heute eine der wichtigsten Quellen für erneuerbaren Strom in Europa. Moderne "
    "Windkraftanlagen an Land erreichen Nabenhöhen von über 150 Metern und Rotordurchmesser von "
    "mehr als 160 Metern. Je höher die Anlage, desto gleichmäßiger und stärker weht der Wind, und "
    "desto mehr Strom kann sie erzeugen. Auf See sind die Bedingungen noch besser, allerdings sind "
    "Bau und Wartung der Fundamente deutlich teurer. Ein großes Problem bleibt die schwankende "
    "Einspeisung: Wenn der Wind nachlässt, müssen Speicher, flexible Kraftwerke oder Stromimporte "
    "die Lücke schließen. Deshalb gehören Netzausbau und Speicher zu den zentralen Aufgaben der "
    "Energiewende."
)

DIRECT_USE_GEOTHERMAL = (
    "Direct-use geothermal systems skip electricity generation entirely and pipe warm water "
    "straight to where heat is needed. Towns in volcanic regions run district heating networks "
    "from wells only a few hundred metres deep, greenhouses use the water to grow vegetables "
    "through the winter, and some spas and fish farms rely on it all year. Because the water does "
    "not need to be hot enough to drive a turbine, direct use works with much cooler resources "
    "than a power plant, and the conversion losses are small."
)

# Fake contact details: example.com/.org domains and 555 numbers are reserved for fiction.
SITE_VISIT = (
    "Notes from the site visit to the community solar cooperative on the old landfill. The array "
    "has 1,200 panels on fixed ground mounts and feeds a shared meter that splits credits between "
    "140 member households. Members asked how winter output compares with summer; the operator "
    "expects roughly a quarter of the July yield in December. For questions about membership, "
    "contact the coordinator at alex.morgan@example.com or call (555) 014-2290. Maintenance "
    "requests go to field-team@example.org, and the emergency line is +1 555 019 7731. The next "
    "open day is planned for the spring, when the new battery cabinet should be commissioned and "
    "visitors can see the inverter room."
)

MICROGRID_HTML = """<!DOCTYPE html><html><head><style>.nav{color:#333}</style>
<script>window.dataLayer=window.dataLayer||[];</script></head><body>
<div class="article"><h2>Microgrids</h2>
<p>A <b>microgrid</b> is a local group of generators, batteries and loads that can run connected
to the main grid or on its own as an &ldquo;island&rdquo;.</p>
<p>Hospitals, military bases and remote villages use microgrids so that the lights stay on when
the wider network fails.&nbsp;A controller decides when to import power, when to export it and
when to disconnect.</p>
<!-- legacy layout -->
<p>Solar panels and batteries are the most common building blocks, often with a diesel or gas
generator as backup.<br/>Falling battery prices have made <i>island mode</i> practical for many
more sites over the last decade.</p>
</div></body></html>"""

REFERENCES_ONLY = """== See also ==
Grid energy storage
List of energy storage power plants

== References ==
Smith, J. (2019). "Storage at scale". Journal of Power Systems. 12 (3): 45–60.
Lee, K.; Patel, R. (2021). Batteries for the Grid. Example Press.

== External links ==
Energy storage overview (archived)"""


def synthetic(kind: str, title: str, text: str) -> dict:
    return {
        "id": f"synthetic-{kind}", "title": title, "source": "synthetic",
        "url": f"https://example.org/synthetic/{kind}", "license": SYNTHETIC_LICENSE, "text": text,
    }


def lightly_edit(text: str) -> str:
    """Drop the second paragraph and reword a few phrases."""
    paragraphs = text.split("\n\n")
    del paragraphs[1]
    edited = "\n\n".join(paragraphs)
    for old, new in [("rotor", "spinning rotor"), ("system", "installation"), ("high", "very high")]:
        edited = edited.replace(old, new, 2)
    return edited


def build_documents() -> list[tuple[dict, str, str]]:
    """Return (document, expected failing check, problem description) triples."""
    pumped = read_json(RAW_DIR / "pumped-storage-hydroelectricity.json")
    flywheel = read_json(RAW_DIR / "flywheel-energy-storage.json")

    duplicate = {**pumped, "id": "synthetic-exact-duplicate", "source": "synthetic"}
    near = {
        **flywheel, "id": "synthetic-near-duplicate", "source": "synthetic",
        "title": "Flywheel energy storage (mirror copy)",
        "url": "https://example.org/mirror/flywheel-energy-storage",
        "text": lightly_edit(flywheel["text"]),
    }
    no_title = synthetic("missing-title", "", DIRECT_USE_GEOTHERMAL)
    del no_title["title"]

    stub = "Solar panels turn sunlight into electricity. This page is a stub and will be expanded with more details soon, thanks."
    return [
        (duplicate, "exact_duplicate", "Exact copy of the Pumped-storage hydroelectricity article"),
        (near, "near_duplicate", "Flywheel energy storage with a paragraph dropped and a few words changed"),
        (synthetic("empty", "Empty page", ""), "min_length", "Empty document"),
        (synthetic("stub", "Solar panels", stub), "min_length", "A 20-word stub"),
        (synthetic("mojibake", "Molten-salt storage", MOLTEN_SALT.encode("utf-8").decode("sloppy-windows-1252")),
         "mojibake", "UTF-8 text decoded as Windows-1252"),
        (synthetic("replacement-chars", "Export cable repair", re.sub(r"[^\x00-\x7f]", "�", CABLE_REPAIR)),
         "mojibake", "Every non-ASCII character lost to U+FFFD replacement characters"),
        (synthetic("boilerplate", "Heat pumps explained", BOILERPLATE_PAGE), "boilerplate",
         "Cookie banner, navigation and footer around one paragraph"),
        (synthetic("non-english", "Windenergie", GERMAN), "language", "German article"),
        (no_title, "schema", "Document without a title field"),
        (synthetic("pii", "Community solar co-op: site visit notes", SITE_VISIT), "pii",
         "Fake email addresses and phone numbers (flagged, not quarantined)"),
        (synthetic("html-litter", "Microgrids", MICROGRID_HTML), "markup",
         "HTML page source with tags, entities, script and style"),
        (synthetic("references-only", "Energy storage (reading list)", REFERENCES_ONLY), "min_length",
         "Only Wikipedia 'See also' and 'References' sections, nothing left after cleaning"),
    ]


def main() -> None:
    expected = {}
    for doc, check, problem in build_documents():
        write_json(RAW_DIR / f"{doc['id']}.json", doc)
        expected[doc["id"]] = {"check": check, "problem": problem}
    write_json(EXPECTED_PATH, expected)
    print(f"wrote {len(expected)} synthetic documents and {EXPECTED_PATH.name}")


if __name__ == "__main__":
    main()
