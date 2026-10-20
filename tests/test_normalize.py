from nepali_eval.normalize import (
    classify_script,
    extract_numbers,
    normalize_text,
    script_stats,
)


def test_digits_and_danda_unified():
    assert normalize_text("भोलि १० बजे।") == normalize_text("भोलि 10 बजे.")


def test_zero_width_removed_and_nfc():
    assert normalize_text("क्‍ष") == normalize_text("क्ष")
    # decomposed nukta (क + ़) equals the composition-excluded precomposed U+0958
    assert normalize_text("क़") == normalize_text("क़")


def test_case_and_whitespace():
    assert normalize_text("  Hello   WORLD ") == "hello world"


def test_does_not_merge_real_spelling_variants():
    # chandrabindu vs anusvara may be a genuine spelling difference: kept distinct
    assert normalize_text("काठमाडौँ") != normalize_text("काठमाडौं")


def test_extract_numbers_mixed_digit_systems():
    assert extract_numbers("२०८२ सालमा 1,500 रुपैयाँ") == ["2082", "1500"]
    assert extract_numbers("३.५ किलो") == ["3.5"]


def test_script_classification():
    assert classify_script("नेपाली भाषा") == "devanagari"
    assert classify_script("Nepali language") == "latin"
    assert classify_script("Meeting को लागि office") == "mixed"
    assert classify_script("१२३ !!") == "empty"
    assert script_stats("")["letters"] == 0


def test_devanagari_marks_counted_as_devanagari():
    s = script_stats("कृपया")  # contains vowel signs / virama (category M)
    assert s["devanagari"] == 1.0
