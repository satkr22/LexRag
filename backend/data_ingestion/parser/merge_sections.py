import json
from pathlib import Path

def merge_section(input_dir: Path, output_dir: Path):
    
    for dir in input_dir.iterdir():
        
        all_sections: list = []
        file_name = dir.name
        
        print(f"appending sections of act: {dir}")
        for j in dir.glob("*json"):
            if j.name == "manifest.json":
                continue
            
            with j.open("r", encoding="utf-8") as f:
                content = json.load(f)
            
            if isinstance(content, dict):
                all_sections.append(content)  
                
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{file_name}.json"
        
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(all_sections, f, indent=2)
        

if __name__ == "__main__":
    
    input_dir = Path(__file__).parent / "parsed"
    output_dir = Path(__file__).parent / "parsed" / "aaalll"
    
    merge_section(input_dir, output_dir)
    print("done.")
    
    