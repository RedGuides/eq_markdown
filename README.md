# eq_markdown

Python-Markdown extensions for RG/MQ Docs. 

## Install

```
pip install -e path/to/eq_markdown
```

`mkdocs.yml`:

```yaml
markdown_extensions:
  - eq_markdown.member
```

## `member` block

Documents one datatype member or TLO form.

```markdown
/// member | int HPDrain[string]
    label: HPDrain
Description, in Markdown.
///
```

- **type member** - After the `|`. A single word is a member with no type.
- **label** - (optional) TOC text and anchor. Defaults to the member.
- **attrs** - (optional) Attributes for the heading. See the
  [pymdownx.blocks docs](https://facelessuser.github.io/pymdown-extensions/extensions/blocks/).

Heading level is set automatically (one below the section above it). To fix it, use
`- eq_markdown.member: {level: 3}`.
