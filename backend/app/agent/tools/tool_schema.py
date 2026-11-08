from pydantic import BaseModel, ConfigDict, Field


class LegalToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetActInput(LegalToolInput):
    act_name_query: str = Field(
        description=(
            "Official name, full title, or recognizable alias of the statutory "
            "Act to identify. Prefer including the enactment year. Provide an "
            "Act name only, not a legal question, section number, or legal topic."
        )
    )


class ViewTocInput(LegalToolInput):
    act: str = Field(
        description=(
            "Name or canonical corpus code of the statutory Act whose table "
            "of contents should be retrieved. Prefer the full official Act name."
        )
    )

    section_range: list[str] | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description=(
            "Two-element [start_section, end_section] pair. Leave null or omit "
            "for Stage 1, which retrieves the chapter list. For Stage 2, pass "
            "the exact section_range pair returned by a previous Stage 1 call. "
            "Both elements must be strings. Never guess or construct this range."
        )
    )


class GetSectionInput(LegalToolInput):
    act: str = Field(
        description=(
            "Act code of the statutory Act containing "
            "the requested section."
        )
    )

    section_number: str = Field(
        description=(
            "Exact statutory section number as represented in the corpus. "
            "Examples: '302', '10A'. Always represent it as a string, not "
            "an integer. Prefer the section number returned by view_toc "
            "or search_sections."
        )
    )

    section_id: str | None = Field(
        default=None,
        description=(
            "Exact section_id previously returned by get_section, view_toc, "
            "or search_sections. Normally leave null. Use it when a previous "
            "get_section response returned ambiguous=true and you have selected "
            "one of its matches. When provided, it takes precedence over the "
            "Act and section-number lookup. The current function signature still "
            "requires act and section_number to be supplied."
        )
    )


class SearchSectionsInput(LegalToolInput):
    query: str = Field(
        description=(
            "Natural-language description of the legal issue, question, factual "
            "scenario, rights, obligations, offence, or legal concepts for which "
            "relevant statutory provisions must be discovered. Include material "
            "facts and specific legal concepts. Do not provide only a generic "
            "legal category when a more specific description is available."
        )
    )

    acts_filter: list[str] | None = Field(
        default=None,
        min_length=1,
        max_length=10,
        description=(
            "Optional non-empty list of statutory Act names or canonical corpus "
            "codes restricting the search. Results may belong to ANY of the "
            "specified Acts. Omit or pass null to search the entire statutory "
            "corpus. Do not supply section numbers, chapter names, legal topics, "
            "or category labels here."
        )
    )