#!/usr/bin/env python3
"""DOCXTEXT - the one way the engine reads text out of a .docx (v0.8, code audit H1).

Every checker (audit_claims, verify_resume, keywords, consistency, intake) used to read `doc.paragraphs` only. Text in
table cells, headers, footers and text boxes was invisible to the honesty audit, so a forbidden claim placed there passed.
This module returns EVERY paragraph the reader of the printed page would see, in page order, and tags where it came from.

    paragraphs(path_or_doc) -> [(paragraph, where)]   where in: body, table, header, footer, textbox
    text(path_or_doc)       -> one string, all channels, newline-separated
    kind(path_or_doc)       -> "resume" | "cv" | "letter" | None   (the stamp written by resume_builder / stamp_letter)

Document kind stamp: `core_properties.subject` holds "jobkit:resume", "jobkit:cv" or "jobkit:letter". A .docx with no
stamp is audited as a resume (the strict path) - a document never fails the audit for being mislabelled, only for content.
"""
import os
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

KINDS = ("resume", "cv", "letter")


def _doc(p):
    return p if hasattr(p, "paragraphs") else Document(p)


def _cell_paragraphs(cell):
    for para in cell.paragraphs:
        yield para
    for t in cell.tables:   # nested tables
        for row in t.rows:
            for c in row.cells:
                yield from _cell_paragraphs(c)


def _textbox_paragraphs(doc):
    """Paragraphs inside text boxes / shapes (w:txbxContent), which python-docx does not expose."""
    body = doc.element.body
    for txbx in body.iter(qn("w:txbxContent")):
        for p in txbx.iter(qn("w:p")):
            yield Paragraph(p, doc)


def paragraphs(path_or_doc):
    doc = _doc(path_or_doc)
    out = []
    seen = set()
    for sec in doc.sections:
        for hf, where in ((sec.header, "header"), (sec.first_page_header, "header"), (sec.even_page_header, "header")):
            try:
                for p in hf.paragraphs:
                    if id(p._p) not in seen:
                        seen.add(id(p._p)); out.append((p, where))
                for t in hf.tables:
                    for row in t.rows:
                        for c in row.cells:
                            for p in _cell_paragraphs(c):
                                if id(p._p) not in seen:
                                    seen.add(id(p._p)); out.append((p, where))
            except Exception:
                pass
    for p in doc.paragraphs:
        out.append((p, "body")); seen.add(id(p._p))
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                for p in _cell_paragraphs(c):
                    if id(p._p) not in seen:
                        seen.add(id(p._p)); out.append((p, "table"))
    for p in _textbox_paragraphs(doc):
        if id(p._p) not in seen:
            seen.add(id(p._p)); out.append((p, "textbox"))
    for sec in doc.sections:
        for hf in (sec.footer, sec.first_page_footer, sec.even_page_footer):
            try:
                for p in hf.paragraphs:
                    if id(p._p) not in seen:
                        seen.add(id(p._p)); out.append((p, "footer"))
                for t in hf.tables:
                    for row in t.rows:
                        for c in row.cells:
                            for p in _cell_paragraphs(c):
                                if id(p._p) not in seen:
                                    seen.add(id(p._p)); out.append((p, "footer"))
            except Exception:
                pass
    return out


def text(path_or_doc):
    return "\n".join(p.text for p, _ in paragraphs(path_or_doc))


def kind(path_or_doc):
    try:
        s = str(_doc(path_or_doc).core_properties.subject or "")
    except Exception:
        return None
    if s.startswith("jobkit:"):
        k = s.split(":", 1)[1].strip().lower()
        return k if k in KINDS else None
    return None


def stamp(doc, k):
    """Mark a python-docx Document as a jobkit document of kind k (resume | cv | letter)."""
    if k not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    doc.core_properties.subject = f"jobkit:{k}"
    return doc


def stamp_letter(path):
    """Mark an existing .docx (a cover letter / statement the build skill wrote) as a jobkit letter."""
    d = Document(path)
    stamp(d, "letter")
    d.save(path)
    return path


def is_stray(path):
    """Files the audit must never treat as documents: Word lock files and dated backups of a built folder."""
    base = os.path.basename(path)
    parts = os.path.normpath(path).split(os.sep)
    return base.startswith("~$") or any(".bak-" in part for part in parts)


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        if a == "--stamp-letter":
            continue
        if "--stamp-letter" in sys.argv:
            print("stamped letter:", stamp_letter(a)); continue
        print(f"== {a}  kind={kind(a)}")
        for p, where in paragraphs(a):
            if p.text.strip():
                print(f"[{where:7}] {p.text.strip()[:110]}")
