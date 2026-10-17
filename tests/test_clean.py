from pipeline.clean import (
    clean_text,
    collapse_whitespace,
    fix_encoding,
    normalize_headings,
    remove_boilerplate,
    strip_html,
    strip_wiki_leftovers,
)


def test_fix_encoding_repairs_mojibake():
    assert fix_encoding("cafÃ© at 565 Â°C") == "café at 565 °C"


def test_strip_html_drops_scripts_comments_and_decodes_entities():
    out = strip_html("<script>x=1</script><p>Wind &amp; solar</p><!-- note -->")
    assert out.strip() == "Wind & solar"


def test_strip_wiki_leftovers_cuts_reference_tail_and_markers():
    text = "Body text.[1] More.[edit]\n\n== See also ==\nOther article\n\n== References ==\nA book."
    assert strip_wiki_leftovers(text).strip() == "Body text. More."


def test_strip_wiki_leftovers_keeps_only_formula_latex():
    text = "Here \n  \n    \n        m\n    \n    {\\displaystyle m}\n  \n is the mass."
    assert collapse_whitespace(strip_wiki_leftovers(text)) == "Here m is the mass."


def test_normalize_headings_turns_wiki_headings_into_markdown():
    assert normalize_headings("== History ==\ntext\n=== Early days ===") == "## History\ntext\n### Early days"


def test_remove_boilerplate_keeps_prose():
    text = (
        "Accept all cookies\nHome | About | Contact\n"
        "Wind turbines convert kinetic energy into electricity.\nHome | About | Contact"
    )
    assert remove_boilerplate(text) == "Wind turbines convert kinetic energy into electricity."


def test_clean_text_records_characters_removed_per_step():
    raw = "<p>Solar&nbsp;power</p>\n\n\n\nAccept all cookies"
    cleaned, removed = clean_text(raw)
    assert cleaned == "Solar power"
    assert sum(removed.values()) == len(raw) - len(cleaned)
    assert removed["strip_html"] > 0
    assert removed["remove_boilerplate"] > 0
