"""
This module provides SVG map data and functions for creating
an interactive zone-based project progress visualization.
"""

# Define a simplified SVG representation of the site layout
# The zones correspond to the blocks in the layout diagram
SITE_MAP_SVG = """
<svg viewBox="0 0 1000 600" xmlns="http://www.w3.org/2000/svg">
    <!-- Border -->
    <rect x="10" y="10" width="980" height="580" fill="none" stroke="black" stroke-width="2"/>
    
    <!-- Block 1C area -->
    <path id="block-1c" d="M 180,350 L 80,450 L 180,500 L 320,500 L 400,400 L 300,330 Z" 
          fill="#e6f7ff" stroke="black" stroke-width="2" 
          data-name="BLOCK-1C" data-zone="production"/>
    
    <!-- Block 2C area -->
    <path id="block-2c" d="M 400,400 L 320,500 L 500,550 L 650,450 L 550,350 L 450,380 Z" 
          fill="#e6f7ff" stroke="black" stroke-width="2" 
          data-name="BLOCK-2C" data-zone="production"/>
    
    <!-- Main facility area -->
    <path id="facility-area" d="M 300,330 L 400,400 L 450,380 L 550,350 L 500,250 L 350,200 L 250,250 Z" 
          fill="#fff0e6" stroke="black" stroke-width="2" 
          data-name="Facility Area" data-zone="facility"/>
    
    <!-- Green area -->
    <path id="green-area" d="M 350,200 L 500,250 L 600,200 L 700,220 L 750,170 L 550,100 L 350,120 Z" 
          fill="#e6ffe6" stroke="black" stroke-width="2" 
          data-name="Green Area" data-zone="green"/>
    
    <!-- Pond area -->
    <rect id="pond-area" x="150" y="190" width="150" height="110" 
          fill="#e6f9ff" stroke="black" stroke-width="2" 
          data-name="Pond Area" data-zone="pond"/>
    
    <!-- Private area -->
    <rect id="private-area" x="700" y="300" width="150" height="100" rx="10" ry="10" 
          fill="#ffe6e6" stroke="black" stroke-width="2" 
          data-name="Private Area" data-zone="private"/>
    
    <!-- Labels -->
    <text x="150" y="440" font-family="Arial" font-size="20" fill="black">BLOCK-1C</text>
    <text x="470" y="470" font-family="Arial" font-size="20" fill="black">BLOCK-2C</text>
    <text x="370" y="310" font-family="Arial" font-size="16" fill="black">Facility Area</text>
    <text x="500" y="170" font-family="Arial" font-size="16" fill="black">Green Area</text>
    <text x="180" y="250" font-family="Arial" font-size="16" fill="black">Pond</text>
    <text x="730" y="350" font-family="Arial" font-size="16" fill="black">Private</text>
    
    <!-- Compass -->
    <circle cx="80" cy="80" r="30" fill="white" stroke="black" stroke-width="1"/>
    <path d="M 80,50 L 80,110" stroke="black" stroke-width="1"/>
    <path d="M 50,80 L 110,80" stroke="black" stroke-width="1"/>
    <text x="80" y="60" font-family="Arial" font-size="14" text-anchor="middle" fill="black">N</text>
    <text x="80" y="105" font-family="Arial" font-size="14" text-anchor="middle" fill="black">S</text>
    <text x="55" y="85" font-family="Arial" font-size="14" text-anchor="middle" fill="black">W</text>
    <text x="105" y="85" font-family="Arial" font-size="14" text-anchor="middle" fill="black">E</text>
</svg>
"""

# Map for zone names to the corresponding SVG element IDs
ZONE_TO_ID_MAP = {
    "BLOCK-1C": "block-1c",
    "BLOCK-2C": "block-2c",
    "FACILITY AREA": "facility-area",
    "GREEN AREA": "green-area", 
    "POND AREA": "pond-area",
    "PRIVATE AREA": "private-area"
}

# Function to generate HTML with colored zones based on progress data
def generate_colored_map(progress_data):
    """
    Generate an HTML representation of the site map with zones colored by progress.
    
    Args:
        progress_data: Dictionary mapping zone names to progress percentages (0-100)
        
    Returns:
        HTML string with the SVG map and interactive elements
    """
    # We'll manually build a new SVG from scratch to avoid any HTML parsing issues
    svg_open = """<svg viewBox="0 0 1000 600" xmlns="http://www.w3.org/2000/svg">
    <style>
        path:hover, rect:hover {
            stroke-width: 3;
            stroke: #333;
            cursor: pointer;
            filter: brightness(1.1);
        }
    </style>
    <rect x="10" y="10" width="980" height="580" fill="none" stroke="black" stroke-width="2"/>
    """
    
    svg_close = """</svg>"""
    
    # Color logic - from red (0%) to green (100%)
    def get_color_for_progress(progress):
        # Red to yellow to green gradient
        if progress < 50:
            # Red to yellow (map 0-50 to 0-100)
            mapped = progress * 2
            r = 255
            g = int(255 * (mapped / 100))
            b = 0
        else:
            # Yellow to green (map 50-100 to 0-100)
            mapped = (progress - 50) * 2
            r = int(255 * (1 - mapped / 100))
            g = 255
            b = 0
        
        # Return with opacity for better visualization
        return f"rgba({r}, {g}, {b}, 0.7)"
    
    # Build the SVG content with each zone and its colors
    svg_content = ""
    
    # Block 1C area
    block_1c_progress = 0
    for zone_name, progress in progress_data.items():
        if "BLOCK-1C" in zone_name.upper():
            block_1c_progress = progress
            break
    
    svg_content += f"""
    <path id="block-1c" d="M 180,350 L 80,450 L 180,500 L 320,500 L 400,400 L 300,330 Z" 
          fill="{get_color_for_progress(block_1c_progress)}" stroke="black" stroke-width="2" 
          data-name="BLOCK-1C" data-zone="production">
          <title>BLOCK-1C: {block_1c_progress:.1f}% complete</title>
    </path>
    """
    
    # Block 2C area
    block_2c_progress = 0
    for zone_name, progress in progress_data.items():
        if "BLOCK-2C" in zone_name.upper():
            block_2c_progress = progress
            break
    
    svg_content += f"""
    <path id="block-2c" d="M 400,400 L 320,500 L 500,550 L 650,450 L 550,350 L 450,380 Z" 
          fill="{get_color_for_progress(block_2c_progress)}" stroke="black" stroke-width="2" 
          data-name="BLOCK-2C" data-zone="production">
          <title>BLOCK-2C: {block_2c_progress:.1f}% complete</title>
    </path>
    """
    
    # Facility area
    facility_progress = 0
    for zone_name, progress in progress_data.items():
        if "FACILITY" in zone_name.upper():
            facility_progress = progress
            break
    
    svg_content += f"""
    <path id="facility-area" d="M 300,330 L 400,400 L 450,380 L 550,350 L 500,250 L 350,200 L 250,250 Z" 
          fill="{get_color_for_progress(facility_progress)}" stroke="black" stroke-width="2" 
          data-name="Facility Area" data-zone="facility">
          <title>FACILITY AREA: {facility_progress:.1f}% complete</title>
    </path>
    """
    
    # Green area
    green_progress = 0
    for zone_name, progress in progress_data.items():
        if "GREEN" in zone_name.upper():
            green_progress = progress
            break
    
    svg_content += f"""
    <path id="green-area" d="M 350,200 L 500,250 L 600,200 L 700,220 L 750,170 L 550,100 L 350,120 Z" 
          fill="{get_color_for_progress(green_progress)}" stroke="black" stroke-width="2" 
          data-name="Green Area" data-zone="green">
          <title>GREEN AREA: {green_progress:.1f}% complete</title>
    </path>
    """
    
    # Pond area
    pond_progress = 0
    for zone_name, progress in progress_data.items():
        if "POND" in zone_name.upper():
            pond_progress = progress
            break
    
    svg_content += f"""
    <rect id="pond-area" x="150" y="190" width="150" height="110" 
          fill="{get_color_for_progress(pond_progress)}" stroke="black" stroke-width="2" 
          data-name="Pond Area" data-zone="pond">
          <title>POND AREA: {pond_progress:.1f}% complete</title>
    </rect>
    """
    
    # Private area
    private_progress = 0
    for zone_name, progress in progress_data.items():
        if "PRIVATE" in zone_name.upper():
            private_progress = progress
            break
    
    svg_content += f"""
    <rect id="private-area" x="700" y="300" width="150" height="100" rx="10" ry="10" 
          fill="{get_color_for_progress(private_progress)}" stroke="black" stroke-width="2" 
          data-name="Private Area" data-zone="private">
          <title>PRIVATE AREA: {private_progress:.1f}% complete</title>
    </rect>
    """
    
    # Add labels
    svg_content += """
    <text x="150" y="440" font-family="Arial" font-size="20" fill="black">BLOCK-1C</text>
    <text x="470" y="470" font-family="Arial" font-size="20" fill="black">BLOCK-2C</text>
    <text x="370" y="310" font-family="Arial" font-size="16" fill="black">Facility Area</text>
    <text x="500" y="170" font-family="Arial" font-size="16" fill="black">Green Area</text>
    <text x="180" y="250" font-family="Arial" font-size="16" fill="black">Pond</text>
    <text x="730" y="350" font-family="Arial" font-size="16" fill="black">Private</text>
    """
    
    # Add compass
    svg_content += """
    <circle cx="80" cy="80" r="30" fill="white" stroke="black" stroke-width="1"/>
    <path d="M 80,50 L 80,110" stroke="black" stroke-width="1"/>
    <path d="M 50,80 L 110,80" stroke="black" stroke-width="1"/>
    <text x="80" y="60" font-family="Arial" font-size="14" text-anchor="middle" fill="black">N</text>
    <text x="80" y="105" font-family="Arial" font-size="14" text-anchor="middle" fill="black">S</text>
    <text x="55" y="85" font-family="Arial" font-size="14" text-anchor="middle" fill="black">W</text>
    <text x="105" y="85" font-family="Arial" font-size="14" text-anchor="middle" fill="black">E</text>
    """
    
    # Complete SVG
    svg_complete = svg_open + svg_content + svg_close
    
    # Add debug info for troubleshooting
    debug_info = f"""
    <div style="display:none">
        <p>Progress data: {progress_data}</p>
    </div>
    """
    
    # Wrap in a div with styling for better mobile display and add fallback content
    html = f"""
    <div style="width:100%; overflow-x:auto; max-width:100%; margin:0 auto; min-height:300px; border:1px solid #eee;">
        {svg_complete}
        {debug_info}
    </div>
    """
    
    return html

# Function to extract zone progress from project data
def extract_zone_progress(df):
    """
    Extract progress data by zone from the project dataframe.
    
    Args:
        df: DataFrame containing project data with 'AREA PEKERJAAN' and '% COMPLETE' columns
        
    Returns:
        Dictionary mapping zone names to average progress percentages
    """
    if 'AREA PEKERJAAN' not in df.columns:
        # If no area column exists, try to map using task descriptions
        return extract_zone_progress_from_tasks(df)
    
    # Group by area and calculate weighted average progress
    if 'BOBOT' in df.columns:
        # Use weighted average if weights are available
        grouped = df.groupby('AREA PEKERJAAN').apply(
            lambda x: (x['% COMPLETE'] * x['BOBOT']).sum() / x['BOBOT'].sum() 
            if x['BOBOT'].sum() > 0 else x['% COMPLETE'].mean()
        )
    else:
        # Otherwise use simple average
        grouped = df.groupby('AREA PEKERJAAN')['% COMPLETE'].mean()
    
    return grouped.to_dict()

def extract_zone_progress_from_tasks(df):
    """
    Attempt to extract zone information from task descriptions when no area column exists.
    
    Args:
        df: DataFrame containing project data with 'JENIS PEKERJAAN' and '% COMPLETE' columns
        
    Returns:
        Dictionary mapping zone names to average progress percentages
    """
    import pandas as pd
    import re
    
    # Keywords to look for in task descriptions
    zone_keywords = {
        'BLOCK-1C': ['block 1c', 'block-1c', 'block1c', 'blok 1c'],
        'BLOCK-2C': ['block 2c', 'block-2c', 'block2c', 'blok 2c'],
        'FACILITY AREA': ['facility', 'fasilitas', 'kantor', 'office'],
        'GREEN AREA': ['green', 'taman', 'garden', 'landscape'],
        'POND AREA': ['pond', 'kolam', 'water', 'air'],
        'PRIVATE AREA': ['private', 'pribadi', 'housing', 'perumahan']
    }
    
    # Create a new column for the mapped zone
    df = df.copy()
    df['MAPPED_ZONE'] = 'UNKNOWN'
    
    # Function to determine zone from task description
    def map_to_zone(task_desc):
        if not isinstance(task_desc, str):
            return 'UNKNOWN'
            
        task_lower = task_desc.lower()
        for zone, keywords in zone_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                return zone
        return 'UNKNOWN'
    
    # Apply the mapping function
    df['MAPPED_ZONE'] = df['JENIS PEKERJAAN'].apply(map_to_zone)
    
    # Calculate progress by mapped zone
    if 'BOBOT' in df.columns:
        # Use weighted average if weights are available
        grouped = df.groupby('MAPPED_ZONE').apply(
            lambda x: (x['% COMPLETE'] * x['BOBOT']).sum() / x['BOBOT'].sum() 
            if x['BOBOT'].sum() > 0 else x['% COMPLETE'].mean()
        )
    else:
        # Otherwise use simple average
        grouped = df.groupby('MAPPED_ZONE')['% COMPLETE'].mean()
    
    # Remove UNKNOWN zone if present
    if 'UNKNOWN' in grouped:
        grouped = grouped.drop('UNKNOWN')
        
    # Assign some default values if no data available for some zones
    result = grouped.to_dict()
    
    # Ensure all zones have some value
    for zone in ZONE_TO_ID_MAP.keys():
        if zone not in result:
            result[zone] = 0
            
    return result