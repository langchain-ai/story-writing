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

async def get_new_thread(client):
    thread = await client.threads.create()
    return thread

async def run_graph_with_input(client,thread,assistant,input,metadata):
    data = []
    async for chunk in client.runs.stream(
    thread['thread_id'], assistant['assistant_id'], input=input, config={'configurable':metadata}, stream_mode="updates",
):
        if chunk.data and 'run_id' not in chunk.data:
            for t in ['rewrite','continue','first']:
                try:
                    data = chunk.data[t]['chapters']
                except:
                    pass
    return data

async def get_next_parent_info(client,thread,node_id):
    current_node_history = await client.threads.get_history(thread_id=thread['thread_id'],metadata={'node_id':node_id})
    parent_node_id = [h for h in current_node_history if h['next'] == []][0]['metadata']['parent_id']
    parent_node_history = await client.threads.get_history(thread_id=thread['thread_id'],metadata={'node_id':parent_node_id})
    parent_node_last_state = [h for h in parent_node_history if h['next'] == []][0]
    return [parent_node_id,parent_node_last_state['parent_config']['configurable'],
            parent_node_last_state['values']['chapters']]

async def get_forward_branches(client,thread,node_id):
    node_child_history = await client.threads.get_history(thread_id=thread['thread_id'],metadata={'parent_id':node_id})
    return [h for h in node_child_history if h['next'] == []]

async def get_current_config(client,thread):
    current_state = await client.threads.get_state(thread_id=thread['thread_id'])
    return current_state['config']['configurable']

async def call_async_function_safely(func,*args):
    try:
        # Try to run the async function using the existing event loop
        result = await func(*args)
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            # If the event loop is closed, create a new one and run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = await func(*args)
        else:
            raise e
    return result

async def main():
    st.title("Story Writing with Langgraph")

    async def update_session_variabeles_on_graph_run():
        st.session_state.parent_node_id = st.session_state.current_node_id
        #st.session_state.current_config = await call_async_function_safely(get_current_config,st.session_state.client,st.session_state.thread)
        st.session_state.current_config = {}
        st.session_state.current_node_id += 1

    if "forward_in_time_list_mode" not in st.session_state:
        st.session_state.forward_in_time_list_mode = False
        st.session_state.forward_branches = []

    if "page_loaded" not in st.session_state:
        st.session_state.page_loaded = False

    if st.session_state.page_loaded == False:
        st.session_state.current_node_id = 1
        st.session_state.parent_node_id = -1
        st.session_state.current_config = {}
        st.session_state.chapters = [{'number':-1,'content':"Click Start Story to begin writing!"}]
        st.session_state.client,st.session_state.thread,st.session_state.assistant = await call_async_function_safely(start_agent)

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

                # If we start a new story, reset all of our session variables
                if st.session_state.story_started:
                    st.session_state.thread = await call_async_function_safely(get_new_thread,st.session_state.client)
                    st.session_state.current_config = {}
                    st.session_state.current_chapter_index = 0
                    st.session_state.current_node_id = 1
                    st.session_state.parent_node_id = -1
                    st.session_state.chapters = [{'number':-1,'content':"Click Start Story to begin writing!"}]

                st.session_state.chapters = await call_async_function_safely(run_graph_with_input,st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'summary':summary_text,'details':detail_text,
                                                'style':style_text},{**{'node_id':st.session_state.current_node_id,
                                                'parent_id':st.session_state.parent_node_id},**st.session_state.current_config})
                st.session_state.story_started = True
                await update_session_variabeles_on_graph_run()
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
                print("editing",st.session_state.parent_node_id)
                edited_chapter = await call_async_function_safely(run_graph_with_input,st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'rewrite_instructions':edit_chapter_text},
                                                {**{'node_id':st.session_state.current_node_id,
                                                'parent_id':st.session_state.parent_node_id},**st.session_state.current_config})
                st.session_state.chapters = st.session_state.chapters[:-1] + edited_chapter
                await update_session_variabeles_on_graph_run()
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
                st.session_state.chapters += await call_async_function_safely(run_graph_with_input,st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'continue_instructions':next_chapter_text}
                                                ,{**{'node_id':st.session_state.current_node_id,
                                                'parent_id':st.session_state.parent_node_id,**st.session_state.current_config}})
                st.session_state.current_chapter_index += 1
                await update_session_variabeles_on_graph_run()
                st.session_state.show_continue_input = False
                st.rerun()
    else:
        st.sidebar.header("Navigation")
        if st.sidebar.button("New Story" if st.session_state.story_started else "Start Story"):
            st.session_state.show_start_input = True
            st.rerun()
        elif st.sidebar.button("Edit") and st.session_state.story_started \
            and st.session_state.current_chapter_index == len(st.session_state.chapters) - 1:
            st.session_state.show_edit_input = True
            st.rerun()
        elif st.sidebar.button("Continue") and st.session_state.story_started:
            st.session_state.show_continue_input = True
            st.rerun()

    st.sidebar.write(" ")
    if "current_chapter_index" not in st.session_state:
        st.session_state.current_chapter_index = 0

    if st.session_state.story_started:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("Go back in time") and st.session_state.parent_node_id > 1:
                next_parent_info = await call_async_function_safely(get_next_parent_info,st.session_state.client,st.session_state.thread
                                                                        ,st.session_state.parent_node_id)
                st.session_state.parent_node_id = next_parent_info[0]
                st.session_state.current_config = next_parent_info[1]
                st.session_state.chapters = next_parent_info[2]
                st.session_state.current_chapter_index = min(st.session_state.current_chapter_index,len(st.session_state.chapters)-1)

                st.rerun()
        with col3:
            if st.session_state.forward_in_time_list_mode == False:
                if st.button("Go forward in time") and st.session_state.parent_node_id != -1:
                    st.session_state.forward_branches = await call_async_function_safely(get_forward_branches,
                                        st.session_state.client,st.session_state.thread,st.session_state.parent_node_id)

                    if len(st.session_state.forward_branches) > 0:
                        st.session_state.forward_in_time_list_mode = True
                        st.rerun()
            else:
                st.write("Select a branch to proceed on")
                print("Branch options")
                for b in st.session_state.forward_branches:
                    print(f"Node id {b['metadata']['node_id']} Chapter Length {len(b['values']['chapters'])}")
                for i in range(1,len(st.session_state.forward_branches)+1):
                    if st.button(f"Branch {i}"):
                        future_branch_node = st.session_state.forward_branches[i-1]
                        st.session_state.parent_node_id = future_branch_node['metadata']['node_id']
                        st.session_state.current_config = future_branch_node['config']['configurable']
                        st.session_state.chapters = future_branch_node['values']['chapters']
                        st.session_state.forward_in_time_list_mode = False
                        st.session_state.forward_branches = []
                        st.rerun()
                if st.button("Cancel",key="cancel-forward-in-time"):
                    st.session_state.forward_in_time_list_mode = False
                    st.session_state.forward_branches = []
                    st.rerun()
        st.markdown(f"<h2 style='text-align: center; color: white;'> Chapter \
                    {st.session_state.chapters[st.session_state.current_chapter_index]['number']+1} \
                          </h2>",unsafe_allow_html=True)
    st.text_area(" ", value=st.session_state.chapters[st.session_state.current_chapter_index]['content'], height=450)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("◀️") and st.session_state.current_chapter_index > 0:
            st.session_state.current_chapter_index -= 1
            st.rerun()
        st.write("Prev. Chapter")
    with col2:
        pass
    with col3:
        if st.button("▶️") and st.session_state.current_chapter_index < len(st.session_state.chapters) - 1:
            st.session_state.current_chapter_index += 1
            st.rerun()
        st.write("Next Chapter")


if __name__ == "__main__":
    asyncio.run(main())