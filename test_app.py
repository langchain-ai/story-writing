import streamlit as st
from streamlit import components

def main():
    # Custom CSS to potentially hide tooltips on selectbox
    custom_css = """
    <style>
    /* Example CSS to hide tooltips on selectbox */
    option {
        pointer-events: none; /* Disable mouse events */
        cursor: default; /* Remove cursor change */
        /* Add other CSS properties to hide tooltips */
    }
    </style>
    """

    # Injecting custom CSS
    st.markdown(custom_css, unsafe_allow_html=True)

    # Example usage of selectbox

    _, col2, _ = st.columns([3, 1, 3])
    with col2:
        option = st.selectbox("Select an option", ["Option 1 more text", \
                             "Option 2 also more text", "Option 3 lots of text"])





if __name__ == "__main__":
    main()
