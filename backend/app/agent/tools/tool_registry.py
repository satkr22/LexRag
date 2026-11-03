from app.agent.tools.legal_tools import *
from app.agent.tools.tool_schema import *
from app.agent.tools.tool_description import *

from langchain_core.tools import StructuredTool



def build_legal_tools(db, client):

    def _get_act(act_name_query: str):
        return get_act(client, act_name_query)

    def _view_toc(
        act: str,
        section_range: list[str] | None = None,
    ):
        return view_toc(
            db,
            client,
            act,
            tuple(section_range) if section_range is not None else None, # type: ignore
        )
    
    def _get_section(
        act: str,
        section_number: str,
        section_id: str | None = None,
    ):
        return get_section(
            db,
            client,
            act,
            section_number,
            section_id,
        )

    def _search_sections(
        query: str,
        acts_filter: list[str] | None = None,
    ):
        return search_sections(
            client,
            query,
            acts_filter,
        )

    tools = [
        StructuredTool.from_function(
            func=_get_act,
            name="get_act",
            description=GET_ACT_DESCRIPTION,
            args_schema=GetActInput,
        ),
        StructuredTool.from_function(
            func=_view_toc,
            name="view_toc",
            description=VIEW_TOC_DESCRIPTION,
            args_schema=ViewTocInput,
        ),
        StructuredTool.from_function(
            func=_get_section,
            name="get_section",
            description=GET_SECTION_DESCRIPTION,
            args_schema=GetSectionInput,
        ),
        StructuredTool.from_function(
            func=_search_sections,
            name="search_sections",
            description=SEARCH_SECTIONS_DESCRIPTION,
            args_schema=SearchSectionsInput,
        ),
    ]

    return tools