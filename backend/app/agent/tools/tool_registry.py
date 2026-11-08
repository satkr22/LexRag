from app.agent.tools.legal_tools import *
from app.agent.tools.tool_schema import *
from app.agent.tools.tool_description import *

from sqlalchemy.orm import sessionmaker
from qdrant_client import AsyncQdrantClient
from fastembed import TextEmbedding, SparseTextEmbedding
from langchain_core.tools import StructuredTool



async def build_legal_tools(
    session_factory: sessionmaker, 
    client: AsyncQdrantClient,
    dense_model: TextEmbedding,
    sparse_model: SparseTextEmbedding,
    
) -> list[StructuredTool]:

    async def _get_act(act_name_query: str):
        return await get_act(
            client=client, 
            dense_model=dense_model,
            sparse_model=sparse_model,
            act_name_query=act_name_query
        )

    async def _view_toc(
        act: str,
        section_range: list[str] | None = None,
    ):
        with session_factory() as db: # this is per call or request
            return await view_toc(
                db,
                client,
                dense_model,
                sparse_model,
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
                dense_model,
                sparse_model,
                act,
                section_number,
                section_id,
            )

    async def _search_sections(
        query: str,
        acts_filter: list[str] | None = None,
    ):
        return await search_sections(
            client=client,
            dense_model=dense_model,
            sparse_model=sparse_model,
            query=query,
            acts_filter=acts_filter,
        )

    tools = [
        StructuredTool.from_function(
            coroutine=_get_act,
            name="get_act",
            description=GET_ACT_DESCRIPTION,
            args_schema=GetActInput,
            handle_valiadtion_error=True
        ),
        StructuredTool.from_function(
            coroutine=_view_toc,
            name="view_toc",
            description=VIEW_TOC_DESCRIPTION,
            args_schema=ViewTocInput,
            handle_valiadtion_error=True
        ),
        StructuredTool.from_function(
            coroutine=_get_section,
            name="get_section",
            description=GET_SECTION_DESCRIPTION,
            args_schema=GetSectionInput,
            handle_valiadtion_error=True
        ),
        StructuredTool.from_function(
            coroutine=_search_sections,
            name="search_sections",
            description=SEARCH_SECTIONS_DESCRIPTION,
            args_schema=SearchSectionsInput,
            handle_valiadtion_error=True
        ),
    ]

    return tools