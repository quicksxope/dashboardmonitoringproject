import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date
import unicodedata
import re
import base64
import io
from io import BytesIO
import numpy as np
import plotly.graph_objects as go

def clean_text(x):
    if pd.isna(x):
        return ''
    x = unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode('utf-8')
    x = re.sub(r'\s+', ' ', x)
    return x.strip().upper()

st.set_page_config(page_title="📊 PT INCA Dashboard", layout="wide")

# Mobile styling
st.markdown("""
<style>
@media (max-width: 768px) {
    .element-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    div[data-testid="column"] > div {
        margin-bottom: 1rem;
    }
    h2 {
        font-size: 1.4rem !important;
    }
    .stMarkdown > div {
        font-size: 0.95rem;
    }
    
    /* Remove unwanted borders and outlines on mobile without affecting backgrounds */
    div:not(.metric-card), span, p, h1, h2, h3, h4, h5, h6, a, button, input, select, 
    textarea, table, tr, td, th, ul, ol, li, section, article, 
    header, footer, nav, aside, main, figure, figcaption, blockquote, 
    pre, code, svg, canvas, img, iframe, object, embed, video, audio {
        border: none !important;
        outline: none !important;
    }
    
    /* Override any background color settings on .metric-card to ensure gradients work */
    .metric-card {
        background-color: initial !important;
    }
    
    /* Make sure metric cards preserve their gradient backgrounds */
    .metric-card {
        border: none !important;
        box-shadow: 0 3px 10px rgba(0,0,0,0.2) !important;
    }
    
    /* Keep only the metric card children backgrounds transparent */
    .metric-card div {
        background: transparent !important;
    }
    
    /* Better spacing for buttons */
    .stButton button {
        margin: 0.25rem 0 !important;
    }
    
    /* Adjust table styling for better mobile view */
    .stDataFrame, .stTable {
        overflow-x: auto !important;
        font-size: 0.9rem !important;
    }
}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data(file):
    # Load the main data sheet
    df = pd.read_excel(file, sheet_name="BASE DATA (wajib update)")
    df.columns = df.columns.str.strip()
    
    # Clean text columns
    for col in ['KONTRAK', 'JENIS PEKERJAAN', 'STATUS']:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)
    
    # Format percentage completion
    if '% COMPLETE' in df.columns:
        df['% COMPLETE'] = df['% COMPLETE'].apply(lambda x: x * 100 if x <= 1 else x)
    
    # Add unique ID for tasks if it doesn't exist
    if 'TASK_ID' not in df.columns:
        df['TASK_ID'] = [f"task_{i}" for i in range(len(df))]
    
    # Add task level for hierarchical view if it doesn't exist
    if 'TASK_LEVEL' not in df.columns:
        # Default all tasks to level 1, but try to infer hierarchy from task names if possible
        df['TASK_LEVEL'] = 1
        
        # Try to identify parent-child relationships from task names
        # For example, if tasks have numbering like "1. Main Task" and "1.1 Subtask"
        # This is a simple heuristic and might not work for all data
        # In a real app, this would come from the data source
        if 'JENIS PEKERJAAN' in df.columns:
            # Check for common patterns like "1.1", "1.1.1", etc.
            df['TASK_LEVEL'] = df['JENIS PEKERJAAN'].apply(
                lambda x: len(str(x).split('.')) if re.match(r'^\d+(\.\d+)*', str(x)) else 1
            )
    
    # Determine if a task is a milestone (typically very short duration tasks)
    if 'IS_MILESTONE' not in df.columns:
        if {'START', 'PLAN END'}.issubset(df.columns):
            # Calculate task duration in days
            df['DURATION'] = (pd.to_datetime(df['PLAN END']) - pd.to_datetime(df['START'])).dt.days
            # Consider tasks with 0-1 day duration as milestones
            df['IS_MILESTONE'] = df['DURATION'] <= 1
        else:
            df['IS_MILESTONE'] = False
    
    # For demo purposes, let's assume some dependencies between tasks
    # In a real app, this would come from the data source
    if 'PREDECESSORS' not in df.columns:
        df['PREDECESSORS'] = ""
        
        # Create simple sequential dependencies within same project
        if 'KONTRAK' in df.columns:
            for project in df['KONTRAK'].unique():
                project_tasks = df[df['KONTRAK'] == project].sort_values('START').copy()
                for i in range(1, len(project_tasks)):
                    curr_id = project_tasks.iloc[i]['TASK_ID']
                    prev_id = project_tasks.iloc[i-1]['TASK_ID']
                    df.loc[df['TASK_ID'] == curr_id, 'PREDECESSORS'] = prev_id
    
    # Resource data is not available yet, so we won't generate mock data
    
    # Calculate planned vs actual progress
    if '% COMPLETE' in df.columns and 'PLAN_PROGRESS' not in df.columns:
        # Simplified calculation - in real life this would be based on actual planned values
        today = datetime.today()
        df['PLAN_PROGRESS'] = df.apply(
            lambda row: calculate_planned_progress(row, today), 
            axis=1
        )
    
    return df

def calculate_planned_progress(row, today):
    """Calculate what the planned progress should be based on dates"""
    try:
        start = pd.to_datetime(row['START'], errors='coerce')
        end = pd.to_datetime(row['PLAN END'], errors='coerce')
        
        if pd.isna(start) or pd.isna(end):
            return 0
        
        # If task is completed or past due date
        if today >= end:
            return 100
        # If task hasn't started yet
        elif today <= start:
            return 0
        # If task is in progress
        else:
            total_days = (end - start).days
            if total_days <= 0:  # For tasks with same start and end date
                return 50
            days_in = (today - start).days
            return min(100, max(0, (days_in / total_days) * 100))
    except:
        return 0

@st.cache_data
def calculate_priority_score(row):
    """Calculate priority score based on deadline, weight, and status"""
    today = datetime.today()
    
    try:
        deadline = pd.to_datetime(row['PLAN END'], errors='coerce')
        if pd.isna(deadline):
            days_left = 100  # Default high value for missing deadlines
        else:
            days_left = max(1, (deadline - today).days)  # At least 1 day to avoid division by zero
            
        # Overdue tasks get higher priority
        if days_left < 0:
            deadline_factor = 100
        else:
            deadline_factor = min(100, 100 / days_left)
            
        # Weight factor - higher weight means higher priority
        weight_factor = row['BOBOT'] * 10
        
        # Status factor - different statuses have different priorities
        status_mapping = {
            'TUNDA': 80,
            'DALAM PROSES': 60,
            'BELUM MULAI': 40,
            'SELESAI': 0
        }
        status_factor = status_mapping.get(row['STATUS'], 30)
        
        # Incomplete factor - tasks with lower completion percentage get higher priority
        incomplete_factor = 100 - row['% COMPLETE']
        
        # Calculate final score (0-100 range)
        score = (deadline_factor * 0.4) + (weight_factor * 0.3) + (status_factor * 0.2) + (incomplete_factor * 0.1)
        return min(100, score)
    
    except Exception:
        return 50  # Default for any errors
        
@st.cache_data
def create_enhanced_tooltip(row):
    """Create an enhanced tooltip with all available task information"""
    tooltip = f"<b>{row['JENIS PEKERJAAN']}</b><br>Project: {row['KONTRAK']}<br>Status: {row['STATUS']}"
    
    # Add progress if available
    if '% COMPLETE' in row and not pd.isna(row['% COMPLETE']):
        tooltip += f"<br>Progress: {row['% COMPLETE']:.1f}%"
    
    # Add dates
    if 'START' in row and 'PLAN END' in row:
        start_str = row['START'].strftime('%Y-%m-%d')
        end_str = row['PLAN END'].strftime('%Y-%m-%d')
        tooltip += f"<br>Duration: {start_str} to {end_str}"
    
    # Add resource if available
    if 'RESOURCE' in row and not pd.isna(row['RESOURCE']):
        tooltip += f"<br>Resource: {row['RESOURCE']}"
    
    # Add milestone indicator
    if 'IS_MILESTONE' in row and row['IS_MILESTONE']:
        tooltip += "<br><b>MILESTONE</b>"
    
    return tooltip

# Critical path functions removed - not being used anymore
        
def get_to_csv_download_link(df, filename="data.csv", text="Download CSV"):
    """Generate a download link for a DataFrame"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href
    
def get_excel_download_link(df, filename="data.xlsx", text="Download Excel"):
    """Generate a download link for Excel file"""
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, sheet_name='Sheet1', index=False)
    writer.close()
    output.seek(0)
    
    b64 = base64.b64encode(output.read()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{text}</a>'
    return href
    
def get_py_download_link(text="Download Fixed Python File"):
    """Generate a download link for the clean_version.py file"""
    with open('clean_version.py', 'r') as f:
        py_code = f.read()
    
    b64 = base64.b64encode(py_code.encode()).decode()
    href = f'<a href="data:text/plain;base64,{b64}" download="fixed_dashboard.py">{text}</a>'
    return href

@st.cache_data
def card(title, value, sub, icon="✅", bg="#ffffff"):
    # Define better color schemes with gradients for better contrast - each card with its own color
    if bg.lower() == "#e3f2fd":  # Blue - Tasks Completed
        gradient = "linear-gradient(135deg, #1976d2, #2196f3)"
        text_color = "#ffffff"
        sub_color = "#e1f5fe"
        shadow_color = "rgba(25, 118, 210, 0.4)"
    elif bg.lower() == "#f1f8e9":  # Green - Upcoming Deadlines
        gradient = "linear-gradient(135deg, #388e3c, #4caf50)"
        text_color = "#ffffff"
        sub_color = "#e8f5e9"
        shadow_color = "rgba(56, 142, 60, 0.4)"
    elif bg.lower() == "#fff3e0":  # Orange - In Progress
        gradient = "linear-gradient(135deg, #e65100, #ff9800)"
        text_color = "#ffffff"
        sub_color = "#fff3e0"
        shadow_color = "rgba(230, 81, 0, 0.4)"
    elif bg.lower() in ["#ffebee", "#ffe0e0"]:  # Red - Pending Issues
        gradient = "linear-gradient(135deg, #c62828, #f44336)"
        text_color = "#ffffff"
        sub_color = "#ffebee"
        shadow_color = "rgba(198, 40, 40, 0.4)"
    else:
        gradient = f"linear-gradient(135deg, {bg}, {bg})"
        text_color = "#ffffff"
        sub_color = "#e0e0e0"
        shadow_color = "rgba(0, 0, 0, 0.3)"
    
    return f"""
    <div class="metric-card" style="padding:1.2rem; background:{gradient}; border-radius:1rem; box-shadow:0 3px 10px {shadow_color}; text-align:center; margin-bottom:1rem; height:100%; width:100%; max-width:100%; border:none !important; outline:none !important;">
        <div style="font-size:1.5rem; margin-bottom:0.3rem; border:none !important;">{icon}</div>
        <div style="font-size:1.2rem; font-weight:600; color:{text_color}; text-shadow:1px 1px 2px rgba(0,0,0,0.2); margin-bottom:0.5rem; border:none !important;">{title}</div>
        <div style="font-size:calc(1.5rem + 0.5vw); font-weight:700; margin:0.6rem 0; color:{text_color}; text-shadow:1px 1px 2px rgba(0,0,0,0.2); border:none !important;">{value}</div>
        <div style="color:{sub_color}; font-size:0.9rem; border:none !important;">{sub}</div>
    </div>
    """

def section_card(title=None):
    """Create a modern card container for a section of the dashboard
    Returns a context manager that will be used with 'with' statement
    """
    container = st.container()
    
    # Create a unique ID for this section to target with CSS
    section_id = f"section_{title.replace(' ', '_').lower() if title else 'no_title'}"
    
    # Apply custom styling to make it look like a modern card with shadow
    if title:
        container.markdown(f"""
        <div id="{section_id}_header" style="background: linear-gradient(to right, #3498db, #1abc9c); color: white; padding: 12px 15px; 
                border-radius: 10px 10px 0 0; margin-bottom: 0; font-weight: 600; font-size: 1.2rem;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.3); box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            {title}
        </div>
        """, unsafe_allow_html=True)
    
    # Return a styled container with a subtle gradient background and shadow
    container = st.container(border=True)
    
    # Add a subtle gradient background and shadow to the container
    st.markdown(f"""
    <style>
    /* Styling for section container */
    [data-testid="stExpander"] .streamlit-expanderContent {{
        background: linear-gradient(to bottom, #f8f9fa, #e9ecef);
    }}
    .stAlert {{
        background-color: white !important;
    }}
    
    /* Add shadow to the container */
    [data-testid="stContainer"] > [data-testid="block-container"] > [data-testid="stVerticalBlock"] > div:has(> [data-testid="stHorizontalBlock"] > [data-testid="column"]):nth-of-type(n+{container.id}) {{
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        border-radius: 0 0 10px 10px;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
    }}
    </style>
    """, unsafe_allow_html=True)
    
    return container


import streamlit as st

# --- Basic User Database ---
USERS = {
    'admin': {'password': 'admin123', 'role': 'admin'},
    'john': {'password': 'john123', 'role': 'viewer'},
    'sarah': {'password': 'sarahpass', 'role': 'editor'}
}

# --- Initialize Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# --- Login Section ---
if not st.session_state.logged_in:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = USERS.get(username)
        if user and user['password'] == password:
            st.session_state.logged_in = True
            st.session_state.user = username
            st.session_state.role = user['role']
            st.success(f"Welcome, {username}!")
            st.rerun()
        else:
            st.error("❌ Invalid username or password")
    st.stop()

# --- Sidebar info & logout ---
st.sidebar.markdown(f"👤 **User:** {st.session_state.user}")
st.sidebar.markdown(f"🔑 **Role:** {st.session_state.role}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()


def main():
    # Ensure pandas is available in this scope
    import pandas as pd
    from datetime import datetime
    
    # Add responsive viewport meta tag for better mobile display
    st.markdown("""
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                @media (max-width: 640px) {
                    .metric-card {
                        margin-bottom: 1rem !important;
                    }
                    /* Make sure content doesn't overflow on small screens */
                    .stPlotlyChart {
                        max-width: 100%;
                        overflow-x: auto;
                    }
                    /* Improve table responsiveness */
                    .stTable, .dataframe {
                        overflow-x: auto;
                        font-size: 0.9rem;
                    }
                    /* Adjust header on mobile */
                    h2 {
                        font-size: 1.5rem !important;
                    }
                    h3 {
                        font-size: 1.2rem !important;
                    }
                    /* Improve sidebar usability on mobile */
                    .st-emotion-cache-16txtl3, .st-emotion-cache-z5fcl4 {
                        padding-top: 1rem;
                        padding-left: 0.8rem;
                        padding-right: 0.8rem;
                    }
                    /* Smaller padding on expanders for mobile */
                    .st-expander {
                        padding: 0.5rem !important;
                    }
                    /* Better tooltip visibility on mobile */
                    .tooltip-inner {
                        max-width: 200px !important;
                        font-size: 0.8rem !important;
                    }
                    /* Remove black borders from all elements on mobile */
                    div, span, p, h1, h2, h3, h4, h5, h6, a, button, input, select, 
                    textarea, table, tr, td, th, ul, ol, li, section, article, 
                    header, footer, nav, aside, main, figure, figcaption, blockquote, 
                    pre, code, svg, canvas, img, iframe, object, embed, video, audio {
                        border: none !important;
                        outline: none !important;
                        box-shadow: none !important;
                    }
                    /* But keep shadows for cards and sections */
                    .metric-card, [data-testid="stContainer"] > [data-testid="block-container"] > [data-testid="stVerticalBlock"] > div:has(> [data-testid="stHorizontalBlock"] > [data-testid="column"]) {
                        box-shadow: 0 3px 10px rgba(0,0,0,0.2) !important;
                    }
                    
                    /* High contrast version of info messages for dark mode */
                    .high-contrast-info {
                        background-color: rgba(51, 102, 255, 0.15) !important;
                        border-left: 5px solid #3366ff !important;
                        color: white !important;
                        padding: 10px 15px !important;
                        border-radius: 4px !important;
                        margin: 8px 0 !important;
                        font-weight: 500 !important;
                    }
                    
                    /* Make sure alerts and St.info boxes are visible in dark mode */
                    .stAlert, [data-baseweb="notification"] {
                        background-color: rgba(240, 240, 240, 0.1) !important;
                        color: white !important;
                    }
                }
            </style>
        </head>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='margin-bottom: 1rem;'>📋 Project Monitoring Dashboard</h2>", unsafe_allow_html=True)
    
    uploaded_file = st.sidebar.file_uploader("📂 Upload Excel File", type="xlsx")
    if not uploaded_file:
        # Mobile-friendly empty state message
        st.warning("Please upload an Excel file to continue.")
        
        # Show a sample of expected data format
        st.markdown("### 📊 Sample Data Format")
        st.markdown("""
        The dashboard expects Excel files with the following columns:
        - **KONTRAK**: Project identifier
        - **JENIS PEKERJAAN**: Task description
        - **START**: Task start date
        - **PLAN END**: Task planned end date
        - **STATUS**: Task status (SELESAI, DALAM PROSES, TUNDA, BELUM MULAI)
        - **% COMPLETE**: Completion percentage (0-100)
        - **BOBOT**: Task weight (importance)
        """)
        
        # Give mobile-friendly instructions
        st.info("👈 Tap the arrow icon in the top-left corner to open the sidebar and upload your file")
        return

    original_df = load_data(uploaded_file)
    df = original_df.copy()

    kontrak_opts = ['All'] + sorted(original_df['KONTRAK'].dropna().unique())
    selected_kontrak = st.sidebar.selectbox("Filter by KONTRAK", kontrak_opts)

    filter_columns = [col for col in df.columns if col not in ['KONTRAK', 'NO']]
    selected_filter_col = st.sidebar.selectbox("Filter Column", filter_columns)
    filter_values = ['All'] + sorted(original_df[selected_filter_col].dropna().unique())
    selected_filter_val = st.sidebar.selectbox("Select Value", filter_values)

    if selected_kontrak != 'All':
        df = df[df['KONTRAK'] == selected_kontrak]
    if selected_filter_val != 'All':
        df = df[df[selected_filter_col] == selected_filter_val]

    total_tasks = len(df)
    completed = (df['STATUS'] == 'SELESAI').sum()
    upcoming = (pd.to_datetime(df['PLAN END'], errors='coerce') - datetime.today()).dt.days.between(0, 7).sum()
    ongoing = (df['STATUS'] == 'DALAM PROSES').sum()
    pending = df[df['STATUS'].isin(['TUNDA', 'BELUM MULAI'])].shape[0]

    # Add some space at the top
    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
    
    # Responsive 2x2 Cards with better spacing
    col1, col2 = st.columns([1, 1], gap="large")
    
    # First row
    with col1:
        st.markdown(card("Tasks Completed", f"{completed}/{total_tasks}", "Done", "✅", "#e3f2fd"), unsafe_allow_html=True)
        
    with col2:
        st.markdown(card("Upcoming Deadlines", upcoming, "Within 7 Days", "📅", "#f1f8e9"), unsafe_allow_html=True)
    
    # Add spacing between rows
    st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
    
    # Second row
    col3, col4 = st.columns([1, 1], gap="large")
    with col3:
        st.markdown(card("In Progress", ongoing, "Active Tasks", "🚧", "#fff3e0"), unsafe_allow_html=True)
        
    with col4:
        st.markdown(card("Pending Issues", pending, "Status: Tunda/Belum Mulai", "⚠️", "#ffebee"), unsafe_allow_html=True)
        
    # Add spacing after cards
    st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)

    # --- Weighted Progress ---
    with section_card("🎯 Weighted Progress by Bobot × % Complete (All Projects)"):
        colA, colB = st.columns(2)
        for project, col in zip(['PROJECT 1 A', 'PROJECT 1 B'], [colA, colB]):
            proj_df = original_df[original_df['KONTRAK'] == project]
            if not proj_df.empty:
                weighted = (proj_df['BOBOT'] * proj_df['% COMPLETE']).sum()
                total_bobot = proj_df['BOBOT'].sum()
                progress = (weighted / total_bobot) if total_bobot else 0
                with col:
                    st.markdown(f"**📌 {project}**")
                    st.progress(int(progress))
                    st.caption(f"Progress: **{progress:.2f}%**")
            else:
                with col:
                    st.markdown(f"**📌 {project}**")
                    st.info("No data available.")

    # --- Timeline & Task Table ---
    with section_card("🗓 Interactive Project Timeline"):
        # Define color map
        color_map = {
            'SELESAI': 'green',
            'DALAM PROSES': 'blue',
            'TUNDA': 'orange',
            'BELUM MULAI': 'yellow',
            'TERLAMBAT' : 'red'
        }
        
        # Project filter buttons with visual indicators
        st.write("Filter Timeline by Project:")
        
        # Use session state to track the active filter
        if 'active_project_filter' not in st.session_state:
            st.session_state.active_project_filter = 'all'
            
        # Reset button state flags on each run
        if 'button_clicked_this_run' not in st.session_state:
            st.session_state.button_clicked_this_run = False
            
        # Callback functions to update session state for each button
        def set_all_filter():
            st.session_state.active_project_filter = 'all'
            st.session_state.button_clicked_this_run = True
            
        def set_p1a_filter():
            st.session_state.active_project_filter = 'p1a'
            st.session_state.button_clicked_this_run = True
            
        def set_p1b_filter():
            st.session_state.active_project_filter = 'p1b'
            st.session_state.button_clicked_this_run = True
            
        # Define button styles based on active state
        active_style = """
            background: linear-gradient(to right, #3498db, #1abc9c);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            font-weight: bold;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            margin: 5px 0;
            width: 100%;
        """
        
        inactive_style = """
            background: #f0f2f6;
            color: #31333F;
            border: 1px solid #e0e0e0;
            padding: 8px 16px;
            border-radius: 5px;
            font-weight: normal;
            margin: 5px 0;
            width: 100%;
        """
        
        # Column layout for buttons - more balanced layout on mobile (will stack nicely)
        timeline_col1, timeline_col2, timeline_col3 = st.columns([1, 1, 1])
        
        # Render single buttons with appropriate styles for each filter option
        with timeline_col1:
            all_active = st.session_state.active_project_filter == 'all'
            if st.button(
                f"{'✓ ' if all_active else ''}All Projects", 
                key="all_timeline",
                on_click=set_all_filter,
                type="primary" if all_active else "secondary",
                use_container_width=True
            ):
                st.rerun()
            
        with timeline_col2:
            p1a_active = st.session_state.active_project_filter == 'p1a'
            if st.button(
                f"{'✓ ' if p1a_active else ''}PROJECT 1 A", 
                key="p1a_timeline",
                on_click=set_p1a_filter,
                type="primary" if p1a_active else "secondary",
                use_container_width=True
            ):
                st.rerun()
            
        with timeline_col3:
            p1b_active = st.session_state.active_project_filter == 'p1b'
            if st.button(
                f"{'✓ ' if p1b_active else ''}PROJECT 1 B", 
                key="p1b_timeline",
                on_click=set_p1b_filter,
                type="primary" if p1b_active else "secondary",
                use_container_width=True
            ):
                st.rerun()
        
        # Initialize view tabs for timeline features
        timeline_tabs = st.tabs(["🗓️ Gantt Chart", "📊 S-Curve", "📝 Task Details"])
    
    # Prepare timeline data with all enhanced features
    if {'START', 'PLAN END'}.issubset(original_df.columns):
        # Create timeline dataframe from original data with additional columns for enhanced features
        timeline_columns = [
            'KONTRAK', 'JENIS PEKERJAAN', 'START', 'PLAN END', 'STATUS', '% COMPLETE', 
            'TASK_ID', 'TASK_LEVEL', 'IS_MILESTONE', 'PREDECESSORS', 'RESOURCE', 'PLAN_PROGRESS', 'BOBOT'
        ]
        
        # Only include columns that exist in the data
        available_columns = [col for col in timeline_columns if col in original_df.columns]
        timeline_df = original_df[available_columns].dropna(subset=['START', 'PLAN END'])
        
        # Filter based on session state active filter
        if st.session_state.active_project_filter == 'p1a':
            timeline_df = timeline_df[timeline_df['KONTRAK'] == 'PROJECT 1 A']
            st.markdown("<div class='high-contrast-info'>Showing timeline for <strong>PROJECT 1 A</strong></div>", unsafe_allow_html=True)
        elif st.session_state.active_project_filter == 'p1b':
            timeline_df = timeline_df[timeline_df['KONTRAK'] == 'PROJECT 1 B']
            st.markdown("<div class='high-contrast-info'>Showing timeline for <strong>PROJECT 1 B</strong></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='high-contrast-info'>Showing timeline for <strong>all projects</strong></div>", unsafe_allow_html=True)
            
        # Initialize view dates for timeline without zoom controls
        all_dates = pd.concat([
            pd.to_datetime(timeline_df['START'], errors='coerce'),
            pd.to_datetime(timeline_df['PLAN END'], errors='coerce')
        ]).dropna()
        
        if not all_dates.empty:
            # Use full date range for the timeline
            view_start = all_dates.min().date()
            view_end = all_dates.max().date()
        else:
            # Fallback if no valid dates found
            view_start, view_end = None, None
            st.warning("No valid dates found in the dataset")
            
        # Convert dates to datetime format
        timeline_df['START'] = pd.to_datetime(timeline_df['START'])
        timeline_df['PLAN END'] = pd.to_datetime(timeline_df['PLAN END'])
        
        # Format and ensure consistent data types
        if '% COMPLETE' in timeline_df.columns:
            timeline_df['% COMPLETE'] = pd.to_numeric(timeline_df['% COMPLETE'], errors='coerce').fillna(0)
            timeline_df['% COMPLETE'] = timeline_df['% COMPLETE'].apply(lambda x: x * 100 if x <= 1 else x)
        
        # Add task IDs if not present
        if 'TASK_ID' not in timeline_df.columns:
            timeline_df['TASK_ID'] = [f"task_{i}" for i in range(len(timeline_df))]
            
        # Add milestones if not present
        if 'IS_MILESTONE' not in timeline_df.columns:
            # Calculate duration in days
            timeline_df['DURATION'] = (timeline_df['PLAN END'] - timeline_df['START']).dt.days
            # Consider tasks with 0-1 day duration as milestones
            timeline_df['IS_MILESTONE'] = timeline_df['DURATION'] <= 1
        
        # Format tooltips with enhanced information
        timeline_df['Tooltip'] = timeline_df.apply(create_enhanced_tooltip, axis=1)
        
        # Hierarchical view setup
        if 'TASK_LEVEL' in timeline_df.columns:
            # Create indented task names for hierarchy visualization
            timeline_df['Task'] = timeline_df.apply(
                lambda row: ("  " * (max(0, row['TASK_LEVEL'] - 1))) + f"{row['KONTRAK']} - {row['JENIS PEKERJAAN']}", 
                axis=1
            )
            # Sort by level and task order for hierarchical display
            timeline_df = timeline_df.sort_values(['KONTRAK', 'TASK_LEVEL', 'START'])
        else:
            # Simple task format without hierarchy
            timeline_df['Task'] = timeline_df.apply(
                lambda row: f"{row['KONTRAK']} - {row['JENIS PEKERJAAN']}", 
                axis=1
            )
        
        # ===== GANTT CHART TAB =====
        with timeline_tabs[0]:
            st.markdown("### 🔄 Enhanced Timeline View")
            # No show_critical_path toggle needed anymore
            
            # Create dictionary to map tasks by ID (for dependencies)
            task_dict = {}
            for _, row in timeline_df.iterrows():
                task_dict[row['TASK_ID']] = row
            
            # Create Gantt chart with custom hover info
            fig = px.timeline(
                timeline_df, 
                x_start='START', 
                x_end='PLAN END', 
                y='Task', 
                color='STATUS', 
                color_discrete_map=color_map,
                hover_name='Tooltip',
                custom_data=['% COMPLETE', 'TASK_ID'] if '% COMPLETE' in timeline_df.columns else None
            )
            
            # Reverse the y-axis so tasks appear in chronological order
            fig.update_yaxes(autorange="reversed")
            
            # Customize task bar appearance (diamond shapes for milestones)
            for i, row in timeline_df.iterrows():
                # Check if it's a milestone
                if 'IS_MILESTONE' in timeline_df.columns and row['IS_MILESTONE']:
                    # Add diamond marker for milestone
                    midpoint = row['START'] + (row['PLAN END'] - row['START'])/2
                    fig.add_trace(go.Scatter(
                        x=[midpoint],
                        y=[row['Task']],
                        mode='markers',
                        marker=dict(
                            symbol='diamond',
                            size=16,
                            color=color_map.get(row['STATUS'], 'blue'),
                            line=dict(color='black', width=1)
                        ),
                        name=f"Milestone: {row['JENIS PEKERJAAN']}",
                        showlegend=False,
                        hoverinfo='text',
                        hovertext=f"<b>MILESTONE:</b> {row['JENIS PEKERJAAN']}<br>Date: {midpoint.strftime('%Y-%m-%d')}"
                    ))
            
            # Add dependency arrows if predecessors exist
            if 'PREDECESSORS' in timeline_df.columns:
                for _, row in timeline_df.iterrows():
                    if pd.notna(row['PREDECESSORS']) and row['PREDECESSORS'] and row['PREDECESSORS'] in task_dict:
                        # Get predecessor task
                        pred = task_dict[row['PREDECESSORS']]
                        
                        # Add arrow connecting tasks
                        fig.add_shape(
                            type="line",
                            x0=pred['PLAN END'],  # End of predecessor
                            y0=pred['Task'],
                            x1=row['START'],     # Start of current task
                            y1=row['Task'],
                            line=dict(
                                color="rgba(0,0,0,0.5)",
                                width=1.5,
                                dash="dot"
                            ),
                            layer="below"
                        )
                        
                        # Add arrowhead
                        fig.add_annotation(
                            x=row['START'],
                            y=row['Task'],
                            xanchor="right",
                            showarrow=True,
                            arrowhead=2,
                            arrowsize=1,
                            arrowwidth=1.5,
                            arrowcolor="rgba(0,0,0,0.5)",
                            ax=-10,
                            ay=0,
                            text="",
                            hovertext=f"Depends on: {pred['JENIS PEKERJAAN']}",
                            hoverlabel=dict(bgcolor="white")
                        )
            
            # Set the x-axis range based on slider selection
            if 'view_start' in locals() and 'view_end' in locals() and view_start and view_end:
                fig.update_layout(
                    height=600,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(
                        range=[view_start, view_end],
                        rangeslider=dict(visible=True)  # Add range slider for easy navigation
                    )
                )
            else:
                # Default layout without date range filter - with responsive settings for mobile
                fig.update_layout(
                    height=600,
                    margin=dict(l=10, r=10, t=10, b=10),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    autosize=True,
                    # Make the chart mobile-friendly
                    modebar=dict(orientation='v'),
                    hovermode='closest'
                )
            
            # Add progress indicators and text inside the timeline bars if % COMPLETE is available
            if '% COMPLETE' in timeline_df.columns:
                for i, row in timeline_df.iterrows():
                    # Skip milestones for progress indicators (they're just points in time)
                    if 'IS_MILESTONE' in timeline_df.columns and row['IS_MILESTONE']:
                        continue
                        
                    # Calculate positions for all tasks
                    start_date = row['START']
                    end_date = row['PLAN END']
                    total_days = (end_date - start_date).total_seconds()
                    
                    if total_days > 0:
                        # Middle position for text label
                        middle_date = start_date + (end_date - start_date) / 2
                        
                        # Add percentage text in the middle of each bar
                        percentage_text = f"{row['% COMPLETE']:.0f}%"
                        
                        # Add text annotation for percentage
                        fig.add_annotation(
                            x=middle_date,
                            y=row['Task'],
                            text=percentage_text,
                            showarrow=False,
                            font=dict(
                                size=12,
                                color="black",
                                family="Arial, sans-serif bold"
                            ),
                            bgcolor="rgba(255, 255, 255, 0.7)",  # Semi-transparent white background
                            bordercolor="rgba(0, 0, 0, 0.5)",
                            borderwidth=1,
                            borderpad=2,
                            opacity=0.9
                        )
                        
                        # Only add progress bar for non-completed tasks with progress
                        if row['STATUS'] != 'SELESAI' and row['% COMPLETE'] > 0:
                            # Calculate the progress end date based on % completion
                            progress_seconds = total_days * (row['% COMPLETE'] / 100)
                            progress_end = start_date + timedelta(seconds=progress_seconds)
                            
                            # Add a colored overlay to show progress
                            fig.add_trace(go.Scatter(
                                x=[start_date, progress_end, progress_end, start_date, start_date],
                                y=[row['Task'], row['Task'], row['Task'], row['Task'], row['Task']],
                                fill="toself",
                                mode="lines",
                                line=dict(width=0),
                                fillcolor="rgba(0, 255, 0, 0.5)",  # Green with 50% opacity
                                hoverinfo="skip",
                                showlegend=False
                            ))
            
            # Add today's date line as a reference using a custom shape
            today = datetime.today()
            
            # Add a vertical line for today using shapes
            fig.update_layout(
                shapes=[
                    # Vertical line for today
                    dict(
                        type="line",
                        xref="x",
                        yref="paper",
                        x0=today,
                        y0=0,
                        x1=today,
                        y1=1,
                        line=dict(
                            color="red",
                            width=2,
                            dash="dash",
                        )
                    )
                ],
                annotations=[
                    # Today label
                    dict(
                        x=today,
                        y=1.05,
                        xref="x",
                        yref="paper",
                        text="Today",
                        showarrow=False,
                        font=dict(color="red", size=12),
                    )
                ]
            )
            
            # Display the chart with full width
            st.plotly_chart(fig, use_container_width=True)
            
            # Critical path analysis has been removed to simplify the application
            
            # S-Curve Progress Tracking Tab - Now as timeline_tabs[1]
            with timeline_tabs[1]:
                if '% COMPLETE' in timeline_df.columns:
                    st.markdown("### 📊 S-Curve Progress Tracking")

                    # ✅ Normalize % COMPLETE to 0–1 scale if needed
                    if timeline_df['% COMPLETE'].max() > 1.5:
                        timeline_df['% COMPLETE'] = timeline_df['% COMPLETE'] / 100

                    # Generate weekly intervals
                    min_date = timeline_df['START'].min().date()
                    max_date = timeline_df['PLAN END'].max().date()
                    time_periods = []
                    current = min_date
                    while current <= max_date:
                        time_periods.append(current)
                        current += timedelta(days=7)

                    # Calculate progress
                    progress_data = []
                    today_date = date.today()

                    for period in time_periods:
                        planned_progress = 0
                        actual_progress = 0
                        total_weight = 0

                        for _, row in timeline_df.iterrows():
                            if row['START'].date() > period:
                                continue

                            weight = row.get('BOBOT', 0)

                            # ❗️ SKIP rows with 0 or invalid weight
                            if pd.isna(weight) or weight <= 0:
                                continue

                            total_weight += weight

                            # Planned progress (0–1)
                            if period >= row['PLAN END'].date():
                                task_planned = 1.0
                            elif period < row['START'].date():
                                task_planned = 0.0
                            else:
                                total_days = (row['PLAN END'] - row['START']).days
                                days_passed = (period - row['START'].date()).days
                                task_planned = days_passed / total_days if total_days > 0 else 1.0

                            # Actual progress
                            if period >= today_date:
                                task_actual = row['% COMPLETE']
                            elif period < row['START'].date():
                                task_actual = 0.0
                            else:
                                total_days = (today_date - row['START'].date()).days
                                days_passed = (period - row['START'].date()).days
                                task_actual = min(
                                    row['% COMPLETE'],
                                    (days_passed / total_days) * row['% COMPLETE'] if total_days > 0 else 0
                                )

                            planned_progress += task_planned * weight
                            actual_progress += task_actual * weight

                        if total_weight > 0:
                            planned_progress = (planned_progress / total_weight) * 100
                            actual_progress = (actual_progress / total_weight) * 100
                        else:
                            planned_progress = 0
                            actual_progress = 0

                        progress_data.append({'Date': period, 'Type': 'Planned', 'Progress': planned_progress})
                        progress_data.append({'Date': period, 'Type': 'Actual', 'Progress': actual_progress})

                    # Convert to DataFrame
                    progress_df = pd.DataFrame(progress_data)
                    progress_df['Date'] = pd.to_datetime(progress_df['Date'])
                    progress_df = progress_df.sort_values(by=["Type", "Date"])

                    # Ensure cumulative max
                    for t in ['Planned', 'Actual']:
                        mask = progress_df['Type'] == t
                        progress_df.loc[mask, 'Progress'] = progress_df.loc[mask, 'Progress'].cummax()

                    # Plot S-Curve
                    fig_scurve = px.line(
                        progress_df,
                        x='Date',
                        y='Progress',
                        color='Type',
                        title="Project Progress S-Curve",
                        labels={'Progress': 'Cumulative Progress (%)', 'Date': 'Date'},
                        color_discrete_map={'Planned': 'blue', 'Actual': 'green'}
                    )

                    fig_scurve.update_layout(
                        xaxis_title="Date",
                        yaxis_title="Cumulative Progress (%)",
                        yaxis=dict(range=[0, 100]),
                        legend_title="Progress Type",
                        hovermode="x unified",
                        autosize=True,
                        modebar=dict(orientation='v'),
                        margin=dict(l=10, r=10, t=30, b=10),
                        shapes=[
                            dict(
                                type="line",
                                xref="x",
                                yref="paper",
                                x0=today_date,
                                y0=0,
                                x1=today_date,
                                y1=1,
                                line=dict(color="red", width=2, dash="dash")
                            )
                        ],
                        annotations=[
                            dict(
                                x=today_date,
                                y=1.05,
                                xref="x",
                                yref="paper",
                                text="Today",
                                showarrow=False,
                                font=dict(color="red", size=12),
                            )
                        ]
                    )

                    st.plotly_chart(fig_scurve, use_container_width=True)

                    # Earned Value Metrics
                    st.markdown("### 📈 Earned Value Metrics")
                    
                    try:
                        time_periods = pd.to_datetime(progress_df['Date'].unique())
                        latest_periods = [p for p in time_periods if p <= pd.Timestamp(today_date)]
                    
                        if latest_periods:
                            latest_period = pd.Timestamp(max(latest_periods))  # ✅ force to Timestamp
                    
                            planned_val = progress_df[
                                (progress_df['Type'] == 'Planned') &
                                (progress_df['Date'] == latest_period)
                            ]['Progress'].mean()
                    
                            actual_val = progress_df[
                                (progress_df['Type'] == 'Actual') &
                                (progress_df['Date'] == latest_period)
                            ]['Progress'].mean()
                    
                            current_planned = float(planned_val) if pd.notnull(planned_val) else 0
                            current_actual = float(actual_val) if pd.notnull(actual_val) else 0
                    
                            spi = current_actual / current_planned if current_planned > 0 else 0
                        else:
                            current_planned = 0
                            current_actual = 0
                            spi = 0
                    
                    except Exception as e:
                        st.error(f"Error calculating metrics: {e}")
                        current_planned = 0
                        current_actual = 0
                        spi = 0

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Planned Progress", f"{current_planned:.1f}%")
                    with col2:
                        st.metric("Actual Progress", f"{current_actual:.1f}%")
                    with col3:
                        delta_color = "normal" if spi >= 1 else "inverse"
                        st.metric("SPI", f"{spi:.2f}", delta=f"{(spi-1)*100:.1f}%", delta_color=delta_color)

                    if spi >= 1.1:
                        st.success("🎯 Project is ahead of schedule!")
                    elif spi >= 0.9:
                        st.info("✓ Project is on schedule (within 10% variance).")
                    else:
                        st.error("⚠️ Project is behind schedule! Action needed.")

            
            # Task Details Panel Tab
            with timeline_tabs[2]:
                st.markdown("### 📝 Interactive Task Details")
                
                # Create an expander for each task with details
                for _, row in timeline_df.iterrows():
                    with st.expander(f"{row['KONTRAK']} - {row['JENIS PEKERJAAN']}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"**Project:** {row['KONTRAK']}")
                            st.markdown(f"**Task:** {row['JENIS PEKERJAAN']}")
                            st.markdown(f"**Status:** {row['STATUS']}")
                            if 'RESOURCE' in row and not pd.isna(row['RESOURCE']):
                                st.markdown(f"**Resource:** {row['RESOURCE']}")
                            if 'BOBOT' in row and not pd.isna(row['BOBOT']):
                                st.markdown(f"**Weight:** {row['BOBOT']}")
                        
                        with col2:
                            st.markdown(f"**Start Date:** {row['START'].strftime('%Y-%m-%d')}")
                            st.markdown(f"**End Date:** {row['PLAN END'].strftime('%Y-%m-%d')}")
                            if '% COMPLETE' in row and not pd.isna(row['% COMPLETE']):
                                st.markdown(f"**Progress:** {row['% COMPLETE']:.1f}%")
                                st.progress(int(row['% COMPLETE']))
                            
                            if 'IS_MILESTONE' in row and row['IS_MILESTONE']:
                                st.markdown("**Type:** 🎯 Milestone")
                        
                        # Show dependencies if available
                        if 'PREDECESSORS' in row and row['PREDECESSORS']:
                            if row['PREDECESSORS'] in task_dict:
                                pred = task_dict[row['PREDECESSORS']]
                                st.markdown(f"**Depends on:** {pred['JENIS PEKERJAAN']} (must finish before this task can start)")
                                
                                # Calculate critical dependency status
                                if pd.to_datetime(pred['PLAN END']) > pd.to_datetime(row['START']):
                                    st.warning("⚠️ Dependency conflict: Predecessor end date is after this task's start date!")
                        
                        # Show days left until deadline
                        days_left = (row['PLAN END'].date() - today.date()).days
                        if days_left < 0:
                            st.error(f"⚠️ **Overdue by {abs(days_left)} days**")
                        elif days_left == 0:
                            st.warning("⏰ **Due today!**")
                        else:
                            st.info(f"⏳ **Days remaining: {days_left}**")
    
    # Task details are now in the interactive task details tab

   # --- Status Pie & Pending Chart ---
    with section_card("📊 Task Distribution & Issues"):
        c1, c2 = st.columns(2)

        with c1:
            status_counts = df['STATUS'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            fig_status = px.pie(
                status_counts, names='Status', values='Count', hole=0.4,
                title="Status Breakdown",
                color='Status',
                color_discrete_map=color_map
            )
            st.plotly_chart(fig_status, use_container_width=True)

        with c2:
            pending_df = df[df['STATUS'].isin(['TUNDA', 'BELUM MULAI'])]  # Combined logic
            if not pending_df.empty:
                pending_count = pending_df['KONTRAK'].value_counts().reset_index()
                pending_count.columns = ['KONTRAK', 'Pending Count']
                fig_pending = px.bar(
                    pending_count,
                    x='Pending Count',
                    y='KONTRAK',
                    orientation='h',
                    text='Pending Count',
                    title="Projects with Pending Tasks",
                    color='Pending Count',
                    color_continuous_scale='Oranges'
                )
                fig_pending.update_layout(
                    yaxis_title="Project",
                    xaxis_title="Pending Tasks",
                    height=400,
                    margin=dict(l=40, r=10, t=40, b=40)
                )
                st.plotly_chart(fig_pending, use_container_width=True)
            else:
                st.info("No 'Tunda' or 'Belum Mulai' tasks to display.")


    # --- Late Tasks Section ---
    with section_card("🕰 Overdue Tasks"):
        late_df = df[(pd.to_datetime(df['PLAN END'], errors='coerce') < datetime.today()) & (df['STATUS'] != 'SELESAI')]
        late_df['LATE DAYS'] = (datetime.today() - pd.to_datetime(late_df['PLAN END'], errors='coerce')).dt.days

        if not late_df.empty:
            total_late_tasks = len(late_df)
            total_late_days = late_df['LATE DAYS'].sum()

            rowL1, rowL2 = st.columns(2)
            with rowL1:
                st.markdown(card("Late Tasks", f"{total_late_tasks} tasks", "Tasks overdue", "⏳", "#ffebee"), unsafe_allow_html=True)
            with rowL2:
                st.markdown(card("Total Late Days", f"{total_late_days}", "Total days overdue", "⚠️", "#ffe0e0"), unsafe_allow_html=True)

            late_df_display = late_df[['KONTRAK', 'JENIS PEKERJAAN', 'LATE DAYS']]
            late_df_display = late_df_display.rename(columns={
                'KONTRAK': 'Project',
                'JENIS PEKERJAAN': 'Task',
                'LATE DAYS': 'Days Late'
            })
            st.dataframe(late_df_display, use_container_width=True, height=350)
        else:
            st.info("No overdue tasks found.")

    # --- Task Recommendations & Prioritization ---
    with section_card("🔍 Task Recommendations"):
        # Only show recommendations for non-completed tasks
        active_tasks = df[df['STATUS'] != 'SELESAI'].copy()
        if not active_tasks.empty:
            # Calculate priority scores
            active_tasks['PRIORITY_SCORE'] = active_tasks.apply(calculate_priority_score, axis=1)
            active_tasks = active_tasks.sort_values('PRIORITY_SCORE', ascending=False)
            
            # Color coding for priority with better dark mode contrast
            def color_priority(val):
                if val >= 80:
                    return 'background-color: rgba(255, 0, 0, 0.3); color: white; font-weight: bold'  # High priority (red)
                elif val >= 50:
                    return 'background-color: rgba(255, 165, 0, 0.3); color: white; font-weight: bold'  # Medium priority (orange)
                else:
                    return 'background-color: rgba(0, 128, 0, 0.3); color: white; font-weight: bold'  # Low priority (green)
            
            # Prepare recommendation dataframe with Area Pekerjaan
            columns_to_include = ['KONTRAK', 'JENIS PEKERJAAN', 'AREA PEKERJAAN', 'STATUS', 'PLAN END', 'BOBOT', 'PRIORITY_SCORE']
            # Filter to only include columns that actually exist in the dataframe
            existing_columns = [col for col in columns_to_include if col in active_tasks.columns]
            rec_df = active_tasks[existing_columns].head(5)
            
            # Create a rename mapping for all possible columns
            rename_mapping = {
                'KONTRAK': 'Project',
                'JENIS PEKERJAAN': 'Task',
                'AREA PEKERJAAN': 'Area',
                'STATUS': 'Status',
                'PLAN END': 'Deadline',
                'BOBOT': 'Weight',
                'PRIORITY_SCORE': 'Priority'
            }
            
            # Only rename columns that exist
            columns_to_rename = {k: v for k, v in rename_mapping.items() if k in existing_columns}
            rec_df = rec_df.rename(columns=columns_to_rename)
            
            # Show recommendations with styling
            st.write("Top 5 Tasks Requiring Attention:")
            # Use style.format for formatting numbers
            styled_rec_df = rec_df.style.format({
                'Priority': '{:.1f}'
            })
            
            # Handle both newer and older pandas versions
            try:
                # For newer pandas versions
                styled_rec_df = styled_rec_df.map(color_priority, subset=['Priority'])
            except AttributeError:
                # For older pandas versions
                styled_rec_df = styled_rec_df.applymap(color_priority, subset=['Priority'])
            
            st.dataframe(styled_rec_df, use_container_width=True)
            
            # Generate action recommendations with high contrast styling
            st.markdown("<div style='font-size: 16px; font-weight: bold; margin-bottom: 10px;'>📝 Suggested Actions:</div>", unsafe_allow_html=True)
            
            for i, row in rec_df.head(3).iterrows():
                if row['Priority'] >= 80:
                    st.markdown(
                        f"<div class='high-contrast-action' style='background-color: rgba(255, 0, 0, 0.15); border-left: 4px solid red; padding: 10px; border-radius: 4px; margin-bottom: 8px;'>"
                        f"<span style='font-weight: bold; color: white;'>🔴 URGENT:</span> '{row['Task']}' in project '{row['Project']}' requires immediate attention."
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                elif row['Priority'] >= 60:
                    st.markdown(
                        f"<div class='high-contrast-action' style='background-color: rgba(255, 165, 0, 0.15); border-left: 4px solid orange; padding: 10px; border-radius: 4px; margin-bottom: 8px;'>"
                        f"<span style='font-weight: bold; color: white;'>🟠 IMPORTANT:</span> Schedule time for '{row['Task']}' soon."
                        f"</div>", 
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        f"<div class='high-contrast-action' style='background-color: rgba(0, 128, 0, 0.15); border-left: 4px solid green; padding: 10px; border-radius: 4px; margin-bottom: 8px;'>"
                        f"<span style='font-weight: bold; color: white;'>🟢 PLAN:</span> Add '{row['Task']}' to your upcoming work plan."
                        f"</div>", 
                        unsafe_allow_html=True
                    )
        else:
            st.info("No active tasks to recommend.")



    # --- Project Zone Map ---
    with section_card("🗺️ Zone-Based Project Progress Map"):
        try:
            # Import the map_zones module
            import map_zones
            
            # Create a simple method to add "AREA PEKERJAAN" if not present
            if 'AREA PEKERJAAN' not in original_df.columns and 'JENIS PEKERJAAN' in original_df.columns:
                st.info("No 'AREA PEKERJAAN' column found. Using task descriptions to map work areas.")
            
            # Get progress data by zone
            progress_by_zone = map_zones.extract_zone_progress(original_df)
            
            # Create colored map based on progress data 
            colored_map_html = map_zones.generate_colored_map(progress_by_zone)
            
            # Create two columns - one for the map and one for the legend
            map_col, legend_col = st.columns([2, 1])
            
            # Display the simplified map using a more robust approach
            with map_col:
                st.markdown("<h4>Project Site Map</h4>", unsafe_allow_html=True)
                
                # Create a simple DataFrame for the zones
                zone_data = []
                for zone, progress in progress_by_zone.items():
                    zone_data.append({
                        'Zone': zone,
                        'Progress': progress,
                        'Status': 'High' if progress >= 75 else ('Medium' if progress >= 50 else 'Low'),
                        'Display': f"{zone}: {progress:.1f}%"
                    })
                
                zone_df = pd.DataFrame(zone_data)
                
                # Define a simplified color scale
                color_scale = {
                    'Low': 'rgb(255,0,0)',      # Red for low progress
                    'Medium': 'rgb(255,255,0)',  # Yellow for medium progress
                    'High': 'rgb(0,128,0)'       # Green for high progress
                }
                
                # Create a simple bar chart for the zones
                fig = px.bar(
                    zone_df, 
                    x='Zone', 
                    y='Progress',
                    color='Status',
                    color_discrete_map=color_scale,
                    text='Display',
                    labels={'Progress': 'Completion %', 'Zone': 'Project Zone'},
                    height=400
                )
                
                # Update the layout
                fig.update_layout(
                    title="Project Progress by Zone",
                    xaxis_title="",
                    yaxis_title="Completion %",
                    yaxis=dict(range=[0, 100]),
                    legend_title="Progress Status",
                    font=dict(size=12),
                    plot_bgcolor='rgba(0,0,0,0.05)',
                    margin=dict(l=40, r=40, t=60, b=40)
                )
                
                # Display the chart
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Simplified zone progress visualization")
            
            # Display the progress legend only
            with legend_col:
                st.markdown("<h4>Progress Legend</h4>", unsafe_allow_html=True)
                st.markdown("""
                <small>
                Progress level indicators:<br>
                🟥 Red = 0–49% Complete<br>
                🟨 Yellow = 50–74% Complete<br>
                🟩 Green = 75–100% Complete
                </small>
                """, unsafe_allow_html=True)

                
            # Show Sub-Area Progress Chart
            st.markdown("<h4>Progress by Sub-Area Pekerjaan</h4>", unsafe_allow_html=True)
            
            # Get progress data by sub-area if available
            if 'SUB AREA PEKERJAAN' in original_df.columns:
                # Group by sub-area and calculate weighted average progress
                if 'BOBOT' in original_df.columns:
                    # Use weighted average if weights are available
                    sub_area_progress = original_df.groupby('SUB AREA PEKERJAAN').apply(
                        lambda x: (x['% COMPLETE'] * x['BOBOT']).sum() / x['BOBOT'].sum() 
                        if x['BOBOT'].sum() > 0 else x['% COMPLETE'].mean()
                    )
                else:
                    # Otherwise use simple average
                    sub_area_progress = original_df.groupby('SUB AREA PEKERJAAN')['% COMPLETE'].mean()
                
                # Convert to DataFrame for visualization
                sub_area_df = pd.DataFrame({
                    'Sub Area': sub_area_progress.index,
                    'Progress': sub_area_progress.values,
                })
                
                # Add status column for color-coding
                sub_area_df['Status'] = sub_area_df['Progress'].apply(
                    lambda x: 'High' if x >= 75 else ('Medium' if x >= 50 else 'Low')
                )
                
                # Sort by progress (descending)
                sub_area_df = sub_area_df.sort_values('Progress', ascending=False)
                
                # Create bar chart for sub-areas
                sub_area_fig = px.bar(
                    sub_area_df,
                    x='Sub Area',
                    y='Progress',
                    color='Status',
                    color_discrete_map=color_scale,
                    text=sub_area_df['Sub Area'] + ': ' + sub_area_df['Progress'].round(1).astype(str) + '%',
                    labels={'Progress': 'Completion %', 'Sub Area': 'Sub Area Pekerjaan'},
                    height=500
                )
                
                # Update layout
                sub_area_fig.update_layout(
                    title="Project Progress by Sub-Area",
                    xaxis_title="",
                    yaxis_title="Completion %",
                    yaxis=dict(range=[0, 100]),
                    legend_title="Progress Status",
                    font=dict(size=12),
                    plot_bgcolor='rgba(0,0,0,0.05)',
                    margin=dict(l=40, r=40, t=60, b=80)
                )
                
                # Handle long bar labels if needed
                if len(sub_area_df) > 5:
                    sub_area_fig.update_layout(
                        xaxis_tickangle=-45,
                        height=min(500 + (len(sub_area_df) - 5) * 15, 800)  # Adjust height based on number of bars
                    )
                
                # Display the chart
                st.plotly_chart(sub_area_fig, use_container_width=True)
                st.caption("Progress breakdown by sub-area pekerjaan")
            else:
                # Try to extract sub-area information from 'JENIS PEKERJAAN' or other available columns
                if 'JENIS PEKERJAAN' in original_df.columns:
                    st.info("No 'SUB AREA PEKERJAAN' column found. Creating sub-areas based on task descriptions.")
                    
                    # Extract sub-areas by taking the first part of task descriptions
                    original_df['EXTRACTED_SUB_AREA'] = original_df['JENIS PEKERJAAN'].apply(
                        lambda x: str(x).split(' - ')[0] if ' - ' in str(x) else str(x)
                    )
                    
                    # Group by extracted sub-area
                    if 'BOBOT' in original_df.columns:
                        sub_area_progress = original_df.groupby('EXTRACTED_SUB_AREA').apply(
                            lambda x: (x['% COMPLETE'] * x['BOBOT']).sum() / x['BOBOT'].sum() 
                            if x['BOBOT'].sum() > 0 else x['% COMPLETE'].mean()
                        )
                    else:
                        sub_area_progress = original_df.groupby('EXTRACTED_SUB_AREA')['% COMPLETE'].mean()
                    
                    # Convert to DataFrame and prepare for visualization
                    sub_area_df = pd.DataFrame({
                        'Sub Area': sub_area_progress.index,
                        'Progress': sub_area_progress.values,
                    })
                    
                    # Add status column for color-coding
                    sub_area_df['Status'] = sub_area_df['Progress'].apply(
                        lambda x: 'High' if x >= 75 else ('Medium' if x >= 50 else 'Low')
                    )
                    
                    # Sort by progress (descending)
                    sub_area_df = sub_area_df.sort_values('Progress', ascending=False)
                    
                    # Create bar chart for sub-areas
                    sub_area_fig = px.bar(
                        sub_area_df,
                        x='Sub Area',
                        y='Progress',
                        color='Status',
                        color_discrete_map=color_scale,
                        text=sub_area_df['Sub Area'] + ': ' + sub_area_df['Progress'].round(1).astype(str) + '%',
                        labels={'Progress': 'Completion %', 'Sub Area': 'Extracted Sub-Area'},
                        height=500
                    )
                    
                    # Update layout
                    sub_area_fig.update_layout(
                        title="Project Progress by Extracted Sub-Area",
                        xaxis_title="",
                        yaxis_title="Completion %",
                        yaxis=dict(range=[0, 100]),
                        legend_title="Progress Status",
                        font=dict(size=12),
                        plot_bgcolor='rgba(0,0,0,0.05)',
                        margin=dict(l=40, r=40, t=60, b=80)
                    )
                    
                    # Handle long bar labels if needed
                    if len(sub_area_df) > 5:
                        sub_area_fig.update_layout(
                            xaxis_tickangle=-45,
                            height=min(500 + (len(sub_area_df) - 5) * 15, 800)  # Adjust height based on number of bars
                        )
                    
                    # Display the chart
                    st.plotly_chart(sub_area_fig, use_container_width=True)
                    st.caption("Progress breakdown by extracted sub-area")
                else:
                    st.warning("No columns found for sub-area analysis. Please add 'SUB AREA PEKERJAAN' or similar to your data.")
        except Exception as e:
            st.error(f"Could not display zone map: {str(e)}")
            st.info("Make sure you've uploaded a file with 'AREA PEKERJAAN' or 'JENIS PEKERJAAN' columns.")
    
    # --- Export Options ---
    with section_card("📊 Export Reports"):
        export_col1, export_col2, export_col3 = st.columns(3)
        
        with export_col1:
            st.write("Download Current View")
            st.markdown(get_to_csv_download_link(df, "project_data.csv", "📥 Download CSV"), unsafe_allow_html=True)
            st.markdown(get_excel_download_link(df, "project_data.xlsx", "📥 Download Excel"), unsafe_allow_html=True)
        
        with export_col2:
            report_type = st.selectbox(
                "Generate Report",
                ["Current Status Report", "Late Tasks Report", "Priority Tasks Report"]
            )
            
            if report_type == "Current Status Report":
                report_df = df[['KONTRAK', 'JENIS PEKERJAAN', 'STATUS', '% COMPLETE', 'PLAN END']]
            elif report_type == "Late Tasks Report":
                report_df = late_df[['KONTRAK', 'JENIS PEKERJAAN', 'LATE DAYS', 'PLAN END', 'BOBOT']]
            else:  # Priority Tasks Report
                active_df = df[df['STATUS'] != 'SELESAI'].copy()
                active_df['PRIORITY_SCORE'] = active_df.apply(calculate_priority_score, axis=1)
                report_df = active_df.sort_values('PRIORITY_SCORE', ascending=False)[
                    ['KONTRAK', 'JENIS PEKERJAAN', 'STATUS', 'PLAN END', 'PRIORITY_SCORE']
                ]
            
            report_filename = f"{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
            st.markdown(get_excel_download_link(report_df, f"{report_filename}.xlsx", f"📥 Download {report_type}"), unsafe_allow_html=True)
            

    
    st.success("✅ Dashboard rendered successfully.")

if __name__ == "__main__":
    main()
