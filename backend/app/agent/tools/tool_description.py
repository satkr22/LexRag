

GET_ACT_DESCRIPTION = """

Use this tool to identify the canonical internal corpus code of an Indian statutory Act from its official title, commonly used name, or recognizable alias.

The input must identify an Act, not describe a legal question or request a particular provision. Include the enactment year wherever possible to distinguish Acts with similar names.

The tool performs hybrid semantic and keyword retrieval against the Act registry and returns the best matching Act code only when its internal confidence threshold is met.

Use this tool when the Act's name is unfamiliar, abbreviated, incomplete, or uncertain. Do not call it when the Act is already clearly identified, because the other legal tools can resolve recognized Act names and codes themselves.

This tool does not retrieve section content, search for relevant legal provisions, or enumerate all Acts available in the corpus.


"""



VIEW_TOC_DESCRIPTION = """

Use this tool to explore the hierarchical structure of a statutory Act, including its chapters, section ranges, section numbers, section titles, and section IDs.

This tool operates in two mandatory stages:

Stage 1 - Retrieve chapters

Call the tool with the Act code and leave section_range unset or null. The tool returns the Act's available chapters, their titles, their corresponding section ranges, and the number of sections in each chapter.

Stage 2 - Retrieve sections within a chapter

After receiving the Stage 1 response, select the relevant chapter and call the tool again using the exact section_range pair returned for that chapter.

Never invent, estimate, or independently construct a section range. Always reuse the exact two values returned by Stage 1.

Use this tool when the user or you wants to know about an Act's structure, wants to browse its chapters, or wants to identify the sections belonging to a particular chapter.

Do not use this tool to retrieve the complete legal text of a section. Use get_section for that purpose. If the Act has no chapter metadata, use search_sections or get_section instead.

The section listing is capped at 300 records per call. Check the truncated field before assuming the returned list is complete.

"""


GET_SECTION_DESCRIPTION = """

Use this tool to retrieve the complete stored statutory text and metadata of one specific section from an Act in the legal corpus.

This is an exact section lookup, not a semantic search tool.

Provide the statutory Act code together with the section number. The section number must correspond to the numbering used in the corpus. Preserve alphanumeric section numbers as strings, such as "10A" or "302".

If you alread have section_id then use that instead of section number.

The tool first attempts an indexed lookup using the Act code and normalized section number. If that fails, it performs a secondary lookup using the Act and section number.

If the tool returns ambiguous: true, inspect the returned matches array and select the appropriate record. Re-call the tool using the exact section_id associated with the intended match. Never construct or guess a section ID.

The optional section_id parameter provides a direct database lookup and takes precedence over the Act and section-number lookup.

Use this tool when:
- you want to explicitly identifies an Act and section.
- A section has already been identified through view_toc.
- search_sections returns a relevant section whose is_complete field is false.
- A previous lookup returns multiple matching records and requires disambiguation.
Do not use this tool when you only know the legal issue but do not know which statutory provisions are relevant. Use search_sections to discover those provisions first.

"""



SEARCH_SECTIONS_DESCRIPTION = """

Use this tool to discover statutory sections relevant to a user's legal question, factual scenario, legal issue, rights, obligations, offences, procedures, or other legal concepts.

This tool performs hybrid retrieval over the statutory corpus using dense semantic search and BM25 keyword search. The retrieved results are combined using Reciprocal Rank Fusion (RRF).

Provide a natural-language description of the legal issue or question. Include the important facts, actions, circumstances, and legal concepts that determine which statutory provisions may be relevant.

The optional 'acts_filter' parameter restricts retrieval to the specified Acts. Use it only when the relevant Act or Acts are already known or clearly identified. When the relevant Act is unknown, omit the parameter or pass null to search across the entire statutory corpus.

When multiple Acts are supplied, results may come from any of those Acts. The filter is an inclusion filter, not a requirement that a result belong to all specified Acts.

The tool returns up to five unique section-level results, ranked using hybrid retrieval. Each result includes its Act code, section identifier, section number, section title, a text snippet, and an is_complete flag.

Very important: Interpret is_complete before using the retrieved text.
- is_complete: true means the returned text represents the complete section.
- is_complete: false means the returned text is only a fragment of the section. Call get_section to retrieve the complete statutory provision before relying on it for detailed legal reasoning.
Use the exact Act code, section number, and section ID from the search result when fetching the complete section.

This tool discovers candidate legal provisions. It does not establish that a provision applies to the user's facts, provide a definitive legal interpretation, or replace the need to read the complete statutory text.

"""
