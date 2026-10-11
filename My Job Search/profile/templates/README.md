# profile/templates - letters and statements (any field)

Markdown templates for the documents a posting may ask for besides the resume or CV. They are PROSE, so the
audit cannot check them line-by-line the way it checks a resume; the rules that make them honest are:
1. Every factual statement comes from `profile/evidence/*.md` (confirmed) or `profile/approved_claims.yaml`.
   The `[CLAIM: ...]` markers name the YAML key or evidence file a sentence rests on; delete the marker when the
   draft is final, never the trail (keep it in the build-script comments).
2. `audit_claims.py` still runs on the built .docx: never-claims, operator patterns and retired claims apply.
3. Nothing is sent. The draft is approved by the user, who submits it on the employer's / program's site.
4. Fit statements point at the posting's own words (the unit's stated needs, the lab's stated questions, the
   team's stated stack), not at generic enthusiasm. Honest gaps stay out of the document and go into the job card.

| file | when |
|---|---|
| `cover_letter.TEMPLATE.md` | any industry, clinical, government or nonprofit posting that asks for a letter (one page, requirement by requirement) |
| `academic_cover_letter.TEMPLATE.md` | research assistant / technician / lab manager / coordinator postings at universities and labs |
| `research_statement.TEMPLATE.md` | research-staff and fellowship applications (what you have done, what you would do) - academic track |
| `statement_of_purpose.TEMPLATE.md` | PhD applications (program-facing: why this program, this advisor, this question) - academic track |
Build scripts fill them (python-docx or plain .md) from `approved_claims` names, exactly like a resume build.
The academic templates are offered only when `settings.yaml build.format` is `academic_cv` or the person asks for them.
