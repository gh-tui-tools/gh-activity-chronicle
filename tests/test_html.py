"""Tests for markdown_to_html() and _inline_markdown() converters."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import load_chronicle_module  # noqa: E402

mod = load_chronicle_module()


class TestInlineMarkdown:
    """Tests for _inline_markdown() inline markup conversion."""

    def test_bold(self):
        assert mod._inline_markdown("**bold**") == "<strong>bold</strong>"

    def test_italic(self):
        assert mod._inline_markdown("*italic*") == "<em>italic</em>"

    def test_link(self):
        result = mod._inline_markdown("[text](https://example.com)")
        assert result == '<a href="https://example.com">text</a>'

    def test_bold_and_italic(self):
        result = mod._inline_markdown("**bold** and *italic*")
        assert "<strong>bold</strong>" in result
        assert "<em>italic</em>" in result

    def test_link_with_bold(self):
        result = mod._inline_markdown("**[text](https://example.com)**")
        assert "<strong>" in result
        assert '<a href="https://example.com">' in result

    def test_plain_text_unchanged(self):
        assert mod._inline_markdown("plain text") == "plain text"

    def test_multiple_links(self):
        result = mod._inline_markdown("[a](http://a) and [b](http://b)")
        assert '<a href="http://a">a</a>' in result
        assert '<a href="http://b">b</a>' in result

    def test_link_with_brackets_in_text(self):
        md = (
            "[[Editorial] Fixes terminology]"
            "(https://github.com/w3c/manifest/pull/1204)"
        )
        result = mod._inline_markdown(md)
        assert "https://github.com/w3c/manifest/pull/1204" in result
        assert "[Editorial] Fixes terminology" in result
        assert "<a href=" in result


class TestMarkdownToHtml:
    """Tests for markdown_to_html() document conversion."""

    def test_returns_complete_html_document(self):
        html = mod.markdown_to_html("# Hello")
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "</body>" in html

    def test_has_css_styles(self):
        html = mod.markdown_to_html("# Hello")
        assert "<style>" in html
        assert "font-family" in html

    def test_heading_levels(self):
        md = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
        html = mod.markdown_to_html(md)
        assert "<h1>H1</h1>" in html
        assert "<h2>H2</h2>" in html
        assert "<h3>H3</h3>" in html
        assert "<h4>H4</h4>" in html
        assert "<h5>H5</h5>" in html
        assert "<h6>H6</h6>" in html

    def test_horizontal_rule(self):
        html = mod.markdown_to_html("---")
        assert "<hr>" in html

    def test_table_basic(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = mod.markdown_to_html(md)
        assert "<table>" in html
        assert "</table>" in html
        assert "<th>A</th>" in html
        assert "<th>B</th>" in html
        assert "<td>1</td>" in html
        assert "<td>2</td>" in html

    def test_table_with_alignment(self):
        md = "| Left | Right |\n|:-----|------:|\n| a | b |"
        html = mod.markdown_to_html(md)
        assert "<th>Left</th>" in html
        assert "<td>a</td>" in html

    def test_bullet_list(self):
        md = "- item 1\n- item 2\n- item 3"
        html = mod.markdown_to_html(md)
        assert "<ul>" in html
        assert "</ul>" in html
        assert "<li>item 1</li>" in html
        assert "<li>item 2</li>" in html
        assert "<li>item 3</li>" in html

    def test_bullet_list_with_links(self):
        md = "- [link](http://example.com): description"
        html = mod.markdown_to_html(md)
        assert "<li>" in html
        assert '<a href="http://example.com">link</a>' in html

    def test_html_passthrough_details(self):
        md = (
            '<details name="test">\n'
            "<summary>Click me</summary>\n"
            "\nContent\n\n</details>"
        )
        html = mod.markdown_to_html(md)
        assert '<details name="test">' in html
        assert "<summary>Click me</summary>" in html
        assert "</details>" in html

    def test_html_passthrough_span(self):
        md = '<span id="my-id"></span>'
        html = mod.markdown_to_html(md)
        assert '<span id="my-id"></span>' in html

    def test_paragraph(self):
        html = mod.markdown_to_html("Some text here.")
        assert "<p>Some text here.</p>" in html

    def test_bold_in_paragraph(self):
        html = mod.markdown_to_html("**Period:** 2026-01-01 to 2026-01-07")
        assert "<strong>Period:</strong>" in html

    def test_blank_lines_close_elements(self):
        md = "| A |\n|---|\n| 1 |\n\n# Next"
        html = mod.markdown_to_html(md)
        assert "</table>" in html
        assert "<h1>Next</h1>" in html

    def test_list_then_heading(self):
        md = "- item\n\n## Heading"
        html = mod.markdown_to_html(md)
        assert "</ul>" in html
        assert "<h2>Heading</h2>" in html

    def test_heading_closes_table(self):
        """A heading immediately after table rows closes the table."""
        md = "| A |\n|---|\n| 1 |\n# Heading"
        html = mod.markdown_to_html(md)
        assert "</table>" in html
        assert "<h1>Heading</h1>" in html

    def test_html_passthrough_closes_table(self):
        """HTML passthrough lines close any open table."""
        md = "| A |\n|---|\n| 1 |\n<details>"
        html = mod.markdown_to_html(md)
        assert "</table>" in html
        assert "<details>" in html

    def test_table_after_list(self):
        """A table starting after a list closes the list."""
        md = "- item\n| A |\n|---|\n| 1 |"
        html = mod.markdown_to_html(md)
        assert "</ul>" in html
        assert "<table>" in html

    def test_paragraph_closes_table(self):
        """A regular paragraph line closes any open table."""
        md = "| A |\n|---|\n| 1 |\nSome text"
        html = mod.markdown_to_html(md)
        assert "</table>" in html
        assert "<p>Some text</p>" in html

    def test_paragraph_closes_list(self):
        """A regular paragraph line closes any open list."""
        md = "- item\nSome text"
        html = mod.markdown_to_html(md)
        assert "</ul>" in html
        assert "<p>Some text</p>" in html

    def test_html_passthrough_closes_list(self):
        """HTML passthrough lines close any open list."""
        md = "- item\n<details>"
        html = mod.markdown_to_html(md)
        assert "</ul>" in html
        assert "<details>" in html

    def test_unclosed_table_at_end(self):
        """Table still open at end of input gets closed."""
        md = "| A |\n|---|\n| 1 |"
        html = mod.markdown_to_html(md)
        assert html.count("<table>") == html.count("</table>")

    def test_unclosed_list_at_end(self):
        """List still open at end of input gets closed."""
        md = "- item"
        html = mod.markdown_to_html(md)
        assert html.count("<ul>") == html.count("</ul>")

    def test_heading_with_inline_html(self):
        """Heading containing HTML anchor tags."""
        md = '### <a id="my-anchor">Title</a>'
        html = mod.markdown_to_html(md)
        assert "<h3>" in html

    def test_full_report_conversion(self):
        """Convert a representative mini-report to HTML."""
        md = """# github activity chronicle: [alice](https://github.com/alice)

**Period:** 2026-01-01 to 2026-01-07

---

## Executive summary

| Metric | Count |
|--------|------:|
| Commits (default branches) | 42 |
| PRs created | 5 |

## Languages

| Language | Commits | Lines |
|----------|--------:|------:|
| Python | 30 | +1,000/-200 |

## PRs created

| Status | Count |
|--------|------:|
| Merged | 3 |
| Open | 1 |
| **Total** | **5** |

---

*Report generated on 2026-01-07.*"""
        html = mod.markdown_to_html(md)

        # Verify structure
        assert "<!DOCTYPE html>" in html
        assert "<h1>" in html
        assert "<h2>" in html
        assert "<table>" in html
        assert "<hr>" in html
        assert "<strong>" in html
        assert '<a href="https://github.com/alice">alice</a>' in html

    def test_hr_not_confused_with_table_separator(self):
        """--- outside a table should be <hr>, not a table separator."""
        md = "Some text\n\n---\n\nMore text"
        html = mod.markdown_to_html(md)
        assert "<hr>" in html
        assert "<table>" not in html

    def test_heading_closes_list(self):
        """A heading after list items closes the list."""
        md = "- item 1\n- item 2\n## Next Section"
        html = mod.markdown_to_html(md)
        assert "</ul>" in html
        assert "<h2>Next Section</h2>" in html

    def test_hr_closes_list(self):
        """A horizontal rule after list items closes the list."""
        md = "- item 1\n- item 2\n---"
        html = mod.markdown_to_html(md)
        assert "</ul>" in html
        assert "<hr>" in html

    def test_user_content_prefix_stripped(self):
        """user-content- prefix is stripped from fragment links."""
        md = '<a id="org-tc39"></a>\n- [link](#user-content-org-tc39)'
        html = mod.markdown_to_html(md)
        assert 'href="#org-tc39"' in html
        assert "user-content-" not in html

    def test_bullet_list_closes_table(self):
        """A bullet list item after table rows closes the table."""
        md = "| A |\n|---|\n| 1 |\n- item"
        html = mod.markdown_to_html(md)
        assert "</table>" in html
        assert "<ul>" in html
        assert "<li>item</li>" in html
