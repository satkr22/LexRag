# import json
# import re
# from pathlib import Path
# from typing import List, Dict, Any, Optional
# from bs4 import BeautifulSoup, Tag
# import tiktoken


# class LegalHTMLChunker:
#     def __init__(
#         self,
#         max_tokens: int = 512,
#         overlap_tokens: int = 75,
#         encoding_name: str = "cl100k_base",
#     ):
#         """
#         Hierarchical & overlapping chunker for scraped legal JSON files.
        
#         :param max_tokens: Maximum tokens allowed per chunk (including injected metadata).
#         :param overlap_tokens: Target token budget for sliding-window overlap between chunks.
#         :param encoding_name: Tiktoken encoding ('cl100k_base' is standard for modern embeddings).
#         """
#         self.max_tokens = max_tokens
#         self.overlap_tokens = overlap_tokens
#         self.tokenizer = tiktoken.get_encoding(encoding_name)

#     def count_tokens(self, text: str) -> int:
#         return len(self.tokenizer.encode(text))

#     @staticmethod
#     def clean_tag_text(tag: Tag) -> str:
#         """
#         Extracts text from a <p> tag while ensuring spaces after <span class="lbl">
#         and <span class="named"> so labels like '(1)' or 'Explanation 1' do not 
#         concatenate directly with the following word.
#         """
#         # Work on a copy of the tag so we don't mutate the soup tree in place
#         tag_copy = BeautifulSoup(str(tag), "lxml").find(tag.name)
#         for span in tag_copy.find_all("span", class_=["lbl", "named"]):
#             span.insert_after(" ")

#         raw_text = tag_copy.get_text(separator=" ", strip=True)
#         return re.sub(r"\s+", " ", raw_text).strip()

#     def build_metadata_header(self, data: Dict[str, Any]) -> str:
#         """Builds the context header injected at the top of every chunk."""
#         meta = data.get("metadata", {})
#         act = meta.get("act", None)
#         section_id = data.get("id", "")
#         doc_title = meta.get("document_title", "")
#         chap_num = meta.get("heading_number", "")
#         chap_title = meta.get("heading_title", "")
#         sec_num = meta.get("article_number", "")
#         sec_title = meta.get("article_title", "")

#         return (
#             f"[Act: {act} | {chap_num}: {chap_title} | "
#             f"Section {sec_num}: {sec_title} | Section ID: {section_id}]"
#         )

#     def parse_hierarchy(self, html_content: str) -> Dict[str, Any]:
#         """
#         Parses <div class="prov-body"> into:
#           - 'chapeau': Section-level introductory line (if present)
#           - 'blocks': List of hierarchical Level-1 subsection blocks, each containing
#                       its parent text and nested Level-2 ('lvl') / Level-3 ('lvl2') children.
#         """
#         soup = BeautifulSoup(html_content, "lxml")
#         prov_body = soup.find("div", class_="prov-body")
#         if not prov_body:
#             prov_body = soup

#         chapeau: Optional[str] = None
#         blocks: List[Dict[str, Any]] = []
#         current_lvl1: Optional[Dict[str, Any]] = None
#         current_lvl2: Optional[Dict[str, Any]] = None

#         p_tags = prov_body.find_all("p", recursive=False)
#         for idx, p in enumerate(p_tags):
#             classes = p.get("class", [])
#             has_lbl = p.find("span", class_="lbl") is not None
#             text = self.clean_tag_text(p)
#             if not text:
#                 continue

#             # 1. Detect Section-level Chapeau (e.g., "In this Sanhita, unless the context...")
#             if idx == 0 and not classes and not has_lbl:
#                 chapeau = text
#                 continue

#             # 2. Level 3: <p class="lvl2"> (e.g., sub-clauses (i), (ii))
#             if "lvl2" in classes:
#                 if current_lvl2 is not None:
#                     current_lvl2["children"].append(text)
#                 elif current_lvl1 is not None:
#                     current_lvl1["children"].append({"text": text, "children": []})
#                 else:
#                     blocks.append({"text": text, "children": []})

#             # 3. Level 2: <p class="lvl"> or <p class="illus-head"> (e.g., (a), Explanation, Illustrations)
#             elif "lvl" in classes or "illus-head" in classes:
#                 lvl2_node = {"text": text, "children": []}
#                 current_lvl2 = lvl2_node
#                 if current_lvl1 is not None:
#                     current_lvl1["children"].append(lvl2_node)
#                 else:
#                     blocks.append({"text": text, "children": []})

#             # 4. Level 1: Top-level subsection <p> (e.g., (1), (2), (28))
#             else:
#                 current_lvl1 = {"text": text, "children": []}
#                 current_lvl2 = None
#                 blocks.append(current_lvl1)

#         # Append footnotes at the end if present
#         fnotes_div = soup.find("div", class_="fnotes")
#         if fnotes_div:
#             for fn in fnotes_div.find_all("p", class_="fn"):
#                 fn_text = f"Footnote: {self.clean_tag_text(fn)}"
#                 blocks.append({"text": fn_text, "children": []})

#         return {"chapeau": chapeau, "blocks": blocks}

#     def render_block(self, block: Dict[str, Any]) -> str:
#         """Flattens a Level-1 block and all its nested children into a single string."""
#         lines = [block["text"]]
#         for lvl2 in block.get("children", []):
#             if isinstance(lvl2, dict):
#                 lines.append(f"  {lvl2['text']}")
#                 for lvl3 in lvl2.get("children", []):
#                     lines.append(f"    {lvl3}")
#             else:
#                 lines.append(f"  {lvl2}")
#         return "\n".join(lines)

#     def split_oversized_block(
#         self, block: Dict[str, Any], max_body_tokens: int
#     ) -> List[Dict[str, Any]]:
#         """
#         If a single subsection (like Section 2(28) 'public servant') exceeds max_body_tokens,
#         splits it at its Level-2 ('lvl') boundaries while prepending the Level-1 parent clause
#         to every resulting sub-unit so nested clauses never lose their parent context.
#         """
#         parent_text = block["text"]
#         parent_tokens = self.count_tokens(parent_text + "\n")
#         sub_budget = max_body_tokens - parent_tokens

#         sub_units: List[Dict[str, Any]] = []
#         for lvl2 in block.get("children", []):
#             lvl2_lines = [f"  {lvl2['text']}"]
#             for lvl3 in lvl2.get("children", []):
#                 lvl2_lines.append(f"    {lvl3}")
#             lvl2_full_str = "\n".join(lvl2_lines)

#             # If a single lvl2 + its lvl3 children is still within budget, keep together
#             if self.count_tokens(lvl2_full_str) <= sub_budget or not lvl2.get("children"):
#                 sub_units.append({
#                     "parent_prefix": parent_text,
#                     "text": lvl2_full_str,
#                 })
#             else:
#                 # Split at lvl3 boundaries and prepend both Level-1 and Level-2 parents
#                 combined_prefix = f"{parent_text}\n  {lvl2['text']}"
#                 for lvl3 in lvl2.get("children", []):
#                     sub_units.append({
#                         "parent_prefix": combined_prefix,
#                         "text": f"    {lvl3}",
#                     })

#         # Greedily group sub-units that share the same parent_prefix
#         grouped_chunks: List[Dict[str, Any]] = []
#         current_lines: List[str] = []
#         current_prefix: Optional[str] = None

#         for unit in sub_units:
#             prefix = unit["parent_prefix"]
#             candidate_lines = (
#                 current_lines + [unit["text"]] if prefix == current_prefix else [unit["text"]]
#             )
#             candidate_str = f"{prefix}\n" + "\n".join(candidate_lines)

#             if current_lines and (
#                 prefix != current_prefix or self.count_tokens(candidate_str) > max_body_tokens
#             ):
#                 grouped_chunks.append({
#                     "text": f"{current_prefix}\n" + "\n".join(current_lines),
#                     "is_sub_split": True,
#                 })
#                 current_prefix = prefix
#                 current_lines = [unit["text"]]
#             else:
#                 current_prefix = prefix
#                 current_lines = candidate_lines

#         if current_lines and current_prefix:
#             grouped_chunks.append({
#                 "text": f"{current_prefix}\n" + "\n".join(current_lines),
#                 "is_sub_split": True,
#             })

#         return grouped_chunks

#     def chunk_section(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
#         """
#         Main entry point to chunk a single section JSON object.
#         """
#         meta = data.get("metadata", {})
#         section_id = data.get("id", "unknown_section")
#         html_content = data.get("article", {}).get("html") or data.get("article", {}).get("inner_html", "")

#         meta_header = self.build_metadata_header(data)
#         parsed = self.parse_hierarchy(html_content)
#         chapeau = parsed["chapeau"]
#         blocks = parsed["blocks"]

#         # Build prefix that goes into every chunk of this section
#         base_prefix = f"{meta_header}\n{chapeau}" if chapeau else meta_header
#         prefix_tokens = self.count_tokens(base_prefix + "\n\n")
#         max_body_tokens = self.max_tokens - prefix_tokens

#         # 1. Flatten all blocks to check if the entire section fits in <= 512 tokens
#         rendered_blocks = [self.render_block(b) for b in blocks]
#         full_section_text = f"{base_prefix}\n\n" + "\n\n".join(rendered_blocks)

#         if self.count_tokens(full_section_text) <= self.max_tokens:
#             return [
#                 self._format_chunk_output(
#                     data=data,
#                     chunk_index=0,
#                     text=full_section_text,
#                     is_intact=True,
#                 )
#             ]

#         # 2. Prepare atomic semantic units (splitting any single oversized subsection)
#         units: List[str] = []
#         for block in blocks:
#             rendered = self.render_block(block)
#             if self.count_tokens(rendered) <= max_body_tokens:
#                 units.append(rendered)
#             else:
#                 sub_chunks = self.split_oversized_block(block, max_body_tokens)
#                 units.extend([sc["text"] for sc in sub_chunks])

#         # 3. Pack units into chunks <= 512 tokens with sliding-window boundary overlap
#         final_chunks_text: List[str] = []
#         current_units: List[str] = []

#         for unit in units:
#             candidate_body = "\n\n".join(current_units + [unit])
#             candidate_full = f"{base_prefix}\n\n{candidate_body}"

#             if current_units and self.count_tokens(candidate_full) > self.max_tokens:
#                 # Commit current chunk
#                 committed_body = "\n\n".join(current_units)
#                 final_chunks_text.append(f"{base_prefix}\n\n{committed_body}")

#                 # Compute overlap units from the tail of current_units
#                 overlap_units: List[str] = []
#                 overlap_count = 0
#                 for prev_unit in reversed(current_units):
#                     u_tokens = self.count_tokens(prev_unit)
#                     if overlap_count + u_tokens <= self.overlap_tokens:
#                         overlap_units.insert(0, prev_unit)
#                         overlap_count += u_tokens
#                     else:
#                         break

#                 # Ensure overlap doesn't prevent the new unit from fitting
#                 while overlap_units and (
#                     self.count_tokens(f"{base_prefix}\n\n" + "\n\n".join(overlap_units + [unit]))
#                     > self.max_tokens
#                 ):
#                     overlap_units.pop(0)

#                 current_units = overlap_units + [unit]
#             else:
#                 current_units.append(unit)

#         if current_units:
#             committed_body = "\n\n".join(current_units)
#             final_chunks_text.append(f"{base_prefix}\n\n{committed_body}")

#         return [
#             self._format_chunk_output(
#                 data=data,
#                 chunk_index= idx,
#                 text=chunk_text,
#                 is_intact=False,
#             )
#             for idx, chunk_text in enumerate(final_chunks_text)
#         ]

#     def _format_chunk_output(
#         self, data: Dict[str, Any], chunk_index: int, text: str, is_intact: bool
#     ) -> Dict[str, Any]:
#         meta = data.get("metadata", {})
#         section_id = data.get("id", "unknown_section")
#         chunk_id = f"{section_id}_chunk_{chunk_index}"

#         return {
#             "chunk_id": chunk_id,
#             "section_id": section_id,
#             "token_count": self.count_tokens(text),
#             "text": text,
#             "metadata": {
#                 "chunk_id": chunk_id,
#                 "section_id": section_id,
#                 "chunk_index": chunk_index,
#                 "is_intact_section": is_intact,
#                 "act": meta.get("act"),
#                 "document_title": meta.get("document_title"),
#                 "chapter_number": meta.get("heading_number"),
#                 "chapter_title": meta.get("heading_title"),
#                 "section_number": meta.get("article_number"),
#                 "section_title": meta.get("article_title"),
#             },
#         }


# # ==========================================
# # Example Usage on Your JSON Files
# # ==========================================
# if __name__ == "__main__":
#     chunker = LegalHTMLChunker(max_tokens=512, overlap_tokens=75)

#     path = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/parsed/contract_sections/section_97.json"
#     path2 = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/parsed/contract_sections/section_49.json"
    
#     for file_path in [path, path2]:
#         path = Path(file_path)
#         if not path.exists():
#             continue

#         with open(path, "r", encoding="utf-8") as f:
#             section_data = json.load(f)

#         chunks = chunker.chunk_section(section_data)
#         print(f"=== {file_path} (Section ID: {section_data['id']}) -> {len(chunks)} chunk(s) ===")
#         for c in chunks:
#             print(
#                 f"  • {c['chunk_id']} | Tokens: {c['token_count']} | "
#                 f"Intact: {c['metadata']['is_intact_section']}"
#             )
#             print(f"chunk content:\n{c['text']}\n\n")


















import json
import re
from pathlib import Path
from typing import List, Dict, Any
from bs4 import BeautifulSoup, Tag
import tiktoken


class LegalChunker:
    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 75,
        encoding_name: str = "cl100k_base",
    ):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Cleans up excessive indentation and blank lines from raw content."""
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned.strip()

    @staticmethod
    def extract_p_text(p_tag: Tag) -> str:
        """Extracts clean text from a <p> tag while preserving space after labels."""
        for span in p_tag.find_all("span", class_=["lbl", "named"]):
            span.insert_after(" ")
        return re.sub(r"\s+", " ", p_tag.get_text(separator=" ", strip=True)).strip()

    def build_metadata_header(self, data: Dict[str, Any]) -> str:
        """Reads all fields directly from root 'id' and 'metadata' dict."""
        meta = data.get("metadata", {})
        return (
            f"[Act: {meta.get('act', '')} | "
            f"{meta.get('heading_number', '')}: {meta.get('heading_title', '')} | "
            f"Section {meta.get('article_number', '')}: {meta.get('article_title', '')} | "
            f"Section ID: {data.get('id', '')}]"
        )

    def chunk_section(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Main entrypoint: Routes to fast-path (raw text) or slow-path (HTML parser)."""
        header = self.build_metadata_header(data)
        
        # Ensure we safely access the content dictionary
        article_data = data.get("article", {})
        raw_content = self.normalize_whitespace(article_data.get("content", ""))
        fast_path_text = f"{header}\n\n{raw_content}"

        # =====================================================================
        # FAST PATH: If raw content + metadata <= 512 tokens, skip HTML parsing
        # =====================================================================
        if self.count_tokens(fast_path_text) <= self.max_tokens:
            return [self._create_chunk_dict(data, 0, fast_path_text, is_intact=True)]

        # =====================================================================
        # SLOW PATH: Section > 512 tokens -> Parse <div class="prov-body"> only
        # =====================================================================
        html_str = article_data.get("inner_html") or article_data.get("html", "")
        units, chapeau = self._parse_html_into_units(html_str, header)

        base_prefix = f"{header}\n{chapeau}" if chapeau else header
        chunks_text = self._pack_units_with_overlap(units, base_prefix)

        return [
            self._create_chunk_dict(data, idx, text, is_intact=False)
            for idx, text in enumerate(chunks_text)
        ]

    def _parse_html_into_units(self, html_str: str, header: str) -> tuple[List[str], str]:
        """Parses only <div class="prov-body"> into hierarchical text units."""
        soup = BeautifulSoup(html_str, "lxml")
        prov_body = soup.find("div", class_="prov-body")
        if not prov_body:
            prov_body = soup  # Fallback if class is missing

        chapeau = ""
        subsections: List[Dict[str, Any]] = []

        for idx, p in enumerate(prov_body.find_all("p", recursive=False)):
            classes = p.get("class", []) #type: ignore
            has_lbl = p.find("span", class_="lbl") is not None
            text = self.extract_p_text(p)
            if not text:
                continue

            # Detect introductory section line (e.g., "In this Sanhita, unless...")
            if idx == 0 and not classes and not has_lbl:
                chapeau = text
                continue

            # Top-level subsection (e.g., (1), (2), (28))
            if not classes:
                subsections.append({"parent": text, "children": []})
            # Nested clause/explanation/illustration (lvl, lvl2, illus-head)
            else:
                indent = "    " if "lvl2" in classes else "  "
                if subsections:
                    subsections[-1]["children"].append(f"{indent}{text}")
                else:
                    subsections.append({"parent": text, "children": []})

        # Calculate available token budget for body text
        base_prefix = f"{header}\n{chapeau}\n\n" if chapeau else f"{header}\n\n"
        max_body_tokens = self.max_tokens - self.count_tokens(base_prefix)

        # Convert subsections into semantic strings; split any single subsection > budget
        units: List[str] = []
        for sub in subsections:
            full_sub = "\n".join([sub["parent"]] + sub["children"])
            if self.count_tokens(full_sub) <= max_body_tokens or not sub["children"]:
                units.append(full_sub)
            else:
                # If a single subsection exceeds budget, split its children
                # while keeping the subsection's parent line attached to each part
                parent_line = sub["parent"]
                current_children: List[str] = []
                for child in sub["children"]:
                    candidate = "\n".join([parent_line] + current_children + [child])
                    if current_children and self.count_tokens(candidate) > max_body_tokens:
                        units.append("\n".join([parent_line] + current_children))
                        current_children = [child]
                    else:
                        current_children.append(child)
                if current_children:
                    units.append("\n".join([parent_line] + current_children))

        return units, chapeau

    def _pack_units_with_overlap(self, units: List[str], base_prefix: str) -> List[str]:
        """Packs units up to max_tokens with sliding-window overlap."""
        chunks: List[str] = []
        current_units: List[str] = []

        for unit in units:
            candidate = f"{base_prefix}\n\n" + "\n\n".join(current_units + [unit])

            if current_units and self.count_tokens(candidate) > self.max_tokens:
                chunks.append(f"{base_prefix}\n\n" + "\n\n".join(current_units))

                # Carry over trailing units that fit within overlap_tokens
                overlap: List[str] = []
                overlap_toks = 0
                for prev in reversed(current_units):
                    t = self.count_tokens(prev)
                    if overlap_toks + t <= self.overlap_tokens:
                        overlap.insert(0, prev)
                        overlap_toks += t
                    else:
                        break

                # Drop oldest overlap if the next unit is huge and needs the space
                while overlap and (
                    self.count_tokens(f"{base_prefix}\n\n" + "\n\n".join(overlap + [unit]))
                    > self.max_tokens
                ):
                    overlap.pop(0)

                current_units = overlap + [unit]
            else:
                current_units.append(unit)

        if current_units:
            chunks.append(f"{base_prefix}\n\n" + "\n\n".join(current_units))

        return chunks

    def _create_chunk_dict(
        self, data: Dict[str, Any], chunk_index: int, text: str, is_intact: bool
    ) -> Dict[str, Any]:
        """Constructs the final dictionary structure for the chunk."""
        meta = data.get("metadata", {})
        section_id = data.get("id", f"unknown_{chunk_index}")
        chunk_id = f"{section_id}_chunk_{chunk_index}"

        return {
            "chunk_id": chunk_id,
            "section_id": section_id,
            "token_count": self.count_tokens(text),
            "text": text,
            "metadata": {
                "chunk_id": chunk_id,
                "section_id": section_id,
                "chunk_index": chunk_index,
                "is_intact_section": is_intact,
                "act": meta.get("act", ""),
                "document_title": meta.get("document_title", ""),
                "chapter_number": meta.get("heading_number", ""),
                "chapter_title": meta.get("heading_title", ""),
                "section_number": meta.get("article_number", ""),
                "section_title": meta.get("article_title", ""),
            },
        }


def process_corpus(input_directory: str, output_dir: str):
    """Iterates through all JSON files in the directory and saves chunks to a single file."""
    chunker = LegalChunker(max_tokens=512, overlap_tokens=75)

    dirs = [p.name for p in Path(input_directory).iterdir() if p.is_dir()]

    
    for dir in dirs:
        
        all_chunks = []
        
        # Point this to the folder containing your 41 documents' JSON files
        folder_path = Path(input_directory) / dir
        
        if not folder_path.exists() or not folder_path.is_dir():
            print(f"Error: Directory '{input_directory}' not found.")
            return

        # Process every JSON file in the target directory
        for file_path in folder_path.glob("*.json"):
            current_file_chunks = []
            try:
                if "manifest.json" in str(file_path):
                    continue
                with open(file_path, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    
                # Handle both single objects and arrays of sections in a JSON file
                if isinstance(doc, list):
                    for section in doc:
                        # all_chunks.extend(chunker.chunk_section(section))
                        current_file_chunks.extend(chunker.chunk_section(section))
                else:
                    # all_chunks.extend(chunker.chunk_section(doc))
                    current_file_chunks.extend(chunker.chunk_section(doc))
                    
                print(f"Processed {file_path.name}...")
                # to get section wise chunks do a file operation here also 
                
                outdir = Path(output_dir) / dir
                Path(outdir).mkdir(parents=True, exist_ok=True)
                output_path = outdir / f"{file_path.name}"
                
                with open(output_path, "w", encoding="utf-8") as out_f:
                    json.dump(current_file_chunks, out_f, indent=2, ensure_ascii=False)

                all_chunks.extend(current_file_chunks) 
            except Exception as e:
                print(f"Failed to process {file_path.name}: {e}")
                
                
        # Export all chunks to the final JSON payload for your vector database
        outdir = Path(output_dir) / "aaalll"
        Path(outdir).mkdir(parents=True, exist_ok=True)
        output_path = outdir / f"{dir}.json"
        
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(all_chunks, out_f, indent=2, ensure_ascii=False)
            
        print(f"\nSuccessfully generated {len(all_chunks)} chunks.")
        print(f"Saved to: {output_path}")



if __name__ == "__main__":
    # Replace './legal_data' with the actual path to your scraped JSON files
    INPUT_FOLDER = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/parsed"  
    OUTPUT_FOLDER = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/chunked"
    
    # Run the bulk processing script
    process_corpus(INPUT_FOLDER, OUTPUT_FOLDER)
                    
                    
# if __name__ == "__main__":
#     chunker = LegalChunker(max_tokens=512, overlap_tokens=75)

#     path = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/parsed/contract_sections/section_97.json"
#     path2 = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/parsed/contract_sections/section_49.json"
    
#     for file_path in [path, path2]:
#         path = Path(file_path)
#         if not path.exists():
#             continue

#         with open(path, "r", encoding="utf-8") as f:
#             section_data = json.load(f)

#         chunks = chunker.chunk_section(section_data)
#         print(f"=== {file_path} (Section ID: {section_data['id']}) -> {len(chunks)} chunk(s) ===")
#         for c in chunks:
#             print(
#                 f"  • {c['chunk_id']} | Tokens: {c['token_count']} | "
#                 f"Intact: {c['metadata']['is_intact_section']}"
#             )
#             print(f"chunk content:\n{c['text']}\n\n")