import random
import string
import streamlit as st
from langgraph_sdk import get_client
import asyncio
from langsmith import Client
from streamlit_extras.stylable_container import stylable_container
from copy import deepcopy
st.set_page_config(layout="wide")

# Langsmith feedback client
feedback_client = Client(api_url="https://beta.api.smith.langchain.com")

# Find run id for giving feedback
async def get_run_id_corresponding_to_node(client, thread, node_id):
    '''Get the run id corresponding to the chapter written'''
    runs = await client.runs.list(thread_id=thread['thread_id'])

    for r in runs:
        if r['kwargs']['config']['configurable']['node_id'] == node_id:
            return r['run_id']
    return None

# Create the agent
async def start_agent(session_id):
    client = get_client(url="https://ht-mundane-strait-97-7d4d2b12ec9c54a4aa34492a954c-g3ps4aazkq-uc.a.run.app")
    assistants = await client.assistants.search()
    assistants = [a for a in assistants if not a['config']]
    thread = await client.threads.create(metadata={"user":session_id})
    assistant = assistants[0]
    await asyncio.sleep(5.5)
    return [client,thread,assistant]

# Find a story that we had previously written
async def get_thread_state(client,thread_id):
    return await client.threads.get_state(thread_id)

# Find stories user has written
async def get_user_threads(client,session_id):
    threads = await client.threads.search(metadata={"user":session_id})
    
    untitled_count = 1
    for t in threads:
        t_state = await get_thread_state(client,t['thread_id'])
        try:
            t['story_title'] = t_state['values']['story_title']
        except:
            t['story_title'] = f"Untitled story #{untitled_count}"
            untitled_count += 1
    return threads

llm_to_title = {
    "starting":"Waiting for user input ...",
    "brainstorm_llm": "Brainstorming ideas for chapter...",
    "plan_llm": "Planning outline for chapter...",
    "summary_llm": "Summarizing story so far...",
    "write_llm": "Writing the chapter...",
    "title_llm": "Generating a title for the story...",
    "chapter_title_llm": "Generating title for chapter..."
}

# Streaming chapter writing
async def generate_answer(placeholder, placeholder_title, input, client, thread, assistant, metadata = {}):
    current_llm = "starting"
    placeholder_title.markdown(f"<h4 style='text-align: center; color: rgb(206,234,253);'>  \
            {llm_to_title[current_llm]} \
            </h4>",unsafe_allow_html=True)
    current_ind = 0
    ans = ""
    async for chunk in client.runs.stream(
    thread['thread_id'], assistant['assistant_id'], input=input, config={"configurable":metadata}, \
        stream_mode="messages", multitask_strategy="rollback"
    ):
        if chunk.data and 'run_id' not in chunk.data:
            if isinstance(chunk.data,dict):
                try:
                    current_llm = chunk.data[list(chunk.data.keys())[0]]['metadata']['name']
                    placeholder_title.markdown(f"<h4 style='text-align: center; color: rgb(206,234,253);'>  \
                        {llm_to_title[current_llm]}</h4>",unsafe_allow_html=True)
                except:
                    pass
            elif current_llm == "write_llm" and chunk.data[0]['content']:
                ans += chunk.data[0]['content'][current_ind:]
                placeholder.info(ans)
                current_ind += len(chunk.data[0]['content'][current_ind:])

# Update variables after chapter has been written
async def get_current_state(client,thread):
    current_state = await client.threads.get_state(thread_id=thread['thread_id'])
    return current_state

# When user selects a different chapter to view
async def update_current_state(client,thread,values):
    await client.threads.update_state(thread_id=thread['thread_id'],values=values)

# Create new thread for new story
async def get_new_thread(client,session_id):
    thread = await client.threads.create(metadata={"user":session_id})
    return thread

# Make sure event loop never closes
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

# Helper function for chapter options
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

# Update variables after writing
async def update_session_variables():
    current_state = await call_async_function_safely(get_current_state,st.session_state.client,st.session_state.thread)
    st.session_state.chapter_graph = current_state['values']['chapter_graph']
    st.session_state.story_title = current_state['values']['story_title']
    st.session_state.currently_selected_chapter = str(current_state['values']['chapter_id_viewing'])
    st.session_state.current_node_id = str(int(current_state['values']['current_chapter_id']) + 1)
    st.session_state.next_chapter_options = st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['children']
    st.session_state.current_chapter_options = st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['siblings'] \
                                                + st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['cousins'] + [st.session_state.currently_selected_chapter]
    st.session_state.previous_chapter_options = [x for x in [st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['parent']] if x!= '-1']

# Reset variables on new story     
async def reset_session_variables():
    st.session_state.chapter_graph = {"-1":{'content':"Click Start Story to begin writing!", 'title':"Pre-start Chapter"}}
    st.session_state.currently_selected_chapter = "-1"
    st.session_state.chapter_number = 0
    st.session_state.current_node_id = '1'
    st.session_state.story_title = ""
    st.session_state.current_chapter_options = ["-1"]
    st.session_state.previous_chapter_options, st.session_state.next_chapter_options = [],[]

async def stream(*args):
    await asyncio.gather(call_async_function_safely(generate_answer,*args))

async def main():
    st.markdown("""
    <style>
    /* Centering title horizontally */
    .centered-title {
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)
    if "story_title" not in st.session_state or st.session_state.story_title == "":
        st.markdown("<h1 class='centered-title'>Story Writing with LangGraph</h1>", unsafe_allow_html=True)
    else:
        st.markdown(f"<h1 class='centered-title'>{st.session_state.story_title}</h1>", unsafe_allow_html=True)

    if "page_loaded" not in st.session_state:
        st.session_state.page_loaded = False
        st.session_state.selected_previous_chapter, st.session_state.selected_next_chapter, st.session_state.selected_current_chapter = None,None,None
        st.session_state.story_title = ""
        st.session_state.num_selected = 0
        st.session_state.writing = False

    if "session_id" not in st.session_state:
        st.session_state.session_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    if st.session_state.page_loaded == False:
        st.session_state.client,st.session_state.thread,st.session_state.assistant = await call_async_function_safely(start_agent,st.session_state.session_id)
        await reset_session_variables()
        st.session_state.page_loaded = True

    if "story_started" not in st.session_state:
        st.session_state.story_started = False

    if "show_edit_input" not in st.session_state:
        st.session_state.show_edit_input = False
    
    if "show_start_input" not in st.session_state:
        st.session_state.show_start_input = False

    if "show_continue_input" not in st.session_state:
        st.session_state.show_continue_input = False

    if "show_load_story" not in st.session_state:
        st.session_state.show_load_story = False

    if ('start_submit' in st.session_state and st.session_state.start_submit == True) or \
       ('edit_submit' in st.session_state and st.session_state.edit_submit == True) or \
       ('continue_submit' in st.session_state and st.session_state.continue_submit == True):
        st.session_state.running = True
    else:
        st.session_state.running = False

    # Starting/New story
    if st.session_state.show_start_input:
        summary_text = st.sidebar.text_area("Summary", disabled=st.session_state.running)
        detail_text = st.sidebar.text_area("Details", disabled=st.session_state.running)
        style_text = st.sidebar.text_area("Writing Style", disabled=st.session_state.running)
        col1, col2 = st.sidebar.columns([1, 1]) 
        with col1:
            if st.button("Back",key="start-back", disabled=st.session_state.running):
                st.session_state.show_start_input = False
                st.session_state.writing = False
                st.rerun()
        with col2:
            if st.button("Submit",key="start_submit", disabled=st.session_state.running):
                if st.session_state.story_started:
                    st.session_state.thread = await call_async_function_safely(get_new_thread,st.session_state.client,st.session_state.session_id)
                    await reset_session_variables()     
                await stream(st.session_state.box,st.session_state.box_title,{'summary':summary_text,'details':detail_text,'style':style_text},st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{"node_id":st.session_state.current_node_id})
                st.session_state.story_started = True
                await update_session_variables()

                st.session_state.show_start_input = False
                st.session_state.writing = False
                st.session_state.chapter_number = 1
                st.rerun()
    # Editing story
    elif st.session_state.show_edit_input:
        edit_chapter_text = st.sidebar.text_area("Edit Instructions", disabled=st.session_state.running)
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="edit-back", disabled=st.session_state.running):
                st.session_state.show_edit_input = False
                st.session_state.writing = False
                st.rerun()
        with col2:
            if st.button("Submit",key="edit_submit", disabled=st.session_state.running):
                await stream(st.session_state.box,st.session_state.box_title,{'rewrite_instructions':edit_chapter_text},st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{"node_id":st.session_state.current_node_id})

                await update_session_variables()
                st.session_state.show_edit_input = False
                st.session_state.writing = False
                st.rerun()
    # Continuing story
    elif st.session_state.show_continue_input:
        next_chapter_text = st.sidebar.text_area("Next Chapter Instructions", disabled=st.session_state.running)
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="continue-back", disabled=st.session_state.running):
                st.session_state.show_continue_input = False
                st.session_state.writing = False
                st.rerun()
        with col2:
            if st.button("Submit",key="continue_submit", disabled=st.session_state.running):
                await stream(st.session_state.box,st.session_state.box_title,{'continue_instructions':next_chapter_text},st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{"node_id":st.session_state.current_node_id})

                await update_session_variables()
                st.session_state.show_continue_input = False
                st.session_state.writing = False
                st.session_state.chapter_number += 1
                st.rerun()
    # Loading story
    elif st.session_state.show_load_story:
        col1, col2 = st.sidebar.columns([1, 1])
        threads = await call_async_function_safely(get_user_threads,st.session_state.client,st.session_state.session_id)
        threads_without_current = [t for t in threads if t['thread_id'] != st.session_state.thread['thread_id'] and 'Untitled' not in t['story_title']]
        options = [t['story_title'] for t in threads_without_current]

        if len(options) > 0:
            selected_story = st.sidebar.selectbox("",options,index=None,placeholder="Select story", \
                                                                label_visibility="collapsed",key=f"story_selector")
        else:
            selected_story = None
            st.sidebar.write("No alternate stories!")

        if selected_story is not None:
            st.session_state.thread = threads_without_current[options.index(selected_story)]
            await update_session_variables()
            st.session_state.show_load_story = False
            st.session_state.chapter_number = 1
            cur_chapter = st.session_state.currently_selected_chapter
            while st.session_state.chapter_graph[cur_chapter]['parent'] != '-1':
                st.session_state.chapter_number += 1
                cur_chapter = st.session_state.chapter_graph[cur_chapter]['parent']
            st.rerun()
        with col1:
            if st.button("Back",key="load-story-back"):
                st.session_state.show_load_story = False
                st.rerun()
    # Default Navigation pane
    else:
        st.sidebar.header("Navigation")
        if st.sidebar.button("New Story" if st.session_state.story_started else "Start Story"):
            st.session_state.writing = True
            st.session_state.show_start_input = True
            st.rerun()
        elif st.sidebar.button("Edit") and st.session_state.story_started and st.session_state.story_started:
            st.session_state.show_edit_input = True
            st.session_state.writing = True
            st.rerun()
        elif st.sidebar.button("Continue") and st.session_state.story_started:
            st.session_state.show_continue_input = True
            st.session_state.writing = True
            st.rerun()
        elif st.sidebar.button("Load Story"):
            st.session_state.show_load_story = True
            st.rerun()

    st.sidebar.write(" ")  

    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] > * {
        max-height: 300px;
        overflow-y: scroll;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, _, col3 = st.columns([1, 2, 1]) 

    if st.session_state.writing == False:
        # Previous chapter options
        with col1:
            options = transform_titles_into_options([st.session_state.chapter_graph[chapter_id]['title'] for chapter_id in st.session_state.previous_chapter_options])
            if len(options) > 0:
                st.session_state.selected_previous_chapter = st.selectbox("",options,index=None,placeholder="Select previous chapter", \
                                                                    label_visibility="collapsed",key=f"previous_chapter_{st.session_state.num_selected}")
            else:
                st.session_state.selected_previous_chapter = None
                st.markdown(f"<p style='text-align: center;'>  \
                No previous chapters! \
                </p>",unsafe_allow_html=True)


            if st.session_state.selected_previous_chapter is not None:
                st.session_state.num_selected += 1
                new_chapter_selected = st.session_state.previous_chapter_options[options.index(st.session_state.selected_previous_chapter)]
                
                await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'chapter_id_viewing':new_chapter_selected})
                await call_async_function_safely(update_session_variables)
                st.session_state.chapter_number -= 1
                st.rerun()
        # Next chapter options
        with col3:
            options = transform_titles_into_options([st.session_state.chapter_graph[chapter_id]['title'] for chapter_id in st.session_state.next_chapter_options])
            if len(options) > 0:
                st.session_state.selected_next_chapter = st.selectbox("",options,index=None,placeholder="Select next chapter", \
                                                                    label_visibility="collapsed",key=f"next_chapter_{st.session_state.num_selected}")
            else:
                st.session_state.selected_next_chapter = None
                st.markdown(f"<p style='text-align: center;'>  \
                No next chapters! \
                </p>",unsafe_allow_html=True)


            if st.session_state.selected_next_chapter is not None:
                    st.session_state.num_selected += 1
                    new_chapter_selected = st.session_state.next_chapter_options[options.index(st.session_state.selected_next_chapter)]

                    await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'chapter_id_viewing':new_chapter_selected})
                    await call_async_function_safely(update_session_variables)
                    st.session_state.chapter_number += 1
                    st.rerun()

    _, col_middle_title, _ = st.columns([1, 6, 1])
    
    if "box_title" not in st.session_state or st.session_state.writing == False:
        st.session_state.box_title = col_middle_title.empty()
    elif st.session_state.writing == True:
        with col_middle_title:
            st.markdown(f"<h4 style='text-align: center; color: rgb(206,234,253);'>  \
                Waiting for user input... \
                </h4>",unsafe_allow_html=True)

    st.session_state.chapter_title = st.markdown(f"<h2 style='text-align: center; color: white;'>  \
                {st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['title']} \
                </h2>",unsafe_allow_html=True)
    _, col_middle, col_scroll = st.columns([1, 6, 1])
    if "box" not in st.session_state:
        st.session_state.box = col_middle.empty()
        st.rerun()
    else:
        st.session_state.box.info(st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['content'])

    with col_scroll:
        st.write("🔺  \nScroll  \n🔻")
    
    st.markdown(f"<h5 style='text-align: center;'>  \
                Chapter {st.session_state.chapter_number} \
                </h5>",unsafe_allow_html=True)

    _, col2, _ = st.columns([1, 2, 1])
    if st.session_state.writing == False:
        # Current chapter options
        with col2:
            options = transform_titles_into_options([st.session_state.chapter_graph[chapter_id]['title'] for chapter_id in st.session_state.current_chapter_options if chapter_id != "-1"])
            if len(options) > 0:
                st.session_state.selected_current_chapter = st.selectbox("",options,index=None,placeholder="Select current chapter", \
                                                                    label_visibility="collapsed",key=f"current_chapter_{st.session_state.num_selected}")
            else:
                st.session_state.selected_current_chapter = None
                st.markdown(f"<p style='text-align: center;'>  \
                No alternate current chapters! \
                </p>",unsafe_allow_html=True)

            if st.session_state.selected_current_chapter is not None:
                st.session_state.num_selected += 1
                new_chapter_selected = st.session_state.current_chapter_options[options.index(st.session_state.selected_current_chapter)]
                
                await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'chapter_id_viewing':new_chapter_selected})
                
                await call_async_function_safely(update_session_variables)
                st.rerun()

        # Feedback options
        if st.session_state.current_node_id != '1':
            _, col2a,col2b, _ = st.columns([1, 1,1, 1])
            # Bad writing
            with col2a:
                with stylable_container(
                    key="red_button",
                    css_styles="""
                        button {
                            background-color: red;
                            color: white;
                            border-radius: 20px;
                            margin-left: 80px;
                        }
                        """,
                ):
                    if st.button("Bad writing",key = "red_button"):
                        run_id = await call_async_function_safely(get_run_id_corresponding_to_node,st.session_state.client, \
                                                            st.session_state.thread, str(int(st.session_state.current_node_id)-1))
                        feedback_client.create_feedback(
                            run_id=run_id,
                            key="feedback-key",
                            score=0.0,
                            comment="comment",
                        )
            # Good writing
            with col2b:
                with stylable_container(
                    key="green_button",
                    css_styles="""
                        button {
                            background-color: green;
                            color: white;
                            border-radius: 20px;
                            margin-left: 80px;
                        }
                        """,
                ):
                    if st.button("Good writing",key = "green_button"):
                        run_id = await call_async_function_safely(get_run_id_corresponding_to_node,st.session_state.client, \
                                                            st.session_state.thread, str(int(st.session_state.current_node_id)-1))
                        feedback_client.create_feedback(
                            run_id=run_id,
                            key="feedback-key",
                            score=1.0,
                            comment="comment",
                        )

if __name__ == "__main__":
    asyncio.run(main())