import streamlit as st
from langgraph_sdk import get_client
import asyncio

async def start_agent():
    client = get_client()
    assistants = await client.assistants.search()
    assistants = [a for a in assistants if not a['config']]
    thread = await client.threads.create()
    assistant = assistants[0]
    return [client,thread,assistant]

async def run_graph_with_input(client,thread,assistant,input,type_of_input):
    data = []
    async for chunk in client.runs.stream(
    thread['thread_id'], assistant['assistant_id'], input=input, stream_mode="updates",
):
        if chunk.data and 'run_id' not in chunk.data:
            data = chunk.data[type_of_input]['chapters']
    return data

async def call_async_function(client,thread,assistant,input,type_of_input):
    try:
        # Try to run the async function using the existing event loop
        result = await run_graph_with_input(client,thread,assistant,input,type_of_input)
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            # If the event loop is closed, create a new one and run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = await run_graph_with_input(client,thread,assistant,input,type_of_input)
        else:
            # If it's another RuntimeError, raise the error
            raise e
    return result

async def main():
    st.title("Story Writing with Langgraph")

    if "page_loaded" not in st.session_state:
        st.session_state.page_loaded = False

    if st.session_state.page_loaded == False:
        st.session_state.chapters = [{'number':'Prelude','content':"Click Start Story to begin writing!"}]
        st.session_state.client,st.session_state.thread,st.session_state.assistant = await start_agent()

    if "story_started" not in st.session_state:
        st.session_state.story_started = False

    if "show_edit_input" not in st.session_state:
        st.session_state.show_edit_input = False
    
    if "show_start_input" not in st.session_state:
        st.session_state.show_start_input = False

    if "show_continue_input" not in st.session_state:
        st.session_state.show_continue_input = False


    if st.session_state.show_start_input:
        summary_text = st.sidebar.text_area("Summary")
        detail_text = st.sidebar.text_area("Details")
        style_text = st.sidebar.text_area("Writing Style")
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="start-back"):
                st.session_state.show_start_input = False
                st.rerun()
        with col2:
            if st.button("Submit",key="start-submit"):
                st.session_state.page_loaded = True
                st.session_state.chapters = await call_async_function(st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'summary':summary_text,'details':detail_text,
                                                'style':style_text},'first')
                
                st.session_state.story_started = True
                st.session_state.show_start_input = False
                st.rerun()
    elif st.session_state.show_edit_input:
        edit_chapter_text = st.sidebar.text_area("Edit Instructions")
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="edit-back"):
                st.session_state.show_edit_input = False
                st.rerun()
        with col2:
            if st.button("Submit",key="edit-submit"):
                print(st.session_state.thread)
                edited_chapter = await call_async_function(st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'rewrite_instructions':edit_chapter_text},'rewrite')
                st.session_state.chapters = st.session_state.chapters[:-1] + edited_chapter
                st.session_state.show_edit_input = False
                st.rerun()
    elif st.session_state.show_continue_input:
        next_chapter_text = st.sidebar.text_area("Next Chapter Instructions")
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="continue-back"):
                st.session_state.show_continue_input = False
                st.rerun()
        with col2:
            if st.button("Submit",key="continue-submit"):
                st.session_state.chapters += await call_async_function(st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'continue_instructions':next_chapter_text},'continue')
                st.session_state.show_continue_input = False
                st.session_state.current_chapter_index += 1
                st.rerun()
    else:
        st.sidebar.header("Navigation")
        if st.sidebar.button("New Story" if st.session_state.story_started else "Start Story"):
            if st.session_state.story_started:
                st.session_state.current_chapter_index = 0
                st.session_state.chapters = [{'number':'Prelude','content':"Click Start Story to begin writing!"}]
                st.session_state.client,st.session_state.thread,st.session_state.assistant = await start_agent()
            st.session_state.show_start_input = True
            st.rerun()
        elif st.sidebar.button("Edit") and st.session_state.story_started \
            and st.session_state.current_chapter_index == len(st.session_state.chapters) - 1:
            st.session_state.show_edit_input = True
            st.rerun()
        elif st.sidebar.button("Continue") and st.session_state.story_started:
            st.session_state.show_continue_input = True
            st.rerun()

    st.sidebar.write("")
    if "current_chapter_index" not in st.session_state:
        st.session_state.current_chapter_index = 0

    st.write(f"Chapter {st.session_state.chapters[st.session_state.current_chapter_index]['number']}")

    st.text_area("Chapter Content", value=st.session_state.chapters[st.session_state.current_chapter_index]['content'], height=250)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀️") and st.session_state.current_chapter_index > 0:
            st.session_state.current_chapter_index -= 1
            st.rerun()
    with col2:
        pass
    with col3:
        if st.button("▶️") and st.session_state.current_chapter_index < len(st.session_state.chapters) - 1:
            st.session_state.current_chapter_index += 1
            st.rerun()


if __name__ == "__main__":
    asyncio.run(main())