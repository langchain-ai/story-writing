import streamlit as st
from streamlit import components

def main():

    # Define your options
    options = ['Option 1', 'Option 2', 'Option 3']

    # Initialize session state variable
    if 'selected_option' not in st.session_state:
        st.session_state.selected_option = None
        st.session_state.num_selected = 0

    # Create a selectbox with a placeholder
    st.session_state.selected_option = st.selectbox("", \
                     options=options, index=None,placeholder="Choose an option", \
                        key=f"selectbox-{st.session_state.num_selected}")

    # React to option selection
    
    if st.session_state.selected_option is not None:
        print(st.session_state.selected_option, st.session_state.num_selected)
        st.session_state.num_selected += 1
        
        # Reset the selected option to None
        #st.session_state.selected_option = None
        st.rerun()




if __name__ == "__main__":
    main()
