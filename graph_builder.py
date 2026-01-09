import os
import openpyxl
import networkx as nx
import matplotlib.pyplot as plt
import io
from openpyxl.drawing.image import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import re

def clean_term(term):
    """
    Cleans a term by removing parentheses contents, special chars, and Title Casing.
    """
    if not term:
        return ""
    # Remove contents inside parentheses e.g. "DFT (Density Functional Theory)" -> "DFT "
    term = re.sub(r'\(.*?\)', '', term)
    # Remove chars like [ ]
    term = re.sub(r'[\[\]]', '', term)
    # Remove non-alphanumeric (except space, hyphen) - optional but cleaner
    # term = re.sub(r'[^a-zA-Z0-9 \-]', '', term)
    
    # Strip and Title Case
    return term.strip().title()

def extract_terms_from_sheet(sheet):
    """
    Extracts top technical/concept terms from a paper sheet.
    Priority: Glossary Terms -> Central Variables -> Title Keywords
    Returns a set of normalized (Title Case) terms.
    """
    terms = set()
    
    glossary_text = ""
    variables_text = ""
    
    # Scan rows for keys
    for row in sheet.iter_rows(min_row=1, max_row=30, min_col=1, max_col=2):
        key_cell = row[0]
        val_cell = row[1]
        if not key_cell.value:
            continue
            
        key = str(key_cell.value).strip()
        val = str(val_cell.value) if val_cell.value else ""
        
        if key == "Glossary":
            glossary_text = val
        elif key in ["Central Independent Variables", "Central Dependent Variables"]:
            variables_text += " " + val

    # Logic 1: Glossary Parsing
    import ast
    
    # Try parsing as JSON/List repr first (if saved as raw list)
    # OR if saved as "Term: Definition", parse lines.
    
    # Case A: "Term: Definition\nTerm2: Def2" (Formatted String)
    if ":" in glossary_text and "\n" in glossary_text:
        lines = glossary_text.split('\n')
        for line in lines:
            if ":" in line:
                term = line.split(":")[0]
                cleaned = clean_term(term)
                if cleaned and len(cleaned.split()) <= 3:
                    terms.add(cleaned)

    # Case B: Raw List/JSON "[{...}]" (If not formatted yet)
    elif glossary_text.strip().startswith("["):
        try:
            glossary_list = ast.literal_eval(glossary_text)
            if isinstance(glossary_list, list):
                for item in glossary_list:
                    if isinstance(item, dict):
                        term = item.get("Term", item.get("term", ""))
                        cleaned = clean_term(term)
                        if cleaned and len(cleaned.split()) <= 3:
                            terms.add(cleaned)
        except:
            pass

    # Logic 2: Variables Parsing (Backup)
    if len(terms) < 3 and variables_text:
        parts = [p.strip() for p in variables_text.replace(" and ", ",").split(',')]
        for p in parts:
            cleaned = clean_term(p)
            if cleaned and len(cleaned.split()) <= 3:
                terms.add(cleaned)

    return list(terms)[:5] 

def update_workbook_with_graph(wb):
    """
    Updates the provided workbook object with a Knowledge Graph sheet.
    Does NOT save the file (caller must save).
    """
    G = nx.Graph()
    
    # Iterate sheets
    skip_sheets = ["Dashboard", "Knowledge Graph"]
    
    paper_nodes = []
    concept_nodes = set()
    
    logging.info("Building Knowledge Graph from workbook data...")
    
    for sheet_name in wb.sheetnames:
        if sheet_name in skip_sheets:
            continue
            
        sheet = wb[sheet_name]
        
        # 1. Add Paper Node
        G.add_node(sheet_name, type="paper")
        paper_nodes.append(sheet_name)
        
        # 2. Extract Terms
        terms = extract_terms_from_sheet(sheet)
        
        # 3. Add Edges
        for term in terms:
            G.add_node(term, type="concept")
            concept_nodes.add(term)
            G.add_edge(sheet_name, term)
            
    if len(paper_nodes) == 0:
        logging.warning("No papers found to graph.")
        return

    # --- Visualization ---
    
    # Obsidian Theme Colors (UPDATED Colors for Blue/Red scheme)
    BG_COLOR = "#202020"
    PAPER_COLOR = "#FF4500" # Bright Red/Orange-Red
    CONCEPT_COLOR = "#00BFFF" # Deep Sky Blue
    EDGE_COLOR = "#505050"
    TEXT_COLOR = "white"
    
    # Dynamic Canvas Scaling
    num_papers = len(paper_nodes)
    num_nodes = G.number_of_nodes()
    
    # Base size (10 inches) + Growth Factor (0.5 inch per paper)
    calc_size = 10 + (num_papers * 0.5)
    final_size = min(calc_size, 50) # Cap at 50x50
    
    logging.info(f"Graph Scaling: {num_papers} papers -> Canvas Size {final_size}x{final_size} inches")
    
    # Increase DPI and figure size for better quality
    plt.figure(figsize=(final_size, final_size), facecolor=BG_COLOR, dpi=150)
    ax = plt.gca()
    ax.set_facecolor(BG_COLOR)
    
    # Dynamic Layout Physics
    # k: Optimal distance between nodes. 
    # General rule: k ~ 1/sqrt(n). For disconnected/sparse graphs, larger k helps.
    import math
    if num_nodes > 0:
        k_val = 1.0 / math.sqrt(num_nodes)
        # Tweak: multiply by a factor to spread out more on larger canvas
        k_val = k_val * 2.0 
    else:
        k_val = 0.5
        
    pos = nx.spring_layout(G, k=k_val, iterations=50, seed=42)
    
    # Sizes
    node_sizes = []
    node_colors = []
    
    for node in G.nodes():
        if G.nodes[node].get("type") == "paper":
            node_sizes.append(350)
            node_colors.append(PAPER_COLOR)
        else:
            degree = G.degree(node)
            size = 150 + (degree * 200) # Slightly larger concept nodes
            node_sizes.append(size)
            node_colors.append(CONCEPT_COLOR)
            
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.9, ax=ax)
    
    # Draw Edges
    nx.draw_networkx_edges(G, pos, width=1.0, edge_color=EDGE_COLOR, alpha=0.6, ax=ax)
    
    # Draw Labels with improved font size
    nx.draw_networkx_labels(G, pos, font_size=9, font_color=TEXT_COLOR, font_family="sans-serif", ax=ax)
    
    plt.axis('off')
    plt.tight_layout()
    
    # Save to Buffer with high DPI for quality insertion in Excel
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png', facecolor=BG_COLOR, edgecolor='none', dpi=200)
    img_buffer.seek(0)
    plt.close()

    
    # --- Excel Integration ---
    GRAPH_SHEET_NAME = "Knowledge Graph"
    
    if GRAPH_SHEET_NAME in wb.sheetnames:
        ws = wb[GRAPH_SHEET_NAME]
        ws.delete_rows(1, 100) # Clear
        # Clear images? Hard to clear images easily in openpyxl without deleting sheet
        del wb[GRAPH_SHEET_NAME]
        ws = wb.create_sheet(GRAPH_SHEET_NAME, 0)
    else:
        ws = wb.create_sheet(GRAPH_SHEET_NAME, 0)
        
    # Move to index 0 (or 1 if dashboard is 0? User said "at Index 0 and desplace the rests to right")
    # If Dashboard is at 0, this will take 0 and push Dashboard to 1?
    # User said "Dashboard" as first tab in previous prompt.
    # Now says "Knowledge Graph" at Index 0.
    # I'll put Graph at 0, Dashboard at 1. Or maybe Graph at 1?
    # "at Index 0". I will obey.
    if wb.sheetnames[0] != GRAPH_SHEET_NAME:
        wb.move_sheet(ws, offset=-wb.index(ws))

    # Insert Image
    img = Image(img_buffer)
    img.anchor = 'A1'
    ws.add_image(img)
    
    logging.info(f"Knowledge Graph inserted into '{GRAPH_SHEET_NAME}' sheet.")

if __name__ == "__main__":
    # Test
    # build_graph_from_excel("Paper_Analysis_Results.xlsx")
    pass
