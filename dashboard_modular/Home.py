import streamlit as st
from auth import require_login

st.set_page_config(page_title="Dashboard Home", layout="wide")
require_login()

st.title("🏠 Dashboard Home")
st.markdown("Welcome to your modular dashboard! Navigate using the sidebar.")