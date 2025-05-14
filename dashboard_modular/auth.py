import streamlit as st

USERS = {
    'admin': {'password': 'admin123', 'role': 'admin'},
    'john': {'password': 'john123', 'role': 'viewer'},
    'sarah': {'password': 'sarahpass', 'role': 'editor'}
}

def authenticate(username, password):
    user = USERS.get(username)
    if user and user['password'] == password:
        return user['role']
    return None

def require_login():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🔐 Dashboard Login")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            role = authenticate(username, password)
            if role:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.role = role
                st.success(f"Welcome, {username}! Role: {role}")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
        st.stop()

    st.sidebar.markdown(f"👤 **User:** {st.session_state.user}")
    st.sidebar.markdown(f"🔑 **Role:** {st.session_state.role}")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
