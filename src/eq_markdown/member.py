"""
`/// member | <type> <member>` block for datatype members and TLOs.

    /// member | int HPDrain[string]
    Description, in Markdown.
    ///
"""

import html
import re
import xml.etree.ElementTree as etree

from markdown import util
from markdown.blockprocessors import BlockProcessor
from markdown.extensions.toc import render_inner_html, slugify, strip_tags, unique
from markdown.treeprocessors import Treeprocessor
from pymdownx.blocks import BlocksExtension
from pymdownx.blocks.block import Block, type_multi, type_ranged_integer, type_string, type_string_in

HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
AUTO = "auto"
MEMBER_ATTR = "data-member-level"  # marks our headings until MemberHeadings has sized them
type_level = type_multi(type_string_in([AUTO]), type_ranged_integer(1, 6))


def anchor_for(label):
    """Link anchor for a member label, needed for the TOC links."""
    return re.sub(r"\s+", "-", label.strip())


class Member(Block):
    NAME = "member"
    ARGUMENT = True
    OPTIONS = {
        # TOC text, and the eventual #link.
        "label": ("", type_string),
        # by default there's also `attrs` for HTML attributes like css classes
    }

    def on_validate(self, parent):
        """Runs first, type is optional. `int Foo[a b]` has a type, `Foo[a b]` has none."""
        first, _, rest = self.argument.partition(" ")
        has_type = rest and "[" not in first
        if has_type:
            self.type_name, self.member = first, rest.strip()
        else:
            self.type_name, self.member = "", self.argument
        return True

    def on_markdown(self):
        # Allow paragraphs and lists where Blocks would otherwise parse <dd> as inline only.
        return "block"

    def on_create(self, parent):
        label = self.options["label"].strip() or self.member
        level = self.config["level"]
        # Auto starts at h3, MemberHeadings sets the real size once the page is built.
        tag = "h3" if level == AUTO else f"h{level}"
        heading = etree.SubElement(parent, tag, id=anchor_for(label))
        heading.set(MEMBER_ATTR, str(level))
        heading.set("data-toc-label", label)
        if self.type_name:
            # Left as Markdown for the parser to finish, e.g. [int][int]
            heading.text = f"[{self.type_name}][{self.type_name}] "
        # AtomicString: shown as written, never parsed as Markdown.
        etree.SubElement(heading, "code").text = util.AtomicString(self.member)
        self.heading = heading
        self.parent = parent

        # Return the <dl>, Blocks moves anything after it into the <dd>.
        dl = etree.SubElement(parent, "dl")
        self.dd = etree.SubElement(dl, "dd")
        return dl

    def on_add(self, block):
        return self.dd

    def on_end(self, block):
        # Blocks applies `attrs` to the returned <dl>, but they're meant for the heading.
        self.heading.attrib.update(block.attrib)
        block.attrib.clear()

        dd = self.dd
        if not len(dd):
            # No description, no <dl>.
            self.parent.remove(block)
        elif len(dd) == 1 and dd[0].tag == "p":
            # A one-paragraph description drops its <p> wrapper, so no space under the heading.
            p = dd[0]
            # Move the paragraph's text and its inline elements (<code>, <em>...) up into the description.
            dd.text = p.text
            dd[:] = list(p)


class MemberHeadings(Treeprocessor):
    """Now that we know every section and ID, give each member a heading size and unique link."""

    def run(self, root):
        section_level = 2  # no heading yet: act as if under an h2, so members are h3
        section = None  # the ordinary heading we are under
        seen = set()  # member ids used so far
        headings = [el for el in root.iter() if el.tag in HEADINGS]
        for heading in headings:
            member_level = heading.attrib.pop(MEMBER_ATTR, None)
            if member_level is None:  # ordinary heading. Members below take their size and prefix from it
                section_level, section = int(heading.tag[1]), heading
                continue
            if member_level == AUTO:
                heading.tag = f"h{min(section_level + 1, 6)}"
            member_id = heading.attrib["id"]
            if member_id in seen:
                # unique() adds _1 if the prefixed id is taken too.
                heading.set("id", unique(self.prefix(section) + member_id, seen))
            else:
                seen.add(member_id)

    def prefix(self, section):
        """The heading's name, to put in front of a repeated link e.g. spawn- """
        if section is None:
            return ""  # toc's `_1` instead
        text = strip_tags(render_inner_html(section, self.md))  # visible text, not Markdown's HTML placeholders
        name = section.get("id") or slugify(html.unescape(text), "-")
        return name + "-"


class DefListIndent(BlockProcessor):
    """Lets a member sit in a definition list."""

    def test(self, parent, block):
        procs = self.parser.blockprocessors
        return "defindent" in procs and block.lstrip(" ").startswith("///") and procs["defindent"].test(parent, block)

    def run(self, parent, blocks):
        # Join the indented chunks that follow, Blocks only finds the closing /// when it gets them together.
        tab = " " * self.tab_length
        chunks = [blocks.pop(0)]
        while blocks and blocks[0].startswith(tab):
            chunks.append(blocks.pop(0))
        blocks.insert(0, "\n\n".join(chunks))
        self.parser.blockprocessors["defindent"].run(parent, blocks)


class MemberExtension(BlocksExtension):
    def __init__(self, level=AUTO):
        """`level`: heading size 1-6, or "auto" to sit one below the heading above."""
        super().__init__()
        self.level = type_level(level)

    def extendMarkdownBlocks(self, md, block_mgr):
        block_mgr.register(Member, {"level": self.level})
        # Before Blocks (blocks, 89.99) and def_list's own indent (defindent, 85).
        md.parser.blockprocessors.register(DefListIndent(md.parser), "member_deflist_indent", 89.995)
        # Resize headings after ids. e.g. `## Spawn {#spawn}` which are (attr_list, 8) yet before the contents (toc, 5).
        md.treeprocessors.register(MemberHeadings(md), "member_headings", 7)


makeExtension = MemberExtension
