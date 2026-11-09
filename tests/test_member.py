import re

import markdown
import pytest

from eq_markdown.member import anchor_for

# The extensions the RedGuides and MacroQuest sites use, minus theme ones.
EXTENSIONS = [
    "eq_markdown.member",
    "toc",
    "attr_list",
    "def_list",
    "md_in_html",
    "admonition",
    "pymdownx.details",
    "pymdownx.superfences",
    "pymdownx.betterem",
]
CONFIGS = {"toc": {"permalink": True}, "pymdownx.betterem": {"smart_enable": "all"}}

# The reference links at the bottom of a members page.
LINKREFS = (
    "\n\n[int]: ../datatype-int.md\n[bool]: ../datatype-bool.md\n[string]: ../datatype-string.md\n"
    "[spawn]: ../datatype-spawn.md\n[debuff]: datatype-debuff.md\n"
)


def render(src, configs=None):
    md = markdown.Markdown(extensions=EXTENSIONS, extension_configs={**CONFIGS, **(configs or {})})
    return md.convert(src), md


def toc_flat(md):
    """(id, name, level) for every TOC entry, in document order."""
    out = []

    def walk(tokens):
        for t in tokens:
            out.append((t["id"], t["name"], t["level"]))
            walk(t["children"])

    walk(md.toc_tokens)
    return out


def legacy(name, type=None, params=None, toc_label=None):
    """The renderMember macro from readguides main.py."""
    type_str = "_varies_" if type == "varies" else f"[{type}][{type}]" if type else ""
    params_str = f"[{params}]" if params else ""
    toc_label = toc_label if toc_label is not None else f"{name}{params_str}"
    anchor = re.sub(r"\s+", "-", toc_label)
    return f"### {type_str} `{name}{params_str}` {{ #{anchor} data-toc-label='{toc_label}' }}"


def block(arg, body="", options=()):
    return f"/// member | {arg}\n" + "".join(f"    {o}\n" for o in options) + f"{body}\n///"


def test_anchor_for():
    assert anchor_for("HPDrain[string]") == "HPDrain[string]"
    assert anchor_for("Debuff[spell id ...]") == "Debuff[spell-id-...]"
    assert anchor_for("To string") == "To-string"


def test_heading_and_toc():
    html, md = render("## Members\n\n" + block("Debuff Debuff[spell id ...]", "A list.") + LINKREFS)
    assert (
        '<h3 id="Debuff[spell-id-...]"><a href="datatype-debuff.md">Debuff</a> <code>Debuff[spell id ...]</code>'
        '<a class="headerlink" href="#Debuff[spell-id-...]" title="Permanent link">&para;</a></h3>\n'
        "<dl>\n<dd>A list.</dd>\n</dl>"
    ) in html
    assert toc_flat(md) == [("members", "Members", 2), ("Debuff[spell-id-...]", "Debuff[spell id ...]", 3)]


def test_member_is_never_parsed_as_markdown():
    html, _ = render(
        "## Members\n\n"
        + block("spawn SpawnSort[<n>,<asc|desc>,<member>]", "d")
        + "\n\n"
        + block("int Foo[string]", "e.g. `${Debuff[self].Slowed}` and *emph*")
        + LINKREFS
    )
    assert 'id="SpawnSort[&lt;n&gt;,&lt;asc|desc&gt;,&lt;member&gt;]"' in html
    assert "<code>SpawnSort[&lt;n&gt;,&lt;asc|desc&gt;,&lt;member&gt;]</code>" in html
    assert "<code>Foo[string]</code>" in html  # [string] is a defined reference; must not become a link
    assert "<dd>e.g. <code>${Debuff[self].Slowed}</code> and <em>emph</em></dd>" in html


def test_body_shapes():
    html, _ = render(
        "## Members\n\n"
        + block("int A", "one paragraph")
        + "\n\n"
        + block("int B", "para one\n\npara two")
        + "\n\n"
        + block("int C", "* No index= HP lost\n* string= counters")
        + "\n\n"
        + block("int D", "")
        + "\n\n"
        + block("int E", "text\n\n```\ncode\n```")
        + LINKREFS
    )
    assert "<dl>\n<dd>one paragraph</dd>\n</dl>" in html
    assert "<dl>\n<dd>\n<p>para one</p>\n<p>para two</p>\n</dd>\n</dl>" in html
    assert "<dl>\n<dd>\n<ul>\n<li>No index= HP lost</li>\n<li>string= counters</li>\n</ul>\n</dd>\n</dl>" in html
    assert '<h3 id="D">' in html and "<dl>\n<dd></dd>\n</dl>" in html
    assert re.search(r'<dd>\n<p>text</p>\n<div class="highlight"><pre>.*?<code>code\n</code></pre></div>\n</dd>', html)


def test_unresolved_type_and_missing_argument():
    html, _ = render(block("mystery Foo", "d") + "\n\n/// member |\nbody\n///")
    assert "[mystery][mystery] <code>Foo</code>" in html  # same as the macro
    assert "/// member |" in html


def test_untyped_member():
    html, md = render("## Members\n\n" + block("Activate", "d") + "\n\n" + block("Move[X, Y, Width, Height]", "d"))
    assert '<h3 id="Activate"><code>Activate</code>' in html
    assert '<h3 id="Move[X,-Y,-Width,-Height]"><code>Move[X, Y, Width, Height]</code>' in html
    assert toc_flat(md)[2] == ("Move[X,-Y,-Width,-Height]", "Move[X, Y, Width, Height]", 3)


def test_varies_is_an_ordinary_type():
    html, _ = render(block("varies Variable", "d") + "\n\n[varies]: ../../macros/variables.md")
    assert '<a href="../../macros/variables.md">varies</a> <code>Variable</code>' in html


def test_level_auto():
    """One below the last section heading; member headings do not count; h3 when none."""
    src = (
        "# Page\n\n" + block("int A", "d") + "\n\n"
        "## Members\n\n"
        + block("int B", "d")
        + "\n\n"
        + block("int C", "d")
        + "\n\n"
        "### [Debuff](x.md)\n\n" + block("int D", "d") + "\n\n"
        "###### Deepest\n\n" + block("int E", "d") + LINKREFS
    )
    html, md = render(src)
    assert [(t[0], t[2]) for t in toc_flat(md)] == [
        ("page", 1),
        ("A", 2),
        ("members", 2),
        ("B", 3),
        ("C", 3),
        ("debuff", 3),
        ("D", 4),
        ("deepest", 6),
        ("E", 6),
    ]
    assert '<h3 id="A">' in render(block("int A", "d"))[0]

    # A heading with data-toc-label is still a section.
    html, _ = render("## Forms\n\n### Custom { data-toc-label='C' }\n\n" + block("int A", "d"))
    assert '<h4 id="A">' in html


def test_repeated_ids_get_their_section_prefix():
    """The datatypes index page has many `Name` members; each TOC entry must reach its own."""
    src = (
        "## Spawns\n\n"
        "### [spawn](datatype-spawn.md)\n\n" + block("string Name", "a") + "\n\n" + block("int ID", "b") + "\n\n"
        "### [`Achievement`](datatype-achievement.md)\n\n" + block("string Name", "c") + "\n\n"
        "### [group](datatype-group.md)\n\n" + block("string Name", "d") + LINKREFS
    )
    html, md = render(src)
    assert [(t[0], t[1]) for t in toc_flat(md)] == [
        ("spawns", "Spawns"),
        ("spawn", "spawn"),
        ("Name", "Name"),  # the first keeps its id
        ("ID", "ID"),
        ("achievement", "Achievement"),
        ("achievement-Name", "Name"),
        ("group", "group"),
        ("group-Name", "Name"),
    ]
    assert '<h4 id="achievement-Name">' in html and 'href="#achievement-Name"' in html
    assert html.count('id="Name"') == 1


def test_repeated_id_edge_cases():
    # No section before it: toc's `_1`.
    html, _ = render(block("int A", "a") + "\n\n" + block("int A", "b"))
    assert '<h3 id="A">' in html and '<h3 id="A_1">' in html

    # Two sections with the same title.
    _, md = render(
        "### [`DisplayItem`](a.md)\n\n" + block("item DisplayItem", "a") + "\n\n"
        "### [`DisplayItem`](b.md)\n\n" + block("item DisplayItem", "b")
    )
    assert [t[0] for t in toc_flat(md)] == ["displayitem", "DisplayItem", "displayitem_1", "displayitem-DisplayItem"]

    # A section's explicit id is the prefix.
    html, _ = render("## Members { #m }\n\n" + block("int A", "a") + "\n\n" + block("int A", "b"))
    assert re.findall(r'<h3 id="([^"]+)"', html) == ["A", "m-A"]

    # inlinehilite stashes a section's `code`; the prefix uses its text.
    md = markdown.Markdown(extensions=EXTENSIONS + ["pymdownx.inlinehilite"], extension_configs=CONFIGS)
    html = md.convert("### [`AutoLogin`](a.md)\n\n" + block("int A", "a") + "\n\n" + block("int A", "b"))
    assert '<h4 id="autologin-A">' in html

    # Pinned levels too.
    html, _ = render("## S\n\n" + block("int A", "a") + "\n\n" + block("int A", "b"), {"eq_markdown.member": {"level": 4}})
    assert '<h4 id="A">' in html and '<h4 id="s-A">' in html


def test_attrs_go_on_the_heading():
    html, _ = render(block("int A", "d", ["attrs: {class: special}"]))
    assert '<h3 class="special" id="A">' in html and "<dl>\n<dd>d</dd>\n</dl>" in html


def test_level_config():
    html, _ = render("### Sub\n\n" + block("int A", "d"), {"eq_markdown.member": {"level": 3}})
    assert '<h3 id="A">' in html
    with pytest.raises(ValueError):
        render("x", {"eq_markdown.member": {"level": 9}})


def test_nested():
    """rg_hooks puts members inside `??? info`, gen_pages inside `<div markdown="1">`, tlo pages under `:   <h3>`."""
    src = (
        "## Inherited\n\n"
        '??? info "Inherited members"\n\n    ### Inherited from spawn\n\n'
        "    /// member | int Level\n    the level\n    ///\n\n"
        '<div class="indent" markdown="1">\n\n### [Debuff](x.md)\n\n'
        "/// member | int Count\ncount\n///\n\n</div>\n\n"
        "## [Debuff](datatype-debuff.md)\ndesc\n:    <h3>Members</h3>\n"
        "    /// member | int Rooted\n    rooted\n    ///\n" + LINKREFS
    )
    html, md = render(src)
    assert '<h4 id="Level">' in html and "<dd>the level</dd>" in html
    assert '<h4 id="Count">' in html and "<dd>count</dd>" in html
    assert '<h3 id="Rooted">' in html and "<dd>rooted</dd>" in html
    assert {"Level", "Count", "Rooted"} <= {t[0] for t in toc_flat(md)}


# Same output as renderMember

CASES = [
    ("Poisoned", "int", None, None, "*#* of poison counters on you"),
    ("HPDrain", "int", "string", None, "* No index= Amount of HP lost per tick\n* string= Disease, Poison, Curse"),
    ("Debuff", "bool", None, None, "True if you have debuffs"),
    ("Debuff", "Debuff", "self", None, "e.g. `${Debuff[self].Slowed}`"),
    ("Debuff[pet|warder]", "Debuff", None, None, ""),
    ("Debuff", "Debuff", "spell id ...", None, "a list, `${Debuff[5682 2899 887].Slowed}`"),  # the macro crashes Markdown 3.11.3
    ("To string", "string", None, None, "text"),
    ("SetText", None, "Text", None, "no type"),
    ("If", "string", "conditions,whentrue,whenfalse", "If", "toc_label override"),
    ("Flag", "int", "#", None, "hash"),
    ("Search", "int", "#, search", None, "hash comma space"),
    ("Key", "string", "opt: Name", None, "colon space"),
    ("Pos", "int", "y, x", None, "comma space"),
    ("Items[#].Name", "string", None, None, "dot"),
    ("SpawnSort", "spawn", "<n>,<asc|desc>,<member>", None, "angle brackets"),
    ("Multi", "int", None, None, "para one\n\n    para two"),
]


@pytest.mark.parametrize("name, type, params, toc_label, desc", CASES)
def test_identical_to_the_macro(name, type, params, toc_label, desc):
    old_html, old_md = render(f"## Members\n\n{legacy(name, type, params, toc_label)}\n\n:   {desc}\n{LINKREFS}")
    member = f"{name}[{params}]" if params else name
    arg = f"{type} {member}" if type else member
    options = [f"label: {toc_label}"] if toc_label else []
    body = desc.replace("\n    ", "\n")
    new_html, new_md = render(f"## Members\n\n{block(arg, body, options)}\n{LINKREFS}")

    if f"[{params}]:" in LINKREFS:
        # The macro breaks: `[string]` inside its `{ #... }` becomes a link and the attributes leak into the heading.
        assert f'<h3 id="{member}">' in new_html
        assert "data-toc-label" in old_html and f'id="{member}"' not in old_html
        assert toc_flat(new_md)[1][0] == member
        return

    # The macro leaves `<n>` unescaped in the id, the block escapes it.
    def unescape(h):
        return h.replace("&lt;", "<").replace("&gt;", ">")

    assert unescape(new_html) == unescape(old_html)
    if "<" in (params or ""):
        # The macro's TOC id has stash placeholders in it.
        assert toc_flat(new_md)[1][0] == f"{name}[{params}]" and "wzxhzdk" in toc_flat(old_md)[1][0]
    else:
        assert toc_flat(new_md) == toc_flat(old_md)
