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
            f"[Act: {meta.get('act', '')}\n"
            f" Chapter: {meta.get('heading_title', '')}\n"
            f" Section: {meta.get('article_number', '')}::{meta.get('article_title', '')}\n]\n"
        )

    def chunk_section(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Main entrypoint: Routes to fast-path (raw text) or slow-path (HTML parser)."""
        header = self.build_metadata_header(data)
        
        # Ensure we safely access the content dictionary
        article_data = data.get("article", {})
        raw_content = self.normalize_whitespace(article_data.get("content", ""))
        fast_path_text = f"{header}\n\n{raw_content}"

        
        # FAST PATH: If raw content + metadata <= 512 tokens, skip HTML parsing
        if self.count_tokens(fast_path_text) <= self.max_tokens:
            return [self._create_chunk_dict(data, 0, fast_path_text, is_intact=True)]

        
        # SLOW PATH: Section > 512 tokens -> Parse <div class="prov-body"> only
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
    # TODO: convert these paths to relative path
    INPUT_FOLDER = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/data_ingestion/parsed"  
    OUTPUT_FOLDER = "/home/usatkr/u_ml/projects/LexRag/src/lexrag/data_ingestion/chunked"
    
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