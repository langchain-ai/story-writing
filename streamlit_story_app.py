import random
import string
import streamlit as st
from langgraph_sdk import get_client
import asyncio
from langsmith import Client
from streamlit_extras.stylable_container import stylable_container
import requests

feedback_client = Client(api_url="https://beta.api.smith.langchain.com")

def get_public_ip():
    try:
        # Use an external API to fetch public IP address
        response = requests.get('https://api64.ipify.org?format=json')
        data = response.json()
        ip_address = data['ip']
        return ip_address
    except requests.RequestException as e:
        print(f"Error fetching IP address: {e}")
        return None

async def start_agent(ip_address):
    client = get_client()
        #url="https://ht-respectful-sundial-15-fbf5e59442b15c23a9306227-g3ps4aazkq-uc.a.run.app")
    assistants = await client.assistants.search()
    assistants = [a for a in assistants if not a['config']]
    thread = await client.threads.create(metadata={"user":ip_address})
    assistant = assistants[0]
    return [client,thread,assistant]


async def get_run_id_corresponding_to_node(client, thread, node_id):
    '''Get the run id corresponding to the chapter written'''
    runs = await client.runs.list(thread_id=thread['thread_id'])

    for r in runs:
        if r['kwargs']['config']['configurable']['node_id'] == node_id:
            return r['run_id']
    return None

async def get_new_thread(client,ip_address):
    thread = await client.threads.create(metadata={"user":ip_address})
    return thread

async def get_thread_state(client,thread_id):
    return await client.threads.get_state(thread_id)

async def get_user_threads(client,ip_address):
    try:
        # Try to run the async function using the existing event loop
        threads = await client.threads.search(metadata={"user":ip_address})
    except RuntimeError as e:
        if "Event loop is closed" in str(e):
            # If the event loop is closed, create a new one and run the async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            threads = await client.threads.search(metadata={"user":ip_address})
        else:
            raise e
    
    untitled_count = 1
    for t in threads:
        t_state = await get_thread_state(client,t['thread_id'])
        try:
            t['story_title'] = t_state['values']['story_title']
        except:
            t['story_title'] = f"Untitled story #{untitled_count}"
            untitled_count += 1
    return threads

async def run_graph_with_input(client,thread,assistant,input,metadata={}):
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

llm_to_title = {
    "starting":"Waiting for user input ...",
    "brainstorm_llm": "Brainstorming ideas for chapter...",
    "plan_llm": "Planning outline for chapter...",
    "summary_llm": "Summarizing story so far...",
    "write_llm": "Writing the chapter...",
    "title_llm": "Generating a title for the story..."
}

async def generate_answer(placeholder, placeholder_title, input, client, thread, assistant, metadata = {}):
        current_llm = "starting"
        placeholder_title.write(llm_to_title[current_llm])
        current_ind = 0
        ans = ""
        async for chunk in client.runs.stream(
        thread['thread_id'], assistant['assistant_id'], input=input, config={"configurable":metadata}, \
            stream_mode="messages",
        ):
            if chunk.data and 'run_id' not in chunk.data:
                if isinstance(chunk.data,dict):
                    current_llm = chunk.data[list(chunk.data.keys())[0]]['metadata']['name']
                    placeholder_title.write(llm_to_title[current_llm])
                elif current_llm == "write_llm" and chunk.data[0]['content']:
                    ans += chunk.data[0]['content'][current_ind:]
                    placeholder.info(ans)
                    current_ind += len(chunk.data[0]['content'][current_ind:])

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
    current_state = await call_async_function_safely(get_current_state,st.session_state.client,st.session_state.thread)
    st.session_state.chapter_graph = current_state['values']['chapter_graph']
    st.session_state.story_title = current_state['values']['story_title']
    st.session_state.currently_selected_chapter = str(current_state['values']['chapter_id_viewing'])
    st.session_state.current_node_id = str(int(current_state['values']['current_chapter_id']) + 1)
    st.session_state.next_chapter_options = st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['children']
    st.session_state.current_chapter_options = st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['siblings'] \
                                                + st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['cousins'] + [st.session_state.currently_selected_chapter]
    st.session_state.previous_chapter_options = [x for x in [st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['parent']] if x!= '-1']
        
async def reset_session_variables(ip_address):
    st.session_state.chapter_graph = {"-1":{'content':"Click Start Story to begin writing!", 'title':"Pre-start Chapter"}}
    st.session_state.currently_selected_chapter = "-1"
    st.session_state.current_node_id = '1'
    st.session_state.story_title = ""
    st.session_state.current_chapter_options = ["-1"]
    st.session_state.previous_chapter_options, st.session_state.next_chapter_options = [],[]

async def stream(*args):
    await asyncio.gather(call_async_function_safely(generate_answer,*args))

async def main():
    if "story_title" not in st.session_state or st.session_state.story_title == "":
        st.title("Story Writing with Langgraph")
    else:
        st.title(st.session_state.story_title)

    if "page_loaded" not in st.session_state:
        st.session_state.page_loaded = False
        st.session_state.selected_previous_chapter, st.session_state.selected_next_chapter, st.session_state.selected_current_chapter = None,None,None
        st.session_state.story_title = ""
        st.session_state.num_selected = 0
        st.session_state.writing = False
        st.session_state.ip_address = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

    if st.session_state.page_loaded == False:
        st.session_state.client,st.session_state.thread,st.session_state.assistant = await call_async_function_safely(start_agent,st.session_state.ip_address)
        await reset_session_variables(st.session_state.ip_address)
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


    if st.session_state.show_start_input:
        summary_text = st.sidebar.text_area("Summary")
        detail_text = st.sidebar.text_area("Details")
        style_text = st.sidebar.text_area("Writing Style")
        col1, col2 = st.sidebar.columns([1, 1])        
        with col1:
            if st.button("Back",key="start-back"):
                st.session_state.show_start_input = False
                st.session_state.writing = False
                st.rerun()
        with col2:
            if st.button("Submit",key="start-submit"):
                st.session_state.writing = True
                # If we start a new story, reset all of our session variables
                if st.session_state.story_started:
                    st.session_state.thread = await call_async_function_safely(get_new_thread,st.session_state.client,st.session_state.ip_address)
                    await reset_session_variables(st.session_state.ip_address)
                    
                

                await stream(st.session_state.box,st.session_state.box_title,{'summary':summary_text,'details':detail_text,'style':style_text},st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{"node_id":st.session_state.current_node_id})

                st.session_state.box_title.write("Saving chapter and returning to story view")
                await asyncio.sleep(5)

                st.session_state.story_started = True
                await update_session_variables()
                st.session_state.show_start_input = False
                st.session_state.writing = False
                st.rerun()
    elif st.session_state.show_edit_input:
        edit_chapter_text = st.sidebar.text_area("Edit Instructions")
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="edit-back"):
                st.session_state.show_edit_input = False
                st.session_state.writing = False
                st.rerun()
        with col2:
            if st.button("Submit",key="edit-submit"):
                
                await stream(st.session_state.box,st.session_state.box_title,{'rewrite_instructions':edit_chapter_text},st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{"node_id":st.session_state.current_node_id})

                st.session_state.box_title.write("Saving chapter and returning to story view")
                await asyncio.sleep(5)
                await update_session_variables()
                st.session_state.show_edit_input = False
                st.session_state.writing = False
                st.rerun()
    elif st.session_state.show_continue_input:
        next_chapter_text = st.sidebar.text_area("Next Chapter Instructions")
        col1, col2 = st.sidebar.columns([1, 1])
        with col1:
            if st.button("Back",key="continue-back"):
                st.session_state.show_continue_input = False
                st.session_state.writing = False
                st.rerun()
        with col2:
            if st.button("Submit",key="continue-submit"):
                
                
                await stream(st.session_state.box,st.session_state.box_title,{'continue_instructions':next_chapter_text},st.session_state.client,st.session_state.thread,
                                                st.session_state.assistant,{"node_id":st.session_state.current_node_id})
                st.session_state.box_title.write("Saving chapter and returning to story view")
                await asyncio.sleep(5)
                await update_session_variables()
                st.session_state.show_continue_input = False
                st.session_state.writing = False
                st.rerun()
    elif st.session_state.show_load_story:
        col1, col2 = st.sidebar.columns([1, 1])
        threads = await call_async_function_safely(get_user_threads,st.session_state.client,st.session_state.ip_address)
        threads_without_current = [t for t in threads if t['thread_id'] != st.session_state.thread['thread_id']]
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
            st.rerun()
        with col1:
            if st.button("Back",key="load-story-back"):
                st.session_state.show_load_story = False
                st.rerun()
    else:
        st.sidebar.header("Navigation")
        if st.sidebar.button("New Story" if st.session_state.story_started else "Start Story"):
            st.session_state.story_title = ""
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

    col1, _, col3 = st.columns([1, 2, 1]) 

    if st.session_state.writing == False:
        with col1:
            options = transform_titles_into_options([st.session_state.chapter_graph[chapter_id]['title'] for chapter_id in st.session_state.previous_chapter_options])
            if len(options) > 0:
                st.session_state.selected_previous_chapter = st.selectbox("",options,index=None,placeholder="Select previous chapter", \
                                                                    label_visibility="collapsed",key=f"previous_chapter_{st.session_state.num_selected}")
            else:
                st.session_state.selected_previous_chapter = None
                st.write("No previous chapters!")


            if st.session_state.selected_previous_chapter is not None:
                st.session_state.num_selected += 1
                new_chapter_selected = st.session_state.previous_chapter_options[options.index(st.session_state.selected_previous_chapter)]
                
                await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'chapter_id_viewing':new_chapter_selected})
                await call_async_function_safely(update_session_variables)
                st.rerun()
        with col3:
            options = transform_titles_into_options([st.session_state.chapter_graph[chapter_id]['title'] for chapter_id in st.session_state.next_chapter_options])
            if len(options) > 0:
                st.session_state.selected_next_chapter = st.selectbox("",options,index=None,placeholder="Select next chapter", \
                                                                    label_visibility="collapsed",key=f"next_chapter_{st.session_state.num_selected}")
            else:
                st.session_state.selected_next_chapter = None
                st.write("No next chapters!")


            if st.session_state.selected_next_chapter is not None:
                    st.session_state.num_selected += 1
                    new_chapter_selected = st.session_state.next_chapter_options[options.index(st.session_state.selected_next_chapter)]

                    await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'chapter_id_viewing':new_chapter_selected})
                    await call_async_function_safely(update_session_variables)
                    st.rerun()

    _, col_middle_title, _ = st.columns([1, 6, 1])
    
    if "box_title" not in st.session_state:
        st.session_state.box_title = col_middle_title.empty()
    elif st.session_state.writing == True:
        with col_middle_title:
            st.write("Waiting for user input...")

    _, col_middle, _ = st.columns([1, 6, 1])
    if "box" not in st.session_state:
        st.session_state.box = col_middle.empty()

    if st.session_state.writing == False:
        st.session_state.chapter_title = st.markdown(f"<h2 style='text-align: center; color: white;'>  \
                    {st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['title']} \
                    </h2>",unsafe_allow_html=True)
        st.session_state.chapter_content = st.text_area(" ", value=st.session_state.chapter_graph[st.session_state.currently_selected_chapter]['content'], height=450)
    
    _, col2, _ = st.columns([1, 2, 1])
    if st.session_state.writing == False:
        with col2:
            options = transform_titles_into_options([st.session_state.chapter_graph[chapter_id]['title'] for chapter_id in st.session_state.current_chapter_options])
            if len(options) > 0:
                st.session_state.selected_current_chapter = st.selectbox("",options,index=None,placeholder="Select current chapter", \
                                                                    label_visibility="collapsed",key=f"current_chapter_{st.session_state.num_selected}")
            else:
                st.session_state.selected_current_chapter = None
                st.write("No alternate current chapters!")

            if st.session_state.selected_current_chapter is not None:
                st.session_state.num_selected += 1
                new_chapter_selected = st.session_state.current_chapter_options[options.index(st.session_state.selected_current_chapter)]
                
                await call_async_function_safely(update_current_state,st.session_state.client,st.session_state.thread,{'chapter_id_viewing':new_chapter_selected})
                
                await call_async_function_safely(update_session_variables)
                st.rerun()

        if st.session_state.current_node_id != '1':
            _, col2a,col2b, _ = st.columns([1, 1,1, 1])
            with col2a:
                with stylable_container(
                    key="red_button",
                    css_styles="""
                        button {
                            background-color: red;
                            color: white;
                            border-radius: 20px;
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
            with col2b:
                with stylable_container(
                    key="green_button",
                    css_styles="""
                        button {
                            background-color: green;
                            color: white;
                            border-radius: 20px;
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