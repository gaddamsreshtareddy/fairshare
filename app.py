"""FairShare entry point: defines the sidebar menu and runs the chosen page."""

import streamlit as st

pages = [
    st.Page("home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📊"),
    st.Page("pages/2_Add_Expense.py", title="Add Expense", icon="➕"),
    st.Page("pages/3_Expenses.py", title="Expenses", icon="🧾"),
    st.Page("pages/4_Balances.py", title="Balances", icon="⚖️"),
    st.Page("pages/5_Settlements.py", title="Settlements", icon="🤝"),
    st.Page("pages/6_Analytics.py", title="Analytics", icon="📈"),
    st.Page("pages/7_Reports.py", title="Reports", icon="📄"),
    st.Page("pages/8_Group_Settings.py", title="Group Settings", icon="⚙️"),
]

st.navigation(pages).run()