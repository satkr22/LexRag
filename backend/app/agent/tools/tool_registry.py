from app.agent.tools.legal_tools import *
from app.agent.tools.tool_schema import *
from app.agent.tools.tool_description import *

from sqlalchemy.orm import sessionmaker
from qdrant_client import AsyncQdrantClient

from langchain_core.tools import StructuredTool



def build_legal_tools(
    session_factory: sessionmaker, 
    client: AsyncQdrantClient
) -> list[StructuredTool]:

    async def _get_act(act_name_query: str):
        return await get_act(client, act_name_query)

    async def _view_toc(
        act: str,
        section_range: list[str] | None = None,
    ):
        with session_factory() as db: # this is per call or request
            return await view_toc(
                db,
                client,
                act,
                tuple(section_range) if section_range is not None else None, # type: ignore
            )
    
    async def _get_section(
        act: str | None = None,
        section_number: str | None = None,
        section_id: str | None = None,
    ):
                
        with session_factory() as db:
            return await get_section(
                db,
                client,
                act,
                section_number,
                section_id,
            )

    async def _search_sections(
        query: str,
        acts_filter: list[str] | None = None,
    ):
        return await search_sections(
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
            handle_valiadtion_error=True
        ),
        StructuredTool.from_function(
            func=_view_toc,
            name="view_toc",
            description=VIEW_TOC_DESCRIPTION,
            args_schema=ViewTocInput,
            handle_valiadtion_error=True
        ),
        StructuredTool.from_function(
            func=_get_section,
            name="get_section",
            description=GET_SECTION_DESCRIPTION,
            args_schema=GetSectionInput,
            handle_valiadtion_error=True
        ),
        StructuredTool.from_function(
            func=_search_sections,
            name="search_sections",
            description=SEARCH_SECTIONS_DESCRIPTION,
            args_schema=SearchSectionsInput,
            handle_valiadtion_error=True
        ),
    ]

    return tools