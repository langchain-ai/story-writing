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
    # Need to add streaming capability
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

async def get_current_state(client,thread):
    current_state = await client.threads.get_state(thread_id=thread['thread_id'])
    return current_state

async def update_current_state(client,thread,values):
    updated_state = await client.threads.update_state(thread_id=thread['thread_id'],values=values)

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

def transform_titles_into_options(titles):
    name_counts = {}
    for name in set(titles):
        name_counts[name] = titles.count(name)

    # Transform names with numbered suffixes
    transformed_titles = []
    for name in titles[::-1]:
        count = name_counts[name]
        if count > 1 or titles.count(name) > 1:
            transformed_titles.append(f"{name} #{count}")
        else:
            transformed_titles.append(name)
        name_counts[name] -= 1

    return transformed_titles[::-1]

async def update_session_variables():
    st.session_state.current_node_id += 1
    current_state = await call_async_function_safely(get_current_state,st.session_state.client,st.session_state.thread)
    st.session_state.all_chapters = current_state['values']['all_chapters']
    st.session_state.current_chapter_indices = current_state['values']['current_chapter_indices']
    st.session_state.currently_selected_chapter = current_state['values']['currently_selected_chapter']

    st.session_state.current_chapter_options = st.session_state.all_chapters[str(int(st.session_state.currently_selected_chapter))]
    st.session_state.previous_chapter_options = st.session_state.all_chapters[str(int(st.session_state.currently_selected_chapter)-1)] if \
        str(int(st.session_state.currently_selected_chapter)-1) in st.session_state.all_chapters else []
    st.session_state.next_chapter_options = st.session_state.all_chapters[str(int(st.session_state.currently_selected_chapter)+1)] if  \
        str(int(st.session_state.currently_selected_chapter)+1) in st.session_state.all_chapters else []
    
    st.session_state.current_chapter_index = st.session_state.current_chapter_indices[st.session_state.currently_selected_chapter]
        
async def reset_session_variables():
    st.session_state.current_node_id = 1
    st.session_state.all_chapters = {'-1':[{'number':-1,'content':"Click Start Story to begin writing!", 'title':"Pre-start Chapter"}]}
    st.session_state.client,st.session_state.thread,st.session_state.assistant = await call_async_function_safely(start_agent)
    st.session_state.current_chapter_indices = {'-1':0}
    st.session_state.currently_selected_chapter = '-1'

    st.session_state.current_chapter_index = 0

    st.session_state.current_chapter_options = st.session_state.all_chapters[st.session_state.currently_selected_chapter]
    st.session_state.previous_chapter_options, st.session_state.next_chapter_options = [],[]

async def main():
    st.title("Story Writing with Langgraph")

    if "forward_in_time_list_mode" not in st.session_state:
        st.session_state.forward_in_time_list_mode = False
        st.session_state.forward_branches = []

    if "page_loaded" not in st.session_state:
        st.session_state.page_loaded = False
        st.session_state.selected_previous_chapter, st.session_state.selected_next_chapter, st.session_state.selected_current_chapter = None,None,None
        st.session_state.num_selected = 0

    if st.session_state.page_loaded == False:
        await reset_session_variables()

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
                    await reset_session_variables()
                    

                await call_async_function_safely(run_graph_with_input,st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'summary':summary_text,'details':detail_text,
                                                'style':style_text},{'node_id':st.session_state.current_node_id})
                
                st.session_state.story_started = True
                await update_session_variables()
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

                await call_async_function_safely(run_graph_with_input,st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'rewrite_instructions':edit_chapter_text},
                                                {'node_id':st.session_state.current_node_id})
                

                await update_session_variables()
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
                
                await call_async_function_safely(run_graph_with_input,st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{'continue_instructions':next_chapter_text}
                                                ,{'node_id':st.session_state.current_node_id})
                await update_session_variables()
                st.session_state.show_continue_input = False
                st.rerun()
    else:
        st.sidebar.header("Navigation")
        if st.sidebar.button("New Story" if st.session_state.story_started else "Start Story"):
            st.session_state.show_start_input = True
            st.rerun()
        elif st.sidebar.button("Edit") and st.session_state.story_started and st.session_state.story_started:
            st.session_state.show_edit_input = True
            st.rerun()
        elif st.sidebar.button("Continue") and st.session_state.story_started:
            st.session_state.show_continue_input = True
            st.rerun()

    st.sidebar.write(" ")  

    col1, _, col3 = st.columns([1, 2, 1]) 

    with col1:
        options = transform_titles_into_options([c['title'].strip() for c in st.session_state.previous_chapter_options])
        if len(options) > 0:
            st.session_state.selected_previous_chapter = st.selectbox("",options,index=None,placeholder="Select previous chapter", \
                                                                 label_visibility="collapsed",key=f"previous_chapter_{st.session_state.num_selected}")
        else:
            st.session_state.selected_previous_chapter = None
            st.write("No previous chapters!")


        if st.session_state.selected_previous_chapter is not None:
            st.session_state.num_selected += 1
            st.session_state.current_chapter_indices[str(int(st.session_state.currently_selected_chapter)-1)] = options.index(st.session_state.selected_previous_chapter)
            await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'current_chapter_indices':st.session_state.current_chapter_indices, \
                                                        'currently_selected_chapter':str(int(st.session_state.currently_selected_chapter)-1)})
            await call_async_function_safely(update_session_variables)
            st.rerun()
    with col3:
        options = transform_titles_into_options([c['title'].strip() for c in st.session_state.next_chapter_options])
        if len(options) > 0:
            st.session_state.selected_next_chapter = st.selectbox("",options,index=None,placeholder="Select next chapter", \
                                                                 label_visibility="collapsed",key=f"next_chapter_{st.session_state.num_selected}")
        else:
            st.session_state.selected_next_chapter = None
            st.write("No next chapters!")


        if st.session_state.selected_next_chapter is not None:
                st.session_state.num_selected += 1
                st.session_state.current_chapter_indices[str(int(st.session_state.currently_selected_chapter)+1)] = options.index(st.session_state.selected_next_chapter)
                await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'current_chapter_indices':st.session_state.current_chapter_indices, \
                                                        'currently_selected_chapter':str(int(st.session_state.currently_selected_chapter)+1)})
                await call_async_function_safely(update_session_variables)
                st.rerun()

    st.markdown(f"<h2 style='text-align: center; color: white;'>  \
                {st.session_state.current_chapter_options[st.session_state.current_chapter_index]['title']} \
                  </h2>",unsafe_allow_html=True)
    st.text_area(" ", value=st.session_state.current_chapter_options[st.session_state.current_chapter_index]['content'], height=450)

    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        options = transform_titles_into_options([c['title'].strip() for c in st.session_state.current_chapter_options])
        st.session_state.selected_current_chapter = st.selectbox("",options,index=None,placeholder="Select current chapter", \
                                                                 label_visibility="collapsed",key=f"current_chapter_{st.session_state.num_selected}")

        if st.session_state.selected_current_chapter is not None:
            st.session_state.num_selected += 1
            st.session_state.current_chapter_index = options.index(st.session_state.selected_current_chapter)
            st.session_state.current_chapter_indices[st.session_state.currently_selected_chapter] = st.session_state.current_chapter_index
            await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'current_chapter_indices':st.session_state.current_chapter_indices})
            await call_async_function_safely(update_session_variables)
            st.rerun()


if __name__ == "__main__":
    asyncio.run(main())